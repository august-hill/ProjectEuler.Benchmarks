#!/usr/bin/env python3
"""Three-metric cross-language report: runtime, cold-start, source-to-answer.

Reads benchmark JSONs and reports three sums per language so the reader can
pick the metric that matches their question. Replaces the old single-number
totals that hid compile-time work (comptime / -O2 constant folding).

Tier-aware (added 2026-05-22): each metric is reported per tier (Foundation /
Deep Coverage / Frontier) so a 10-lang comparison only counts problems all 10
share. Per-problem grid hides cells for langs out-of-scope for that tier.

Inputs default to /tmp/sweep/*.json (smoke-test layout) but can be overridden.

Run: python3 three_metric_report.py [--data-dir DIR] [--output FILE]
"""

import argparse
import json
import sys
from pathlib import Path

# Allow `import tiers` regardless of where this script is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tiers import (
    load_tiers, tier_for_problem, langs_in_tier, in_scope,
    tier_label, tier_problem_range, tier_range_label, TIER_ORDER,
)

# Maintained CamelCase ordering for display/legacy; tier config uses lowercase.
LANG_ORDER = ["C", "CPlusPlus", "Zig", "Rust", "Go", "ARM64",
              "CSharp", "Java", "JavaScript", "Python"]
LANG_DISPLAY = {
    "C": "C", "CPlusPlus": "C++", "Zig": "Zig", "Rust": "Rust",
    "Go": "Go", "ARM64": "ARM64", "CSharp": "C#", "Java": "Java",
    "JavaScript": "JS", "Python": "Python",
}
# CamelCase repo name → lowercase tier key
LANG_TIER_KEY = {
    "C": "c", "CPlusPlus": "cpp", "Zig": "zig", "Rust": "rust",
    "Go": "go", "ARM64": "arm64", "CSharp": "csharp", "Java": "java",
    "JavaScript": "javascript", "Python": "python",
}


def fmt_time(ns):
    if ns is None:
        return "—"
    if ns < 1_000:
        return f"{ns} ns"
    if ns < 1_000_000:
        return f"{ns/1000:.1f} µs"
    if ns < 1_000_000_000:
        return f"{ns/1_000_000:.1f} ms"
    return f"{ns/1_000_000_000:.2f} s"


def load_lang(data_dir, lang):
    """Try CamelCase filename first (legacy /tmp/sweep layout), then fall back
    to lowercase via LANG_TIER_KEY (production data/ layout uses ``cpp.json``,
    ``arm64.json``, etc.)."""
    for candidate in (f"{lang}.json", f"{LANG_TIER_KEY[lang]}.json"):
        p = data_dir / candidate
        if p.exists():
            with open(p) as f:
                return json.load(f)
    return None


def per_lang_totals(data, prob_filter=None):
    """Return (runtime_ns, cold_ns, compile_ns, n_pass) summed across passing problems.

    ``prob_filter`` is an optional callable ``int -> bool``: when set, only
    problems whose integer key passes the filter contribute to the totals.
    Used to scope totals per-tier.
    """
    runtime = cold = compile_t = 0
    n_pass = 0
    for prob, entry in data["problems"].items():
        if entry.get("status") != "pass":
            continue
        if prob_filter is not None and not prob_filter(int(prob)):
            continue
        runtime += entry.get("time_ns", 0)
        cold += entry.get("cold_start_ns", 0)
        compile_t += entry.get("compile_time_ns", 0)
        n_pass += 1
    return runtime, cold, compile_t, n_pass


def tier_totals_table(tier_key, tiers, data_by_lang):
    """Render one tier's totals table; only in-scope langs appear."""
    lo, hi = tier_problem_range(tier_key, tiers)
    hi_eff = hi if hi is not None else 10**9
    tier_langs_lower = set(langs_in_tier(tier_key, tiers))
    in_tier_repo_names = [l for l in LANG_ORDER if LANG_TIER_KEY[l] in tier_langs_lower]

    out = []
    out.append(f"### {tier_label(tier_key, tiers)} — problems {tier_range_label(tier_key, tiers)}\n")
    out.append(f"_{tiers[tier_key]['description']}_\n")
    out.append("| Lang | n | Σ runtime | Σ first-run | Σ source→answer |")
    out.append("|---|---:|---:|---:|---:|")
    pf = lambda p: lo <= p <= hi_eff
    for lang in in_tier_repo_names:
        d = data_by_lang.get(lang)
        if not d:
            out.append(f"| {LANG_DISPLAY[lang]} | — | — | — | — |")
            continue
        runtime, cold, compile_t, n = per_lang_totals(d, prob_filter=pf)
        s2a = compile_t + cold
        out.append(f"| {LANG_DISPLAY[lang]} | {n} | {fmt_time(runtime)} | "
                   f"{fmt_time(cold)} | {fmt_time(s2a)} |")
    return "\n".join(out) + "\n"


def render(data_by_lang, tiers):
    out = ["# Three-Metric Cross-Language Report\n"]
    out.append("Reading the columns:")
    out.append("- **Runtime (warm)** — median per-problem `solve()` execution inside an already-loaded process. Pre-computed constants show as ~0.")
    out.append("- **First run** — `cold_start_ns`: the very first in-process call to `solve()`. Captures JIT warmup, lazy initialization, and runtime work that comptime/`-O2` folded out of the warm path.")
    out.append("- **Source → answer** — `compile_time_ns + cold_start_ns`: total cost from the source file to one printed answer. The honest \"how long does this language take to solve this from scratch?\" number.")
    out.append("")
    out.append("Totals are split by **tier** so cross-language sums only count "
               "problems every in-tier lang shares. See `data/tiers.json` for "
               "definitions; historical 201+ exceptions in foundation-only "
               "langs do NOT count for tier totals.\n")

    # Per-tier totals
    out.append("## Totals by tier\n")
    for tier_key in TIER_ORDER:
        if tier_key not in tiers:
            continue
        out.append(tier_totals_table(tier_key, tiers, data_by_lang))

    # Combined totals across all problems (kept for continuity)
    out.append("## Combined totals across all benched problems\n")
    out.append("Includes historical exceptions; useful only as a per-language workload sanity check.\n")
    out.append("| Lang | n | Σ runtime | Σ first-run | Σ source→answer |")
    out.append("|---|---:|---:|---:|---:|")
    for lang in LANG_ORDER:
        d = data_by_lang.get(lang)
        if not d:
            out.append(f"| {LANG_DISPLAY[lang]} | — | — | — | — |")
            continue
        runtime, cold, compile_t, n = per_lang_totals(d)
        s2a = compile_t + cold
        out.append(f"| {LANG_DISPLAY[lang]} | {n} | {fmt_time(runtime)} | "
                   f"{fmt_time(cold)} | {fmt_time(s2a)} |")
    out.append("")

    # Comptime detection — independent of tier
    out.append("## Comptime / constant-fold detection\n")
    out.append("Problems where `time_ns < 100` AND `compile_time_ns > 1ms` — the compiler did the work.\n")
    out.append("| Lang | # comptime'd | example problems |")
    out.append("|---|---:|---|")
    for lang in LANG_ORDER:
        d = data_by_lang.get(lang)
        if not d:
            continue
        comptimed = []
        for prob, entry in d["problems"].items():
            if entry.get("status") != "pass":
                continue
            if entry.get("time_ns", 999) < 100 and entry.get("compile_time_ns", 0) > 1_000_000:
                comptimed.append(prob)
        if comptimed:
            sample = ", ".join(sorted(comptimed)[:8])
            out.append(f"| {LANG_DISPLAY[lang]} | {len(comptimed)} | {sample} |")

    # Per-problem grid — tier-scoped cells
    out.append("\n## Per-problem grid\n")
    out.append("Each cell: `runtime / compile`. Sorted by problem number. "
               "`⬛` marks cells where a lang is out-of-scope for that problem's tier.\n")
    all_probs = set()
    for d in data_by_lang.values():
        all_probs.update(d["problems"].keys())
    probs = sorted(all_probs, key=lambda p: int(p))
    header_langs = [l for l in LANG_ORDER if l in data_by_lang]
    header = "| # | " + " | ".join(LANG_DISPLAY[l] for l in header_langs) + " |"
    out.append(header)
    out.append("|---|" + "|".join(["---"] * len(header_langs)) + "|")
    for prob in probs:
        row = [prob]
        prob_int = int(prob)
        for lang in header_langs:
            d = data_by_lang[lang]
            entry = d["problems"].get(prob)
            tier_key = LANG_TIER_KEY[lang]
            if not in_scope(tier_key, prob_int, tiers):
                row.append("⬛")
                continue
            if not entry or entry.get("status") != "pass":
                row.append("—")
                continue
            t = fmt_time(entry.get("time_ns", 0))
            c = fmt_time(entry.get("compile_time_ns", 0))
            row.append(f"{t} / {c}")
        out.append("| " + " | ".join(row) + " |")

    return "\n".join(out) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default="/tmp/sweep", type=Path)
    p.add_argument("--output", default="/tmp/sweep/REPORT.md", type=Path)
    args = p.parse_args()

    tiers = load_tiers()
    data_by_lang = {}
    for lang in LANG_ORDER:
        d = load_lang(args.data_dir, lang)
        if d:
            data_by_lang[lang] = d

    md = render(data_by_lang, tiers)
    args.output.write_text(md)
    print(f"Wrote {args.output} ({len(md)} bytes)")
    print(f"Languages: {', '.join(LANG_DISPLAY[l] for l in LANG_ORDER if l in data_by_lang)}")


if __name__ == "__main__":
    main()
