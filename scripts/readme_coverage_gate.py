#!/usr/bin/env python3
"""
README coverage gate: fail when README.md's coverage claims drift from the
bench DB.

Checks, against data/bench-private.db (read-only) and data/tiers.json:

  1. Each row of the "Where things stand" tier table:
       | **<Label>** | <lo>–<hi> | <langs> | <N>/<M> ... |
     - <lo>–<hi> must equal the tier's range; for an open-ended tier (hi=None
       in tiers.json) hi is the highest problem with any row in the DB.
     - <N> = problems in range where EVERY tier lang has status='pass';
       <M> = size of the range.
  2. The intro sentence "every Project Euler problem from 1 to <K>" — K must
     equal the highest problem in the DB.

Limitation: the DB can only say what we've solved, not what PE has published.
A newly published problem nobody has started yet is invisible here.

Exit 0 = consistent (or DB absent, e.g. fresh clone); exit 1 = drift.

History:
  2026-10-03: added after the Frontier row read "709/710" while the DB had
              711/711 (301-1011) — hand-maintained count went stale.
"""
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tiers import TIER_ORDER, load_tiers  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"
DB = REPO / "data" / "bench-private.db"

ROW = re.compile(r"^\|\s*\*\*(?P<label>[^*]+)\*\*\s*\|\s*(?P<lo>\d+)\s*[–-]\s*(?P<hi>\d+)\s*\|"
                 r"[^|]*\|\s*(?P<n>\d+)/(?P<m>\d+)")
INTRO = re.compile(r"problem from 1 to (\d+)")


def load_passes():
    # mode=ro, not immutable: a bench may be writing concurrently.
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        rows = db.execute("SELECT lang, problem, status FROM runs").fetchall()
    finally:
        db.close()
    passes = defaultdict(set)  # problem -> {lang with status pass}
    max_problem = 0
    for lang, problem, status in rows:
        n = int(problem)
        max_problem = max(max_problem, n)
        if status == "pass":
            passes[n].add(lang)
    return passes, max_problem


def main():
    if not DB.exists():
        return 0  # no private DB (fresh clone / CI) — nothing to check against

    tiers = load_tiers()
    passes, max_problem = load_passes()
    text = README.read_text()
    errors = []

    claimed = {}
    for line in text.splitlines():
        m = ROW.match(line)
        if m:
            claimed[m["label"].strip()] = m

    for key in TIER_ORDER:
        tier = tiers[key]
        label = tier["label"]
        lo, hi = tier["problem_range"]
        hi = max_problem if hi is None else hi
        langs = set(tier["langs"])
        total = hi - lo + 1
        done = sum(1 for p in range(lo, hi + 1) if langs <= passes[p])

        m = claimed.get(label)
        if m is None:
            errors.append(f"{label}: no tier-table row found in README.md")
            continue
        if (int(m["lo"]), int(m["hi"])) != (lo, hi):
            errors.append(f"{label}: README range {m['lo']}–{m['hi']}, DB says {lo}–{hi}")
        if (int(m["n"]), int(m["m"])) != (done, total):
            errors.append(f"{label}: README says {m['n']}/{m['m']}, DB says {done}/{total}")

    intro = INTRO.search(text)
    if intro is None:
        errors.append('intro: "problem from 1 to <K>" sentence not found')
    elif int(intro[1]) != max_problem:
        errors.append(f"intro: README says 1 to {intro[1]}, DB max problem is {max_problem}")

    if errors:
        print("README coverage gate: README.md disagrees with data/bench-private.db", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print("Update the tier table / intro in README.md (bypass: git commit --no-verify).",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
