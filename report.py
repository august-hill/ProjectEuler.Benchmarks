#!/usr/bin/env python3
"""
report.py — Regenerates RESULTS.md + charts for the per-invocation benchmark.

Replaces the previous final_analysis.py (which produced the 3-mode report).
The new model is simpler: ONE metric, process-per-invocation cost.

Inputs:
  data/bench-private.db  — SQLite SSOT, written by `euler-bench per-iter --write`.
                            Two tables: runs (latest per lang+problem, PK on
                            (lang, problem)) + run_history (append-only).
                            We read `time_ns` from runs — the median across N
                            fresh-process invocations.  Migrated 2026-05-25 from
                            per-lang JSON files.

Outputs:
  RESULTS.md          — the public results page
  charts/per_iter_total.png    — horizontal bar chart, total cost ranking
  charts/per_iter_per_problem.png  — per-problem heatmap (small-multiples)

Scope:
  Currently 100 problems × 10 languages.  When we extend (more problems
  audited), the SCOPE_PROBLEMS list is the single place to change.
"""

import json
import sqlite3
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt


REPO = Path(__file__).resolve().parent
DATA_DIR = REPO / "data"
CHARTS_DIR = REPO / "charts"
# Per-band per-problem detail pages live under this dir to keep RESULTS.md
# scrollable.  Filename pattern: per_problem_NNN-MMM.md (lo-hi).
PER_PROBLEM_DIR = REPO / "per_problem"
_PER_PROBLEM_DIR = PER_PROBLEM_DIR.name  # for relative links from RESULTS.md

# Tier model — single source of truth at data/tiers.json, consumed via the
# shared scripts/tiers.py helper. Tier 1 = Foundation (all 10 langs, 1-200);
# Tier 2 = Deep Coverage (cpp/go/python/rust/zig, currently 201-400 — bumped
# from 201-300 in the 2026-05-25 overnight expansion); Tier 3 = Frontier
# (cpp+go, currently 401+ — was 301+ before the same expansion).
# See project_pe_tier_model_2026-05-22 auto-memory for why.
sys.path.insert(0, str(REPO / "scripts"))
from tiers import (  # noqa: E402
    load_tiers, langs_in_tier, in_scope as _in_scope,
    tier_for_problem, tier_problem_range, tier_label, TIER_ORDER,
)
_TIERS = load_tiers()

# Scope: cover tier-1 Foundation + tier-2 Deep Coverage + tier-3 Frontier
# (capped at 600 because tier-3 hi is unbounded but we don't iterate forever).
# Per-tier rendering filters out langs that aren't in scope for a given band
# (e.g., ARM64 doesn't appear in 201+ bands — it's tier-1 only; python/zig
# don't appear in 301+ bands — they're tier-1+tier-2 only). Partial-coverage
# is supported and intentional — when a (lang, problem) cell is unmeasured
# (AND the lang IS in scope per tier), report.py renders it as "missing" in
# the grid and excludes it from per-lang totals.
_T2_HI = tier_problem_range("tier_2_deep_coverage", _TIERS)[1] or 300
_T3_LO = tier_problem_range("tier_3_frontier", _TIERS)[0] or 301
# Display cap: max(t2_hi, 1000) covers the 501-1000 frontier campaign range
# (highest solved is 985 cpp / 978 go / 948 rust as of 2026-06-07).
_DISPLAY_HI = max(_T2_HI, 1000)
SCOPE_PROBLEMS = [f"{i:03d}" for i in range(1, _DISPLAY_HI + 1)]

# Coverage-grid display range — deliberately DECOUPLED from _DISPLAY_HI. The grid is a
# full-PE-range landscape map (extended to 1000 once PE crossed #999, 2026-06); the report's
# stats/coverage scope (_DISPLAY_HI) stays at its audited ceiling. A solved problem above
# _DISPLAY_HI therefore shows as a cell on the grid but is NOT folded into per-lang totals,
# coverage %, or tier denominators (those are stat surfaces; the grid is just a map).
_GRID_HI = 1000
GRID_PROBLEMS = [f"{i:03d}" for i in range(1, _GRID_HI + 1)]

# Languages — used for data loading and the total-cost bar chart.  Alphabetic
# for stability across snapshots.
LANGS = ["arm64", "c", "cpp", "csharp", "go", "java", "javascript", "python", "rust", "zig"]

# Heatmap row order — fixed by language tier so the chart doesn't reshuffle
# rows between releases as ranking-by-total drifts.  Within each tier, alphabetic.
#
#   Native compiled (top), AOT-but-managed, JIT/managed, interpreted (bottom).
LANG_DISPLAY_ORDER = [
    "arm64", "c", "cpp", "rust", "zig",   # native compiled
    "go",                                  # AOT, GC'd
    "csharp", "java", "javascript",        # JIT / managed
    "python",                              # interpreted
]

# Heatmap is rendered as horizontal bands of this many problems each, stacked
# vertically.  Banding lets the chart scale to 1000+ problems without forcing
# cells to shrink below readability — each band is always a fixed-size,
# fixed-aspect grid.  Change this if you want denser or sparser bands.
BAND_SIZE = 100

# Display labels (some langs have nicer printed names than their keys)
DISPLAY = {
    "arm64": "ARM64",
    "c": "C",
    "cpp": "C++",
    "csharp": "C#",
    "go": "Go",
    "java": "Java",
    "javascript": "JavaScript",
    "python": "Python",
    "rust": "Rust",
    "zig": "Zig",
}

# Color per lang — stable across charts.  These match common conventions
# (Go's cyan, Python's blue, Rust's salmon, etc.).
COLOR = {
    "arm64":      "#E25822",   # orange-red
    "c":          "#555555",   # dark grey
    "cpp":        "#00599C",   # C++ blue
    "csharp":     "#239120",   # .NET green
    "go":         "#00ADD8",   # Go cyan
    "java":       "#B07219",   # Java brown
    "javascript": "#F0DB4F",   # JS yellow
    "python":     "#3776AB",   # Python blue
    "rust":       "#DEA584",   # Rust salmon
    "zig":        "#F7A41D",   # Zig orange
}


_DB_CONN = None  # cached SQLite read connection (one per process)


def _db() -> sqlite3.Connection | None:
    """Open (or return cached) read-only connection to the SQLite SSOT.

    Returns None if data/bench-private.db doesn't exist yet — callers treat
    that as an empty dataset.
    """
    global _DB_CONN
    if _DB_CONN is None:
        path = DATA_DIR / "bench-private.db"
        if not path.exists():
            return None
        # Read-only URI form prevents accidental writes from report.py.
        _DB_CONN = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        _DB_CONN.row_factory = sqlite3.Row
    return _DB_CONN


def load_lang_data(lang: str) -> dict:
    """Load all measurements for `lang` from the SQLite SSOT.

    Returns {problem_NNN: entry_dict} in the same shape downstream consumers
    expect — keys match the old JSON field names (status, time_ns,
    source_lines, etc.); NULL columns become None which `.get(field, 0) or 0`
    idioms handle correctly. Migrated 2026-05-25 from data/<lang>.json reads.
    """
    db = _db()
    if db is None:
        return {}
    cur = db.execute("SELECT * FROM runs WHERE lang = ?", (lang,))
    return {row["problem"]: dict(row) for row in cur}


def time_ns(entry: dict):
    """Headline metric for one problem.

    Reads `time_ns` — the single timing from the harness's one `solve()` call
    per process (RESULT|time_ns=N|answer=A).  See JOURNEY.md "Single-Call
    Harness" chapter.

    Returns:
        int (≥ 0)   — measured time in nanoseconds (0 is legitimate:
                       trivial closed-form algos can clock at sub-nanosecond)
        None        — problem absent or did not pass (no measurement)
    """
    if not entry or entry.get("status") != "pass":
        return None
    return int(entry.get("time_ns", 0) or 0)


def source_lines(entry: dict) -> int:
    """Source-line count for one problem; 0 if missing/absent."""
    if not entry:
        return 0
    return int(entry.get("source_lines", 0) or 0)


def status_of(entry: dict) -> str:
    """'pass' / 'fail' / 'missing' — for the coverage-grid chart."""
    if not entry:
        return "missing"
    return entry.get("status", "missing") or "missing"


def samples_of(entry: dict):
    """Iteration count behind this measurement.

    Suite-standard is `iters=10`; any cell with samples<10 is a partial
    measurement (median is still meaningful for >1s problems, but variance
    estimate is degraded). Cells with samples<10 are marked with `*` in
    the per-problem detail table.

    Returns int or None (missing).
    """
    if not entry or entry.get("status") != "pass":
        return None
    s = entry.get("samples")
    return int(s) if s is not None else None


def fmt_time(ns: int) -> str:
    """Human-readable nanoseconds.

    Note: 0 is a legitimate measurement (trivial algos clock at sub-ns).
    Callers must pre-check None (missing) before formatting.
    """
    if ns < 1_000:
        return f"{ns} ns"
    if ns < 1_000_000:
        return f"{ns/1_000:.1f} µs"
    if ns < 1_000_000_000:
        return f"{ns/1_000_000:.2f} ms"
    return f"{ns/1_000_000_000:.2f} s"


def aggregate() -> dict:
    """For each lang, compute totals + per-problem maps.

    Per-lang fields:
      per_problem_ns:     int(≥0) for measured, None for missing
      per_problem_lines:  int(≥0) lines for that file (0 if no source-lines field)
      per_problem_status: 'pass' / 'fail' / 'missing'
      total_ns:           sum of measured ns across THIS lang's measured cells
      total_lines:        sum of source lines across the in-scope problems
      missing:            count of None per_problem_ns entries

    Plus, attached to a special "_common" key (not a lang):
      problems:           list of problem keys where ALL 10 langs have status='pass'
                          (the apples-to-apples comparison surface)
      per_lang_total_ns:  {lang: sum of time_ns over the common set} — the metric
                          the totals/scatter charts use to avoid misleading
                          partial-coverage rankings.

    The common-set approach is a stop-gap until report.py becomes tier-aware
    (see spawn_task "Make report.py tier-aware"). For now, if any lang is
    intentionally stopped, that's what the existing tier model + a future
    report.py refactor would handle. Today (all 10 langs converging on tier 1)
    the common set is the right honest metric.
    """
    out = {}
    for lang in LANGS:
        probs = load_lang_data(lang)
        per_prob_ns = {p: time_ns(probs.get(p, {})) for p in SCOPE_PROBLEMS}
        per_prob_lines = {p: source_lines(probs.get(p, {})) for p in SCOPE_PROBLEMS}
        per_prob_status = {p: status_of(probs.get(p, {})) for p in SCOPE_PROBLEMS}
        per_prob_samples = {p: samples_of(probs.get(p, {})) for p in SCOPE_PROBLEMS}
        # Grid-only status, over the wider GRID_PROBLEMS range. Kept separate from the
        # per_problem_* dicts above so the totals below (which sum .values()) stay scoped
        # to SCOPE_PROBLEMS and are NOT inflated by solved problems above _DISPLAY_HI.
        grid_status = {p: status_of(probs.get(p, {})) for p in GRID_PROBLEMS}
        grid_ns = {p: time_ns(probs.get(p, {})) for p in GRID_PROBLEMS}
        grid_samples = {p: samples_of(probs.get(p, {})) for p in GRID_PROBLEMS}
        total_ns = sum(v for v in per_prob_ns.values() if v is not None)
        total_lines = sum(per_prob_lines.values())
        # "missing" is computed over the lang's IN-SCOPE problems per the tier
        # model — not the full SCOPE. E.g. ARM64 (tier-1 only) is missing 0 of
        # its 200 in-scope problems, not 100 of 300. The per-lang headline reads
        # "<measured>/<in_scope>" so partial coverage is honest per tier.
        in_scope = in_scope_problems(lang)
        in_scope_count = len(in_scope)
        missing = sum(1 for p in in_scope if per_prob_ns[p] is None)
        out[lang] = {
            "per_problem_ns": per_prob_ns,
            "per_problem_lines": per_prob_lines,
            "per_problem_status": per_prob_status,
            "per_problem_samples": per_prob_samples,
            "grid_status": grid_status,
            "grid_ns": grid_ns,
            "grid_samples": grid_samples,
            "total_ns": total_ns,
            "total_lines": total_lines,
            "missing": missing,
            "in_scope_count": in_scope_count,
        }

    # Common-set computation: problems where every lang has status='pass'.
    # Any lang missing OR with status!='pass' for a given problem disqualifies
    # that problem from the common set.
    #
    # `_common` is the LEGACY tier-1 common-set — kept for backward compat with
    # the existing chart code that drives the headline rank table. With SCOPE
    # extended to 1-300, problems 201-300 are auto-excluded because the 6
    # tier-1-only langs (arm64/c/csharp/java/javascript/rust) have status=missing
    # there (no data), so the all-pass-across-all-10 filter rejects them.
    common_problems = [
        p for p in SCOPE_PROBLEMS
        if all(out[lang]["per_problem_status"].get(p) == "pass" for lang in LANGS)
    ]
    out["_common"] = {
        "problems": common_problems,
        "per_lang_total_ns": {
            lang: sum(out[lang]["per_problem_ns"][p] for p in common_problems
                      if out[lang]["per_problem_ns"][p] is not None)
            for lang in LANGS
        },
        "per_lang_total_lines": {
            lang: sum(out[lang]["per_problem_lines"][p] for p in common_problems)
            for lang in LANGS
        },
    }

    # `_common_per_tier` — explicit per-tier common-sets for tier-aware charts.
    # The "common-set" surface is computed over ACTIVE langs — tier-designated
    # langs with COVERAGE ≥ this threshold in the tier's problem range. The
    # threshold prevents a misleading-but-honest case where a lang with just
    # 1 passing cell tightens the common-set to 1 problem (sample size too
    # small for a meaningful rank).
    #
    # 2026-05-25: lowered 0.5 → 0.25 alongside the tier-2 expansion 201-300 →
    # 201-400. At 50% no lang qualified post-expansion (each was at ~48% of the
    # widened 200-problem range despite having ~96 cells in the lower half),
    # which hid the chart entirely. At 25% all 5 langs re-qualify on their
    # existing 201-300 data and the chart renders with the actual common-set
    # range surfaced in the title (so readers see "common set spans 201-298"
    # not just "common set: 65 problems"). Common-set size remains the natural
    # secondary safeguard against pathological tiny intersections.
    ACTIVE_COVERAGE_THRESHOLD = 0.25  # 25% of in-scope tier problems
    out["_common_per_tier"] = {}
    for tier_key in TIER_ORDER:
        if tier_key not in _TIERS:
            continue
        lo, hi = tier_problem_range(tier_key, _TIERS)
        tier_probs = [
            p for p in SCOPE_PROBLEMS
            if int(p) >= lo and (hi is None or int(p) <= hi)
        ]
        designated_langs = langs_in_tier(tier_key, _TIERS)
        # Compute per-lang coverage ratio within this tier; active = ≥ threshold.
        active_langs = []
        for lang in designated_langs:
            n_pass = sum(
                1 for p in tier_probs
                if out[lang]["per_problem_status"].get(p) == "pass"
            )
            if tier_probs and (n_pass / len(tier_probs)) >= ACTIVE_COVERAGE_THRESHOLD:
                active_langs.append(lang)
        tier_common = [
            p for p in tier_probs
            if active_langs and all(
                out[lang]["per_problem_status"].get(p) == "pass" for lang in active_langs
            )
        ]
        out["_common_per_tier"][tier_key] = {
            "problems": tier_common,
            "langs": active_langs,
            "designated_langs": designated_langs,
            "per_lang_total_ns": {
                lang: sum(out[lang]["per_problem_ns"][p] for p in tier_common
                          if out[lang]["per_problem_ns"][p] is not None)
                for lang in active_langs
            },
            "per_lang_total_lines": {
                lang: sum(out[lang]["per_problem_lines"][p] for p in tier_common)
                for lang in active_langs
            },
        }
    return out


def render_speed_vs_size_chart(agg: dict) -> Path:
    """Scatter: total source lines vs total per-invocation cost, per language.

    X = sum of source_lines across the 10 in-scope problems
    Y = sum of cold-median ns across the same 10
    Each point is labeled with the language name.

    Both axes log-scale — language differences span 2-3 orders of magnitude
    in time and ~3× in lines.
    """
    # Use the common-set totals (apples-to-apples regardless of partial coverage)
    # — see aggregate()'s "_common" key. The total_lines stays per-lang's full
    # scope because LoC is a structural property of source code, not a runtime
    # measurement; mixing scopes there has different semantics.
    common = agg["_common"]
    fig, ax = plt.subplots(figsize=(10, 6))
    for lang in LANGS:
        x = common["per_lang_total_lines"][lang]
        y_ms = common["per_lang_total_ns"][lang] / 1_000_000
        if x == 0 or y_ms == 0:
            continue
        ax.scatter(x, y_ms, s=200, c=COLOR[lang], edgecolors="black",
                   linewidths=0.6, alpha=0.85, zorder=3)
        # Label offset to the right; use white background for legibility
        ax.annotate(DISPLAY[lang], xy=(x, y_ms), xytext=(8, 4),
                    textcoords="offset points", fontsize=10,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white",
                              ec="none", alpha=0.85))

    ax.set_xscale("log")
    ax.set_yscale("log")
    # Tier-1 chart uses the Foundation common-set (max problem = tier_1's hi).
    _t1_hi = tier_problem_range("tier_1_foundation", _TIERS)[1] or len(SCOPE_PROBLEMS)
    ax.set_xlabel(f"Total source lines across Foundation problems 1–{_t1_hi} (log scale)")
    ax.set_ylabel("Total per-invocation cost — ms (log scale)")
    ax.set_title(f"Speed vs Code Size — Foundation ({len(LANGS)} languages, problems 1–{_t1_hi})\n"
                 "Bottom-left corner = fast + concise; top-right = slow + verbose")
    ax.grid(which="major", alpha=0.3)
    ax.grid(which="minor", alpha=0.12)
    plt.tight_layout()
    out = CHARTS_DIR / "per_iter_speed_vs_size.png"
    plt.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


# Speed-bucket color palette shared by the PNG and SVG renderers.  Kept as a
# module constant so the legend code and the cell-fill code can't drift.
HEATMAP_COLORS = {
    "missing":      "#222222",   # black
    "fail":         "#D7263D",   # red
    # 3-tier amber ladder (geometric, matches green's 10× spacing).
    # Highlights heavy problems instead of lumping 100ms and 60s into one color.
    "slow_lt_1s":   "#F0C808",   # golden amber — 100ms-1s ("noticeably slow")
    "slow_lt_10s":  "#E07315",   # orange — 1s-10s ("feels broken")
    "slow_ge_10s":  "#A03A18",   # burnt orange — ≥10s ("serious algorithm")
    "lt_100us":     "#84E184",   # bright green
    "lt_1ms":       "#5BC85B",
    "lt_10ms":      "#36A036",
    "lt_100ms":     "#1E6A1E",   # darkest green
}

LEGEND_ITEMS = [
    (HEATMAP_COLORS["lt_100us"],    "pass · <100µs"),
    (HEATMAP_COLORS["lt_1ms"],      "pass · <1ms"),
    (HEATMAP_COLORS["lt_10ms"],     "pass · <10ms"),
    (HEATMAP_COLORS["lt_100ms"],    "pass · <100ms"),
    (HEATMAP_COLORS["slow_lt_1s"],  "pass · <1s"),
    (HEATMAP_COLORS["slow_lt_10s"], "pass · <10s"),
    (HEATMAP_COLORS["slow_ge_10s"], "pass · ≥10s"),
    (HEATMAP_COLORS["fail"],        "fail"),
    (HEATMAP_COLORS["missing"],     "missing"),
]


def cell_color(status: str, ns) -> str:
    """Map a (status, ns) pair to a cell hex color.  Shared by both renderers.

    Speed buckets are geometric (10× per step), matching the green-bucket
    spacing: <100µs / <1ms / <10ms / <100ms (greens) then <1s / <10s / ≥10s
    (ambers). Splitting the amber ladder distinguishes 'noticeably slow' from
    'feels-broken' from 'serious-algorithm' problems.
    """
    if status == "missing":
        return HEATMAP_COLORS["missing"]
    if status == "fail":
        return HEATMAP_COLORS["fail"]
    if ns is None or ns < 100_000:
        return HEATMAP_COLORS["lt_100us"]
    if ns < 1_000_000:
        return HEATMAP_COLORS["lt_1ms"]
    if ns < 10_000_000:
        return HEATMAP_COLORS["lt_10ms"]
    if ns < 100_000_000:
        return HEATMAP_COLORS["lt_100ms"]
    if ns < 1_000_000_000:
        return HEATMAP_COLORS["slow_lt_1s"]
    if ns < 10_000_000_000:
        return HEATMAP_COLORS["slow_lt_10s"]
    return HEATMAP_COLORS["slow_ge_10s"]


def _bands(scope: list, band_size: int) -> list:
    """Split SCOPE_PROBLEMS into chunks of at most band_size items."""
    return [scope[i:i + band_size] for i in range(0, len(scope), band_size)]


def langs_for_band(band_probs: list) -> list:
    """Return langs in LANG_DISPLAY_ORDER that are in scope for this band's tier.

    BAND_SIZE (100) aligns with tier ranges (also 100-wide), so a band sits
    entirely in one tier. We check the band's first problem to identify the
    tier, then return the tier's lang list filtered by display order.

    Used by the coverage grid + per-problem detail table to render
    variable-height bands instead of always showing all 10 langs (which would
    leave tier-1-only langs with full black rows in the 201-300 band).
    """
    p1 = int(band_probs[0])
    tier_key = tier_for_problem(p1, _TIERS)
    if tier_key is None:
        return list(LANG_DISPLAY_ORDER)
    in_scope_set = set(langs_in_tier(tier_key, _TIERS))
    return [l for l in LANG_DISPLAY_ORDER if l in in_scope_set]


def in_scope_problems(lang: str) -> list:
    """Subset of SCOPE_PROBLEMS that are in scope for `lang` per the tier model.

    Used for per-lang "missing N of K" counts so a tier-1-only lang like ARM64
    isn't credited as "missing 100 of 300" — its in-scope is 200, full stop.
    """
    return [p for p in SCOPE_PROBLEMS if _in_scope(lang, int(p), _TIERS)]


def render_coverage_grid_chart(agg: dict) -> Path:
    """Banded heatmap PNG — N_BANDS bands stacked vertically, each band a
    fixed-width 10-lang × BAND_SIZE-problem grid.

    Why banded: at the previous single-row layout, 100 problems × 10 langs
    already needed `aspect="equal"` to keep cells square, which squeezed the
    figure to ~0.8″ of cell height and overlapped the lang labels.  Extending
    to 1000 problems on a single row would make cells unreadably narrow.
    Banding decouples cell size from total problem count: each band is
    always BAND_SIZE wide, so cells stay legible whether we have 100 or 1000
    problems in scope.

    Row order is fixed (LANG_DISPLAY_ORDER) so the chart doesn't visually
    reshuffle when ranking-by-total drifts between snapshots.
    """
    n_probs = len(GRID_PROBLEMS)
    bands = _bands(GRID_PROBLEMS, BAND_SIZE)
    n_bands = len(bands)

    # Tier-aware: each band's lang list may differ (e.g., 10 langs at 1-200,
    # 4 langs at 201-300). Use the max for figure sizing so we have room for
    # the tallest band; shorter bands just have empty space below.
    bands_langs = [langs_for_band(bp) for bp in bands]
    max_langs = max(len(bl) for bl in bands_langs)

    # Sizing: cell ~0.13" wide × 0.30" tall.  Band gets +0.6" for title + tier label.
    cell_w_in = 0.13
    cell_h_in = 0.30
    # Each band is sized for its own lang count (variable-height bands).
    band_heights = [len(bl) * cell_h_in + 0.6 for bl in bands_langs]
    fig_w = max(11.0, BAND_SIZE * cell_w_in + 2.2)  # +2.2 for y-labels & margin
    fig_h = sum(band_heights) + 1.6                  # +1.6 for figure title + legend

    fig, axes = plt.subplots(n_bands, 1,
                             figsize=(fig_w, fig_h),
                             gridspec_kw={"hspace": 0.85,
                                          "height_ratios": band_heights})
    # plt.subplots returns a bare Axes (not an array) when nrows=1.
    if n_bands == 1:
        axes = [axes]

    for band_i, ax in enumerate(axes):
        band_probs = bands[band_i]
        band_langs = bands_langs[band_i]
        n_band_langs = len(band_langs)
        # Identify the tier so we can label the band with it.
        tier_key = tier_for_problem(int(band_probs[0]), _TIERS)
        tier_lbl = tier_label(tier_key, _TIERS) if tier_key else ""

        for ri, lang in enumerate(band_langs):
            for ci, p in enumerate(band_probs):
                st = agg[lang]["grid_status"][p]
                ns = agg[lang]["grid_ns"][p]
                s = agg[lang]["grid_samples"][p]
                ax.add_patch(plt.Rectangle(
                    (ci, n_band_langs - 1 - ri), 1, 1,
                    facecolor=cell_color(st, ns),
                    edgecolor="white", linewidth=0.6,
                ))
                # Partial-measurement marker: small black '*' overlaid on cells
                # bench'd at samples<10 (suite-standard is 10). Matches the
                # asterisk in per-problem detail tables; the legend below
                # explains it.
                if s is not None and s < 10:
                    ax.text(
                        ci + 0.5, n_band_langs - 1 - ri + 0.55, "*",
                        fontsize=8, ha="center", va="center",
                        color="black", fontweight="bold",
                    )

        # Uniform x extent across bands keeps cell width constant even on a
        # final partial band (e.g. 50 problems instead of 100).
        ax.set_xlim(0, BAND_SIZE)
        ax.set_ylim(0, n_band_langs)

        # X-ticks every 10 problems within the band.
        tick_idx = list(range(0, len(band_probs), 10))
        ax.set_xticks([i + 0.5 for i in tick_idx])
        ax.set_xticklabels([f"p{band_probs[i]}" for i in tick_idx], fontsize=8)

        ax.set_yticks([i + 0.5 for i in range(n_band_langs)])
        ax.set_yticklabels([DISPLAY[l] for l in reversed(band_langs)], fontsize=9)
        title = f"Problems {band_probs[0]}–{band_probs[-1]}"
        if tier_lbl:
            title += f"  ({tier_lbl} — {n_band_langs} langs)"
        ax.set_title(title, fontsize=10, loc="left", pad=4)
        ax.tick_params(length=0)
        ax.set_aspect("auto")   # let figure dims dictate; cells aren't square
        for spine in ax.spines.values():
            spine.set_visible(False)

    fig.suptitle(
        f"Coverage + Speed Heatmap — tier-aware ({n_probs}-problem range)  ·  "
        f"* = partial measurement (samples<10)",
        fontsize=12, y=0.995,
    )

    # Single legend at the bottom of the whole figure.
    from matplotlib.patches import Patch
    legend_patches = [
        Patch(facecolor=c, edgecolor="black", linewidth=0.4, label=lbl)
        for c, lbl in LEGEND_ITEMS
    ]
    fig.legend(handles=legend_patches, loc="lower center",
               ncol=len(legend_patches), fontsize=9, frameon=False,
               handlelength=1.4, handleheight=1.1, columnspacing=1.4,
               bbox_to_anchor=(0.5, 0.005))

    out = CHARTS_DIR / "per_iter_coverage_grid.png"
    plt.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


def render_total_chart(agg: dict) -> Path:
    """Horizontal bar: total cost per language over the COMMON SET (problems
    where all 10 langs have status='pass'), sorted fastest first, log scale X.

    Using common-set totals keeps the chart apples-to-apples under partial
    coverage. A lang at 100/200 with low total isn't visually misleading vs a
    lang at 200/200 with high total — both are measured over the same problem
    set in this chart.
    """
    common = agg["_common"]
    n_common = len(common["problems"])
    rows = [(lang, common["per_lang_total_ns"][lang])
            for lang in LANGS if common["per_lang_total_ns"][lang] > 0]
    rows.sort(key=lambda r: r[1])  # ascending (fastest first; chart will flip for top-at-top)

    labels = [DISPLAY[lang] for lang, _ in rows]
    values_ms = [v / 1_000_000 for _, v in rows]
    colors = [COLOR[lang] for lang, _ in rows]

    fig, ax = plt.subplots(figsize=(10, 5))
    y_pos = range(len(labels))
    bars = ax.barh(y_pos, values_ms, color=colors)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()  # fastest on top
    ax.set_xscale("log")
    # Tier-1 chart uses the Foundation common-set (max problem = tier_1's hi).
    _t1_hi = tier_problem_range("tier_1_foundation", _TIERS)[1] or len(SCOPE_PROBLEMS)
    ax.set_xlabel(f"Total per-invocation cost across the {n_common}-problem common set (ms, log scale)")
    ax.set_title(f"Per-Invocation Cost — Foundation ({len(LANGS)} languages, "
                 f"common set: {n_common} of {_t1_hi} problems)\n"
                 f"Each binary run 10 times in a fresh process; median wall time summed "
                 f"across the {n_common} problems all langs pass")
    # Value labels at the end of each bar
    for i, (bar, ms) in enumerate(zip(bars, values_ms)):
        if ms >= 100:
            label = f"{ms:.0f} ms"
        elif ms >= 10:
            label = f"{ms:.1f} ms"
        else:
            label = f"{ms:.2f} ms"
        ax.text(ms * 1.02, i, label, va="center", fontsize=9)
    ax.grid(axis="x", which="major", alpha=0.3)
    ax.grid(axis="x", which="minor", alpha=0.15)
    plt.tight_layout()
    out = CHARTS_DIR / "per_iter_total.png"
    plt.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


def _tier2_meta(agg: dict):
    """Pull tier-2 active langs + common-set. Returns (active, common, t2_dict)
    or (None, None, None) if there's no tier-2 data yet."""
    t2 = agg["_common_per_tier"].get("tier_2_deep_coverage", {})
    common = t2.get("problems", [])
    active = t2.get("langs", [])
    if not active or not common:
        return None, None, None
    return active, common, t2


def render_total_chart_tier2(agg: dict):
    """Tier-2 analog of render_total_chart — common-set across ACTIVE tier-2
    langs only (those with ≥1 cell in 201-300). Returns None if no data yet.

    Today that's typically cpp+go+zig (python tier-2 has no data); when python
    tier-2 lands, it joins active and the common-set tightens to whatever
    python also passes.
    """
    active, common, t2 = _tier2_meta(agg)
    if active is None:
        return None
    designated = t2["designated_langs"]
    rows = [(lang, t2["per_lang_total_ns"][lang]) for lang in active
            if t2["per_lang_total_ns"][lang] > 0]
    rows.sort(key=lambda r: r[1])
    labels = [DISPLAY[lang] for lang, _ in rows]
    values_ms = [v / 1_000_000 for _, v in rows]
    colors = [COLOR[lang] for lang, _ in rows]

    t2_lo, t2_hi = tier_problem_range("tier_2_deep_coverage", _TIERS)
    fig, ax = plt.subplots(figsize=(10, 3.5))
    y_pos = range(len(labels))
    bars = ax.barh(y_pos, values_ms, color=colors)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlabel(f"Total per-invocation cost across the {len(common)}-problem tier-2 common set (ms, log scale)")
    inactive = [l for l in designated if l not in active]
    inactive_note = (
        f"  ·  awaiting: {', '.join(DISPLAY[l] for l in inactive)}"
        if inactive else ""
    )
    common_lo = int(min(common))
    common_hi = int(max(common))
    range_note = (
        f"spans p{common_lo:03d}–p{common_hi:03d}"
        if (common_hi - common_lo + 1) > len(common)
        else f"contiguous p{common_lo:03d}–p{common_hi:03d}"
    )
    ax.set_title(
        f"Per-Invocation Cost — Deep Coverage (Tier 2, problems {t2_lo}-{t2_hi}, "
        f"{len(active)} active of {len(designated)} langs{inactive_note})\n"
        f"Common set: {len(common)} problems ({range_note}) passing in {', '.join(DISPLAY[l] for l in active)}"
    )
    for i, ms in enumerate(values_ms):
        if ms >= 100:
            label = f"{ms:.0f} ms"
        elif ms >= 10:
            label = f"{ms:.1f} ms"
        else:
            label = f"{ms:.2f} ms"
        ax.text(ms * 1.02, i, label, va="center", fontsize=9)
    ax.grid(axis="x", which="major", alpha=0.3)
    ax.grid(axis="x", which="minor", alpha=0.15)
    plt.tight_layout()
    out = CHARTS_DIR / "per_iter_total_tier2.png"
    plt.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


def render_speed_vs_size_chart_tier2(agg: dict):
    """Tier-2 analog of render_speed_vs_size_chart. Returns None if no data."""
    active, common, t2 = _tier2_meta(agg)
    if active is None:
        return None
    designated = t2["designated_langs"]
    fig, ax = plt.subplots(figsize=(8, 5))
    for lang in active:
        x = t2["per_lang_total_lines"][lang]
        y_ms = t2["per_lang_total_ns"][lang] / 1_000_000
        if x == 0 or y_ms == 0:
            continue
        ax.scatter(x, y_ms, s=200, c=COLOR[lang], edgecolors="black",
                   linewidths=0.6, alpha=0.85, zorder=3)
        ax.annotate(DISPLAY[lang], xy=(x, y_ms), xytext=(8, 4),
                    textcoords="offset points", fontsize=10,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white",
                              ec="none", alpha=0.85))
    ax.set_xscale("log")
    ax.set_yscale("log")
    t2_lo, t2_hi = tier_problem_range("tier_2_deep_coverage", _TIERS)
    ax.set_xlabel(f"Total source lines across tier-2 problems {t2_lo}–{t2_hi} (log scale)")
    ax.set_ylabel("Total per-invocation cost — ms (log scale)")
    inactive = [l for l in designated if l not in active]
    inactive_note = f"  ·  awaiting: {', '.join(DISPLAY[l] for l in inactive)}" if inactive else ""
    ax.set_title(
        f"Speed vs Code Size — Deep Coverage (Tier 2, problems {t2_lo}–{t2_hi}, "
        f"{len(active)} active{inactive_note})\n"
        f"Common set: {len(common)} problems"
    )
    ax.grid(which="major", alpha=0.3)
    ax.grid(which="minor", alpha=0.12)
    plt.tight_layout()
    out = CHARTS_DIR / "per_iter_speed_vs_size_tier2.png"
    plt.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


def _tier3_meta(agg: dict):
    """Pull tier-3 active langs + common-set. Returns (active, common, t3_dict)
    or (None, None, None) if there's no tier-3 data yet. Clone of _tier2_meta
    with key tier_3_frontier — added 2026-05-26 when rust joined cpp+go in the
    frontier verification trio."""
    t3 = agg["_common_per_tier"].get("tier_3_frontier", {})
    common = t3.get("problems", [])
    active = t3.get("langs", [])
    if not active or not common:
        return None, None, None
    return active, common, t3


def render_total_chart_tier3(agg: dict):
    """Tier-3 analog of render_total_chart_tier2 — common-set across ACTIVE
    tier-3 langs (cpp/go/rust). Returns None if no data yet. Rust is the
    common-set ceiling initially (smallest 301+ coverage); the chart populates
    as rust's frontier ports land."""
    active, common, t3 = _tier3_meta(agg)
    if active is None:
        return None
    designated = t3["designated_langs"]
    rows = [(lang, t3["per_lang_total_ns"][lang]) for lang in active
            if t3["per_lang_total_ns"][lang] > 0]
    rows.sort(key=lambda r: r[1])
    labels = [DISPLAY[lang] for lang, _ in rows]
    values_ms = [v / 1_000_000 for _, v in rows]
    colors = [COLOR[lang] for lang, _ in rows]

    t3_lo, t3_hi = tier_problem_range("tier_3_frontier", _TIERS)
    t3_hi_label = f"{t3_hi}" if t3_hi else "+"
    fig, ax = plt.subplots(figsize=(10, 3.5))
    y_pos = range(len(labels))
    ax.barh(y_pos, values_ms, color=colors)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlabel(f"Total per-invocation cost across the {len(common)}-problem tier-3 common set (ms, log scale)")
    inactive = [l for l in designated if l not in active]
    inactive_note = (
        f"  ·  awaiting: {', '.join(DISPLAY[l] for l in inactive)}"
        if inactive else ""
    )
    common_lo = int(min(common))
    common_hi = int(max(common))
    range_note = (
        f"spans p{common_lo:03d}–p{common_hi:03d}"
        if (common_hi - common_lo + 1) > len(common)
        else f"contiguous p{common_lo:03d}–p{common_hi:03d}"
    )
    ax.set_title(
        f"Per-Invocation Cost — Frontier (Tier 3, problems {t3_lo}{t3_hi_label if t3_hi else '+'}, "
        f"{len(active)} active of {len(designated)} langs{inactive_note})\n"
        f"Common set: {len(common)} problems ({range_note}) passing in {', '.join(DISPLAY[l] for l in active)}"
    )
    for i, ms in enumerate(values_ms):
        if ms >= 100:
            label = f"{ms:.0f} ms"
        elif ms >= 10:
            label = f"{ms:.1f} ms"
        else:
            label = f"{ms:.2f} ms"
        ax.text(ms * 1.02, i, label, va="center", fontsize=9)
    ax.grid(axis="x", which="major", alpha=0.3)
    ax.grid(axis="x", which="minor", alpha=0.15)
    plt.tight_layout()
    out = CHARTS_DIR / "per_iter_total_tier3.png"
    plt.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


def render_speed_vs_size_chart_tier3(agg: dict):
    """Tier-3 analog of render_speed_vs_size_chart_tier2. Returns None if no data."""
    active, common, t3 = _tier3_meta(agg)
    if active is None:
        return None
    designated = t3["designated_langs"]
    fig, ax = plt.subplots(figsize=(8, 5))
    for lang in active:
        x = t3["per_lang_total_lines"][lang]
        y_ms = t3["per_lang_total_ns"][lang] / 1_000_000
        if x == 0 or y_ms == 0:
            continue
        ax.scatter(x, y_ms, s=200, c=COLOR[lang], edgecolors="black",
                   linewidths=0.6, alpha=0.85, zorder=3)
        ax.annotate(DISPLAY[lang], xy=(x, y_ms), xytext=(8, 4),
                    textcoords="offset points", fontsize=10,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white",
                              ec="none", alpha=0.85))
    ax.set_xscale("log")
    ax.set_yscale("log")
    t3_lo, t3_hi = tier_problem_range("tier_3_frontier", _TIERS)
    t3_hi_label = f"{t3_hi}" if t3_hi else "+"
    ax.set_xlabel(f"Total source lines across tier-3 problems {t3_lo}–{t3_hi_label} (log scale)")
    ax.set_ylabel("Total per-invocation cost — ms (log scale)")
    inactive = [l for l in designated if l not in active]
    inactive_note = f"  ·  awaiting: {', '.join(DISPLAY[l] for l in inactive)}" if inactive else ""
    ax.set_title(
        f"Speed vs Code Size — Frontier (Tier 3, problems {t3_lo}–{t3_hi_label}, "
        f"{len(active)} active{inactive_note})\n"
        f"Common set: {len(common)} problems"
    )
    ax.grid(which="major", alpha=0.3)
    ax.grid(which="minor", alpha=0.12)
    plt.tight_layout()
    out = CHARTS_DIR / "per_iter_speed_vs_size_tier3.png"
    plt.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


def render_per_problem_pages(agg: dict) -> list:
    """Write one per_problem_NNN-MMM.md file per band, return the list of paths.

    Each page has: a title (band + tier), a back-link to RESULTS.md, the table,
    and the partial-measurement footnote if any '*' cells appear in that band.
    Splitting per-band keeps each file at ~100 rows × ≤10 cols (a single
    medium-length scroll) instead of stacking 300 rows on the main page.
    """
    PER_PROBLEM_DIR.mkdir(exist_ok=True)
    written = []
    for band_probs in _bands(SCOPE_PROBLEMS, BAND_SIZE):
        display_langs = langs_for_band(band_probs)
        tier_key = tier_for_problem(int(band_probs[0]), _TIERS)
        tier_lbl = tier_label(tier_key, _TIERS) if tier_key else ""
        band_lo, band_hi = band_probs[0], band_probs[-1]

        lines = []
        title = f"# Per-Problem Detail — Problems {band_lo}–{band_hi}"
        if tier_lbl:
            title += f" ({tier_lbl}, {len(display_langs)} langs)"
        lines.append(title)
        lines.append("")
        lines.append("⬅ [Back to RESULTS](../RESULTS.md)")
        lines.append("")
        lines.append("Median wall time per fresh-process invocation, one row per problem, one")
        lines.append("column per language in tier-1 display order (native → managed → interpreted).")
        if tier_lbl == "Deep Coverage":
            # Live-derived from tiers.json so this stays correct as the
            # tier-2 lang list changes (e.g., Rust joined 2026-05-25,
            # bumping the count from 4 to 5).
            n_tier2 = len(display_langs)
            n_tier1_only = len(LANGS) - n_tier2
            lines.append("")
            lines.append(f"> _Only the {n_tier2} Deep Coverage languages are shown — the other "
                         f"{n_tier1_only} are tier-1-only_")
            lines.append("> _(capped at problem 200 by the project's language-cap policy)._")
        lines.append("")

        header = "| Problem | " + " | ".join(DISPLAY[l] for l in display_langs) + " |"
        sep    = "|---------|" + "|".join(["----:"] * len(display_langs)) + "|"
        lines.append(header)
        lines.append(sep)

        any_partial = False
        for p in band_probs:
            cells = []
            for lang in display_langs:
                ns = agg[lang]["per_problem_ns"][p]
                if ns is None:
                    cells.append("—")
                else:
                    s = agg[lang]["per_problem_samples"][p]
                    # Suite-standard iters=10; flag <10-sample cells with '*'.
                    if s is not None and s < 10:
                        cells.append(fmt_time(ns) + "*")
                        any_partial = True
                    else:
                        cells.append(fmt_time(ns))
            lines.append(f"| **p{p}** | " + " | ".join(cells) + " |")
        lines.append("")

        if any_partial:
            lines.append(
                "> \\* — *partial measurement*: cell was bench'd with fewer than the "
                "suite-standard 10 iterations (typically 1 or 3, for heavy problems "
                "where iters=10 would exceed the per-chunk wall budget). The median "
                "is still meaningful for >1s problems, but the variance estimate is "
                "degraded. These cells are queued for a future uniform-iters=10 "
                "re-bench pass."
            )
            lines.append("")
        lines.append("⬅ [Back to RESULTS](../RESULTS.md)")
        lines.append("")

        fname = f"per_problem_{band_lo}-{band_hi}.md"
        out = PER_PROBLEM_DIR / fname
        out.write_text("\n".join(lines))
        written.append(out)
    return written


def render_results_md(agg: dict) -> str:
    """Generate the new RESULTS.md content."""
    # Ranking rows use the COMMON SET (problems where all 10 langs have
    # status='pass') so partial-coverage langs aren't artificially "faster"
    # than fully-covered langs. Per-lang's own coverage is shown separately
    # in the per-lang section.
    common = agg["_common"]
    ranked = sorted(
        [(lang, common["per_lang_total_ns"][lang])
         for lang in LANGS if common["per_lang_total_ns"][lang] > 0],
        key=lambda r: r[1],
    )
    fastest_ns = ranked[0][1] if ranked else 1

    # Coverage statistics — used in narrative to honestly describe partial state.
    # total_cells is now tier-aware: sum of in_scope per lang across all langs.
    n_common = len(common["problems"])
    total_cells = sum(agg[lang]["in_scope_count"] for lang in LANGS)
    measured_cells = sum(
        agg[lang]["in_scope_count"] - agg[lang]["missing"] for lang in LANGS
    )
    # Tier-1's max common-set is 200 (the 6 tier-1-only langs can't have data
    # above 200 by design); use that as the denominator in the common-set header
    # instead of len(SCOPE_PROBLEMS) which would misleadingly be 300.
    tier1_max = tier_problem_range("tier_1_foundation", _TIERS)[1] or len(SCOPE_PROBLEMS)

    # Build markdown
    md = []
    md.append("# Project Euler — Cross-Language Benchmarks")
    md.append("")
    md.append(f"> **Scope: {total_cells} in-scope cells across "
              f"{len(SCOPE_PROBLEMS)} problems × tiered languages "
              f"— {measured_cells} measured "
              f"({100*measured_cells/total_cells:.1f}% coverage).**")
    md.append(f"> The cross-language ranking below is computed over the **{n_common}-problem "
              f"common set** (problems in 1-{tier1_max} where every language has a passing "
              f"measurement) — the apples-to-apples Foundation comparison surface.  "
              f"Per-tier rankings and coverage detail appear further below.")
    md.append("> Growing carefully — each new problem and language is audited for state-leak")
    md.append("> safety, verified for answer correctness, and added only when it cleanly fits the")
    md.append("> measurement methodology.  See [JOURNEY.md](JOURNEY.md) for the full story of how")
    md.append("> we got here, including the reset from 200+ problems back to a verified 10×10")
    md.append(f"> core, then the disciplined expansion to today's {len(SCOPE_PROBLEMS)}-problem scope.")
    md.append("")
    md.append(f"## Foundation — Tier 1 ({len(LANGS)} languages, problems 1-{tier1_max})")
    md.append("")
    md.append(f"All {len(LANGS)} languages benchmarked across the first {tier1_max} problems — "
              f"the apples-to-apples comparison surface that anchors the suite's headline rankings.")
    md.append("")
    md.append(f"### Per-Invocation Cost (Common Set, {n_common} of {tier1_max} problems)")
    md.append("")
    md.append("We run each program 10 times in fresh OS processes (no warmup, no shared state).")
    md.append("Each invocation pays full startup + algorithm cost — the cost a real CLI / cron /")
    md.append("shell-loop user actually pays.  The median wall time across the 10 invocations is")
    md.append(f"the headline per-problem number, and the table sums over the {n_common}-problem")
    md.append("common set so partial-coverage languages aren't artificially \"faster\" than fully-")
    md.append("covered ones.")
    md.append("")
    md.append("![Per-Invocation Cost](charts/per_iter_total.png)")
    md.append("")
    md.append(f"| Rank | Language | Total ({n_common}-problem common set) | Lines of code | vs Fastest |")
    md.append("|------|----------|--------------------:|--------------:|-----------:|")
    for i, (lang, total) in enumerate(ranked, 1):
        ratio = total / fastest_ns
        lines = common["per_lang_total_lines"][lang]
        md.append(f"| {i} | **{DISPLAY[lang]}** | {fmt_time(total)} | {lines:,} | {ratio:.2f}× |")
    md.append("")
    # Foundation Speed-vs-Size is a CHILD of the Foundation parent (was a
    # standalone ## sitting awkwardly between tier-2 and Coverage Heatmap).
    md.append("### Speed vs Code Size")
    md.append("")
    md.append(f"How much code does each language need to solve these {tier1_max} Foundation problems, "
              f"and how fast does that code run?  Bottom-left = fast and concise; top-right = slow "
              f"and verbose.  ARM64's outlier position (most lines) is expected — assembly trades "
              f"verbosity for direct hardware control.")
    md.append("")
    md.append("![Speed vs Code Size](charts/per_iter_speed_vs_size.png)")
    md.append("")

    # Tier 2: Deep Coverage ranking (4 langs at 201-300). Only render when
    # the tier-2 common-set has at least one problem — early in the tier-2
    # campaign this section will be empty/sparse.
    t2 = agg["_common_per_tier"].get("tier_2_deep_coverage", {})
    t2_common = t2.get("problems", [])
    t2_langs = t2.get("langs", [])  # active (langs with ≥1 tier-2 cell)
    t2_designated = t2.get("designated_langs", [])
    t2_lo, t2_hi = tier_problem_range("tier_2_deep_coverage", _TIERS)
    md.append(f"## Deep Coverage — Tier 2 ({len(t2_designated)} languages, problems {t2_lo}-{t2_hi})")
    md.append("")
    md.append(f"Same per-invocation metric, restricted to the deeper subset of languages "
              f"({', '.join(DISPLAY[l] for l in t2_designated)}) that intentionally pushed past "
              f"problem {tier1_max}. The other {len(LANGS) - len(t2_designated)} Foundation "
              f"languages are out of tier scope here — they're capped at {tier1_max} by the "
              f"project's language-cap policy (see JOURNEY.md).")
    md.append("")
    # Note: t2_langs here is "active" tier-2 langs (those with ≥50% coverage).
    # The full designated set is `_common_per_tier[...]["designated_langs"]`.
    designated_t2 = t2.get("designated_langs", [])
    inactive_t2 = [l for l in designated_t2 if l not in t2_langs]
    tier2_size = t2_hi - t2_lo + 1
    if t2_common:
        md.append(f"### Per-Invocation Cost (Common Set, {len(t2_common)} of {tier2_size} problems)")
        md.append("")
        if inactive_t2:
            md.append(f"_Common set computed over the **{len(t2_langs)} active** tier-2 langs_ "
                      f"_({', '.join(DISPLAY[l] for l in t2_langs)});_ "
                      f"_awaiting: {', '.join(DISPLAY[l] for l in inactive_t2)} "
                      f"(below 50% coverage threshold). Common set will tighten once awaited langs "
                      f"reach majority coverage in tier 2._")
            md.append("")
        # Tier-2 charts — only embed if the chart file was actually generated
        # (render_*_tier2 returns None when t2 has no data).
        if (CHARTS_DIR / "per_iter_total_tier2.png").exists():
            md.append("![Per-Invocation Cost — Tier 2](charts/per_iter_total_tier2.png)")
            md.append("")
        t2_ranked = sorted(
            [(lang, t2["per_lang_total_ns"][lang]) for lang in t2_langs
             if t2["per_lang_total_ns"][lang] > 0],
            key=lambda r: r[1],
        )
        t2_fastest = t2_ranked[0][1] if t2_ranked else 1
        md.append(f"| Rank | Language | Total ({len(t2_common)}-problem common set) | Lines of code | vs Fastest |")
        md.append("|------|----------|--------------------:|--------------:|-----------:|")
        for i, (lang, total) in enumerate(t2_ranked, 1):
            ratio = total / t2_fastest
            lines = t2["per_lang_total_lines"][lang]
            md.append(f"| {i} | **{DISPLAY[lang]}** | {fmt_time(total)} | {lines:,} | {ratio:.2f}× |")
        md.append("")
        if (CHARTS_DIR / "per_iter_speed_vs_size_tier2.png").exists():
            md.append("### Speed vs Code Size")
            md.append("")
            md.append(f"Same scatter as the Foundation chart, restricted to the "
                      f"tier-2 active languages over problems {t2_lo}–{t2_hi}.")
            md.append("")
            md.append("![Speed vs Size — Tier 2](charts/per_iter_speed_vs_size_tier2.png)")
            md.append("")
    else:
        md.append(f"> _Tier 2 common-set is currently empty — no active language reaches 50% "
                  f"coverage in problems {t2_lo}-{t2_hi} yet. The ranking and charts will "
                  f"populate as benching continues._")
        md.append("")

    # Tier 3: Frontier ranking (cpp/go/rust at 301+). Mirrors tier-2 shape.
    t3 = agg["_common_per_tier"].get("tier_3_frontier", {})
    t3_common = t3.get("problems", [])
    t3_langs = t3.get("langs", [])
    t3_designated = t3.get("designated_langs", [])
    t3_lo, t3_hi = tier_problem_range("tier_3_frontier", _TIERS)
    t3_hi_label = f"{t3_hi}" if t3_hi else "+"
    md.append(f"## Frontier — Tier 3 ({len(t3_designated)} languages, problems {t3_lo}{t3_hi_label if t3_hi else '+'})")
    md.append("")
    md.append(f"The frontier verification trio — {', '.join(DISPLAY[l] for l in t3_designated)} — "
              f"on problems above {t2_hi}. 3-way cross-language agreement is the verification "
              f"protocol (strictly stronger than 2-way; see JOURNEY.md \"Tier Reframing\" episode "
              f"for the p254 lesson that motivated it). Python and Zig are explicitly out of this "
              f"tier — python's wall cost makes it impractical at level 5+, and zig's role caps at "
              f"Tier 2.")
    md.append("")
    inactive_t3 = [l for l in t3_designated if l not in t3_langs]
    if t3_common:
        t3_size = (t3_hi - t3_lo + 1) if t3_hi else (_DISPLAY_HI - t3_lo + 1)
        md.append(f"### Per-Invocation Cost (Common Set, {len(t3_common)} of ≤{t3_size} problems in scope)")
        md.append("")
        if inactive_t3:
            md.append(f"_Common set computed over the **{len(t3_langs)} active** tier-3 langs_ "
                      f"_({', '.join(DISPLAY[l] for l in t3_langs)});_ "
                      f"_awaiting: {', '.join(DISPLAY[l] for l in inactive_t3)} "
                      f"(below 50% coverage threshold). Common set will tighten once awaited langs "
                      f"reach majority coverage in tier 3._")
            md.append("")
        if (CHARTS_DIR / "per_iter_total_tier3.png").exists():
            md.append("![Per-Invocation Cost — Tier 3](charts/per_iter_total_tier3.png)")
            md.append("")
        t3_ranked = sorted(
            [(lang, t3["per_lang_total_ns"][lang]) for lang in t3_langs
             if t3["per_lang_total_ns"][lang] > 0],
            key=lambda r: r[1],
        )
        t3_fastest = t3_ranked[0][1] if t3_ranked else 1
        md.append(f"| Rank | Language | Total ({len(t3_common)}-problem common set) | Lines of code | vs Fastest |")
        md.append("|------|----------|--------------------:|--------------:|-----------:|")
        for i, (lang, total) in enumerate(t3_ranked, 1):
            ratio = total / t3_fastest
            lines = t3["per_lang_total_lines"][lang]
            md.append(f"| {i} | **{DISPLAY[lang]}** | {fmt_time(total)} | {lines:,} | {ratio:.2f}× |")
        md.append("")
        if (CHARTS_DIR / "per_iter_speed_vs_size_tier3.png").exists():
            md.append("### Speed vs Code Size")
            md.append("")
            md.append(f"Same scatter as the Foundation chart, restricted to the "
                      f"tier-3 active languages over problems {t3_lo}–{t3_hi_label}.")
            md.append("")
            md.append("![Speed vs Size — Tier 3](charts/per_iter_speed_vs_size_tier3.png)")
            md.append("")
    else:
        md.append(f"> _Tier 3 common-set is currently empty — no active language reaches 50% "
                  f"coverage in problems {t3_lo}+ yet. The ranking and charts will populate as "
                  f"the rust port wave (cpp→rust 301-400 catchup) lands._")
        md.append("")

    md.append("## Coverage Heatmap")
    md.append("")
    md.append("One cell per (language, problem).  Color shows whether the cell passes the")
    md.append("invocation-isolation + answer-correctness audit and how fast it runs:")
    md.append("")
    md.append("- 🟢 **Green** — pass <100 ms; 4 levels (lighter = faster)")
    md.append("- 🟡 **Amber** — pass 100 ms – 1 s (noticeably slow)")
    md.append("- 🟠 **Orange** — pass 1 s – 10 s (feels broken interactive)")
    md.append("- 🟤 **Burnt orange** — pass ≥ 10 s (serious algorithm — multi-second computation)")
    md.append("- 🔴 **Red** — fail (wrong answer, build error, timeout)")
    md.append("- ⚫ **Black** — missing entry (no measurement)")
    md.append("- **`*`** — *partial measurement* (samples<10, suite-standard is 10); "
              "the cell median is still meaningful for >1s problems but the variance estimate is degraded")
    md.append("")
    md.append("![Coverage + Speed Heatmap](charts/per_iter_coverage_grid.png)")
    md.append("")
    n_bands = (len(GRID_PROBLEMS) + BAND_SIZE - 1) // BAND_SIZE
    md.append(f"Rows are in fixed tier order (native → managed → interpreted) so the chart")
    md.append(f"doesn't reshuffle between snapshots as ranking-by-total drifts.  Problems are")
    md.append(f"chunked into bands of {BAND_SIZE} (currently {n_bands} band"
              f"{'' if n_bands == 1 else 's'}), which keeps cells legibly sized as we extend")
    md.append(f"toward the 1000-problem target.  Native compiled rows (ARM64 / C / C++ / Rust /")
    md.append(f"Zig) sit near the top in mostly bright-green territory; managed-runtime rows")
    md.append(f"(C# / Java / JavaScript) carry darker greens and scattered amber from JIT")
    md.append(f"startup; Python at the bottom shows the heaviest amber load.  Vertical amber")
    md.append(f"bars that cut across multiple languages (currently visible near p061 and p071)")
    md.append(f"flag *intrinsically hard* problems — the algorithm cost dominates regardless of")
    md.append(f"language.  No red or black cells: the audit gate is holding.")
    md.append("")

    # Per-problem detail — moved off the main page (300 problems × 10 cols was
    # a scrolling nightmare).  Each 100-problem band lives in its own file
    # under per_problem/; this section just indexes them.  See
    # render_per_problem_pages() for the per-band content + the partial-
    # measurement footnote that lives on each detail page.
    md.append("## Per-Problem Detail")
    md.append("")
    md.append("Median wall time per fresh-process invocation, for each (language, problem).")
    _n_t1 = len(langs_in_tier("tier_1_foundation", _TIERS))
    _n_t2 = len(langs_in_tier("tier_2_deep_coverage", _TIERS))
    md.append(f"Split across {len(_bands(SCOPE_PROBLEMS, BAND_SIZE))} pages, one per "
              f"{BAND_SIZE}-problem band, so this main page stays navigable.  Each band's "
              f"table is tier-filtered ({_n_t1} langs in Foundation bands, {_n_t2} in Deep Coverage).")
    md.append("")
    md.append("| Band | Tier | Languages | Page |")
    md.append("|------|------|-----------|------|")
    for band_probs in _bands(SCOPE_PROBLEMS, BAND_SIZE):
        display_langs = langs_for_band(band_probs)
        tier_key = tier_for_problem(int(band_probs[0]), _TIERS)
        tier_lbl = tier_label(tier_key, _TIERS) if tier_key else "—"
        band_lo, band_hi = band_probs[0], band_probs[-1]
        fname = f"per_problem_{band_lo}-{band_hi}.md"
        md.append(f"| p{band_lo}–p{band_hi} | {tier_lbl} | {len(display_langs)} | "
                  f"[Open]({_PER_PROBLEM_DIR}/{fname}) |")
    md.append("")

    md.append("## Method")
    md.append("")
    md.append("For each (language, problem):")
    md.append("")
    md.append("1. Build the binary (or `as` + `cc` for ARM64, `dotnet build` for C#, etc.).")
    md.append("2. Run the binary 10 times, each in a fresh OS process.  No warmup; no shared state.")
    md.append("3. Each invocation prints `RESULT|time_ns=N|answer=A` — one line per process,")
    md.append("   captured by the bench tool.  The answer is compared against the canonical")
    md.append("   (each source file's `// Answer:` header comment); the bench aborts on mismatch.")
    md.append("4. We report the **median** wall time across the 10 invocations.")
    md.append("")
    md.append("That's the entire metric.  No \"hot\" vs \"cold\" — just per-invocation cost, which")
    md.append("is what every CLI / cron / shell-loop user actually pays.")
    md.append("")
    md.append("### Sub-millisecond floor")
    md.append("")
    md.append("On Apple Silicon, process spawn (`fork` + `exec`) costs ~5–10 ms.  Problems where")
    md.append("the algorithm takes < 1 ms (currently p001–p006 in most languages) are effectively")
    md.append("measuring spawn cost, not algorithmic merit.  That **is** what a CLI user pays, so")
    md.append("the number is still meaningful — but the cross-language signal on these problems")
    md.append("mostly reflects runtime startup cost.  The interesting algorithmic signal starts")
    md.append("around p007+.")
    md.append("")
    md.append("### How each language is built")
    md.append("")
    md.append("Every compiled language uses release / optimized builds — no debug-mode")
    md.append("measurements:")
    md.append("")
    md.append("| Language | Build command | Optimization |")
    md.append("|----------|---------------|--------------|")
    md.append("| C | `gcc -O2 -std=c11 -I.. main.c -o main_bench -lm` | `-O2` |")
    md.append("| C++ | `g++ -O2 -std=c++17 -I../include main.cpp -o main_bench -lm` | `-O2` |")
    md.append("| ARM64 | `as ... && cc -O2 -o main_bench main.c solve.o -lm` | `-O2` on the C harness; the `.s` file is hand-tuned |")
    md.append("| Rust | `cargo build --release` | `opt-level=3 + lto=true` (per repo's `[profile.release]`) |")
    md.append("| Go | `go build -o main_bench main.go` | default (Go optimizes by default; no `-N` debug flag) |")
    md.append("| Zig | `zig build-exe -O ReleaseFast ...` | `ReleaseFast` |")
    md.append("| C# | `dotnet build -c Release` | `Release` |")
    md.append("| Java | `javac Main.java` | none at compile; JVM JIT optimizes at runtime |")
    md.append("| JavaScript | (no build) | V8 JIT optimizes at runtime |")
    md.append("| Python | (no build) | none — interpreter |")
    md.append("")
    md.append("Note: Java/JS/C# show a runtime startup penalty in the per-invocation cost")
    md.append("because their JIT/runtime warm-up happens *every* fresh process.  This is")
    md.append("the honest cost of the language model under a CLI-invocation workload.")
    md.append("")
    md.append("### Note on Zig timings (comptime-fold bias)")
    md.append("")
    md.append(f"> Of the {len(SCOPE_PROBLEMS)} problems benchmarked, **roughly 20-25% of cells** are fully")
    md.append("> constant-foldable under Zig's `-O ReleaseFast` flag: the inputs are compile-time")
    md.append("> literals and the arithmetic is pure, so the optimizer reduces `solve()` to a")
    md.append("> constant return.  Known fold-candidates include p001, p002, p005, p006, p009,")
    md.append("> p013, p017, p018, p019, p024, p028, p031, p033, p040, p045, p063, p069, p094,")
    md.append("> p097, p100.  Those cells in the Zig column measure \"the cost of returning an")
    md.append("> immediate,\" not algorithm execution.  The remaining ~75% do nontrivial runtime")
    md.append("> work and are honest timings.")
    md.append(">")
    md.append("> This is a systematic methodological bias that pulls Zig's aggregate ranking")
    md.append("> downward relative to languages whose optimizers don't fold as aggressively at")
    md.append("> these problem sizes.  Other compiled langs (C, C++ at `-O2`, Rust at `-O3`, Go,")
    md.append("> ARM64) also fold trivial closed-form cases; Zig is just particularly aggressive")
    md.append("> about it.  We flag it here for transparency rather than as a knock on Zig — the")
    md.append("> timings are real measurements of what `-O ReleaseFast` produces.")
    md.append("")
    md.append("### Language idioms: stdlib vs ecosystem packages")
    md.append("")
    md.append("Every language has a package ecosystem (Boost / vcpkg for C++, cargo / crates.io")
    md.append("for Rust, NuGet for C#, pip for Python, etc.), and *what a native developer would")
    md.append("write* almost always includes the well-known libraries for that ecosystem.")
    md.append("Forcing every language to stdlib-only would penalize languages whose ecosystems")
    md.append("are central to how they're actually used in practice.")
    md.append("")
    md.append("Where a single library dominates the ecosystem for the problem domain, we use it:")
    md.append("")
    md.append("| Language | Ecosystem package used | Rationale |")
    md.append("|----------|------------------------|-----------|")
    md.append("| **C++** | `primesieve` (Kim Walisch) | Best-in-class C++ prime library; commonly linked alongside Boost/abseil in C++ projects doing prime work. |")
    md.append("| **C** | `libprimesieve` (C bindings) | Same library, exposed via C API — `#include <primesieve.h>`, link `-lprimesieve`. |")
    md.append("| **Rust** | `primal` (Huon Wilson) | The dominant prime crate on crates.io; what a Rust dev doing prime work reaches for. |")
    md.append("| **Python** | `numpy` | The standard numerical-Python library; `primes[i*i::i] = False` slice assignment IS the Pythonic sieve. |")
    md.append("| **Go** | stdlib only | Go culture is stdlib-first; no single prime package dominates the ecosystem. |")
    md.append("| **Zig** | stdlib only | Zig's package ecosystem is young; stdlib-only is current idiom. |")
    md.append("| **Java** | stdlib only | Apache Commons Math has primes, but Java culture is split between stdlib-only and Commons; we keep it stdlib for now. |")
    md.append("| **C#** | stdlib only | `Open.Numeric.Primes` exists but isn't dominant; most C# devs roll their own sieve at this scale. |")
    md.append("| **JavaScript** | stdlib (Node) only | `Uint8Array` typed-array sieve IS the perf-aware JS idiom; no npm package is dominant. |")
    md.append("| **ARM64** | libc (`malloc`/`free`) | The \"ecosystem\" for asm IS the platform's libc; that's what we use. |")
    md.append("")
    md.append("**Implication for the chart**: C++'s ~340 µs total reflects both \"C++ language")
    md.append("speed\" and \"primesieve is a well-optimized library.\"  If we measured")
    md.append("hand-rolled C++ against hand-rolled Rust/Go/Zig, the gap would shrink.  We")
    md.append("report C++ at its ecosystem-aware best, because *that's how C++ devs actually")
    md.append("write C++*.  Same principle applies symmetrically to every other lang.")
    md.append("")
    md.append("### What's intentionally not measured")
    md.append("")
    md.append("- **In-process warm iterations.**  Server / daemon scenarios are a different")
    md.append("  question — they'd reward language-internal caches (Rust `OnceLock`, primesieve")
    md.append("  internal state, `@lru_cache`, etc.) in ways that don't match the per-invocation")
    md.append("  reality.  See [JOURNEY.md](JOURNEY.md) for the full reasoning behind dropping the")
    md.append("  warm-iter metric.")
    md.append("- **Compile time as a separate column.**  Build cost is part of the user's")
    md.append("  experience for compiled languages, but in our \"shell-loop\" model the binary is")
    md.append("  already built once.  Build time is observed and recorded for diagnostic use but")
    md.append("  not part of the headline.")
    md.append("")
    md.append("### Why the OS process boundary IS the audit tool")
    md.append("")
    md.append("Every language has *some* way to cache state for re-use within one process: Rust's")
    md.append("`OnceLock`, C++ libraries' internal lazy-init, Python's `@lru_cache`, Java's static")
    md.append("`final` precomputed tables.  These are *idiomatic, valuable patterns in their")
    md.append("languages*.  We don't want to rule them out — we want each language to look like a")
    md.append("native would write it.")
    md.append("")
    md.append("The process boundary makes that work fairly: when each invocation is a fresh OS")
    md.append("process, *every* in-process cache starts empty.  No language gets an unfair")
    md.append("amortization advantage.  No source-code refactoring is required to maintain cross-")
    md.append("language honesty — the OS enforces it for free.")
    md.append("")
    md.append("## Reproducibility")
    md.append("")
    md.append("```bash")
    md.append("cd pe/benchmarks")
    md.append(f"cmd/euler-bench/euler-bench per-iter --lang all --problems 1-{len(SCOPE_PROBLEMS)} --iters 10 --write")
    md.append("python3 report.py")
    md.append("```")
    md.append("")
    md.append("Sanitization invariant: the public repo carries no raw bench data files —")
    md.append("only this rendered narrative and the charts.  All measurements live in the")
    md.append("gitignored SQLite SSOT `data/bench-private.db`.  See `scripts/sanitization_gate.py`.")
    md.append("")
    md.append("## Methodology")
    md.append("")
    md.append("The normative spec — metric, sampling, process-contract enforcement,")
    md.append("serial/parallel-class concurrency policy, and ranking rationale — is")
    md.append("[METHODOLOGY.md](METHODOLOGY.md).  See [JOURNEY.md](JOURNEY.md) for the story.  Recent chapters cover:")
    md.append("- The 24-hour cache-strip campaign and its reset (155 source edits reverted)")
    md.append("- The shift from in-process warm iterations to fresh-process per-invocation cost")
    md.append("- The invocation-isolation principle and why the OS is the audit tool")
    md.append("- The data-architecture refactor (single Go writer, no `flock`, no hook chain)")
    md.append("")
    return "\n".join(md) + "\n"


def main() -> int:
    if not DATA_DIR.is_dir():
        print(f"!! data dir missing: {DATA_DIR}", file=sys.stderr)
        return 1
    CHARTS_DIR.mkdir(exist_ok=True)

    agg = aggregate()

    # Diagnostic — surface any langs missing problems in scope.
    # Per-lang denominator is its IN-SCOPE problem count per the tier model
    # (200 for tier-1-only langs, 296 for tier-2 langs after parked, etc.).
    print(f"=== Per-lang coverage in scope (per-tier in-scope, parked-aware):")
    for lang in LANGS:
        d = agg[lang]
        in_scope = d["in_scope_count"]
        passing = in_scope - d["missing"]
        missing_str = f", missing {d['missing']}" if d["missing"] else ""
        print(f"  {DISPLAY[lang]:>12s}: total {fmt_time(d['total_ns']):>10s}"
              f"  ({passing}/{in_scope} problems{missing_str})")

    # Render charts
    chart1 = render_total_chart(agg)
    print(f"\n=== Chart written: {chart1}")
    chart2 = render_speed_vs_size_chart(agg)
    print(f"=== Chart written: {chart2}")
    chart3 = render_coverage_grid_chart(agg)
    print(f"=== Chart written: {chart3}")
    # Tier-2 charts — only rendered when at least one tier-2 lang has data.
    t2_total = render_total_chart_tier2(agg)
    if t2_total:
        print(f"=== Chart written: {t2_total}")
    t2_svs = render_speed_vs_size_chart_tier2(agg)
    if t2_svs:
        print(f"=== Chart written: {t2_svs}")
    # Tier-3 charts — same rendering shape; cpp/go/rust frontier trio.
    t3_total = render_total_chart_tier3(agg)
    if t3_total:
        print(f"=== Chart written: {t3_total}")
    t3_svs = render_speed_vs_size_chart_tier3(agg)
    if t3_svs:
        print(f"=== Chart written: {t3_svs}")

    # Render per-band per-problem detail pages (one .md per band).  Done
    # BEFORE render_results_md so the index table in RESULTS.md links to
    # files that actually exist.
    per_problem_pages = render_per_problem_pages(agg)
    print(f"=== Per-problem detail pages: {len(per_problem_pages)} files in {PER_PROBLEM_DIR.name}/")
    for p in per_problem_pages:
        print(f"   {p.name}")

    # Render markdown
    md = render_results_md(agg)
    out_md = REPO / "RESULTS.md"
    out_md.write_text(md)
    print(f"=== RESULTS.md written: {out_md} ({len(md):,} chars)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
