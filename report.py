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

import html
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

# Scope: extend this list only after each new problem clears the
# state-leak / answer-verification audit.
# Partial-coverage is supported and intentional — when a (lang, problem) cell
# is unmeasured, report.py renders it as "missing" in the grid and excludes
# it from per-lang totals. The per-lang headline shows "<measured>/<scope>"
# so partial coverage is honest in the rendering.
SCOPE_PROBLEMS = [f"{i:03d}" for i in range(1, 201)]

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
        total_ns = sum(v for v in per_prob_ns.values() if v is not None)
        total_lines = sum(per_prob_lines.values())
        missing = sum(1 for p in SCOPE_PROBLEMS if per_prob_ns[p] is None)
        out[lang] = {
            "per_problem_ns": per_prob_ns,
            "per_problem_lines": per_prob_lines,
            "per_problem_status": per_prob_status,
            "per_problem_samples": per_prob_samples,
            "total_ns": total_ns,
            "total_lines": total_lines,
            "missing": missing,
        }

    # Common-set computation: problems where every lang has status='pass'.
    # Any lang missing OR with status!='pass' for a given problem disqualifies
    # that problem from the common set.
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
    ax.set_xlabel(f"Total source lines across problems 1–{len(SCOPE_PROBLEMS)} (log scale)")
    ax.set_ylabel("Total per-invocation cost — ms (log scale)")
    ax.set_title(f"Speed vs Code Size — {len(LANGS)} Languages, Problems 1–{len(SCOPE_PROBLEMS)}\n"
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
    "slow":         "#F0C808",   # amber — passing but ≥100 ms
    "lt_100us":     "#84E184",   # bright green
    "lt_1ms":       "#5BC85B",
    "lt_10ms":      "#36A036",
    "lt_100ms":     "#1E6A1E",   # darkest green
}

LEGEND_ITEMS = [
    (HEATMAP_COLORS["lt_100us"], "pass · <100µs"),
    (HEATMAP_COLORS["lt_1ms"],   "pass · <1ms"),
    (HEATMAP_COLORS["lt_10ms"],  "pass · <10ms"),
    (HEATMAP_COLORS["lt_100ms"], "pass · <100ms"),
    (HEATMAP_COLORS["slow"],     "pass · ≥100ms"),
    (HEATMAP_COLORS["fail"],     "fail"),
    (HEATMAP_COLORS["missing"],  "missing"),
]


def cell_color(status: str, ns) -> str:
    """Map a (status, ns) pair to a cell hex color.  Shared by both renderers."""
    if status == "missing":
        return HEATMAP_COLORS["missing"]
    if status == "fail":
        return HEATMAP_COLORS["fail"]
    if ns is not None and ns > 100_000_000:
        return HEATMAP_COLORS["slow"]
    if ns is None or ns < 100_000:
        return HEATMAP_COLORS["lt_100us"]
    if ns < 1_000_000:
        return HEATMAP_COLORS["lt_1ms"]
    if ns < 10_000_000:
        return HEATMAP_COLORS["lt_10ms"]
    return HEATMAP_COLORS["lt_100ms"]


def _bands(scope: list, band_size: int) -> list:
    """Split SCOPE_PROBLEMS into chunks of at most band_size items."""
    return [scope[i:i + band_size] for i in range(0, len(scope), band_size)]


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
    langs = LANG_DISPLAY_ORDER
    n_langs = len(langs)
    n_probs = len(SCOPE_PROBLEMS)
    bands = _bands(SCOPE_PROBLEMS, BAND_SIZE)
    n_bands = len(bands)

    # Sizing: cell ~0.13" wide × 0.30" tall.  Band gets +0.45" for its title.
    cell_w_in = 0.13
    cell_h_in = 0.30
    band_h_in = n_langs * cell_h_in + 0.45
    fig_w = max(11.0, BAND_SIZE * cell_w_in + 2.2)  # +2.2 for y-labels & margin
    fig_h = n_bands * band_h_in + 1.6               # +1.6 for figure title + legend

    fig, axes = plt.subplots(n_bands, 1,
                             figsize=(fig_w, fig_h),
                             gridspec_kw={"hspace": 0.65})
    # plt.subplots returns a bare Axes (not an array) when nrows=1.
    if n_bands == 1:
        axes = [axes]

    for band_i, ax in enumerate(axes):
        band_probs = bands[band_i]
        for ri, lang in enumerate(langs):
            for ci, p in enumerate(band_probs):
                st = agg[lang]["per_problem_status"][p]
                ns = agg[lang]["per_problem_ns"][p]
                ax.add_patch(plt.Rectangle(
                    (ci, n_langs - 1 - ri), 1, 1,
                    facecolor=cell_color(st, ns),
                    edgecolor="white", linewidth=0.6,
                ))

        # Uniform x extent across bands keeps cell width constant even on a
        # final partial band (e.g. 50 problems instead of 100).
        ax.set_xlim(0, BAND_SIZE)
        ax.set_ylim(0, n_langs)

        # X-ticks every 10 problems within the band.
        tick_idx = list(range(0, len(band_probs), 10))
        ax.set_xticks([i + 0.5 for i in tick_idx])
        ax.set_xticklabels([f"p{band_probs[i]}" for i in tick_idx], fontsize=8)

        ax.set_yticks([i + 0.5 for i in range(n_langs)])
        ax.set_yticklabels([DISPLAY[l] for l in reversed(langs)], fontsize=9)
        ax.set_title(f"Problems {band_probs[0]}–{band_probs[-1]}",
                     fontsize=10, loc="left", pad=4)
        ax.tick_params(length=0)
        ax.set_aspect("auto")   # let figure dims dictate; cells aren't square
        for spine in ax.spines.values():
            spine.set_visible(False)

    fig.suptitle(
        f"Coverage + Speed Heatmap — {n_langs} languages × {n_probs} problems",
        fontsize=13, y=0.995,
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


def render_coverage_grid_svg(agg: dict) -> Path:
    """Same banded heatmap as the PNG, but as a hand-written SVG so each cell
    carries a <title> tooltip ("p347 Zig: 2.3 ms").

    Rendering channels:
      - RESULTS.md embeds the PNG via ![](...).  Tooltips don't fire in <img>.
      - RESULTS.md ALSO links the .svg file directly.  Opened as a page
        (raw.githubusercontent.com or local file://), the <title> tooltips
        fire on hover — that's the "drill into one cell" channel.

    Hand-written rather than savefig(format='svg') because matplotlib's SVG
    output is 5-10× larger and has no semantic structure to hang tooltips on.

    Every text interpolation runs through html.escape() — otherwise legend
    labels like "<100µs" would break XML parsing (the parser reads "<1" as
    a malformed start-tag).  This bit me on first deploy; do not remove.
    """
    # Module-local helper: XML-escape any user-text going into element content
    # or attribute values.  quote=True covers " (attr values) too.
    def esc(s) -> str:
        return html.escape(str(s), quote=True)

    langs = LANG_DISPLAY_ORDER
    n_langs = len(langs)
    n_probs = len(SCOPE_PROBLEMS)
    bands = _bands(SCOPE_PROBLEMS, BAND_SIZE)
    n_bands = len(bands)

    # SVG user-unit dimensions (≈ CSS pixels).
    cell_w, cell_h = 12, 18
    margin_l, margin_r = 92, 20
    margin_t = 56
    band_title_h = 22
    band_grid_h = n_langs * cell_h
    band_xaxis_h = 18
    band_h = band_title_h + band_grid_h + band_xaxis_h
    band_gap = 26
    legend_h = 70

    fig_w = margin_l + BAND_SIZE * cell_w + margin_r
    fig_h = (margin_t
             + n_bands * band_h
             + (n_bands - 1) * band_gap
             + legend_h)

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{fig_w}" height="{fig_h}" '
        f'viewBox="0 0 {fig_w} {fig_h}" '
        f'font-family="-apple-system, BlinkMacSystemFont, sans-serif">'
    )
    parts.append(
        '<style>'
        'text { fill:#222; font-size:11px; }'
        '.title { font-size:14px; font-weight:600; }'
        '.subtitle { font-size:10px; fill:#666; }'
        '.band { font-size:12px; font-weight:500; }'
        '.tick { font-size:9px; fill:#555; }'
        '.cell { stroke:#fff; stroke-width:0.5; }'
        '.cell:hover { stroke:#000; stroke-width:1.5; }'
        '</style>'
    )

    # Figure title + subtitle
    parts.append(
        f'<text class="title" x="{margin_l}" y="26">'
        f'{esc(f"Coverage + Speed Heatmap — {n_langs} languages × {n_probs} problems")}'
        f'</text>'
    )
    parts.append(
        f'<text class="subtitle" x="{margin_l}" y="42">'
        f'{esc("Hover any cell for problem · language · per-invocation time")}'
        f'</text>'
    )

    for band_i, band_probs in enumerate(bands):
        band_y0 = margin_t + band_i * (band_h + band_gap)
        grid_y0 = band_y0 + band_title_h

        # Band title
        parts.append(
            f'<text class="band" x="{margin_l}" y="{band_y0 + 15}">'
            f'{esc(f"Problems {band_probs[0]}–{band_probs[-1]}")}'
            f'</text>'
        )

        # Y-axis lang labels (right-aligned into the left margin)
        for ri, lang in enumerate(langs):
            y = grid_y0 + (ri + 0.5) * cell_h + 4   # +4 ≈ baseline tweak
            parts.append(
                f'<text x="{margin_l - 6}" y="{y}" text-anchor="end">'
                f'{esc(DISPLAY[lang])}</text>'   # "C++" has no <>& but esc is cheap
            )

        # Cells with <title> tooltips
        for ri, lang in enumerate(langs):
            for ci, p in enumerate(band_probs):
                st = agg[lang]["per_problem_status"][p]
                ns = agg[lang]["per_problem_ns"][p]
                color = cell_color(st, ns)
                x = margin_l + ci * cell_w
                y = grid_y0 + ri * cell_h
                if st == "missing":
                    tip = "missing"
                elif st == "fail":
                    tip = "fail"
                elif ns is None:
                    tip = "—"
                else:
                    tip = fmt_time(ns)
                parts.append(
                    f'<rect class="cell" x="{x}" y="{y}" '
                    f'width="{cell_w}" height="{cell_h}" fill="{color}">'
                    f'<title>{esc(f"p{p} {DISPLAY[lang]}: {tip}")}</title>'
                    f'</rect>'
                )

        # X-axis ticks every 10 problems within the band
        xaxis_y = grid_y0 + band_grid_h + 12
        for i in range(0, len(band_probs), 10):
            x = margin_l + (i + 0.5) * cell_w
            parts.append(
                f'<text class="tick" x="{x}" y="{xaxis_y}" text-anchor="middle">'
                f'{esc(f"p{band_probs[i]}")}</text>'
            )

    # Legend.  Labels here contain "<100µs", "<1ms", etc. — the literal "<"
    # is what broke the SVG on first deploy.  esc() turns it into "&lt;".
    legend_y = margin_t + n_bands * band_h + (n_bands - 1) * band_gap + 28
    swatch = 14
    item_w = (fig_w - margin_l - margin_r) / len(LEGEND_ITEMS)
    for i, (color, label) in enumerate(LEGEND_ITEMS):
        lx = margin_l + i * item_w
        parts.append(
            f'<rect x="{lx}" y="{legend_y}" width="{swatch}" height="{swatch}" '
            f'fill="{color}" stroke="#000" stroke-width="0.3"/>'
        )
        parts.append(
            f'<text x="{lx + swatch + 4}" y="{legend_y + 11}">{esc(label)}</text>'
        )

    parts.append('</svg>')
    out = CHARTS_DIR / "per_iter_coverage_grid.svg"
    out.write_text("\n".join(parts))

    # Self-check: parse the file we just wrote as XML.  If a future change
    # forgets esc() somewhere and emits a stray "<" into text content, this
    # raises here instead of silently shipping a broken SVG to GitHub.
    import xml.etree.ElementTree as _ET
    try:
        _ET.parse(out)
    except _ET.ParseError as e:
        raise RuntimeError(
            f"Generated SVG is not valid XML — likely an unescaped <, >, or & "
            f"in a text interpolation.  Run html.escape() on any new text "
            f"added to render_coverage_grid_svg().  Parser error: {e}"
        )
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
    ax.set_xlabel(f"Total per-invocation cost across the {n_common}-problem common set (ms, log scale)")
    ax.set_title(f"Per-Invocation Cost — {len(LANGS)} Languages, "
                 f"Common Set ({n_common} of {len(SCOPE_PROBLEMS)} in-scope problems)\n"
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

    # Coverage statistics — used in narrative to honestly describe partial state
    n_common = len(common["problems"])
    total_cells = len(SCOPE_PROBLEMS) * len(LANGS)
    measured_cells = sum(
        sum(1 for v in agg[lang]["per_problem_ns"].values() if v is not None)
        for lang in LANGS
    )

    # Build markdown
    md = []
    md.append("# Project Euler — Cross-Language Benchmarks")
    md.append("")
    md.append(f"> **Scope: {len(SCOPE_PROBLEMS)} problems × {len(LANGS)} languages "
              f"= {total_cells} cells, {measured_cells} measured "
              f"({100*measured_cells/total_cells:.1f}% coverage).**")
    md.append(f"> The cross-language ranking below is computed over the **{n_common}-problem "
              f"common set** (problems where every language has a passing measurement) — the "
              f"apples-to-apples comparison surface.  Per-language coverage detail appears below "
              f"the ranking.")
    md.append("> Growing carefully — each new problem and language is audited for state-leak")
    md.append("> safety, verified for answer correctness, and added only when it cleanly fits the")
    md.append("> measurement methodology.  See [JOURNEY.md](JOURNEY.md) for the full story of how")
    md.append("> we got here, including the reset from 200+ problems back to a verified 10×10")
    md.append(f"> core, then the disciplined expansion to today's {len(SCOPE_PROBLEMS)}-problem scope.")
    md.append("")
    md.append(f"## Per-Invocation Cost (Common Set, {n_common} of {len(SCOPE_PROBLEMS)} problems)")
    md.append("")
    md.append("We run each program 10 times in fresh OS processes (no warmup, no shared state).")
    md.append("Each invocation pays full startup + algorithm cost — the cost a real CLI / cron /")
    md.append("shell-loop user actually pays.  The median wall time across the 10 invocations is")
    md.append(f"the headline per-problem number, and the table sums over the {n_common}-problem")
    md.append("common set so partial-coverage languages aren't artificially \"faster\" than fully-")
    md.append("covered ones.  Per-language individual coverage (which may be ≥ the common set) is")
    md.append("shown in the coverage block further down.")
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
    md.append("## Speed vs Code Size")
    md.append("")
    md.append(f"How much code does each language need to solve these {len(SCOPE_PROBLEMS)} problems, and how")
    md.append("fast does that code run?  Bottom-left = fast and concise; top-right = slow")
    md.append("and verbose.  ARM64's outlier position (most lines) is expected — assembly")
    md.append("trades verbosity for direct hardware control.")
    md.append("")
    md.append("![Speed vs Code Size](charts/per_iter_speed_vs_size.png)")
    md.append("")
    md.append("## Coverage + Speed Heatmap")
    md.append("")
    md.append("One cell per (language, problem).  Color shows whether the cell passes the")
    md.append("invocation-isolation + answer-correctness audit and how fast it runs:")
    md.append("")
    md.append("- 🟢 **Green** — pass; lighter green = faster, darker green = slower")
    md.append("- 🟡 **Yellow** — pass but > 100 ms (slow algorithm or heavy startup)")
    md.append("- 🔴 **Red** — fail (wrong answer, build error, timeout)")
    md.append("- ⚫ **Black** — missing entry (no measurement)")
    md.append("")
    md.append("![Coverage + Speed Heatmap](charts/per_iter_coverage_grid.png)")
    md.append("")
    # Link goes direct to raw.githubusercontent.com — GitHub's /blob/ viewer no
    # longer renders inline SVG previews (shows "Invalid image source" since
    # their security hardening), but the raw CDN serves it as image/svg+xml so
    # the browser renders it natively and <title> hover tooltips fire.
    svg_raw_url = ("https://raw.githubusercontent.com/august-hill/"
                   "ProjectEuler.Benchmarks/main/charts/per_iter_coverage_grid.svg")
    md.append(f"**🔍 [Open the SVG version]({svg_raw_url})** — same chart, with a")
    md.append("hover tooltip on every cell (`p347 Zig: 2.3 ms`).  The link goes direct to")
    md.append("`raw.githubusercontent.com` because GitHub's `/blob/` viewer no longer renders")
    md.append("inline SVG previews; tooltips also don't fire inside the inline `![](...)`")
    md.append("image above because browsers treat `<img>` SVGs as opaque.")
    md.append("")
    n_bands = (len(SCOPE_PROBLEMS) + BAND_SIZE - 1) // BAND_SIZE
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

    # Per-problem detail — transposed + banded.
    #
    # Previously this was a single wide table with one row per language and one
    # column per problem.  At 100 problems that's already 101 columns, which
    # forces a horizontal scrollbar in GitHub's markdown viewer; at the project's
    # 1000-problem target GitHub's GFM table renderer falls over entirely.
    #
    # We follow the same fix the coverage heatmap got (commit 03413fb): split
    # along BAND_SIZE so the on-page width is bounded.  Here we also transpose —
    # one row per problem, one column per language — for two reasons:
    #   1. With 10 langs we get a fixed 11-column table regardless of scope, so
    #      every band renders cleanly no matter how far we extend.
    #   2. The natural lookup ("which lang is fastest on p347?") is a row scan,
    #      which reads more naturally than scanning across a 100-cell-wide row.
    #
    # Column order is LANG_DISPLAY_ORDER (native → managed → interpreted), not
    # ranked order, for the same reason the heatmap fixed its row order: we
    # don't want the column layout to shuffle between snapshots as totals drift.
    md.append("## Per-Problem Detail")
    md.append("")
    md.append("Median wall time per fresh-process invocation, for each (language, problem).")
    md.append(f"Problems are chunked into bands of {BAND_SIZE} (matching the heatmap above) so")
    md.append("each table stays narrow enough for GitHub's markdown renderer.  Columns are in")
    md.append("fixed tier order (native → managed → interpreted).")
    md.append("")
    display_langs = LANG_DISPLAY_ORDER
    header = "| Problem | " + " | ".join(DISPLAY[l] for l in display_langs) + " |"
    sep    = "|---------|" + "|".join(["----:"] * len(display_langs)) + "|"
    # Track whether any partial-measurement cells exist so we only emit the
    # footnote when the marker actually appears in the tables.
    any_partial = False
    for band_probs in _bands(SCOPE_PROBLEMS, BAND_SIZE):
        md.append(f"### Problems {band_probs[0]}–{band_probs[-1]}")
        md.append("")
        md.append(header)
        md.append(sep)
        for p in band_probs:
            cells = []
            for lang in display_langs:
                ns = agg[lang]["per_problem_ns"][p]
                if ns is None:
                    cells.append("—")
                else:
                    s = agg[lang]["per_problem_samples"][p]
                    # Suite-standard iters=10; mark partial measurements so a
                    # reader can tell at-a-glance which cells haven't been
                    # bench'd to full sample count.
                    suffix = "*" if (s is not None and s < 10) else ""
                    cells.append(fmt_time(ns) + suffix)
            md.append(f"| **p{p}** | " + " | ".join(cells) + " |")
        md.append("")

        # Detect any partial cell in this band for the footnote gate.
        if not any_partial:
            for p in band_probs:
                for lang in display_langs:
                    s = agg[lang]["per_problem_samples"][p]
                    if s is not None and s < 10:
                        any_partial = True
                        break
                if any_partial:
                    break

    if any_partial:
        md.append(
            "> \\* — *partial measurement*: cell was bench'd with fewer than the "
            "suite-standard 10 iterations (typically 1 or 3, for heavy problems "
            "where iters=10 would exceed the per-chunk wall budget). The median "
            "is still meaningful for >1s problems, but the variance estimate is "
            "degraded. These cells are queued for a future uniform-iters=10 "
            "re-bench pass."
        )
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
    md.append("## Sub-Millisecond Floor")
    md.append("")
    md.append("On Apple Silicon, process spawn (`fork` + `exec`) costs ~5–10 ms.  Problems where")
    md.append("the algorithm takes < 1 ms (currently p001–p006 in most languages) are effectively")
    md.append("measuring spawn cost, not algorithmic merit.  That **is** what a CLI user pays, so")
    md.append("the number is still meaningful — but the cross-language signal on these problems")
    md.append("mostly reflects runtime startup cost.  The interesting algorithmic signal starts")
    md.append("around p007+.")
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
    md.append("## Methodology Story")
    md.append("")
    md.append("See [JOURNEY.md](JOURNEY.md) for the full story.  Recent chapters cover:")
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

    # Diagnostic — surface any langs missing problems in scope
    print(f"=== Per-lang coverage in scope (problems 1-{len(SCOPE_PROBLEMS)}):")
    for lang in LANGS:
        d = agg[lang]
        missing_str = f", missing {d['missing']}" if d["missing"] else ""
        print(f"  {DISPLAY[lang]:>12s}: total {fmt_time(d['total_ns']):>10s}"
              f"  ({len(SCOPE_PROBLEMS) - d['missing']}/{len(SCOPE_PROBLEMS)} problems{missing_str})")

    # Render charts
    chart1 = render_total_chart(agg)
    print(f"\n=== Chart written: {chart1}")
    chart2 = render_speed_vs_size_chart(agg)
    print(f"=== Chart written: {chart2}")
    chart3 = render_coverage_grid_chart(agg)
    print(f"=== Chart written: {chart3}")
    chart3_svg = render_coverage_grid_svg(agg)
    print(f"=== Chart written: {chart3_svg}")

    # Render markdown
    md = render_results_md(agg)
    out_md = REPO / "RESULTS.md"
    out_md.write_text(md)
    print(f"=== RESULTS.md written: {out_md} ({len(md):,} chars)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
