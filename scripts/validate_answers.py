#!/usr/bin/env python3
"""
PE benchmark cross-validation:
  - Take C++ as canonical for problems 1-200.
  - Mark any other language's problem as fail if answer != C++'s.
  - Output: corrected per-language pass/fail counts and per-problem mismatch report.
"""
import json
from pathlib import Path

DATA = Path("/Users/augusthill/ccdev/ProjectEuler.Benchmarks/data")
LANGS = ["c", "cpp", "csharp", "go", "java", "javascript", "python", "rust", "zig", "arm64"]

# Load all
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

# Build canonical answer map from C++
canonical = {}
for p, v in data["cpp"]["problems"].items():
    if v.get("status") == "pass" and v.get("answer") is not None:
        canonical[p] = v["answer"]

print(f"Canonical answers from C++: {len(canonical)} of {len(data['cpp']['problems'])}")

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
            ans = v.get("answer")
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
