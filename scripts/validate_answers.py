#!/usr/bin/env python3
"""
PE benchmark cross-validation:
  - Take C++ as canonical for problems 1-200.
  - Mark any other language's problem as fail if answer != C++'s.
  - Output: corrected per-language pass/fail counts and per-problem mismatch report.

Note: data/*.json is sanitized (no `answer` for problems >100 per public-repo
policy). Answers are read from sibling private repos' benchmark_results.json.
"""
import json
from pathlib import Path

DATA = Path("/Users/augusthill/ccdev/ProjectEuler.Benchmarks/data")
SIBLINGS = Path("/Users/augusthill/ccdev")
LANGS = ["c", "cpp", "csharp", "go", "java", "javascript", "python", "rust", "zig", "arm64"]
REPO_NAMES = {"cpp":"CPlusPlus","c":"C","csharp":"CSharp","go":"Go","java":"Java",
              "javascript":"JavaScript","python":"Python","rust":"Rust","zig":"Zig","arm64":"ARM64"}

# Load sanitized data (timings + answers for ≤100)
data = {}
for lang in LANGS:
    f = DATA / f"{lang}.json"
    if f.exists():
        data[lang] = json.load(open(f))
    else:
        print(f"  [missing] {lang}.json — skipping")

if "cpp" not in data:
    print("ERROR: cpp.json not present, cannot cross-validate.")
    raise SystemExit(1)

# Per-lang answer maps from sibling private repos
def _load_answers(lang):
    sib = SIBLINGS / f"ProjectEuler.{REPO_NAMES[lang]}" / "benchmark_results.json"
    if sib.exists():
        full = json.load(open(sib))
        return {p: v.get("answer") for p, v in full["problems"].items()
                if v.get("status") == "pass" and v.get("answer") is not None}
    # Fallback to sanitized data (≤100 only)
    return {p: v["answer"] for p, v in data.get(lang, {}).get("problems", {}).items()
            if v.get("status") == "pass" and v.get("answer") is not None}

answers = {l: _load_answers(l) for l in LANGS if l in data}
canonical = answers.get("cpp", {})

print(f"Canonical answers from C++ (sibling repo): {len(canonical)} of {len(data['cpp']['problems'])}")

# Cross-validate each language
print()
print(f"{'Lang':<10}{'Pass(reported)':>16}{'Pass(verified)':>16}{'Wrong':>8}{'No-answer':>11}")
print("-" * 65)

mismatches = {}
for lang in LANGS:
    if lang not in data:
        continue
    reported_pass = 0
    verified_pass = 0
    wrong_answer = []
    no_answer = []
    for p, v in data[lang]["problems"].items():
        if int(p) > 200:
            continue
        if v.get("status") == "pass":
            reported_pass += 1
            ans = answers.get(lang, {}).get(p)
            if ans is None:
                no_answer.append(p)
                continue
            if p not in canonical:
                # no canonical to compare; trust as pass
                verified_pass += 1
                continue
            if str(ans) == str(canonical[p]):
                verified_pass += 1
            else:
                wrong_answer.append((p, ans, canonical[p]))
    mismatches[lang] = wrong_answer
    print(f"{lang:<10}{reported_pass:>16}{verified_pass:>16}{len(wrong_answer):>8}{len(no_answer):>11}")

print()
print("=== Per-language mismatch detail ===")
for lang, mm in mismatches.items():
    if not mm:
        continue
    print(f"\n  {lang} ({len(mm)} mismatches):")
    for p, got, expect in mm[:15]:
        print(f"    P{p}: got {got}, expected {expect}")
    if len(mm) > 15:
        print(f"    ... and {len(mm) - 15} more")
