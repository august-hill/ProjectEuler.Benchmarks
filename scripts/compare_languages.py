#!/usr/bin/env python3
"""
PE benchmark final report — generates the language comparison table.
Uses C++ answers as canonical (cross-validated). Reports:
  - Per-language verified-pass count, hot/cold/compile geomean and median.
  - Per-problem fastest-language counts (wins).
  - Source code size summary.

Note: data/*.json is sanitized (no `answer` for problems >100 per public-repo
policy). Answers are read from sibling private repos' benchmark_results.json
for cross-validation.
"""
import json, math, statistics
from pathlib import Path

DATA = Path("/Users/augusthill/ccdev/ProjectEuler.Benchmarks/data")
SIBLINGS = Path("/Users/augusthill/ccdev")
LANGS = ["cpp", "c", "csharp", "go", "java", "javascript", "python", "rust", "zig", "arm64"]
LABELS = {"cpp":"C++","c":"C","csharp":"C#","go":"Go","java":"Java",
          "javascript":"JS","python":"Python","rust":"Rust","zig":"Zig","arm64":"ARM64"}
REPO_NAMES = {"cpp":"CPlusPlus","c":"C","csharp":"CSharp","go":"Go","java":"Java",
              "javascript":"JavaScript","python":"Python","rust":"Rust","zig":"Zig","arm64":"ARM64"}

data = {l: json.load(open(DATA/f"{l}.json")) for l in LANGS if (DATA/f"{l}.json").exists()}

# Per-lang answer maps from sibling private repos (data/*.json is sanitized for >100).
def _load_answers(lang):
    sib = SIBLINGS / f"ProjectEuler.{REPO_NAMES[lang]}" / "benchmark_results.json"
    if sib.exists():
        full = json.load(open(sib))
        return {p: v.get("answer") for p, v in full["problems"].items()
                if v.get("status") == "pass" and v.get("answer") is not None}
    # Fallback to sanitized data (≤100 only) if sibling unavailable
    return {p: v["answer"] for p, v in data.get(lang, {}).get("problems", {}).items()
            if v.get("status") == "pass" and v.get("answer") is not None}

answers = {l: _load_answers(l) for l in LANGS if l in data}
canonical = answers.get("cpp", {})
if not any(p for p in canonical if int(p) > 100):
    print("WARNING: no canonical answers for problems >100; cross-validation limited to ≤100")

def is_verified_pass(lang, p):
    v = data[lang]["problems"].get(p, {})
    if v.get("status") != "pass": return False
    ans = answers.get(lang, {}).get(p)
    if ans is None: return False
    if p in canonical and str(ans) != str(canonical[p]): return False
    return True

def fmt_ns(x):
    if x is None: return "—"
    if x < 1000: return f"{x:.0f}ns"
    if x < 1e6: return f"{x/1000:.1f}µs"
    if x < 1e9: return f"{x/1e6:.1f}ms"
    return f"{x/1e9:.2f}s"

def stats(values):
    v = [x for x in values if x and x > 0]
    if not v: return (None, None, None)
    log = [math.log(x) for x in v]
    geomean = math.exp(sum(log)/len(log))
    return (min(v), statistics.median(v), geomean)

# Find common problem set (verified-pass everywhere) in 1-200
common = None
for lang in data:
    pass_set = {p for p in data[lang]["problems"] if 1 <= int(p) <= 200 and is_verified_pass(lang, p)}
    common = pass_set if common is None else common & pass_set

print(f"Common verified-pass set (1-200, all langs): {len(common)}")
print()

# Per-language table
print(f"{'Lang':<8}{'Pass(v)':>9}{'Hot min':>10}{'Hot med':>10}{'Hot gmean':>12}  {'Cold med':>10}{'Comp med':>10}{'RSS med':>10}{'src med':>10}")
print("-" * 100)
for lang in LANGS:
    if lang not in data: continue
    passed = sum(1 for p in data[lang]["problems"] if 1 <= int(p) <= 200 and is_verified_pass(lang, p))
    hot, cold, comp, rss, src = [], [], [], [], []
    for p in common:
        v = data[lang]["problems"].get(p, {})
        hot.append(v.get("time_ns") or 0)
        cold.append(v.get("cold_start_ns") or 0)
        comp.append(v.get("compile_time_ns") or 0)
        rss.append(v.get("peak_rss_bytes") or 0)
        src.append(v.get("source_bytes") or 0)
    h_min, h_med, h_gm = stats(hot)
    _, c_med, _ = stats(cold)
    _, p_med, _ = stats(comp)
    _, r_med, _ = stats(rss)
    _, s_med, _ = stats(src)
    print(f"{LABELS[lang]:<8}{passed:>9}{fmt_ns(h_min):>10}{fmt_ns(h_med):>10}{fmt_ns(h_gm):>12}  {fmt_ns(c_med):>10}{fmt_ns(p_med):>10}{(str(int(r_med//1024))+'KB' if r_med else '—'):>10}{(str(int(s_med))+'B' if s_med else '—'):>10}")

# Wins
print()
print("Per-problem fastest (verified-pass only, common set):")
wins = {l: 0 for l in data}
top3 = {l: 0 for l in data}
for p in common:
    times = []
    for lang in data:
        v = data[lang]["problems"].get(p, {})
        if not is_verified_pass(lang, p): continue
        t = v.get("time_ns") or 0
        if t > 0: times.append((t, lang))
    times.sort()
    if times:
        wins[times[0][1]] += 1
        for t, l in times[:3]:
            top3[l] += 1
for lang in sorted(wins, key=lambda l: -wins[l]):
    print(f"  {LABELS[lang]:<8} fastest: {wins[lang]:>3}  top-3: {top3[lang]:>3}")
