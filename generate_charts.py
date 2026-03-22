#!/usr/bin/env python3
"""Generate benchmark comparison charts from per-language benchmark results.

Usage:
    python3 generate_charts.py [--output-dir charts/]

Reads benchmark_results.json from each language repo and produces:
1. Total time bar chart (all languages)
2. Per-problem heatmap (language x problem, colored by time)
3. Language ranking by problem count won
4. Source lines of code comparison
5. Compiler comparison (GCC vs Clang for C/C++)
"""

import json
import os
import sys
import argparse
from pathlib import Path

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# Language repos and display config
LANGUAGES = {
    'C':          {'dir': 'ProjectEuler.C',          'color': '#555555', 'short': 'C'},
    'C++':        {'dir': 'ProjectEuler.CPlusPlus',  'color': '#00599C', 'short': 'C++'},
    'Rust':       {'dir': 'ProjectEuler.Rust',       'color': '#DEA584', 'short': 'Rust'},
    'Go':         {'dir': 'ProjectEuler.Go',         'color': '#00ADD8', 'short': 'Go'},
    'Java':       {'dir': 'ProjectEuler.Java',       'color': '#B07219', 'short': 'Java'},
    'C#':         {'dir': 'ProjectEuler.CSharp',     'color': '#178600', 'short': 'C#'},
    'JavaScript': {'dir': 'ProjectEuler.JavaScript', 'color': '#F7DF1E', 'short': 'JS'},
    'Python':     {'dir': 'ProjectEuler.Python',     'color': '#3776AB', 'short': 'Python'},
    'ARM64':      {'dir': 'ProjectEuler.ARM64',      'color': '#E34F26', 'short': 'ARM64'},
}

BASE_DIR = Path(__file__).parent.parent  # /Users/.../ccdev


def load_all_results():
    """Load benchmark results from all language repos."""
    results = {}
    for lang, cfg in LANGUAGES.items():
        path = BASE_DIR / cfg['dir'] / 'benchmark_results.json'
        if not path.exists():
            print(f"  Warning: {path} not found, skipping {lang}")
            continue
        with open(path) as f:
            data = json.load(f)

        problems = data.get('problems', data.get('results', {}))

        # Normalize: if it's a list (JS/ARM64 old format), convert to dict
        if isinstance(problems, list):
            normalized = {}
            for p in problems:
                if p.get('status') == 'pass':
                    key = str(p.get('problem', '')).zfill(3)
                    normalized[key] = p
            problems = normalized

        results[lang] = {
            'metadata': {k: v for k, v in data.items() if k != 'problems' and k != 'results'},
            'problems': problems,
        }
    return results


def chart_total_time(results, output_dir):
    """Bar chart: total benchmark time per language."""
    langs = []
    times = []
    colors = []

    for lang in sorted(results.keys(),
                       key=lambda l: sum(p.get('time_ns', 0) for p in results[l]['problems'].values())):
        total_ns = sum(p.get('time_ns', 0) for p in results[lang]['problems'].values())
        total_s = total_ns / 1e9
        langs.append(LANGUAGES[lang]['short'])
        times.append(total_s)
        colors.append(LANGUAGES[lang]['color'])

    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.barh(langs, times, color=colors, edgecolor='black', linewidth=0.5)

    # Add time labels on bars
    for bar, t in zip(bars, times):
        if t < 1:
            label = f'{t*1000:.0f}ms'
        else:
            label = f'{t:.2f}s'
        ax.text(bar.get_width() + max(times) * 0.01, bar.get_y() + bar.get_height() / 2,
                label, va='center', fontsize=10)

    ax.set_xlabel('Total Time (seconds)', fontsize=12)
    ax.set_title('Project Euler Benchmark: Total Time by Language', fontsize=14, fontweight='bold')
    ax.set_xlim(0, max(times) * 1.15)
    plt.tight_layout()
    plt.savefig(output_dir / 'total_time.png', dpi=150)
    plt.close()
    print(f"  Saved total_time.png")


def chart_problem_wins(results, output_dir):
    """Bar chart: how many problems each language wins (fastest)."""
    # Find all problems present in at least 2 languages
    all_problems = set()
    for lang_data in results.values():
        all_problems.update(lang_data['problems'].keys())

    wins = {lang: 0 for lang in results}

    for prob in sorted(all_problems):
        best_lang = None
        best_time = float('inf')
        for lang, data in results.items():
            if prob in data['problems']:
                t = data['problems'][prob].get('time_ns', float('inf'))
                if t > 0 and t < best_time:
                    best_time = t
                    best_lang = lang
        if best_lang:
            wins[best_lang] += 1

    # Sort by wins
    sorted_langs = sorted(wins.keys(), key=lambda l: wins[l], reverse=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(
        [LANGUAGES[l]['short'] for l in sorted_langs],
        [wins[l] for l in sorted_langs],
        color=[LANGUAGES[l]['color'] for l in sorted_langs],
        edgecolor='black', linewidth=0.5
    )

    for bar, l in zip(bars, sorted_langs):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                str(wins[l]), ha='center', va='bottom', fontsize=11, fontweight='bold')

    ax.set_ylabel('Problems Won (Fastest)', fontsize=12)
    ax.set_title('Project Euler: Problems Won by Language', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_dir / 'problem_wins.png', dpi=150)
    plt.close()
    print(f"  Saved problem_wins.png")


def chart_source_lines(results, output_dir):
    """Bar chart: average source lines of code per language."""
    langs = []
    avg_lines = []
    colors = []

    for lang in sorted(results.keys()):
        lines = [p.get('source_lines', 0) for p in results[lang]['problems'].values() if p.get('source_lines', 0) > 0]
        if lines:
            langs.append(LANGUAGES[lang]['short'])
            avg_lines.append(sum(lines) / len(lines))
            colors.append(LANGUAGES[lang]['color'])

    if not langs:
        print("  No source_lines data available, skipping chart")
        return

    # Sort by avg lines
    sorted_idx = sorted(range(len(langs)), key=lambda i: avg_lines[i])
    langs = [langs[i] for i in sorted_idx]
    avg_lines = [avg_lines[i] for i in sorted_idx]
    colors = [colors[i] for i in sorted_idx]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(langs, avg_lines, color=colors, edgecolor='black', linewidth=0.5)

    for bar, lines in zip(bars, avg_lines):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f'{lines:.0f}', va='center', fontsize=10)

    ax.set_xlabel('Average Lines of Code per Solution', fontsize=12)
    ax.set_title('Code Verbosity by Language', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_dir / 'source_lines.png', dpi=150)
    plt.close()
    print(f"  Saved source_lines.png")


def chart_per_problem_comparison(results, output_dir):
    """Line chart: time per problem for top languages."""
    # Pick top 4 fastest languages for readability
    lang_totals = {lang: sum(p.get('time_ns', 0) for p in data['problems'].values())
                   for lang, data in results.items()}
    top_langs = sorted(lang_totals.keys(), key=lambda l: lang_totals[l])[:5]

    fig, ax = plt.subplots(figsize=(16, 6))

    for lang in top_langs:
        problems = sorted(results[lang]['problems'].keys())
        times_ms = []
        probs = []
        for p in problems:
            t = results[lang]['problems'][p].get('time_ns', 0)
            if t > 0:
                times_ms.append(t / 1e6)  # Convert to ms
                probs.append(int(p))

        ax.plot(probs, times_ms, label=LANGUAGES[lang]['short'],
                color=LANGUAGES[lang]['color'], alpha=0.7, linewidth=1.2)

    ax.set_xlabel('Problem Number', fontsize=12)
    ax.set_ylabel('Time (ms, log scale)', fontsize=12)
    ax.set_yscale('log')
    ax.set_title('Per-Problem Timing: Top 5 Languages', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / 'per_problem.png', dpi=150)
    plt.close()
    print(f"  Saved per_problem.png")


def chart_language_speedup_vs_python(results, output_dir):
    """Bar chart: median speedup of each language vs Python."""
    if 'Python' not in results:
        print("  No Python results, skipping speedup chart")
        return

    py_problems = results['Python']['problems']
    speedups = {}

    for lang, data in results.items():
        if lang == 'Python':
            continue
        ratios = []
        for prob, py_data in py_problems.items():
            py_time = py_data.get('time_ns', 0)
            if prob in data['problems'] and py_time > 0:
                lang_time = data['problems'][prob].get('time_ns', 0)
                if lang_time > 0:
                    ratios.append(py_time / lang_time)
        if ratios:
            speedups[lang] = sorted(ratios)[len(ratios) // 2]  # median

    sorted_langs = sorted(speedups.keys(), key=lambda l: speedups[l], reverse=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(
        [LANGUAGES[l]['short'] for l in sorted_langs],
        [speedups[l] for l in sorted_langs],
        color=[LANGUAGES[l]['color'] for l in sorted_langs],
        edgecolor='black', linewidth=0.5
    )

    for bar, l in zip(bars, sorted_langs):
        ax.text(bar.get_width() + max(speedups.values()) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f'{speedups[l]:.0f}x', va='center', fontsize=10)

    ax.set_xlabel('Median Speedup vs Python', fontsize=12)
    ax.set_title('How Much Faster Than Python?', fontsize=14, fontweight='bold')
    ax.set_xscale('log')
    plt.tight_layout()
    plt.savefig(output_dir / 'speedup_vs_python.png', dpi=150)
    plt.close()
    print(f"  Saved speedup_vs_python.png")


def generate_summary_table(results, output_dir):
    """Generate a markdown summary table."""
    rows = []
    for lang in sorted(results.keys(),
                       key=lambda l: sum(p.get('time_ns', 0) for p in results[l]['problems'].values())):
        data = results[lang]
        n_problems = len(data['problems'])
        total_ns = sum(p.get('time_ns', 0) for p in data['problems'].values())
        total_s = total_ns / 1e9

        lines = [p.get('source_lines', 0) for p in data['problems'].values() if p.get('source_lines', 0) > 0]
        avg_sloc = f"{sum(lines)/len(lines):.0f}" if lines else "N/A"

        compiler = data.get('metadata', {}).get('compiler', 'N/A')

        if total_s < 1:
            time_str = f"{total_s*1000:.0f}ms"
        else:
            time_str = f"{total_s:.2f}s"

        rows.append(f"| {lang} | {n_problems} | {time_str} | {avg_sloc} | {compiler} |")

    table = "| Language | Problems | Total Time | Avg SLOC | Compiler |\n"
    table += "|----------|----------|------------|----------|----------|\n"
    table += "\n".join(rows) + "\n"

    with open(output_dir / 'summary.md', 'w') as f:
        f.write("# Benchmark Summary\n\n")
        f.write(table)
    print(f"  Saved summary.md")


def main():
    parser = argparse.ArgumentParser(description='Generate benchmark charts')
    parser.add_argument('--output-dir', default='charts', help='Output directory for charts')
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading benchmark results...")
    results = load_all_results()
    print(f"  Loaded {len(results)} languages")

    if not results:
        print("No benchmark data found!")
        sys.exit(1)

    print("\nGenerating charts...")
    chart_total_time(results, output_dir)
    chart_problem_wins(results, output_dir)
    chart_source_lines(results, output_dir)
    chart_per_problem_comparison(results, output_dir)
    chart_language_speedup_vs_python(results, output_dir)
    generate_summary_table(results, output_dir)

    print(f"\nDone! Charts saved to {output_dir}/")


if __name__ == '__main__':
    main()
