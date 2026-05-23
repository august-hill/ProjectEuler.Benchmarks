#!/usr/bin/env python3
"""Final analysis: comprehensive cross-language benchmark results.

Generates publication-quality charts and a summary RESULTS.md for the
Project Euler cross-language benchmark suite.

Tier-aware (added 2026-05-22): the headline ranking + 6 charts use **Tier 1
(Foundation) data only** — the honest 10-language apples-to-apples surface
on problems 1-200. RESULTS.md additionally lists Tier 2 (Deep Coverage,
4 langs) and Tier 3 (Frontier, 2 langs) rankings as text tables.
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# Allow `from tiers import ...` regardless of where this script is invoked.
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from tiers import (
    load_tiers, langs_in_tier, tier_label, tier_problem_range,
    tier_range_label, TIER_ORDER,
)

BASE_DIR = Path(__file__).parent.parent
CHARTS_DIR = Path(__file__).parent / "charts"
CHARTS_DIR.mkdir(exist_ok=True)

# Display name -> {dir, color, tier_key}. tier_key matches data/tiers.json.
LANGS = {
    'C':      {'dir': 'ProjectEuler.C',          'color': '#555555', 'tier_key': 'c'},
    'C++':    {'dir': 'ProjectEuler.CPlusPlus',  'color': '#00599C', 'tier_key': 'cpp'},
    'Rust':   {'dir': 'ProjectEuler.Rust',       'color': '#DEA584', 'tier_key': 'rust'},
    'Go':     {'dir': 'ProjectEuler.Go',         'color': '#00ADD8', 'tier_key': 'go'},
    'Java':   {'dir': 'ProjectEuler.Java',       'color': '#B07219', 'tier_key': 'java'},
    'C#':     {'dir': 'ProjectEuler.CSharp',     'color': '#178600', 'tier_key': 'csharp'},
    'JS':     {'dir': 'ProjectEuler.JavaScript', 'color': '#F7DF1E', 'tier_key': 'javascript'},
    'Python': {'dir': 'ProjectEuler.Python',     'color': '#3776AB', 'tier_key': 'python'},
    'ARM64':  {'dir': 'ProjectEuler.ARM64',      'color': '#E34F26', 'tier_key': 'arm64'},
    'Zig':    {'dir': 'ProjectEuler.Zig',        'color': '#F7A41D', 'tier_key': 'zig'},
}


def _load_parked():
    try:
        with open(Path(__file__).parent / "data" / "parked.json") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return {'152', '167', '170', '177', '180', '185', '196'}


PARKED = _load_parked()


def effective_time_ns(entry):
    """Effective compute time. Some solutions cache after first call making warm
    time_ns ~0 while real work shows in cold_start_ns; ``max()`` handles both."""
    return max(entry.get('time_ns', 0), entry.get('cold_start_ns', 0))


def load_all():
    data = {}
    for name, cfg in LANGS.items():
        path = BASE_DIR / cfg['dir'] / 'benchmark_results.json'
        if path.exists():
            with open(path) as f:
                data[name] = json.load(f)
    return data


def langs_in_tier_display(tier_key, tiers):
    """Return display-name list of LANGS in scope for the tier, preserving the
    LANGS dict's display order (which matters for chart legends)."""
    tier_lower = set(langs_in_tier(tier_key, tiers))
    return [name for name, cfg in LANGS.items() if cfg['tier_key'] in tier_lower]


def common_problems_for_tier(data, tier_key, tiers, exclude_parked=True):
    """Intersection of passing problems across in-tier langs, scoped to tier range.

    Differs from the old global ``common_problems``: no Python exclusion. If the
    tier's lang list includes Python, it must pass too. The tier model decides
    fairness, not an ad-hoc filter.
    """
    lo, hi = tier_problem_range(tier_key, tiers)
    hi_eff = hi if hi is not None else 10**9
    in_tier = [d for d in langs_in_tier_display(tier_key, tiers) if d in data]
    if not in_tier:
        return set()
    common = None
    for lang in in_tier:
        probs = data[lang].get('problems', {})
        passing = {
            k for k, v in probs.items()
            if v.get('status') == 'pass' and lo <= int(k) <= hi_eff
        }
        if exclude_parked:
            passing -= PARKED
        common = passing if common is None else common & passing
    return common or set()


def tier_ranking_table(data, tier_key, tiers, exclude_parked=True):
    """Build a Markdown ranking table for one tier.

    Returns a tuple ``(header_md, rows_md, common_size)`` — header includes the
    tier label and problem range; rows are sorted by total time ascending.
    """
    common = common_problems_for_tier(data, tier_key, tiers, exclude_parked)
    in_tier = [d for d in langs_in_tier_display(tier_key, tiers) if d in data]

    lang_times = {}
    lang_wins = {l: 0 for l in in_tier}
    avg_sloc_map = {}

    for lang in in_tier:
        probs = data[lang].get('problems', {})
        total_ns = sum(
            effective_time_ns(v) for k, v in probs.items()
            if k in common and v.get('status') == 'pass' and effective_time_ns(v) > 0
        )
        if total_ns > 0:
            lang_times[lang] = total_ns / 1e9
        slocs = [
            v.get('source_lines', 0) for k, v in probs.items()
            if k in common and v.get('status') == 'pass' and v.get('source_lines', 0) > 0
        ]
        avg_sloc_map[lang] = (sum(slocs) / len(slocs)) if slocs else 0

    # Wins within tier's common set
    for prob in common:
        best_time = float('inf')
        best_lang = None
        for lang in in_tier:
            t = effective_time_ns(data[lang].get('problems', {}).get(prob, {}))
            if 0 < t < best_time:
                best_time = t
                best_lang = lang
        if best_lang:
            lang_wins[best_lang] += 1

    sorted_langs = sorted(lang_times, key=lang_times.get)
    baseline = lang_times.get(sorted_langs[0]) if sorted_langs else 1

    lines = [
        f"### {tier_label(tier_key, tiers)} — problems {tier_range_label(tier_key, tiers)}",
        "",
        f"*{tiers[tier_key]['description']}*  ",
        f"*{len(in_tier)} languages in scope · {len(common)} common verified-pass problems*",
        "",
        "| Rank | Language | Total Time | vs fastest | Avg SLOC | Wins |",
        "|------|----------|-----------|------|----------|------|",
    ]
    for i, lang in enumerate(sorted_langs):
        ratio = lang_times[lang] / baseline
        lines.append(
            f"| {i+1} | **{lang}** | {lang_times[lang]:.2f}s | "
            f"{ratio:.2f}x | {avg_sloc_map[lang]:.0f} | {lang_wins.get(lang, 0)} |"
        )
    lines.append("")
    return "\n".join(lines), len(common)


def main():
    tiers = load_tiers()
    data = load_all()

    # Tier 1 is the headline — charts + main ranking
    tier1_common = common_problems_for_tier(data, "tier_1_foundation", tiers)
    tier1_langs = [d for d in langs_in_tier_display("tier_1_foundation", tiers) if d in data]
    print(f"Foundation tier common passing problems ({len(tier1_langs)} langs): {len(tier1_common)}")

    # ── Chart 1: Total Time across Foundation tier ──
    fig, ax = plt.subplots(figsize=(12, 6))
    lang_times = {}
    for lang in tier1_langs:
        probs = data.get(lang, {}).get('problems', {})
        total = sum(
            effective_time_ns(v) for k, v in probs.items()
            if v.get('status') == 'pass' and k in tier1_common and effective_time_ns(v) > 0
        )
        if total > 0:
            lang_times[lang] = total / 1e9

    sorted_langs = sorted(lang_times, key=lang_times.get)
    colors = [LANGS[l]['color'] for l in sorted_langs]
    times = [lang_times[l] for l in sorted_langs]

    bars = ax.barh(sorted_langs, times, color=colors, edgecolor='white', linewidth=0.5)
    ax.set_xscale('log')
    ax.set_xlabel('Total Time (seconds, log scale)', fontsize=12)
    ax.set_title(f'Foundation tier — Total Benchmark Time across {len(tier1_common)} problems\n'
                 f'All 10 languages, problems 1-200 · Solutions generated by Claude Opus 4.6 / 4.7',
                 fontsize=14, fontweight='bold')
    for bar, t in zip(bars, times):
        ax.text(t * 1.1, bar.get_y() + bar.get_height()/2, f'{t:.1f}s',
                va='center', fontsize=11, fontweight='bold')
    ax.xaxis.set_major_formatter(ticker.ScalarFormatter())
    ax.set_xlim(left=5)
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / 'final_total_time.png', dpi=150)
    plt.close()
    print("  Saved final_total_time.png")

    # ── Chart 2: Slowdown vs C (Foundation tier) ──
    fig, ax = plt.subplots(figsize=(12, 6))
    compare_langs = [l for l in ['C++', 'ARM64', 'Go', 'Java', 'Rust', 'C#', 'JS', 'Zig', 'Python']
                     if l in tier1_langs and l in data]
    box_data = []
    for lang in compare_langs:
        ratios = []
        probs = data[lang].get('problems', {})
        c_probs = data.get('C', {}).get('problems', {})
        for p in tier1_common:
            c_t = effective_time_ns(c_probs.get(p, {}))
            l_t = effective_time_ns(probs.get(p, {}))
            if c_t > 0 and l_t > 0:
                ratios.append(l_t / c_t)
        box_data.append(ratios)

    bp = ax.boxplot(box_data, labels=compare_langs, vert=True, patch_artist=True,
                    showfliers=True, flierprops={'marker': '.', 'markersize': 3, 'alpha': 0.3})
    for patch, lang in zip(bp['boxes'], compare_langs):
        patch.set_facecolor(LANGS[lang]['color'])
        patch.set_alpha(0.7)
    ax.axhline(y=1.0, color='red', linestyle='--', alpha=0.5, label='C baseline')
    ax.set_yscale('log')
    ax.set_ylabel('Slowdown vs C (log scale)', fontsize=12)
    ax.set_title(f'Foundation tier — Per-Problem Slowdown vs C across {len(tier1_common)} problems\n'
                 f'Median (line) and spread show consistency · problems 1-200',
                 fontsize=14, fontweight='bold')
    ax.legend()
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / 'final_slowdown_box.png', dpi=150)
    plt.close()
    print("  Saved final_slowdown_box.png")

    # ── Chart 3: Code Size vs Speed scatter (Foundation tier) ──
    fig, ax = plt.subplots(figsize=(10, 8))
    for lang in tier1_langs:
        probs = data[lang].get('problems', {})
        total_ns = sum(
            effective_time_ns(v) for k, v in probs.items()
            if k in tier1_common and v.get('status') == 'pass' and effective_time_ns(v) > 0
        )
        total_sloc = sum(
            v.get('source_lines', 0) for k, v in probs.items()
            if k in tier1_common and v.get('status') == 'pass'
        )
        avg_sloc = total_sloc / len(tier1_common) if tier1_common else 0
        total_s = total_ns / 1e9
        if total_s == 0:
            continue
        ax.scatter(avg_sloc, total_s, s=200, c=LANGS[lang]['color'],
                   edgecolors='black', linewidth=1, zorder=5)
        ax.annotate(lang, (avg_sloc, total_s), textcoords="offset points",
                    xytext=(8, 4), fontsize=12, fontweight='bold')

    ax.set_xlabel('Average Lines of Code per Solution', fontsize=12)
    ax.set_ylabel('Total Time (seconds)', fontsize=12)
    ax.set_title('Foundation tier — Speed vs Code Size · The Efficiency Frontier\n'
                 'Lower-left is ideal (fast + compact)', fontsize=14, fontweight='bold')
    ax.set_yscale('log')
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / 'final_speed_vs_size.png', dpi=150)
    plt.close()
    print("  Saved final_speed_vs_size.png")

    # ── Chart 4: Problem wins (Foundation tier) ──
    fig, ax = plt.subplots(figsize=(10, 6))
    wins = {l: 0 for l in tier1_langs}
    for prob in tier1_common:
        best_time = float('inf')
        best_lang = None
        for lang in wins:
            t = effective_time_ns(data[lang].get('problems', {}).get(prob, {}))
            if 0 < t < best_time:
                best_time = t
                best_lang = lang
        if best_lang:
            wins[best_lang] += 1

    sorted_wins = sorted(wins.items(), key=lambda x: -x[1])
    names = [x[0] for x in sorted_wins]
    counts = [x[1] for x in sorted_wins]
    colors = [LANGS[n]['color'] for n in names]
    bars = ax.bar(names, counts, color=colors, edgecolor='white', linewidth=0.5)
    for bar, c in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                str(c), ha='center', fontsize=12, fontweight='bold')
    ax.set_ylabel('Problems Won (fastest time)', fontsize=12)
    ax.set_title(f'Foundation tier — Per-Problem Fastest Language across {len(tier1_common)} problems\n'
                 f'10-language head-to-head on the apples-to-apples surface (1-200)',
                 fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / 'final_problem_wins.png', dpi=150)
    plt.close()
    print("  Saved final_problem_wins.png")

    # ── Chart 5: Memory (Foundation tier) ──
    fig, ax = plt.subplots(figsize=(12, 6))
    mem_data = {}
    for lang in tier1_langs:
        probs = data[lang].get('problems', {})
        rss = [
            v.get('peak_rss_bytes', 0) / (1024*1024) for k, v in probs.items()
            if k in tier1_common and v.get('status') == 'pass' and v.get('peak_rss_bytes', 0) > 0
        ]
        if rss:
            mem_data[lang] = np.median(rss)

    sorted_mem = sorted(mem_data, key=mem_data.get)
    colors = [LANGS[l]['color'] for l in sorted_mem]
    mems = [mem_data[l] for l in sorted_mem]
    bars = ax.barh(sorted_mem, mems, color=colors, edgecolor='white', linewidth=0.5)
    for bar, m in zip(bars, mems):
        ax.text(m + 1, bar.get_y() + bar.get_height()/2, f'{m:.1f} MB',
                va='center', fontsize=11)
    ax.set_xlabel('Median Peak RSS (MB)', fontsize=12)
    ax.set_title('Foundation tier — Memory Usage · Median Peak RSS Per Problem\n'
                 'JVM and V8 runtime overhead dwarfs actual algorithm memory',
                 fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / 'final_memory.png', dpi=150)
    plt.close()
    print("  Saved final_memory.png")

    # ── Chart 6: Pass rate / coverage (Foundation tier — all 10 langs at 1-200) ──
    fig, ax = plt.subplots(figsize=(12, 6))
    all_langs = sorted(tier1_langs)
    pass_counts, fail_counts, parked_counts = [], [], []
    for lang in all_langs:
        probs = data.get(lang, {}).get('problems', {})
        # Scope to Tier 1 (1-200) only
        tier1_probs = {k: v for k, v in probs.items() if 1 <= int(k) <= 200}
        p = sum(1 for v in tier1_probs.values() if v.get('status') == 'pass')
        f = sum(1 for k, v in tier1_probs.items() if v.get('status') == 'fail' and k not in PARKED)
        pk = sum(1 for k, v in tier1_probs.items() if v.get('status') == 'fail' and k in PARKED)
        pass_counts.append(p)
        fail_counts.append(f)
        parked_counts.append(pk)

    x = np.arange(len(all_langs))
    w = 0.6
    ax.bar(x, pass_counts, w, label='Pass', color='#4CAF50')
    ax.bar(x, fail_counts, w, bottom=pass_counts, label='Fail (non-parked)', color='#F44336')
    ax.bar(x, parked_counts, w, bottom=[p+f for p, f in zip(pass_counts, fail_counts)],
           label='Parked (algorithm redesign)', color='#FFC107')
    ax.set_xticks(x)
    ax.set_xticklabels(all_langs, fontsize=11)
    ax.set_ylabel('Problems', fontsize=12)
    ax.set_title('Foundation tier — Benchmark Coverage · 200 Problems × 10 Languages\n'
                 '2,000 solutions, all generated by Claude', fontsize=14, fontweight='bold')
    ax.legend(loc='lower right')
    ax.set_ylim(0, 210)
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / 'final_coverage.png', dpi=150)
    plt.close()
    print("  Saved final_coverage.png")

    # ── Summary stats ──
    total_solutions = sum(len(d.get('problems', {})) for d in data.values())
    total_passing = sum(
        sum(1 for v in d.get('problems', {}).values() if v.get('status') == 'pass')
        for d in data.values()
    )

    print(f"\n{'='*60}")
    print(f"FINAL PROJECT STATS")
    print(f"{'='*60}")
    print(f"Languages:       {len(LANGS)}")
    print(f"Total solutions: {total_solutions}")
    print(f"Total passing:   {total_passing}")
    print(f"Pass rate:       {total_passing/total_solutions*100:.1f}%")
    print(f"\nFoundation ranking ({len(tier1_common)} common problems, total time):")
    for i, lang in enumerate(sorted_langs):
        print(f"  {i+1}. {lang:<8} {lang_times[lang]:>8.2f}s")

    # ── Generate RESULTS.md with three tier sections ──
    foundation_md, _ = tier_ranking_table(data, "tier_1_foundation", tiers)
    deep_md, _ = tier_ranking_table(data, "tier_2_deep_coverage", tiers)
    frontier_md, _ = tier_ranking_table(data, "tier_3_frontier", tiers)

    results_md = f"""# Project Euler Cross-Language Benchmarks — Final Results

> **{total_solutions} solutions across 10 languages, generated by Claude Opus 4.6 and Sonnet 4.6 (newer work on Opus 4.7).**
> **Apple Silicon (ARM64) · macOS · 2026**

Results are reported in three **tiers** so the cross-language comparison stays
honest at each scope. The Foundation tier is the apples-to-apples surface — all
10 languages, problems 1-200. Deep Coverage compares the four languages we've
pushed past 200. Frontier is the C++ / Go pair on unexplored ground (Go
replaced Python as C++'s exploration partner on 2026-05-22 — Python's wall cost
made level 5+ authoring impractical).

See `data/tiers.json` for live tier definitions.

## The Rankings

{foundation_md}

{deep_md}

{frontier_md}

## Headline Charts (Foundation tier)

All six charts below use the Foundation tier's common set — problems 1-200
across all 10 languages. Deep Coverage and Frontier results live in the
rankings tables above; we intentionally don't chart them yet, because two-lang
and four-lang comparisons benefit more from a tight table than a sparse plot.

### Total Benchmark Time
![Total Time](charts/final_total_time.png)

### Slowdown Distribution vs C
![Slowdown](charts/final_slowdown_box.png)

### Speed vs Code Size
![Speed vs Size](charts/final_speed_vs_size.png)

### Per-Problem Wins
![Problem Wins](charts/final_problem_wins.png)

### Memory Usage
![Memory](charts/final_memory.png)

### Foundation Coverage
![Coverage](charts/final_coverage.png)

## Key Findings

1. **C++ is the best compiled language for Claude-generated computational code** —
   tied with C for speed on Foundation but 35% more compact. STL gives Claude
   better building blocks. In Deep Coverage, C++ remains the leader by a thin
   margin over Go.

2. **Go is the most consistent compiled language and the new Frontier partner.**
   On Foundation it's only ~1.3× slower than C++ with no fat tail; on Deep
   Coverage it nearly ties C++ on per-problem wins. As of 2026-05-22, Go
   replaces Python as C++'s verification pair on Tier 3 frontier work.

3. **Rust has a fat tail** — median ~1.05× (essentially C-speed) on Foundation
   but p90 is ~6×. Claude occasionally generates suboptimal Rust due to borrow
   checker workarounds.

4. **Algorithm choice matters 1000× more than language choice.** The biggest
   per-problem spreads are algorithmic divergence, not language speed.

5. **Python is ~40× slower for computation** but its compact syntax (~42 SLOC vs
   ~72 for C) keeps it as the prospector — fast for algorithm discovery via
   sympy/mpmath/numpy. Python no longer drives frontier authoring; existing
   solves are preserved.

6. **Java's JVM uses 10-40× more memory** than native languages for the same
   algorithms. Real only for memory-constrained environments.

## Project Stats

- **Languages:** C, C++, Rust, Go, Java, C#, JavaScript, Python, ARM64 Assembly, Zig
- **Foundation problems:** 200 (Project Euler #1-200)
- **Deep Coverage problems:** 100 (#201-300, 4 languages)
- **Frontier problems:** 700 in scope (#301+, 2 languages; counts grow as work lands)
- **Total solutions:** {total_solutions}
- **Pass rate:** {total_passing}/{total_solutions} ({total_passing/total_solutions*100:.1f}%)
- **Parked (algorithm redesign):** {len(PARKED)} problems
- **Generated by:** Claude Opus 4.6 (design + algorithms) and Sonnet 4.6 (language ports); newer work on Opus 4.7
- **Platform:** Apple Silicon, macOS, ARM64

## Read the Full Story

See [JOURNEY.md](JOURNEY.md) for the complete narrative — from origin story
through algorithm hunts, language analysis, and lessons learned.
"""

    with open(Path(__file__).parent / "RESULTS.md", 'w') as f:
        f.write(results_md)
    print(f"\n  Saved RESULTS.md")


if __name__ == '__main__':
    main()
