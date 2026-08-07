#!/usr/bin/env python3
"""Pre-commit disk audit for tier-3 trio solves (cpp/go/rust).

Usage:
    python3 scripts/trio_audit.py 0433=326624372659664 0583=1174137929000 ...

Each argument is <4-digit-problem>=<expected-answer-token>. Answer tokens are
passed at runtime only — never stored in this (public) repo.

Checks, per (problem, lang):
  - source file exists
  - line 1 is exactly "// Answer: <token>"
  - exactly ONE "// Answer:" line in the file
  - no answer-cache / parallelism smells (thread spawns, once-cells, ...)
  - no PLACEHOLDER/PENDING markers anywhere

Exits 1 if ANY issue is found (safe to chain with `&& git commit`), 0 if clean.
Also prints `git status --porcelain` for the three lang repos as a convenience.
"""

import re
import subprocess
import sys
from pathlib import Path

PE = Path(__file__).resolve().parent.parent.parent  # .../pe
LANG_PATHS = {
    "cpp": lambda p: PE / "cpp" / f"problem_{p}" / "main.cpp",
    "go": lambda p: PE / "go" / f"problem_{p}" / "main.go",
    "rust": lambda p: PE / "rust" / f"problem_{p}" / "src" / "main.rs",
}
SMELL = re.compile(
    r"(?i)(answer_cache|cached_answer|once\.Do|OnceCell|lazy_static"
    r"|std::thread|go func|#pragma omp|rayon)"
)
BAD_MARKERS = ("PLACEHOLDER", "PENDING")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    expect: dict[str, str] = {}
    for arg in argv:
        prob, _, tok = arg.partition("=")
        if len(prob) != 4 or not prob.isdigit() or not tok:
            print(f"bad argument (want NNNN=token): {arg!r}")
            return 2
        expect[prob] = tok

    issues: list[str] = []
    for prob, tok in expect.items():
        for lang, path_fn in LANG_PATHS.items():
            f = path_fn(prob)
            if not f.exists():
                issues.append(f"MISSING {lang}/{prob}: {f}")
                continue
            text = f.read_text()
            first = text.splitlines()[0].strip() if text else ""
            if first != f"// Answer: {tok}":
                issues.append(f"HEADER {lang}/{prob}: {first!r}")
            n_ans = len(re.findall(r"^\s*//\s*Answer:", text, re.M))
            if n_ans != 1:
                issues.append(f"MULTI-ANSWER {lang}/{prob}: {n_ans} lines")
            m = SMELL.search(text)
            if m:
                issues.append(f"SMELL {lang}/{prob}: {m.group(0)!r}")
            for marker in BAD_MARKERS:
                if marker in text:
                    issues.append(f"{marker} {lang}/{prob}")

    if issues:
        print(f"AUDIT FAILED — {len(issues)} issue(s):")
        for issue in issues:
            print(f"  {issue}")
        return 1

    print(f"AUDIT CLEAN — {3 * len(expect)}/{3 * len(expect)} files")
    for repo in ("cpp", "go", "rust"):
        r = subprocess.run(
            ["git", "-C", str(PE / repo), "status", "--porcelain"],
            capture_output=True,
            text=True,
        )
        print(f"--- {repo} ---")
        print(r.stdout.strip() or "(clean)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
