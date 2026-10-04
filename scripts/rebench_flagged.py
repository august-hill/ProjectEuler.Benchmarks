#!/usr/bin/env python3
"""rebench_flagged.py — re-bench every cell carrying a given flag, one cell at a time.

Written 2026-10-04 to clear stale `wall-suspect` flags after schema v3 switched the
wall statistic from median to minimum (METHODOLOGY.md §2): rows benched before v3
still carry the median, which for 2-sample cells averages in the cold first launch.

  - Targets: `runs` rows with status='pass' whose flags contain --flag, queried at start.
  - Resumable: skips any cell whose latest run_history row already has samples_json
    (i.e. it was measured under v3). A cell that is STILL flagged after a v3 bench is a
    genuine flag and is never retried — it is reported for review instead.
  - Load guard: before each cell, waits while the 1-minute loadavg exceeds --max-load.
  - Writes only to the DB (via euler-bench --write). Never runs report.py, commits or pushes.
  - --detach re-launches itself in a new session (survives the parent shell / Claude
    session exiting) and returns immediately with the log path.

Logs (default ~/Library/Logs/pe-rebench/): run-<ts>.log (human, per cell), results-<ts>.jsonl
(one record per cell), bench-<ts>.log (raw euler-bench output), summary-<ts>.txt (at end).

Usage: python3 scripts/rebench_flagged.py [--flag wall-suspect] [--max-load 6] [--dry-run] [--detach]
"""
import argparse
import json
import os
import sqlite3
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "bench-private.db"
BENCH = REPO / "cmd" / "euler-bench" / "euler-bench"
CELL_TIMEOUT_S = 900


def targets(db, flag):
    rows = db.execute(
        "SELECT lang, problem, time_ns, subprocess_wall_ns FROM runs "
        "WHERE status='pass' AND flags LIKE ? ORDER BY lang, problem", (f"%{flag}%",)).fetchall()
    out, skipped = [], 0
    for lang, prob, t, w in rows:
        sj = db.execute("SELECT samples_json FROM run_history WHERE lang=? AND problem=? "
                        "ORDER BY id DESC LIMIT 1", (lang, prob)).fetchone()
        if sj and sj[0]:
            skipped += 1  # already measured under v3: a remaining flag is genuine
            continue
        out.append((lang, prob, t, w))
    return out, skipped


def other_bench_running():
    r = subprocess.run(["pgrep", "-f", "euler-bench per-iter"], capture_output=True, text=True)
    return [p for p in r.stdout.split() if int(p) != os.getpid()]


def summarize(results, path):
    lines = []
    by = lambda pred: [r for r in results if pred(r)]
    cleared = by(lambda r: r["status"] == "pass" and r["flag_cleared"])
    still = by(lambda r: r["status"] == "pass" and not r["flag_cleared"])
    failed = by(lambda r: r["status"] != "pass")
    lines.append(f"cells: {len(results)}  cleared: {len(cleared)}  still-flagged: {len(still)}  failed: {len(failed)}")
    for lang in sorted({r["lang"] for r in results}):
        d = [r["time_change_pct"] for r in results if r["lang"] == lang and r["time_change_pct"] is not None]
        if d:
            q = statistics.quantiles(d, n=4) if len(d) >= 2 else [d[0]] * 3
            lines.append(f"  {lang:6s} n={len(d):3d}  time change % : p25 {q[0]:+.1f}  median {q[1]:+.1f}  p75 {q[2]:+.1f}")
    cold = [r["per_launch_excess_ms"][0] for r in results if r.get("per_launch_excess_ms")]
    warm = [min(r["per_launch_excess_ms"][1:]) for r in results if len(r.get("per_launch_excess_ms") or []) > 1]
    if cold:
        lines.append(f"  first-launch excess ms: median {statistics.median(cold):.0f}  max {max(cold):.0f}")
    if warm:
        lines.append(f"  warm-launch excess ms:  median {statistics.median(warm):.0f}  max {max(warm):.0f}")
    big = sorted((r for r in results if r["time_change_pct"] is not None and abs(r["time_change_pct"]) > 10),
                 key=lambda r: -abs(r["time_change_pct"]))
    for title, rs in (("STILL FLAGGED (review)", still), ("FAILED (review)", failed),
                      ("TIME CHANGE >10% (review)", big)):
        if rs:
            lines.append(f"\n{title}:")
            for r in rs:
                lines.append(f"  {r['lang']}/{r['problem']}  {r['status']}  time {r['old_time_s']:.3f}->{r['new_time_s']}"
                             f"  ({r['time_change_pct']:+.1f}%)  flags={r['flags']}  err={r.get('error')}")
    text = "\n".join(lines) + "\n"
    path.write_text(text)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flag", default="wall-suspect")
    ap.add_argument("--max-load", type=float, default=6.0)
    ap.add_argument("--logdir", default=str(Path.home() / "Library/Logs/pe-rebench"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--detach", action="store_true")
    a = ap.parse_args()

    logdir = Path(a.logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")

    if a.detach:
        argv = [sys.executable, str(Path(__file__).resolve())] + [x for x in sys.argv[1:] if x != "--detach"]
        out = open(logdir / f"stdout-{ts}.log", "w")
        p = subprocess.Popen(argv, cwd=REPO, stdout=out, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True)
        print(f"detached pid {p.pid}; logs in {logdir} (run-*.log, summary-*.txt)")
        return

    if not BENCH.exists():
        sys.exit(f"euler-bench binary missing: {BENCH}")
    if other_bench_running():
        sys.exit("another euler-bench per-iter is running — benches must run solo")

    runlog = open(logdir / f"run-{ts}.log", "w", buffering=1)
    log = lambda m: runlog.write(f"[{time.strftime('%H:%M:%S')}] {m}\n")
    db = sqlite3.connect(DB)
    todo, skipped = targets(db, a.flag)
    log(f"flag={a.flag} targets={len(todo)} skipped(already v3)={skipped} max_load={a.max_load} pid={os.getpid()}")
    if a.dry_run:
        for t in todo:
            log(f"  would bench {t[0]}/{t[1]}  ({t[2]/1e9:.2f}s)")
        print(f"dry run: {len(todo)} targets, {skipped} skipped; see {runlog.name}")
        return

    results, t0 = [], time.time()
    jsonl = open(logdir / f"results-{ts}.jsonl", "w", buffering=1)
    benchlog = logdir / f"bench-{ts}.log"
    for i, (lang, prob, old_t, old_w) in enumerate(todo, 1):
        waited = 0
        while os.getloadavg()[0] > a.max_load:
            if waited % 300 == 0:
                log(f"  load {os.getloadavg()[0]:.1f} > {a.max_load}: pausing before {lang}/{prob}")
            time.sleep(30)
            waited += 30
        load = os.getloadavg()[0]
        with open(benchlog, "a") as bl:
            try:
                rc = subprocess.run([str(BENCH), "per-iter", "--lang", lang, "--problems", prob, "--write"],
                                    cwd=REPO, stdout=bl, stderr=subprocess.STDOUT, timeout=CELL_TIMEOUT_S).returncode
            except subprocess.TimeoutExpired:
                rc = "timeout"
        row = db.execute("SELECT status, time_ns, subprocess_wall_ns, flags, samples_json, error FROM run_history "
                         "WHERE lang=? AND problem=? ORDER BY id DESC LIMIT 1", (lang, prob)).fetchone()
        st, t, w, fl, sj, err = row
        samples = json.loads(sj) if sj else []
        rec = {
            "lang": lang, "problem": prob, "rc": rc, "status": st, "error": err,
            "old_time_s": old_t / 1e9, "new_time_s": round(t / 1e9, 4) if t else None,
            "time_change_pct": round(100 * (t - old_t) / old_t, 2) if t and st == "pass" else None,
            "old_wall_excess_ms": round((old_w - old_t) / 1e6), "new_wall_excess_ms": round((w - t) / 1e6) if w and t else None,
            "per_launch_excess_ms": [round((s[1] - s[0]) / 1e6) for s in samples],
            "flags": fl, "flag_cleared": not (fl and a.flag in fl), "load": round(load, 2),
            "fresh": bool(sj),  # False => the bench did not write a new v3 row
        }
        results.append(rec)
        jsonl.write(json.dumps(rec) + "\n")
        eta = (time.time() - t0) / i * (len(todo) - i) / 60
        log(f"[{i}/{len(todo)}] {lang}/{prob} {st} time {rec['old_time_s']:.3f}->{rec['new_time_s']}s "
            f"({rec['time_change_pct']}%) launch-excess {rec['per_launch_excess_ms']}ms flags={fl!r} "
            f"load {load:.1f}  ETA {eta:.0f} min")

    text = summarize(results, logdir / f"summary-{ts}.txt")
    log(f"DONE in {(time.time() - t0) / 60:.1f} min\n{text}")


if __name__ == "__main__":
    main()
