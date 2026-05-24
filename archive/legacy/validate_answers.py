#!/usr/bin/env python3
"""
PE benchmark cross-validation against C++ canonical.

Two modes:

  Default (full report) — no args:
    Loads all 10 languages' data and answers, prints per-language pass/fail
    counts and per-problem mismatch detail. Always exits 0.

  Strict (gate mode) — --lang LANG --problems N1,N2 --strict:
    Filters to one language and a comma-separated problem list. Exits 1 if any
    listed problem has a wrong answer relative to C++ canonical. Used as gate
    #1 by lang_repo_post_commit.sh before staging in the public repo.

Note: data/*.json is sanitized (no `answer` for problems >100 per public-repo
policy). Answers are read from sibling private repos' benchmark_results.json.
"""
import argparse
import json
import sys
from pathlib import Path

DATA = Path("/Users/augusthill/ccdev/ProjectEuler.Benchmarks/data")
SIBLINGS = Path("/Users/augusthill/ccdev")
LANGS = ["c", "cpp", "csharp", "go", "java", "javascript", "python", "rust", "zig", "arm64"]
REPO_NAMES = {"cpp":"CPlusPlus","c":"C","csharp":"CSharp","go":"Go","java":"Java",
              "javascript":"JavaScript","python":"Python","rust":"Rust","zig":"Zig","arm64":"ARM64"}


def _load_data():
    """Load each language's sanitized data/{lang}.json (skip missing)."""
    data = {}
    for lang in LANGS:
        f = DATA / f"{lang}.json"
        if f.exists():
            data[lang] = json.load(open(f))
    return data


def _load_answers(lang, data):
    """Build {problem_key: answer} map for one language.

    Prefers the sibling private repo's benchmark_results.json (full answer set
    for problems >100). Falls back to sanitized public data (only ≤100).
    """
    sib = SIBLINGS / f"ProjectEuler.{REPO_NAMES[lang]}" / "benchmark_results.json"
    if sib.exists():
        full = json.load(open(sib))
        return {p: v.get("answer") for p, v in full["problems"].items()
                if v.get("status") == "pass" and v.get("answer") is not None}
    return {p: v["answer"] for p, v in data.get(lang, {}).get("problems", {}).items()
            if v.get("status") == "pass" and v.get("answer") is not None}


def _normalize_keys(problems_csv, answer_map):
    """User may pass '70' or '070'; data is zero-padded. Try both."""
    out = []
    for raw in problems_csv.split(","):
        raw = raw.strip()
        if not raw:
            continue
        candidates = [raw, raw.lstrip("0") or "0", f"{int(raw):03d}" if raw.isdigit() else raw]
        for c in candidates:
            if c in answer_map:
                out.append(c)
                break
        else:
            out.append(raw)
    return out


def run_strict(lang, problems_csv):
    """Strict gate: exit 1 if any specified problem mismatches C++ canonical."""
    if lang not in LANGS:
        print(f"validate_answers.py [strict]: unknown lang '{lang}'", file=sys.stderr)
        return 1
    data = _load_data()
    if "cpp" not in data:
        print("validate_answers.py [strict]: cpp.json not present, cannot validate", file=sys.stderr)
        return 1

    canonical = _load_answers("cpp", data)
    if lang == "cpp":
        # C++ is the canonical itself — nothing to validate against
        print(f"validate_answers.py [strict]: lang=cpp is canonical, skipping", file=sys.stderr)
        return 0
    lang_answers = _load_answers(lang, data)

    requested = _normalize_keys(problems_csv, lang_answers)
    mismatches = []
    no_lang_answer = []
    no_canonical = []
    for p in requested:
        got = lang_answers.get(p)
        if got is None:
            no_lang_answer.append(p)
            continue
        expect = canonical.get(p)
        if expect is None:
            no_canonical.append(p)
            continue
        if str(got) != str(expect):
            mismatches.append((p, got, expect))

    if mismatches:
        print(f"validate_answers.py [strict]: {len(mismatches)} answer mismatch(es) in {lang}", file=sys.stderr)
        for p, got, expect in mismatches:
            print(f"  p{p}: got={got!r} expected={expect!r}", file=sys.stderr)
        return 1

    summary = [f"validate_answers.py [strict]: {lang} ok ({len(requested)} requested)"]
    if no_lang_answer:
        summary.append(f"  no answer in lang repo (likely status!=pass or new): {no_lang_answer}")
    if no_canonical:
        summary.append(f"  no canonical (C++ hasn't solved): {no_canonical}")
    print("\n".join(summary))
    return 0


def run_full_report():
    """Default mode: print full cross-validation report. Always exits 0."""
    data = _load_data()
    for lang in LANGS:
        if lang not in data:
            print(f"  [missing] {lang}.json — skipping")

    if "cpp" not in data:
        print("ERROR: cpp.json not present, cannot cross-validate.")
        return 1

    answers = {l: _load_answers(l, data) for l in LANGS if l in data}
    canonical = answers.get("cpp", {})

    print(f"Canonical answers from C++ (sibling repo): {len(canonical)} of {len(data['cpp']['problems'])}")
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
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true", help="exit 1 on any mismatch (gate mode)")
    ap.add_argument("--lang", help="language key for strict mode")
    ap.add_argument("--problems", help="comma-separated problem keys for strict mode")
    args = ap.parse_args()

    if args.strict:
        if not args.lang or not args.problems:
            ap.error("--strict requires --lang and --problems")
        return run_strict(args.lang, args.problems)
    return run_full_report()


if __name__ == "__main__":
    sys.exit(main())
