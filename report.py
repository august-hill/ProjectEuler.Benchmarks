#!/usr/bin/env python3
"""
report.py — Regenerates RESULTS.md + charts for the per-invocation benchmark.

Replaces the previous final_analysis.py (which produced the 3-mode report).
The new model is simpler: ONE metric, process-per-invocation cost.

Inputs:
  data/<lang>.json    — per-lang bench data, written by `euler-bench per-iter --write`
                        For each problem, the headline number we read is
                        `cold_start_ns` (median wall across N fresh-process
                        invocations under the new schema).

Outputs:
  RESULTS.md          — the public results page
  charts/per_iter_total.png    — horizontal bar chart, total cost ranking
  charts/per_iter_per_problem.png  — per-problem heatmap (small-multiples)

Scope:
  Currently fixed at problems 1-10, all 10 languages.  When we extend (more
  problems audited), the SCOPE_PROBLEMS list is the single place to change.
"""

import json
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
SCOPE_PROBLEMS = [f"{i:03d}" for i in range(1, 11)]

# Languages in display order (preserved alphabetic-ish for stability)
LANGS = ["arm64", "c", "cpp", "csharp", "go", "java", "javascript", "python", "rust", "zig"]

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


def load_lang_data(lang: str) -> dict:
    """Load data/<lang>.json. Returns {problem: entry_dict}."""
    path = DATA_DIR / f"{lang}.json"
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return obj.get("problems", {})


def cold_ns(entry: dict):
    """Headline metric for one problem.

    Returns:
        int (≥ 0)   — measured cold-median in nanoseconds (0 is legitimate:
                       trivial closed-form algos can clock at sub-nanosecond)
        None        — problem absent or did not pass (no measurement)
    """
    if not entry or entry.get("status") != "pass":
        return None
    return int(entry.get("cold_start_ns", 0) or 0)


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

    per_problem_ns:    int(≥0) for measured, None for missing
    per_problem_lines: int(≥0) lines for that file (0 if no source-lines field)
    per_problem_status: 'pass' / 'fail' / 'missing'
    total_ns:   sum of measured ns
    total_lines: sum of source lines across the in-scope problems
    missing:    count of None per_problem_ns entries
    """
    out = {}
    for lang in LANGS:
        probs = load_lang_data(lang)
        per_prob_ns = {p: cold_ns(probs.get(p, {})) for p in SCOPE_PROBLEMS}
        per_prob_lines = {p: source_lines(probs.get(p, {})) for p in SCOPE_PROBLEMS}
        per_prob_status = {p: status_of(probs.get(p, {})) for p in SCOPE_PROBLEMS}
        total_ns = sum(v for v in per_prob_ns.values() if v is not None)
        total_lines = sum(per_prob_lines.values())
        missing = sum(1 for p in SCOPE_PROBLEMS if per_prob_ns[p] is None)
        out[lang] = {
            "per_problem_ns": per_prob_ns,
            "per_problem_lines": per_prob_lines,
            "per_problem_status": per_prob_status,
            "total_ns": total_ns,
            "total_lines": total_lines,
            "missing": missing,
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
    fig, ax = plt.subplots(figsize=(10, 6))
    for lang in LANGS:
        x = agg[lang]["total_lines"]
        y_ms = agg[lang]["total_ns"] / 1_000_000
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
    ax.set_xlabel("Total source lines across problems 1–10 (log scale)")
    ax.set_ylabel("Total per-invocation cost — ms (log scale)")
    ax.set_title("Speed vs Code Size — 10 Languages, Problems 1–10\n"
                 "Bottom-left corner = fast + concise; top-right = slow + verbose")
    ax.grid(which="major", alpha=0.3)
    ax.grid(which="minor", alpha=0.12)
    plt.tight_layout()
    out = CHARTS_DIR / "per_iter_speed_vs_size.png"
    plt.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


def render_coverage_grid_chart(agg: dict) -> Path:
    """10×10 cells colored by status + speed bucket.

    🟩 pass (light → dark green by speed bucket)
    🟨 fail-warn (e.g. cold > 100 ms — still passing, but slow)
    🟥 fail (status != pass)
    ⬛ missing (no entry)

    For our current 10×10 scope, everything should be green; the chart's
    real value emerges as we extend to more problems and per-cell colors
    show heterogeneity.
    """
    n_langs = len(LANGS)
    n_probs = len(SCOPE_PROBLEMS)

    fig, ax = plt.subplots(figsize=(8, 5))
    # Build a color grid: rows = langs (sorted fastest-first), cols = problems
    ranked = sorted(LANGS, key=lambda L: agg[L]["total_ns"])

    for ri, lang in enumerate(ranked):
        for ci, p in enumerate(SCOPE_PROBLEMS):
            st = agg[lang]["per_problem_status"][p]
            ns = agg[lang]["per_problem_ns"][p]
            if st == "missing":
                color = "#222222"  # black
            elif st == "fail":
                color = "#D7263D"  # red
            elif ns is not None and ns > 100_000_000:  # >100 ms
                color = "#F0C808"  # amber/yellow
            else:
                # Green; intensity by speed bucket (lighter = faster)
                if ns is None or ns < 100_000:        # <100 µs — bright green
                    color = "#84E184"
                elif ns < 1_000_000:                  # <1ms — medium
                    color = "#5BC85B"
                elif ns < 10_000_000:                 # <10ms — darker
                    color = "#36A036"
                else:                                  # 10-100ms — darkest green
                    color = "#1E6A1E"
            ax.add_patch(plt.Rectangle((ci, n_langs - 1 - ri), 1, 1,
                                        facecolor=color, edgecolor="white",
                                        linewidth=1.5))

    ax.set_xlim(0, n_probs)
    ax.set_ylim(0, n_langs)
    ax.set_xticks([i + 0.5 for i in range(n_probs)])
    ax.set_xticklabels([f"p{p}" for p in SCOPE_PROBLEMS], fontsize=9)
    ax.set_yticks([i + 0.5 for i in range(n_langs)])
    ax.set_yticklabels([DISPLAY[lang] for lang in reversed(ranked)], fontsize=10)
    ax.set_aspect("equal")
    ax.set_title("Coverage + Speed Heatmap — 10 Languages × 10 Problems",
                 fontsize=12)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Real colored-patch legend.  matplotlib's font on macOS doesn't render
    # emoji squares in color (Apple Color Emoji isn't in matplotlib's font
    # list), so we use Patch objects — same visual outcome, font-independent.
    from matplotlib.patches import Patch
    legend_items = [
        Patch(facecolor="#84E184", edgecolor="black", linewidth=0.5, label="pass · <100µs"),
        Patch(facecolor="#5BC85B", edgecolor="black", linewidth=0.5, label="pass · <1ms"),
        Patch(facecolor="#36A036", edgecolor="black", linewidth=0.5, label="pass · <10ms"),
        Patch(facecolor="#1E6A1E", edgecolor="black", linewidth=0.5, label="pass · <100ms"),
        Patch(facecolor="#F0C808", edgecolor="black", linewidth=0.5, label="pass · ≥100ms"),
        Patch(facecolor="#D7263D", edgecolor="black", linewidth=0.5, label="fail"),
        Patch(facecolor="#222222", edgecolor="black", linewidth=0.5, label="missing"),
    ]
    ax.legend(handles=legend_items, loc="upper center",
              bbox_to_anchor=(0.5, -0.06), ncol=4, fontsize=9,
              frameon=False, handlelength=1.5, handleheight=1.2,
              columnspacing=1.2)
    plt.tight_layout()
    out = CHARTS_DIR / "per_iter_coverage_grid.png"
    plt.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


def render_total_chart(agg: dict) -> Path:
    """Horizontal bar: total cost per language, sorted fastest first, log scale X."""
    rows = [(lang, agg[lang]["total_ns"]) for lang in LANGS if agg[lang]["total_ns"] > 0]
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
    ax.set_xlabel("Total per-invocation cost across problems 1–10 (ms, log scale)")
    ax.set_title("Per-Invocation Cost — 10 Languages, Problems 1–10\n"
                 f"Each binary run {10} times in a fresh process; median wall time summed across the 10 problems")
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
    # Ranking rows, sorted by total
    ranked = sorted(
        [(lang, agg[lang]["total_ns"]) for lang in LANGS if agg[lang]["total_ns"] > 0],
        key=lambda r: r[1],
    )
    fastest_ns = ranked[0][1] if ranked else 1

    # Build markdown
    md = []
    md.append("# Project Euler — Cross-Language Benchmarks")
    md.append("")
    md.append(f"> **Currently: {len(SCOPE_PROBLEMS)} problems × {len(LANGS)} languages "
              f"= {len(SCOPE_PROBLEMS) * len(LANGS)} measurements.**")
    md.append("> Growing carefully — each new problem and language is audited for state-leak")
    md.append("> safety, verified for answer correctness, and added only when it cleanly fits the")
    md.append("> measurement methodology.  See [JOURNEY.md](JOURNEY.md) for the full story of how")
    md.append("> we got here, including the reset from 200+ problems back to a verified 10×10 core.")
    md.append("")
    md.append("## Per-Invocation Cost (Total, Problems 1–10)")
    md.append("")
    md.append("We run each program 10 times in fresh OS processes (no warmup, no shared state).")
    md.append("Each invocation pays full startup + algorithm cost — the cost a real CLI / cron /")
    md.append("shell-loop user actually pays.  The median wall time across the 10 invocations is")
    md.append("the headline per-problem number, and we sum across the 10 problems for the total.")
    md.append("")
    md.append("![Per-Invocation Cost](charts/per_iter_total.png)")
    md.append("")
    md.append("|------|----------|--------------------:|--------------:|-----------:|")
    for i, (lang, total) in enumerate(ranked, 1):
        ratio = total / fastest_ns
        lines = agg[lang]["total_lines"]
        md.append(f"| {i} | **{DISPLAY[lang]}** | {fmt_time(total)} | {lines:,} | {ratio:.2f}× |")
    md.append("")
    md.append("## Speed vs Code Size")
    md.append("")
    md.append("How much code does each language need to solve these 10 problems, and how")
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
    md.append("Rows sorted fastest-to-slowest (top to bottom).  At our current 10×10 scope")
    md.append("every cell is green — that's exactly the audit gate we're holding to as we")
    md.append("extend to more problems.")
    md.append("")

    # Per-problem detail grid (langs as rows, problems as columns, sorted by total)
    md.append("## Per-Problem Detail")
    md.append("")
    md.append("Median wall time per fresh-process invocation, for each (language, problem).  Rows")
    md.append("are sorted by total (fastest language at top).")
    md.append("")
    header = "| Language | " + " | ".join(f"p{p}" for p in SCOPE_PROBLEMS) + " |"
    sep    = "|----------|" + "|".join(["----:"] * len(SCOPE_PROBLEMS)) + "|"
    md.append(header)
    md.append(sep)
    for lang, _ in ranked:
        cells = []
        for p in SCOPE_PROBLEMS:
            ns = agg[lang]["per_problem_ns"][p]
            cells.append(fmt_time(ns) if ns is not None else "—")
        md.append(f"| **{DISPLAY[lang]}** | " + " | ".join(cells) + " |")
    md.append("")

    md.append("## Method")
    md.append("")
    md.append("For each (language, problem):")
    md.append("")
    md.append("1. Build the binary (or `as` + `cc` for ARM64, `dotnet build` for C#, etc.).")
    md.append("2. Run the binary 10 times, each in a fresh OS process.  No warmup; no shared state.")
    md.append("3. Each invocation prints `BENCHMARK|problem=NNN|answer=X|time_ns=Y`.  The answer")
    md.append("   is compared against the canonical (each source file's `// Answer:` header")
    md.append("   comment); the benchmark aborts on mismatch.")
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
    md.append("cd ProjectEuler.Benchmarks")
    md.append("cmd/euler-bench/euler-bench per-iter --lang all --problems 1-10 --iters 10 --write")
    md.append("python3 report.py")
    md.append("```")
    md.append("")
    md.append("Sanitization invariant: `data/<lang>.json` files NEVER contain an `answer` field,")
    md.append("regardless of problem number.  Full data including answers lives in `data/private/`")
    md.append("(gitignored), used locally for verification.  See `scripts/sanitization_gate.py`.")
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
    print("=== Per-lang coverage in scope (problems 1-10):")
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

    # Render markdown
    md = render_results_md(agg)
    out_md = REPO / "RESULTS.md"
    out_md.write_text(md)
    print(f"=== RESULTS.md written: {out_md} ({len(md):,} chars)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
