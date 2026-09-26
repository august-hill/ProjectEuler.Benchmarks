#!/usr/bin/env python3
"""rebench_all.py — full-column re-bench after a toolchain bump.

Runs run_bench.py once per language, SEQUENTIALLY, each with an explicit
problem list (so languages are never asked for cells they do not have).

Usage: python3 scripts/rebench_all.py LISTS.json [--iters 15] [--langs a,b]
LISTS.json maps lang -> [problem numbers].
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ORDER = ["arm64", "c", "go", "zig", "cpp", "javascript", "python", "csharp", "java", "rust"]
HERE = Path(__file__).resolve().parent


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lists")
    ap.add_argument("--iters", type=int, default=15)
    ap.add_argument("--langs", default=",".join(ORDER))
    a = ap.parse_args()
    lists = json.load(open(a.lists))
    t0 = time.time()
    for lang in a.langs.split(","):
        probs = lists.get(lang, [])
        if not probs:
            log(f"{lang}: no cells, skipping")
            continue
        log(f"==== {lang}: {len(probs)} cells START")
        t = time.time()
        rc = subprocess.call(
            [sys.executable, str(HERE / "run_bench.py"),
             "--problems", ",".join(str(p) for p in probs),
             "--iters", str(a.iters), "--langs", lang,
             "--log-prefix", f"/tmp/pe_rebench_{lang}"],
            cwd=HERE.parent)
        log(f"==== {lang}: rc={rc} in {(time.time() - t) / 60:.1f} min "
            f"(total {(time.time() - t0) / 3600:.2f} h)")
    log("ALL DONE")


if __name__ == "__main__":
    main()
