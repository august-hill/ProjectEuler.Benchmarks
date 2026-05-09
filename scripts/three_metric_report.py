#!/usr/bin/env python3
"""Three-metric cross-language report: runtime, cold-start, source-to-answer.

Reads benchmark JSONs and reports three sums per language so the reader can
pick the metric that matches their question. Replaces the old single-number
totals that hid compile-time work (comptime / -O2 constant folding).

Inputs default to /tmp/sweep/*.json (smoke-test layout) but can be overridden.

Run: python3 three_metric_report.py [--data-dir DIR] [--output FILE]
"""

import argparse
import json
from pathlib import Path

LANG_ORDER = ["C", "CPlusPlus", "Zig", "Rust", "Go", "ARM64",
              "CSharp", "Java", "JavaScript", "Python"]
LANG_DISPLAY = {
    "C": "C", "CPlusPlus": "C++", "Zig": "Zig", "Rust": "Rust",
    "Go": "Go", "ARM64": "ARM64", "CSharp": "C#", "Java": "Java",
    "JavaScript": "JS", "Python": "Python",
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
    p = data_dir / f"{lang}.json"
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


def per_lang_totals(data):
    """Return (runtime_ns, cold_ns, compile_ns, n_pass) summed across passing problems."""
    runtime = cold = compile_t = 0
    n_pass = 0
    for entry in data["problems"].values():
        if entry.get("status") != "pass":
            continue
        runtime += entry.get("time_ns", 0)
        cold += entry.get("cold_start_ns", 0)
        compile_t += entry.get("compile_time_ns", 0)
        n_pass += 1
    return runtime, cold, compile_t, n_pass


def render(data_by_lang):
    out = ["# Three-Metric Cross-Language Report\n"]
    out.append("Reading the columns:")
    out.append("- **Runtime (warm)** — median per-problem `solve()` execution inside an already-loaded process. Pre-computed constants show as ~0.")
    out.append("- **First run** — `cold_start_ns`: the very first in-process call to `solve()`. Captures JIT warmup, lazy initialization, and runtime work that comptime/`-O2` folded out of the warm path.")
    out.append("- **Source → answer** — `compile_time_ns + cold_start_ns`: total cost from the source file to one printed answer. The honest \"how long does this language take to solve this from scratch?\" number.\n")

    out.append("## Totals across the sampled problems\n")
    out.append("| Lang | n | Σ runtime | Σ first-run | Σ source→answer |")
    out.append("|---|---:|---:|---:|---:|")

    summary = []
    for lang in LANG_ORDER:
        d = data_by_lang.get(lang)
        if not d:
            out.append(f"| {LANG_DISPLAY[lang]} | — | — | — | — |")
            continue
        runtime, cold, compile_t, n = per_lang_totals(d)
        s2a = compile_t + cold
        summary.append((lang, runtime, cold, compile_t, s2a, n))
        out.append(f"| {LANG_DISPLAY[lang]} | {n} | {fmt_time(runtime)} | {fmt_time(cold)} | {fmt_time(s2a)} |")

    out.append("\n## Comptime / constant-fold detection\n")
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

    out.append("\n## Per-problem grid\n")
    out.append("Each cell: `runtime / compile`. Sorted by problem number.\n")
    all_probs = set()
    for d in data_by_lang.values():
        all_probs.update(d["problems"].keys())
    probs = sorted(all_probs)
    header = "| # | " + " | ".join(LANG_DISPLAY[l] for l in LANG_ORDER if l in data_by_lang) + " |"
    out.append(header)
    out.append("|---|" + "|".join(["---"] * len([l for l in LANG_ORDER if l in data_by_lang])) + "|")
    for prob in probs:
        row = [prob]
        for lang in LANG_ORDER:
            d = data_by_lang.get(lang)
            if not d:
                continue
            entry = d["problems"].get(prob)
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

    data_by_lang = {}
    for lang in LANG_ORDER:
        d = load_lang(args.data_dir, lang)
        if d:
            data_by_lang[lang] = d

    md = render(data_by_lang)
    args.output.write_text(md)
    print(f"Wrote {args.output} ({len(md)} bytes)")
    print(f"Languages: {', '.join(LANG_DISPLAY[l] for l in LANG_ORDER if l in data_by_lang)}")


if __name__ == "__main__":
    main()
