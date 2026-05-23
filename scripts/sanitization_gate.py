#!/usr/bin/env python3
"""
Sanitization gate for ProjectEuler.Benchmarks (the public repo).

Two checks against staged content:
  1. data/*.json: NO `"answer": <value>` for ANY problem, regardless of
     number.  (Policy tightened 2026-05-23: previously the rule allowed
     answers ≤100 per PE's publishing rule, but public bench data is about
     timings — including answers added zero value while enlarging the
     leak surface.  Narrative discussion of ≤100 answers in MDs / JOURNEY
     stays allowed by the rule below.)
  2. MDs / scripts: no forbidden technique term in proximity (same line) to a
     problem reference (p<N> or problem_<N>) where N > 100.

Only staged HUNKS (the +/- lines in `git diff --cached`) are checked, so
pre-existing legitimate mentions in JOURNEY.md / README.md don't trigger
false positives — only new additions pairing a problem number >100 with a
forbidden term get flagged.

Exit 0 = clean; exit 1 = violation (commit rejected).

Override: `git commit --no-verify` bypasses this. Discouraged — see
feedback_pe_data_sanitization.md (auto-memory) for the 2026-05-09 incident.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TERMS_FILE = REPO / "scripts" / "forbidden_terms.txt"

PROBLEM_REF = re.compile(r"\b(?:p|problem_)(\d+)\b", re.IGNORECASE)


def load_forbidden_terms():
    if not TERMS_FILE.exists():
        return []
    terms = []
    for line in TERMS_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        terms.append(line.lower())
    return terms


def staged_files():
    """Files staged for commit (added or modified)."""
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
        capture_output=True, text=True, check=True,
    )
    return [Path(REPO / f) for f in out.stdout.splitlines() if f]


def staged_hunks(path):
    """Return added (+) lines from the staged diff for one file."""
    rel = path.relative_to(REPO)
    out = subprocess.run(
        ["git", "diff", "--cached", "-U0", "--", str(rel)],
        capture_output=True, text=True, check=True,
    )
    added = []
    for line in out.stdout.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
    return added


def check_json_answer_leak(path):
    """For data/*.json: NO `answer` field for ANY problem.

    Skips data/private/ (that path is gitignored and intentionally holds
    full answer values for local verification + debugging).
    """
    p = str(path)
    if not p.endswith(".json"):
        return []
    if "data/" not in p:
        return []
    if "data/private/" in p:
        return []  # gitignored; full data with answers lives here on purpose
    try:
        obj = json.loads(path.read_text())
    except (json.JSONDecodeError, ValueError):
        return []  # Not our concern (e.g., parked.json is a list, not problems)
    if not isinstance(obj, dict) or "problems" not in obj:
        return []
    leaked = []
    for k, v in obj["problems"].items():
        if isinstance(v, dict) and v.get("answer") is not None:
            leaked.append(f"  {path.name}: p{k} has answer field (NEVER allowed in public data)")
    return leaked


def check_proximity(path, terms):
    """For MDs / scripts: forbidden term + problem-ref >100 in same added line."""
    name = path.name.lower()
    if not (name.endswith(".md") or name.endswith(".py") or name.endswith(".sh") or name.endswith(".txt")):
        return []
    if name == "forbidden_terms.txt":
        return []  # The wordlist itself contains the terms; don't recurse
    hits = []
    for line in staged_hunks(path):
        line_lc = line.lower()
        # Find any problem reference >100
        problem_nums = [int(m.group(1)) for m in PROBLEM_REF.finditer(line)]
        problems_over_100 = [n for n in problem_nums if n > 100]
        if not problems_over_100:
            continue
        # Check forbidden terms
        for term in terms:
            if term in line_lc:
                hits.append(f"  {path.relative_to(REPO)}: {sorted(set(problems_over_100))} + '{term}' on line: {line.strip()[:100]}")
                break
    return hits


def main():
    terms = load_forbidden_terms()
    files = staged_files()
    if not files:
        return 0

    answer_violations = []
    proximity_violations = []
    for f in files:
        if not f.exists():
            continue
        answer_violations.extend(check_json_answer_leak(f))
        proximity_violations.extend(check_proximity(f, terms))

    if not answer_violations and not proximity_violations:
        return 0

    print("=" * 70, file=sys.stderr)
    print("SANITIZATION GATE: commit REJECTED", file=sys.stderr)
    print("=" * 70, file=sys.stderr)

    if answer_violations:
        print("\nAnswer field present in public data (NEVER allowed, for any problem):", file=sys.stderr)
        for v in answer_violations:
            print(v, file=sys.stderr)
        print("\nFix: re-write via `euler-bench per-iter --write` (strips answers at write-time),", file=sys.stderr)
        print("or strip manually:", file=sys.stderr)
        print("  jq '.problems |= with_entries(.value |= del(.answer))' data/{lang}.json > /tmp/x && mv /tmp/x data/{lang}.json", file=sys.stderr)

    if proximity_violations:
        print("\nForbidden term in proximity to problem >100 in staged content:", file=sys.stderr)
        for v in proximity_violations:
            print(v, file=sys.stderr)
        print("\nFix: rephrase the line to remove either the technique term or the problem number,", file=sys.stderr)
        print("or refine scripts/forbidden_terms.txt if the term is a false positive.", file=sys.stderr)

    print("\nOverride (discouraged): git commit --no-verify", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
