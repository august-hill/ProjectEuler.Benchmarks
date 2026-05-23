#!/usr/bin/env python3
"""
double_call_audit.py — Invocation-isolation audit for PE solutions.

The contract a solve() function must honor: when called twice in the same
process, both calls must produce the same answer, computed independently.
That is, state must not leak across calls.  This script checks the contract
on bench output.

For each problem under audit:
  1. Build the binary (lang-specific).
  2. Run it once. The bench harness internally calls solve() many times:
       - once for cold-start measurement (first call in a fresh process),
       - twice for warmup,
       - many times for warm-iteration timing.
     The patched harness now emits `COLDSTART|time_ns=N|answer=A` for the
     cold call and `BENCHMARK|...|answer=A|time_ns=M|...` for the last
     warm-iteration call.
  3. Parse both lines, run two independent checks:

     CHECK 1 — answer consistency (state-leak detector):
       cold answer must equal warm answer.  A mismatch means state from
       the first call corrupted the second — an algorithm bug that a
       cache would have hidden by returning the cold answer for every
       subsequent call.

     CHECK 2 — timing sanity (cache-pattern detector):
       For non-trivial problems (cold > 1ms), the warm time should be on
       the same order as cold.  A warm time < cold/100 indicates the bench
       is measuring a constant-time cached return, not the algorithm.

Outputs a clean per-problem pass/fail report and exits non-zero if any
problem fails either check.

USAGE:
  python3 double_call_audit.py --lang cpp --problems 1-10
  python3 double_call_audit.py --lang cpp --problems 1,3,7
  python3 double_call_audit.py --lang cpp --problems 1

NOTE: as of 2026-05-23 this is C++-only.  Per-language harness patches and
adapters land here as we extend the 10×10 audit to each language.
"""

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

BASE = Path("/Users/augusthill/ccdev")

# Per-language adapters.
# Each lang knows: where its repo is, how to build a problem, how to run it,
# what binary file to clean up after.
LANG_CONFIG = {
    "cpp": {
        "repo_dir": BASE / "ProjectEuler.CPlusPlus",
        "prob_dir": lambda p: BASE / "ProjectEuler.CPlusPlus" / f"problem_{p:03d}",
        # Match benchmark.sh:8 CXXFLAGS + line 60-63 link fallback chain.
        "build_cmd_base": [
            "g++", "-O2", "-std=c++17",
            "-I../include", "-I/opt/homebrew/include",
            "main.cpp", "-o", "main_bench",
            "-L/opt/homebrew/lib", "-lm",
        ],
        # benchmark.sh tries plain → +primesieve → +fmt.  We mirror.
        "build_extra_libs": [[], ["-lprimesieve"], ["-lfmt"]],
        "run_cmd": ["./main_bench"],
        "binary_name": "main_bench",
    },
    "c": {
        "repo_dir": BASE / "ProjectEuler.C",
        "prob_dir": lambda p: BASE / "ProjectEuler.C" / f"problem_{p:03d}",
        # Per ProjectEuler.C/CLAUDE.md: gcc -O2 -std=c11 -I.. main.c -o main_bench -lm
        "build_cmd_base": [
            "gcc", "-O2", "-std=c11",
            "-I..", "-I/opt/homebrew/include",
            "main.c", "-o", "main_bench",
            "-L/opt/homebrew/lib", "-lm",
        ],
        "build_extra_libs": [[], ["-lprimesieve"]],
        "run_cmd": ["./main_bench"],
        "binary_name": "main_bench",
    },
}

# Parse the bench-output format.  Both keys (time_ns, answer) appear
# separated by `|`; answer may be int or string (no embedded `|`).
COLDSTART_RE = re.compile(r"^COLDSTART\|time_ns=(\d+)\|answer=(.+)$", re.M)
BENCHMARK_RE = re.compile(r"^BENCHMARK\|problem=\d+\|answer=([^|]+)\|time_ns=(\d+)", re.M)


@dataclass
class AuditResult:
    lang: str
    problem: int
    cold_answer: Optional[str] = None
    warm_answer: Optional[str] = None
    cold_ns: int = 0
    warm_ns: int = 0
    pass_isolation: bool = False  # cold answer == warm answer
    pass_timing: bool = False     # warm time is sane vs cold time
    notes: List[str] = field(default_factory=list)

    @property
    def overall_pass(self) -> bool:
        return self.pass_isolation and self.pass_timing


def audit_problem(lang: str, problem: int) -> AuditResult:
    """Run the audit for one (lang, problem).  Always returns; never raises."""
    cfg = LANG_CONFIG[lang]
    result = AuditResult(lang=lang, problem=problem)
    prob_dir = cfg["prob_dir"](problem)

    if not prob_dir.is_dir():
        result.notes.append(f"problem dir missing: {prob_dir}")
        return result
    # Each lang's build_cmd_base names the source file as a positional arg —
    # we look for it in prob_dir as a generic check.
    src_files = {arg for arg in cfg["build_cmd_base"]
                 if arg.endswith((".c", ".cpp", ".cs", ".go", ".java", ".js", ".py", ".rs", ".s", ".zig"))}
    for src in src_files:
        if not (prob_dir / src).is_file():
            result.notes.append(f"no {src} in {prob_dir}")
            return result

    # 1. Build.  Try the base command first; if it fails, retry with each
    # extra-lib combo (mirrors benchmark.sh's fallback chain for primesieve/fmt).
    build_ok = False
    last_err = ""
    for extra in cfg.get("build_extra_libs", [[]]):
        try:
            build = subprocess.run(
                cfg["build_cmd_base"] + extra,
                cwd=prob_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if build.returncode == 0:
                build_ok = True
                break
            last_err = build.stderr[:200].strip()
        except subprocess.TimeoutExpired:
            result.notes.append("build timeout (60s)")
            return result
    if not build_ok:
        result.notes.append(f"build failed (all link combos): {last_err}")
        return result

    # 2. Run (always clean up the binary, regardless of outcome)
    try:
        try:
            proc = subprocess.run(
                cfg["run_cmd"],
                cwd=prob_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            result.notes.append("run timeout (120s)")
            return result

        if proc.returncode != 0:
            result.notes.append(
                f"run exited {proc.returncode}: {proc.stderr[:200].strip()}"
            )
            return result

        # 3. Parse COLDSTART + BENCHMARK lines
        out = proc.stdout
        cold_match = COLDSTART_RE.search(out)
        warm_match = BENCHMARK_RE.search(out)

        if not cold_match:
            result.notes.append("no COLDSTART line (harness not patched?)")
            return result
        if not warm_match:
            result.notes.append("no BENCHMARK line")
            return result

        result.cold_ns = int(cold_match.group(1))
        result.cold_answer = cold_match.group(2).strip()
        result.warm_answer = warm_match.group(1).strip()
        result.warm_ns = int(warm_match.group(2))

        # CHECK 1: answer consistency (state-leak detector)
        if result.cold_answer == result.warm_answer:
            result.pass_isolation = True
        else:
            result.notes.append(
                f"STATE LEAK: cold={result.cold_answer!r} != warm={result.warm_answer!r}"
            )

        # CHECK 2: timing sanity (cache-pattern detector).
        # For tiny problems (cold < 1ms) both can be sub-microsecond and the
        # ratio is dominated by noise — skip the check.
        if result.cold_ns < 1_000_000:
            result.pass_timing = True
            result.notes.append(
                f"timing-check skipped: cold {result.cold_ns}ns < 1ms (too small to assess)"
            )
        elif result.warm_ns >= result.cold_ns / 100:
            # Warm is at least 1% of cold — algorithm time dominates startup;
            # no cache short-circuit.
            result.pass_timing = True
        else:
            ratio = result.cold_ns / max(result.warm_ns, 1)
            result.notes.append(
                f"CACHE SUSPECTED: warm/cold ratio = {ratio:.0f}× "
                f"(cold={result.cold_ns:,}ns warm={result.warm_ns:,}ns)"
            )
    finally:
        # Always clean up the binary so the working tree stays untracked-free
        binary = prob_dir / cfg["binary_name"]
        if binary.exists():
            binary.unlink()

    return result


def parse_problems(spec: str) -> List[int]:
    """Parse '1-10' or '1,3,7' or '1' into a list of ints."""
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument(
        "--lang",
        default="cpp",
        choices=sorted(LANG_CONFIG),
        help="Language to audit (default: cpp)",
    )
    ap.add_argument(
        "--problems",
        default="1-10",
        help="Problem range or list: '1-10', '1,3,7', or '1' (default: 1-10)",
    )
    args = ap.parse_args()

    problems = parse_problems(args.problems)

    print(f"=== Invocation-isolation audit  lang={args.lang}  problems={problems}\n")
    header = (
        f"  {'PROB':<5} {'COLD ANS':<22} {'WARM ANS':<22} "
        f"{'COLD ns':>14} {'WARM ns':>14}  STATUS"
    )
    print(header)
    print("  " + "-" * (len(header) - 2))

    results = []
    for p in problems:
        r = audit_problem(args.lang, p)
        results.append(r)
        cold = (r.cold_answer or "(missing)")[:21]
        warm = (r.warm_answer or "(missing)")[:21]
        status = "✓ PASS" if r.overall_pass else "✗ FAIL"
        print(
            f"  p{p:03d}  {cold:<22} {warm:<22} "
            f"{r.cold_ns:>14,} {r.warm_ns:>14,}  {status}"
        )
        for note in r.notes:
            print(f"         · {note}")

    n_pass = sum(1 for r in results if r.overall_pass)
    print(f"\n=== Summary: {n_pass}/{len(results)} pass")
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
