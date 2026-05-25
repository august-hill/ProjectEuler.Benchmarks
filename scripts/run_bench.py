#!/usr/bin/env python3
"""run_bench.py — sequential orchestrator for `euler-bench per-iter --write`
across one or more languages.

Why it exists: euler-bench prints multi-KB of per-problem stdout per lang.
Naive `subprocess.run(..., capture_output=True)` deadlocks at the OS pipe
buffer (~64KB) for long-running subprocesses — a real bug class that ate
a 9-hour rebench on 2026-05-24/25. This wraps Popen with line-by-line
streaming so the pipe never fills + the user sees real-time progress.

Usage:
    python3 scripts/run_bench.py --problems 1-10 --iters 10
    python3 scripts/run_bench.py --problems 1-200 --iters 10 --langs c,cpp
    python3 scripts/run_bench.py --problems 7,10,174 --iters 2

The default lang set is all 10 (slow-langs LAST so visible progress comes
early). Order matches the previous run_full_bench: fast-fail diagnostic
ordering wins over alphabetical.

Logs:
    /tmp/pe_bench_<timestamp>.log   — full transcript (tee'd to stdout too)
    /tmp/pe_bench_<timestamp>.json  — per-lang summary on completion

Anti-patterns intentionally avoided:
    capture_output=True             → pipe-fill deadlock
    parallel across langs           → CPU contention contaminates timings
    silent failure on rc != 0       → euler-bench exits 1 on answer mismatches;
                                       we treat that as warning, not stop
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Default lang order: fast first (visible progress + early bug detection),
# managed/heavy last. Matches the pre-existing convention in pe/CLAUDE.md.
DEFAULT_LANGS = [
    "arm64", "c", "go",            # fast native: ~5-10 min each at full scale
    "zig",                          # variable (comptime spikes some problems)
    "cpp", "javascript", "python",  # ~5-10 min
    "csharp", "java",               # managed startup × N iters: ~15-20 min
    "rust",                         # LTO compile dominates: ~20-25 min
]


def find_benchmarks_dir():
    """Resolve the pe/benchmarks/ directory from this script's location.
    Script lives at <benchmarks_dir>/scripts/run_bench.py."""
    return Path(__file__).resolve().parent.parent


def run_streaming(cmd, cwd, log_handle):
    """Run cmd, piping stdout+stderr line-by-line to log_handle AND sys.stdout.

    Returns the subprocess return code. Doesn't raise on non-zero — caller
    decides what to do.
    """
    p = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # merge into stdout so order is preserved
        bufsize=1,                  # line-buffered
        text=True,
    )
    assert p.stdout is not None
    for line in p.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        log_handle.write(line)
        log_handle.flush()
    p.wait()
    return p.returncode


def say(log_handle, msg):
    """Print a timestamped orchestrator-level message (distinct from
    subprocess output) to both stdout and the log."""
    line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
    sys.stdout.write(line)
    sys.stdout.flush()
    log_handle.write(line)
    log_handle.flush()


def parse_args():
    p = argparse.ArgumentParser(
        description="Sequential euler-bench orchestrator with streaming output.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
    # Round 1: 10×10 sanity baseline
    python3 scripts/run_bench.py --problems 1-10 --iters 10

    # Specific problems across all langs
    python3 scripts/run_bench.py --problems 7,10,174 --iters 10

    # Subset of langs at full scale (e.g. compiled-only sanity)
    python3 scripts/run_bench.py --problems 1-200 --iters 10 --langs c,cpp,rust,go,zig
""",
    )
    p.add_argument("--problems", required=True,
                   help="Problem range/list passed to euler-bench (e.g. '1-10', '7,10,174', '1-200')")
    p.add_argument("--iters", type=int, default=10,
                   help="Fresh-process invocations per problem (default: 10; minimum: 1)")
    p.add_argument("--langs", default=",".join(DEFAULT_LANGS),
                   help=f"Comma-separated lang keys. Default order (fast first): "
                        f"{','.join(DEFAULT_LANGS)}")
    p.add_argument("--log-prefix", default="/tmp/pe_bench",
                   help="Log file prefix (full path: PREFIX_<timestamp>.log)")
    p.add_argument("--per-lang-timeout", type=int, default=3600,
                   help="Per-lang subprocess timeout in seconds (default: 3600)")
    return p.parse_args()


def main():
    args = parse_args()
    if args.iters < 1:
        print(f"--iters must be >= 1 (got {args.iters})", file=sys.stderr)
        return 2

    bench_dir = find_benchmarks_dir()
    euler_bench = bench_dir / "cmd" / "euler-bench" / "euler-bench"
    if not euler_bench.exists():
        print(f"euler-bench binary not found at {euler_bench}", file=sys.stderr)
        print("(build with: cd cmd/euler-bench && go build)", file=sys.stderr)
        return 2

    langs = [s.strip() for s in args.langs.split(",") if s.strip()]
    if not langs:
        print("--langs is empty", file=sys.stderr)
        return 2

    ts = time.strftime("%Y%m%d-%H%M%S")
    log_path = Path(f"{args.log_prefix}_{ts}.log")
    summary_path = Path(f"{args.log_prefix}_{ts}.json")
    log = log_path.open("w", buffering=1)  # line-buffered

    say(log, f"euler-bench orchestrator")
    say(log, f"  problems={args.problems!r}  iters={args.iters}  langs={langs}")
    say(log, f"  log={log_path}  summary={summary_path}")
    say(log, f"  benchmarks_dir={bench_dir}")
    say(log, "")

    total_start = time.time()
    results = {}
    for lang in langs:
        lang_start = time.time()
        say(log, f"━━━━ {lang}: STARTING ━━━━")
        cmd = [
            str(euler_bench), "per-iter",
            "--lang", lang,
            "--problems", args.problems,
            "--iters", str(args.iters),
            "--write",
        ]
        try:
            rc = run_streaming(cmd, bench_dir, log)
        except Exception as e:
            say(log, f"  EXCEPTION: {e}")
            results[lang] = {"rc": -2, "elapsed_s": time.time() - lang_start,
                             "error": str(e)}
            continue
        elapsed = time.time() - lang_start
        # euler-bench exits 1 on answer mismatches; that's a warning, not a stop.
        status = "ok" if rc == 0 else f"warn (rc={rc}, likely answer mismatches)"
        say(log, f"━━━━ {lang}: DONE in {elapsed:.0f}s ({elapsed/60:.1f}m)  {status} ━━━━")
        say(log, "")
        results[lang] = {"rc": rc, "elapsed_s": round(elapsed, 1)}

    total = time.time() - total_start
    say(log, "=" * 70)
    say(log, f"TOTAL: {total:.0f}s = {total/60:.1f} min")
    say(log, "=" * 70)
    say(log, "Per-lang summary:")
    for lang, r in results.items():
        rc = r.get("rc", "?")
        e = r.get("elapsed_s", 0)
        note = f"  ({r['error']})" if "error" in r else ""
        say(log, f"  {lang:<12} rc={rc:>3}  elapsed={e:>6.0f}s{note}")

    summary = {
        "args": vars(args),
        "total_s": round(total, 1),
        "per_lang": results,
        "log": str(log_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2))
    say(log, "")
    say(log, f"Summary written to {summary_path}")
    log.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
