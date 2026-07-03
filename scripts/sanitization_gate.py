#!/usr/bin/env python3
"""
Sanitization gate for ProjectEuler.Benchmarks (the public repo).

Two checks against staged content (only files in `git diff --cached`):

  1. data/ raw bench data: REJECTED.
     Post-2026-05-25 SQLite migration, the public repo carries ONLY rendered
     narrative (RESULTS.md, JOURNEY.md, README.md, charts/*.png|svg). All raw
     bench data lives in the gitignored SQLite SSOT `data/bench-private.db`.
     Per-lang JSON exports are gone. The gate enforces "no raw data in public":
     anything under data/ that isn't on the small allowlist (config files like
     tiers.json) gets rejected. This makes leaks impossible-by-construction
     instead of impossible-by-careful-stripping.

  2. MDs / scripts: no forbidden technique term in proximity (same line) to a
     problem reference (p<N> or problem_<N>) where N > 100.
     Only NEW additions (staged + lines) get checked, so pre-existing
     legitimate mentions don't false-positive.

Exit 0 = clean; exit 1 = violation (commit rejected).
Override: `git commit --no-verify` bypasses this. Discouraged.

Allowlist under data/ (config files, not measurements — stay versioned):
  tiers.json       — tier model (which langs in which problem range)
  parallel.json    — parallel-class problem list (METHODOLOGY.md §5)
  parked.json      — list of parked problems (across all langs)
  difficulty.json  — per-problem PE difficulty ratings (sourced from PE site)
  levels.json      — per-problem PE level metadata (sourced from PE site)

History:
  2026-05-09: Sanitization-regression incident — ~891 answer values leaked
              live for ~30 min. Rule then was "strip the answer field from
              public data/*.json at write time." Worked by careful stripping;
              one bug = leak.
  2026-05-23: Rule tightened from "strip for >100" to "strip for ALL problems."
  2026-05-25: SSOT moved to SQLite (single bench-private.db, gitignored).
              Public repo no longer contains any raw bench data. This gate
              now enforces that structural invariant — leak prevention via
              file-system boundary, not via field-level stripping.
"""
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TERMS_FILE = REPO / "scripts" / "forbidden_terms.txt"

# Config files under data/ that ARE meant to be versioned. Everything else
# under data/ is bench data and must not be committed.
DATA_ALLOWLIST = {"tiers.json", "parked.json", "difficulty.json", "levels.json", "parallel.json"}

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


def check_data_file_blocked(path):
    """Reject any data/ file that isn't on the small config allowlist."""
    rel = path.relative_to(REPO)
    parts = rel.parts
    if len(parts) < 2 or parts[0] != "data":
        return []  # not under data/
    # Allow specific config files at data/ top level only.
    if len(parts) == 2 and parts[1] in DATA_ALLOWLIST:
        return []
    return [
        f"  {rel}: raw bench data must not be committed (SSOT is "
        f"data/bench-private.db, gitignored; only RESULTS.md + charts are "
        f"published). Allowlist: {sorted(DATA_ALLOWLIST)}."
    ]


def check_proximity(path, terms):
    """For MDs / scripts: forbidden term + problem-ref >100 in same added line."""
    name = path.name.lower()
    if not (name.endswith(".md") or name.endswith(".py")
            or name.endswith(".sh") or name.endswith(".txt")):
        return []
    if name == "forbidden_terms.txt":
        return []  # The wordlist itself contains the terms; don't recurse
    hits = []
    for line in staged_hunks(path):
        line_lc = line.lower()
        problem_nums = [int(m.group(1)) for m in PROBLEM_REF.finditer(line)]
        problems_over_100 = [n for n in problem_nums if n > 100]
        if not problems_over_100:
            continue
        for term in terms:
            if term in line_lc:
                hits.append(
                    f"  {path.relative_to(REPO)}: "
                    f"{sorted(set(problems_over_100))} + '{term}' on line: "
                    f"{line.strip()[:100]}"
                )
                break
    return hits


def main():
    terms = load_forbidden_terms()
    files = staged_files()
    if not files:
        return 0

    data_violations = []
    proximity_violations = []
    for f in files:
        if not f.exists():
            continue
        data_violations.extend(check_data_file_blocked(f))
        proximity_violations.extend(check_proximity(f, terms))

    if not data_violations and not proximity_violations:
        return 0

    print("=" * 70, file=sys.stderr)
    print("SANITIZATION GATE: commit REJECTED", file=sys.stderr)
    print("=" * 70, file=sys.stderr)

    if data_violations:
        print("\nRaw bench data files in public repo (forbidden post-2026-05-25):",
              file=sys.stderr)
        for v in data_violations:
            print(v, file=sys.stderr)
        print("\nFix: don't commit raw bench data. The SSOT is the gitignored "
              "data/bench-private.db.", file=sys.stderr)
        print("If this was an accidental `git add data/something.json`, "
              "unstage with `git reset HEAD data/<file>`.", file=sys.stderr)

    if proximity_violations:
        print("\nForbidden term in proximity to problem >100 in staged content:",
              file=sys.stderr)
        for v in proximity_violations:
            print(v, file=sys.stderr)
        print("\nFix: rephrase the line to remove either the technique term "
              "or the problem number,", file=sys.stderr)
        print("or refine scripts/forbidden_terms.txt if the term is a false "
              "positive.", file=sys.stderr)

    print("\nOverride (discouraged): git commit --no-verify", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
