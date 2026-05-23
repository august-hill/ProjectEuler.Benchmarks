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

NOTE: as of 2026-05-23 covers cpp, c, arm64, rust, go, zig, java, javascript,
python, csharp.  Each lang's harness emits COLDSTART|time_ns=N|answer=A.
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
    "arm64": {
        "repo_dir": BASE / "ProjectEuler.ARM64",
        "prob_dir": lambda p: BASE / "ProjectEuler.ARM64" / f"problem_{p:03d}",
        # ARM64 builds in two steps: assemble solve.s then link with main.c.
        # Per ProjectEuler.ARM64/CLAUDE.md.  sh -c chains the two cleanly.
        "build_cmd_base": [
            "sh", "-c",
            "as -o solve.o solve.s && cc -O2 -o main_bench main.c solve.o -lm",
        ],
        "build_extra_libs": [[]],
        "src_files": {"solve.s", "main.c"},
        "run_cmd": ["./main_bench"],
        "binary_name": "main_bench",
        # solve.o is a build artifact we also clean up
        "extra_cleanup": ["solve.o"],
    },
    "rust": {
        "repo_dir": BASE / "ProjectEuler.Rust",
        "prob_dir": lambda p: BASE / "ProjectEuler.Rust" / f"problem_{p:03d}",
        # Per ProjectEuler.Rust/CLAUDE.md: `cargo build --release`.  --quiet
        # suppresses cargo's compiling/finished noise on stdout so the bench
        # output isn't mixed in.
        "build_cmd_base": ["cargo", "build", "--release", "--quiet"],
        "build_extra_libs": [[]],
        "src_files": {"src/main.rs", "Cargo.toml"},
        # Binary lives in per-problem target/release/problem_NNN
        "run_cmd": lambda p: [f"./target/release/problem_{p:03d}"],
        # target/ is gitignored; no manual cleanup needed
        "skip_binary_cleanup": True,
    },
    "go": {
        "repo_dir": BASE / "ProjectEuler.Go",
        "prob_dir": lambda p: BASE / "ProjectEuler.Go" / f"problem_{p:03d}",
        # Per ProjectEuler.Go/CLAUDE.md: `go build -o main_bench main.go`
        "build_cmd_base": ["go", "build", "-o", "main_bench", "main.go"],
        "build_extra_libs": [[]],
        "src_files": {"main.go"},
        "run_cmd": ["./main_bench"],
        "binary_name": "main_bench",
    },
    "zig": {
        "repo_dir": BASE / "ProjectEuler.Zig",
        "prob_dir": lambda p: BASE / "ProjectEuler.Zig" / f"problem_{p:03d}",
        # Per ProjectEuler.Zig/benchmark.sh:58 — must build from repo root so
        # module imports resolve.  We wrap in sh -c so the audit's
        # cwd=prob_dir contract still holds for the run step; the build step
        # explicitly `cd`'s to the repo root.
        "build_cmd_base": lambda p: [
            "sh", "-c",
            f"cd {BASE / 'ProjectEuler.Zig'} && "
            f"zig build-exe -O ReleaseFast --dep bench "
            f"-Mroot=problem_{p:03d}/main.zig "
            f"-Mbench=bench/bench.zig "
            f"-femit-bin=problem_{p:03d}/main_bench",
        ],
        "build_extra_libs": [[]],
        "src_files": {"main.zig"},
        "run_cmd": ["./main_bench"],
        "binary_name": "main_bench",
        # Zig drops a couple of build artifacts next to the binary
        "extra_cleanup": ["main_bench.o"],
    },
    "java": {
        "repo_dir": BASE / "ProjectEuler.Java",
        "prob_dir": lambda p: BASE / "ProjectEuler.Java" / f"problem_{p:03d}",
        # Mirrors the cmd/euler-bench langs.go PreBuild: copy the shared
        # Bench.java into the problem dir, then `javac Bench.java Main.java`.
        "pre_build": lambda repo_dir, prob_dir, p: (prob_dir / "Bench.java").write_bytes(
            (repo_dir / "Bench.java").read_bytes()
        ),
        "build_cmd_base": ["javac", "Bench.java", "Main.java"],
        "build_extra_libs": [[]],
        "src_files": {"Main.java"},
        "run_cmd": ["java", "Main"],
        # No single "binary" — Java drops .class files.  Use extra_cleanup
        # for both and skip the binary unlink.  Note: we do NOT clean up
        # Bench.java — it is a committed file in each problem dir (the
        # repo ships a synced copy alongside Main.java), and pre_build
        # overwrites it from the repo-root canonical each run anyway.
        "skip_binary_cleanup": True,
        "extra_cleanup": ["Main.class", "Bench.class"],
    },
    "javascript": {
        "repo_dir": BASE / "ProjectEuler.JavaScript",
        "prob_dir": lambda p: BASE / "ProjectEuler.JavaScript" / f"problem_{p:03d}",
        # No build step.  Run main.js with node.
        "build_cmd_base": None,
        "src_files": {"main.js"},
        "run_cmd": ["node", "main.js"],
        "skip_binary_cleanup": True,
    },
    "python": {
        "repo_dir": BASE / "ProjectEuler.Python",
        # File-based layout (unique among the suite): problem_NNN.py lives at
        # the repo root, not in a per-problem dir.  We point prob_dir at the
        # repo root, then src_files names the file we expect.
        "prob_dir": lambda p: BASE / "ProjectEuler.Python",
        "build_cmd_base": None,
        "src_files": lambda p: {f"problem_{p:03d}.py"},
        "run_cmd": lambda p: ["python3", f"problem_{p:03d}.py"],
        "skip_binary_cleanup": True,
    },
    "csharp": {
        "repo_dir": BASE / "ProjectEuler.CSharp",
        "prob_dir": lambda p: BASE / "ProjectEuler.CSharp" / f"problem_{p:03d}",
        # Per ProjectEuler.CSharp/CLAUDE.md: `dotnet build -c Release`,
        # then `dotnet bin/Release/net10.0/problem_NNN.dll`.
        # --nologo --verbosity quiet keeps stdout clean.
        "build_cmd_base": ["dotnet", "build", "-c", "Release", "--nologo", "-v", "quiet"],
        "build_extra_libs": [[]],
        "src_files": {"Program.cs"},
        "run_cmd": lambda p: ["dotnet", f"bin/Release/net10.0/problem_{p:03d}.dll"],
        # bin/ and obj/ are gitignored; no in-tree binary to clean.
        "skip_binary_cleanup": True,
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
    # Verify expected source file(s) exist before attempting the build.
    # Configs that don't expose source names (e.g. wrapped in sh -c) can list
    # them explicitly via `src_files` — which itself may be a set or a
    # callable(problem_int)→set (e.g. Python's file-based layout).
    if "src_files" in cfg:
        src_files = cfg["src_files"](problem) if callable(cfg["src_files"]) else cfg["src_files"]
    else:
        src_files = {arg for arg in cfg["build_cmd_base"]
                     if arg.endswith((".c", ".cpp", ".cs", ".go", ".java", ".js", ".py", ".rs", ".s", ".zig"))}
    for src in src_files:
        if not (prob_dir / src).is_file():
            result.notes.append(f"no {src} in {prob_dir}")
            return result

    # Optional pre-build hook (e.g. Java copies Bench.java into the prob dir).
    pre_build = cfg.get("pre_build")
    if pre_build is not None:
        try:
            pre_build(cfg["repo_dir"], prob_dir, problem)
        except Exception as e:
            result.notes.append(f"pre-build failed: {e}")
            return result

    # 1. Build.  Try the base command first; if it fails, retry with each
    # extra-lib combo (mirrors benchmark.sh's fallback chain for primesieve/fmt).
    # `build_cmd_base` may be a list (fixed), callable(problem_int)→list
    # (per-prob, e.g. Zig's build-from-repo-root sh -c), or None (no build
    # step needed — e.g. interpreted languages like Python and JavaScript).
    build_cmd_base = cfg["build_cmd_base"]
    if build_cmd_base is None:
        # No build step.  The "run" step will do everything.
        pass
    else:
        if callable(build_cmd_base):
            build_cmd_base = build_cmd_base(problem)
        build_ok = False
        last_err = ""
        for extra in cfg.get("build_extra_libs", [[]]):
            try:
                build = subprocess.run(
                    build_cmd_base + extra,
                    cwd=prob_dir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if build.returncode == 0:
                    build_ok = True
                    break
                last_err = build.stderr[:200].strip() or build.stdout[:200].strip()
            except subprocess.TimeoutExpired:
                result.notes.append("build timeout (60s)")
                return result
        if not build_ok:
            result.notes.append(f"build failed (all link combos): {last_err}")
            return result

    # 2. Run (always clean up the binary, regardless of outcome).
    # `run_cmd` may be a list (fixed) or callable(problem_int)→list (per-prob).
    run_cmd = cfg["run_cmd"](problem) if callable(cfg["run_cmd"]) else cfg["run_cmd"]
    try:
        try:
            proc = subprocess.run(
                run_cmd,
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
        # Always clean up the binary so the working tree stays untracked-free.
        # Some langs (Rust, JS, Python, Java, C#) either have no in-tree
        # binary or put their build artifacts in gitignored dirs — set
        # `skip_binary_cleanup: True` and use `extra_cleanup` for any
        # incidental files (e.g. Java's .class files).
        if not cfg.get("skip_binary_cleanup", False):
            binary = prob_dir / cfg["binary_name"]
            if binary.exists():
                binary.unlink()
        # Extra cleanup for multi-step builds (e.g. ARM64's solve.o)
        for extra in cfg.get("extra_cleanup", []):
            path = prob_dir / extra
            if path.exists():
                path.unlink()

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
