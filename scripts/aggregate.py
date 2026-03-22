#!/usr/bin/env python3
"""aggregate.py - Generate cross-language comparison tables and charts.

Reads benchmark_results.json files from data/ directory,
generates BENCHMARKS.md and SVG charts in charts/ directory.
"""

import json
import os
import sys
import math
from pathlib import Path

# Optional: matplotlib for chart generation
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("WARNING: matplotlib not found. Charts will be skipped.", file=sys.stderr)

SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
DATA_DIR = ROOT_DIR / "data"
CHARTS_DIR = ROOT_DIR / "charts"

LANG_NAMES = {
    "c": "C", "cpp": "C++", "csharp": "C#", "go": "Go",
    "rust": "Rust", "python": "Python", "java": "Java",
    "haskell": "Haskell", "javascript": "JavaScript", "arm64": "ARM64"
}

LANG_COLORS = {
    "c": "#555555", "cpp": "#f34b7d", "csharp": "#178600",
    "go": "#00ADD8", "rust": "#dea584", "python": "#3572A5",
    "java": "#b07219", "haskell": "#5e5086", "javascript": "#f1e05a",
    "arm64": "#6E4C13"
}

# Desired display order
LANG_ORDER = ["arm64", "c", "cpp", "rust", "go", "java", "csharp", "javascript", "python"]


def load_data():
    """Load all benchmark JSON files from data/."""
    data = {}
    for lang in LANG_ORDER:
        path = DATA_DIR / f"{lang}.json"
        if path.exists():
            with open(path) as f:
                data[lang] = json.load(f)
    return data


def load_answers():
    """Load known correct answers."""
    path = DATA_DIR / "answers.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def geometric_mean(values):
    """Compute geometric mean of positive values."""
    values = [v for v in values if v > 0]
    if not values:
        return 0
    return math.exp(sum(math.log(v) for v in values) / len(values))


def format_time(ns):
    """Format nanoseconds into human-readable string."""
    if ns < 1_000:
        return f"{ns} ns"
    elif ns < 1_000_000:
        return f"{ns / 1_000:.1f} us"
    elif ns < 1_000_000_000:
        return f"{ns / 1_000_000:.1f} ms"
    else:
        return f"{ns / 1_000_000_000:.2f} s"


def format_bytes(b):
    """Format bytes into human-readable string."""
    if b < 1024:
        return f"{b} B"
    elif b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    else:
        return f"{b / (1024 * 1024):.1f} MB"


def validate_answers(data, answers):
    """Check all answers against known correct values."""
    errors = []
    for lang, info in data.items():
        problems = info.get("problems", {})
        for prob, pdata in problems.items():
            expected = answers.get(prob)
            actual = pdata.get("answer")
            if expected is not None and actual is not None and actual != expected:
                errors.append(f"  {LANG_NAMES.get(lang, lang)} problem {prob}: "
                              f"got {actual}, expected {expected}")
    return errors


def generate_rankings_table(data):
    """Generate overall rankings by geometric mean time."""
    rankings = []
    for lang in LANG_ORDER:
        if lang not in data:
            continue
        problems = data[lang].get("problems", {})
        times = [p["time_ns"] for p in problems.values() if p.get("time_ns", 0) > 0]
        if times:
            gmean = geometric_mean(times)
            rankings.append((lang, gmean, len(times)))

    rankings.sort(key=lambda x: x[1])

    lines = ["## Overall Rankings (by geometric mean time)\n"]
    lines.append("| Rank | Language | Geo. Mean Time | Problems |")
    lines.append("|------|----------|----------------|----------|")
    for i, (lang, gmean, count) in enumerate(rankings, 1):
        name = LANG_NAMES.get(lang, lang)
        lines.append(f"| {i} | **{name}** | {format_time(gmean)} | {count} |")
    lines.append("")
    return "\n".join(lines), rankings


def generate_problem_table(data):
    """Generate per-problem comparison table."""
    langs = [l for l in LANG_ORDER if l in data]
    headers = ["#"] + [LANG_NAMES.get(l, l) for l in langs]

    lines = ["## Per-Problem Comparison\n"]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")

    for prob_num in range(1, 101):
        prob = f"{prob_num:03d}"
        row = [prob]
        times = {}
        for lang in langs:
            problems = data[lang].get("problems", {})
            if prob in problems and problems[prob].get("time_ns", 0) > 0:
                times[lang] = problems[prob]["time_ns"]

        min_time = min(times.values()) if times else 0

        for lang in langs:
            if lang in times:
                t = times[lang]
                cell = format_time(t)
                if t == min_time and len(times) > 1:
                    cell = f"**{cell}**"  # Bold the fastest
                row.append(cell)
            else:
                row.append("—")

        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    return "\n".join(lines)


def generate_memory_table(data):
    """Generate average memory comparison."""
    lines = ["## Memory Usage (Peak RSS)\n"]
    lines.append("| Language | Avg Peak RSS | Min | Max |")
    lines.append("|----------|-------------|-----|-----|")

    for lang in LANG_ORDER:
        if lang not in data:
            continue
        problems = data[lang].get("problems", {})
        rss_values = [p["peak_rss_bytes"] for p in problems.values()
                      if p.get("peak_rss_bytes", 0) > 0]
        if rss_values:
            avg = sum(rss_values) / len(rss_values)
            lines.append(f"| **{LANG_NAMES[lang]}** | {format_bytes(avg)} | "
                         f"{format_bytes(min(rss_values))} | {format_bytes(max(rss_values))} |")

    lines.append("")
    return "\n".join(lines)


def generate_sloc_table(data):
    """Generate source lines of code comparison."""
    lines = ["## Code Size (Source Lines of Code)\n"]
    lines.append("| Language | Avg SLOC | Total SLOC | Avg Bytes |")
    lines.append("|----------|----------|------------|-----------|")

    for lang in LANG_ORDER:
        if lang not in data:
            continue
        problems = data[lang].get("problems", {})
        sloc = [p["source_lines"] for p in problems.values() if p.get("source_lines", 0) > 0]
        sbytes = [p["source_bytes"] for p in problems.values() if p.get("source_bytes", 0) > 0]
        if sloc:
            lines.append(f"| **{LANG_NAMES[lang]}** | {sum(sloc)/len(sloc):.0f} | "
                         f"{sum(sloc)} | {sum(sbytes)/len(sbytes):.0f} |")

    lines.append("")
    return "\n".join(lines)


def generate_charts(data, rankings):
    """Generate SVG charts using matplotlib."""
    if not HAS_MATPLOTLIB:
        return

    CHARTS_DIR.mkdir(exist_ok=True)

    # Chart 1: Geometric mean time per language (bar chart)
    langs = [r[0] for r in rankings]
    gmeans = [r[1] for r in rankings]
    colors = [LANG_COLORS.get(l, "#888") for l in langs]
    names = [LANG_NAMES.get(l, l) for l in langs]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(names, gmeans, color=colors, edgecolor="white", linewidth=0.5)
    ax.set_yscale("log")
    ax.set_ylabel("Geometric Mean Time (ns)")
    ax.set_title("Average Performance by Language (lower is faster)")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: format_time(x)))
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "avg_time_per_language.svg", format="svg")
    plt.savefig(CHARTS_DIR / "avg_time_per_language.png", format="png", dpi=150)
    plt.close()

    # Chart 2: Slowdown factor box plot
    # For each language, compute slowdown = time / min(time across languages) per problem
    slowdowns = {l: [] for l in LANG_ORDER if l in data}
    for prob_num in range(1, 101):
        prob = f"{prob_num:03d}"
        times = {}
        for lang in data:
            problems = data[lang].get("problems", {})
            if prob in problems and problems[prob].get("time_ns", 0) > 0:
                times[lang] = problems[prob]["time_ns"]
        if len(times) < 2:
            continue
        min_t = min(times.values())
        if min_t == 0:
            continue
        for lang, t in times.items():
            slowdowns[lang].append(t / min_t)

    fig, ax = plt.subplots(figsize=(10, 6))
    plot_data = []
    plot_labels = []
    plot_colors = []
    for lang in LANG_ORDER:
        if lang in slowdowns and slowdowns[lang]:
            plot_data.append(slowdowns[lang])
            plot_labels.append(LANG_NAMES.get(lang, lang))
            plot_colors.append(LANG_COLORS.get(lang, "#888"))

    bp = ax.boxplot(plot_data, labels=plot_labels, patch_artist=True, showfliers=False)
    for patch, color in zip(bp["boxes"], plot_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_yscale("log")
    ax.set_ylabel("Slowdown Factor (vs fastest language per problem)")
    ax.set_title("Performance Consistency by Language")
    ax.axhline(y=1, color="green", linestyle="--", alpha=0.5, label="1x (fastest)")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "slowdown_boxplot.svg", format="svg")
    plt.savefig(CHARTS_DIR / "slowdown_boxplot.png", format="png", dpi=150)
    plt.close()

    # Chart 3: Peak RSS comparison
    rss_avgs = []
    rss_names = []
    rss_colors = []
    for lang in LANG_ORDER:
        if lang not in data:
            continue
        problems = data[lang].get("problems", {})
        rss_values = [p["peak_rss_bytes"] for p in problems.values()
                      if p.get("peak_rss_bytes", 0) > 0]
        if rss_values:
            rss_avgs.append(sum(rss_values) / len(rss_values) / (1024 * 1024))  # MB
            rss_names.append(LANG_NAMES.get(lang, lang))
            rss_colors.append(LANG_COLORS.get(lang, "#888"))

    if rss_avgs:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(rss_names, rss_avgs, color=rss_colors, edgecolor="white")
        ax.set_ylabel("Average Peak RSS (MB)")
        ax.set_title("Memory Usage by Language")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(CHARTS_DIR / "rss_comparison.svg", format="svg")
        plt.savefig(CHARTS_DIR / "rss_comparison.png", format="png", dpi=150)
        plt.close()

    # Chart 4: SLOC comparison
    sloc_avgs = []
    sloc_names = []
    sloc_colors = []
    for lang in LANG_ORDER:
        if lang not in data:
            continue
        problems = data[lang].get("problems", {})
        sloc = [p["source_lines"] for p in problems.values() if p.get("source_lines", 0) > 0]
        if sloc:
            sloc_avgs.append(sum(sloc) / len(sloc))
            sloc_names.append(LANG_NAMES.get(lang, lang))
            sloc_colors.append(LANG_COLORS.get(lang, "#888"))

    if sloc_avgs:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(sloc_names, sloc_avgs, color=sloc_colors, edgecolor="white")
        ax.set_ylabel("Average Source Lines of Code")
        ax.set_title("Code Verbosity by Language")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(CHARTS_DIR / "sloc_comparison.svg", format="svg")
        plt.savefig(CHARTS_DIR / "sloc_comparison.png", format="png", dpi=150)
        plt.close()

    print(f"Charts written to {CHARTS_DIR}/")


def generate_benchmarks_md(data, answers):
    """Generate the main BENCHMARKS.md file."""
    errors = validate_answers(data, answers)
    if errors:
        print("ANSWER VALIDATION ERRORS:")
        for e in errors:
            print(e)

    sections = []
    sections.append("# Cross-Language Benchmark Results\n")
    sections.append(f"Comparing {len(data)} languages across 100 Project Euler problems.\n")
    sections.append("Platform: Apple Silicon | Generated by aggregate.py\n")

    rankings_table, rankings = generate_rankings_table(data)
    sections.append(rankings_table)
    sections.append(generate_memory_table(data))
    sections.append(generate_sloc_table(data))
    sections.append(generate_problem_table(data))

    if HAS_MATPLOTLIB:
        sections.append("## Charts\n")
        sections.append("![Average Time per Language](charts/avg_time_per_language.svg)\n")
        sections.append("![Slowdown Distribution](charts/slowdown_boxplot.svg)\n")
        sections.append("![Memory Usage](charts/rss_comparison.svg)\n")
        sections.append("![Code Verbosity](charts/sloc_comparison.svg)\n")

    benchmarks_md = "\n".join(sections)
    output_path = ROOT_DIR / "BENCHMARKS.md"
    with open(output_path, "w") as f:
        f.write(benchmarks_md)
    print(f"Written {output_path}")

    return rankings


def main():
    data = load_data()
    answers = load_answers()

    if not data:
        print("No benchmark data found in data/. Run collect.sh first.")
        sys.exit(1)

    print(f"Loaded data for: {', '.join(LANG_NAMES.get(l, l) for l in data)}")

    rankings = generate_benchmarks_md(data, answers)
    generate_charts(data, rankings)


if __name__ == "__main__":
    main()
