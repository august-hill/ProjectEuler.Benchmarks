# Legacy artifacts (pre-2026-05-23)

This directory holds the previous benchmark site — the "two modes" / "three modes"
era, where we reported in-process warm timings alongside cold timings and tried
to manage cache-pattern complexity inside the source code.

That worldview was reset on 2026-05-23.  The new site uses a single metric:
**per-invocation cost** (median wall time across N fresh OS process invocations).
See `../../JOURNEY.md` chapters from that date for the story.

Files preserved here for historical reference only — none are part of the live
benchmark pipeline anymore:

- `final_analysis.py` — generated the old RESULTS.md and three_mode charts.
  Replaced by `../../report.py`.
- `three_metric_report.py` — generated `THREE_MODE_REPORT.md`.  Retired.
- `THREE_MODE_REPORT.md` — the deep three-mode analysis (74 KB).  Retired.
- `charts/final_*.png` — chart variants from the three-mode era (total time
  with `max(warm, cold)` band-aid heuristic, slowdown distribution, etc.).

If you want to understand why we don't lead with these metrics anymore, the
shortest answer is in `../../JOURNEY.md` — search for "From In-Process Warm to
Process-Per-Iteration".
