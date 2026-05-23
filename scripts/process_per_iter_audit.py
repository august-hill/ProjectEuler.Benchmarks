#!/usr/bin/env python3
"""
process_per_iter_audit.py — Process-per-invocation timing.

What it measures: the cost a user *actually pays* when invoking the bench
binary as a fresh process N times.  Models the "cron job at scale" or "shell
loop" scenario:

    for i in 1..100; do time ./main_bench; done

Each invocation is independent: no in-process state survives (OS-enforced),
no language-internal caches persist (primesieve, Rust OnceLock, Python
@lru_cache all start empty), no harness warmup iterations amortize startup.

The metric to compare against: the existing harness's "in-process warm"
time (the BENCHMARK line's time_ns), which represents the steady-state cost
of solve() within one long-running process AFTER warm-up — useful for a
server/daemon scenario but not for a CLI/cron one.

Procedure per (lang, problem):
  1. Build the binary (reuse adapter from double_call_audit.py).
  2. Run the binary N times.  For each invocation, parse:
       - COLDSTART time_ns (cost of the first solve() in this process)
       - BENCHMARK time_ns (steady-state per-call in this process, last iter)
       - Also record Python's perf_counter wall (gives spawn-to-exit total).
  3. Aggregate the N cold samples (median is the headline).
  4. Report side-by-side: in-process warm | per-iter cold (median of N
     fresh-process cold times) | divergence ratio.

A high cold/warm divergence ratio (>2×) means the in-process warm number is
under-reporting the cost a real user pays per invocation — either due to a
language-internal cache being warm (Rust OnceLock, primesieve), or because
the algorithm has expensive first-call setup the warm iter skips.

USAGE:
  python3 process_per_iter_audit.py --lang cpp --problems 1-10
  python3 process_per_iter_audit.py --lang all --problems 1-10 --iters 10
"""

import argparse
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# Reuse the lang adapters + parsing from the existing audit
sys.path.insert(0, str(Path(__file__).parent))
from double_call_audit import (  # noqa: E402
    BENCHMARK_RE,
    COLDSTART_RE,
    LANG_CONFIG,
    parse_problems,
)


@dataclass
class PerIterResult:
    lang: str
    problem: int
    in_process_warm_ns: int = 0
    cold_samples: List[int] = field(default_factory=list)
    wall_samples_ns: List[int] = field(default_factory=list)
    answer: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    build_ok: bool = False

    @property
    def cold_median_ns(self) -> int:
        return int(statistics.median(self.cold_samples)) if self.cold_samples else 0

    @property
    def cold_min_ns(self) -> int:
        return min(self.cold_samples) if self.cold_samples else 0

    @property
    def wall_median_ns(self) -> int:
        return int(statistics.median(self.wall_samples_ns)) if self.wall_samples_ns else 0

    @property
    def divergence_ratio(self) -> float:
        """cold_median / in_process_warm.  High → warm is hiding real work."""
        if self.in_process_warm_ns <= 0:
            return float("inf") if self.cold_median_ns > 0 else 0.0
        return self.cold_median_ns / self.in_process_warm_ns


def build_problem(lang: str, problem: int) -> tuple[bool, str, Path]:
    """Build the binary for (lang, problem).  Returns (ok, error_msg, prob_dir)."""
    cfg = LANG_CONFIG[lang]
    prob_dir = cfg["prob_dir"](problem)
    if not prob_dir.is_dir():
        return (False, f"missing dir: {prob_dir}", prob_dir)

    # Verify expected source files
    if "src_files" in cfg:
        for src in cfg["src_files"]:
            if not (prob_dir / src).is_file():
                return (False, f"missing src: {src}", prob_dir)

    # Build with fallback chain (e.g. -lprimesieve)
    last_err = ""
    for extra in cfg.get("build_extra_libs", [[]]):
        try:
            r = subprocess.run(
                cfg["build_cmd_base"] + extra,
                cwd=prob_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if r.returncode == 0:
                return (True, "", prob_dir)
            last_err = r.stderr[:200].strip()
        except subprocess.TimeoutExpired:
            return (False, "build timeout (60s)", prob_dir)
    return (False, f"build failed: {last_err}", prob_dir)


def cleanup_binary(lang: str, problem: int, prob_dir: Path) -> None:
    cfg = LANG_CONFIG[lang]
    if not cfg.get("skip_binary_cleanup", False):
        binary = prob_dir / cfg["binary_name"]
        if binary.exists():
            binary.unlink()
    for extra in cfg.get("extra_cleanup", []):
        path = prob_dir / extra
        if path.exists():
            path.unlink()


def measure_one_invocation(lang: str, prob_dir: Path, problem: int) -> dict:
    """Run binary once.  Return dict with cold_ns, warm_ns, wall_ns, answer."""
    cfg = LANG_CONFIG[lang]
    run_cmd = cfg["run_cmd"](problem) if callable(cfg["run_cmd"]) else cfg["run_cmd"]

    wall_t0 = time.perf_counter_ns()
    try:
        proc = subprocess.run(
            run_cmd,
            cwd=prob_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        wall_ns = time.perf_counter_ns() - wall_t0
    except subprocess.TimeoutExpired:
        return {"error": "run timeout"}

    if proc.returncode != 0:
        return {"error": f"exit {proc.returncode}: {proc.stderr[:100].strip()}"}

    cold_m = COLDSTART_RE.search(proc.stdout)
    warm_m = BENCHMARK_RE.search(proc.stdout)
    if not cold_m or not warm_m:
        return {"error": "missing COLDSTART or BENCHMARK line"}

    return {
        "cold_ns": int(cold_m.group(1)),
        "cold_answer": cold_m.group(2).strip(),
        "warm_ns": int(warm_m.group(2)),
        "warm_answer": warm_m.group(1).strip(),
        "wall_ns": wall_ns,
    }


def audit_problem(lang: str, problem: int, n_iters: int) -> PerIterResult:
    result = PerIterResult(lang=lang, problem=problem)

    ok, err, prob_dir = build_problem(lang, problem)
    if not ok:
        result.notes.append(err)
        return result
    result.build_ok = True

    try:
        for i in range(n_iters):
            m = measure_one_invocation(lang, prob_dir, problem)
            if "error" in m:
                result.notes.append(f"iter {i+1}: {m['error']}")
                continue
            result.cold_samples.append(m["cold_ns"])
            result.wall_samples_ns.append(m["wall_ns"])
            # Capture answer + in-process warm from last successful iter (all
            # invocations run the same code, so the last is representative).
            result.in_process_warm_ns = m["warm_ns"]
            result.answer = m["warm_answer"]
    finally:
        cleanup_binary(lang, problem, prob_dir)

    return result


def fmt_ns(ns: int) -> str:
    """Format nanoseconds with appropriate unit."""
    if ns < 1_000:
        return f"{ns}ns"
    if ns < 1_000_000:
        return f"{ns / 1_000:.1f}µs"
    if ns < 1_000_000_000:
        return f"{ns / 1_000_000:.1f}ms"
    return f"{ns / 1_000_000_000:.2f}s"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--lang", default="cpp",
                    help="Language to audit, or 'all' for all configured (default: cpp)")
    ap.add_argument("--problems", default="1-10",
                    help="Problem range/list: '1-10', '1,3,7', or '1' (default: 1-10)")
    ap.add_argument("--iters", type=int, default=10,
                    help="Fresh-process invocations per problem (default: 10)")
    args = ap.parse_args()

    if args.lang == "all":
        langs = sorted(LANG_CONFIG.keys())
    else:
        if args.lang not in LANG_CONFIG:
            print(f"!! unknown lang: {args.lang} (have: {sorted(LANG_CONFIG)})", file=sys.stderr)
            return 2
        langs = [args.lang]

    problems = parse_problems(args.problems)

    print(f"=== Process-per-iter audit  langs={langs}  problems={problems}  iters={args.iters}\n")

    all_results: Dict[str, List[PerIterResult]] = {}
    for lang in langs:
        print(f"--- {lang}:")
        results = []
        for p in problems:
            print(f"    p{p:03d}...", end=" ", flush=True)
            r = audit_problem(lang, p, args.iters)
            results.append(r)
            if r.notes:
                print(f"({r.notes[0]})")
            else:
                print(f"warm={fmt_ns(r.in_process_warm_ns):>7s}  "
                      f"cold-median={fmt_ns(r.cold_median_ns):>7s}  "
                      f"wall-median={fmt_ns(r.wall_median_ns):>7s}  "
                      f"div={r.divergence_ratio:>6.1f}×")
        all_results[lang] = results

    # Summary table — cross-lang per problem
    print(f"\n{'='*100}")
    print("CROSS-LANG SUMMARY")
    print(f"{'='*100}")
    print(f"  warm:        in-process steady state (BENCHMARK line time_ns)")
    print(f"  cold-med:    median COLDSTART across {args.iters} fresh-process invocations")
    print(f"  wall-med:    median Python-perceived wall (incl. process spawn + full harness)")
    print(f"  div:         cold-median / warm; >2× means warm is under-reporting real per-iter cost\n")

    for p in problems:
        print(f"\n  p{p:03d}:")
        print(f"    {'lang':<8} {'warm':>10} {'cold-med':>10} {'wall-med':>10} {'div':>7}  notes")
        print(f"    {'-'*8} {'-'*10} {'-'*10} {'-'*10} {'-'*7}  -----")
        for lang in langs:
            r = next((x for x in all_results[lang] if x.problem == p), None)
            if r is None: continue
            if r.notes and not r.cold_samples:
                print(f"    {lang:<8} {'-':>10} {'-':>10} {'-':>10} {'-':>7}  {r.notes[0][:60]}")
                continue
            div_str = f"{r.divergence_ratio:>6.1f}×" if r.divergence_ratio > 0 else "    -"
            print(f"    {lang:<8} {fmt_ns(r.in_process_warm_ns):>10} "
                  f"{fmt_ns(r.cold_median_ns):>10} "
                  f"{fmt_ns(r.wall_median_ns):>10} "
                  f"{div_str:>7}")

    # Notable divergences (>3×)
    print(f"\n{'='*100}")
    print("NOTABLE DIVERGENCES (cold-median / in-process warm > 3×)")
    print(f"{'='*100}")
    notable = []
    for lang in langs:
        for r in all_results[lang]:
            if r.cold_samples and r.divergence_ratio > 3:
                notable.append(r)
    if not notable:
        print("  (none)")
    else:
        for r in sorted(notable, key=lambda x: -x.divergence_ratio):
            print(f"  {r.lang} p{r.problem:03d}: warm={fmt_ns(r.in_process_warm_ns)} "
                  f"cold-median={fmt_ns(r.cold_median_ns)}  "
                  f"divergence={r.divergence_ratio:.1f}×  "
                  f"→ in-process warm hides {fmt_ns(r.cold_median_ns - r.in_process_warm_ns)} of real cost")
    return 0


if __name__ == "__main__":
    sys.exit(main())
