#!/usr/bin/env python3
"""Generate COVERAGE.md — a visual dashboard of Project Euler coverage across
all 10 language repos. Run from anywhere; outputs to ProjectEuler.Benchmarks/COVERAGE.md.
"""
from __future__ import annotations
import datetime
import os
import re
from pathlib import Path

ROOT = Path("/Users/augusthill/ccdev")
OUTPUT = ROOT / "ProjectEuler.Benchmarks" / "COVERAGE.md"

# (display_name, repo_name, solution_file_glob)
LANGS = [
    ("C", "ProjectEuler.C", "problem_{n}/main.c"),
    ("C++", "ProjectEuler.CPlusPlus", "problem_{n}/main.cpp"),
    ("C#", "ProjectEuler.CSharp", "problem_{n}/Program.cs"),
    ("Go", "ProjectEuler.Go", "problem_{n}/main.go"),
    ("Java", "ProjectEuler.Java", "problem_{n}/Main.java"),
    ("JS", "ProjectEuler.JavaScript", "problem_{n}/main.js"),
    ("Py", "ProjectEuler.Python", "problem_{n}.py"),
    ("Rust", "ProjectEuler.Rust", "problem_{n}/src/main.rs"),
    ("Zig", "ProjectEuler.Zig", "problem_{n}/main.zig"),
    ("ARM64", "ProjectEuler.ARM64", "problem_{n}/solve.s"),
]

# ARM64 capped at 200 by user decision.
ARM64_CAP = 200

DONE = "🟩"
PARKED = "🟨"
MISSING = "🟥"
SCOPE_OUT = "⬛"  # out of scope (e.g., ARM64 past 200)

PARKED_PATTERNS = [
    re.compile(r"PARKED", re.IGNORECASE),
    re.compile(r"SKIPPED", re.IGNORECASE),
    re.compile(r"too complex"),
    re.compile(r"^\s*return\s+-1\s*;?\s*$", re.MULTILINE),  # placeholder
]

# Header that introduces a per-repo permanent-skip section in CLAUDE.md.
SKIP_SECTION_RE = re.compile(r"##+\s+.*permanent\s+skip", re.IGNORECASE)
# Bullet item like "- **185** — reason..." inside a skip section.
SKIP_ITEM_RE = re.compile(r"^\s*[-*]\s*\*\*(\d{1,4})\*\*", re.MULTILINE)


def read_skip_list(repo_dir: Path) -> set[int]:
    """Parse a repo's CLAUDE.md for an intentional permanent-skip list.

    Returns the set of problem numbers the repo has decided not to attempt.
    Empty set if no CLAUDE.md or no skip section.
    """
    claude_md = repo_dir / "CLAUDE.md"
    if not claude_md.exists():
        return set()
    try:
        content = claude_md.read_text(errors="ignore")
    except Exception:
        return set()
    # Find the skip section header; collect bullets until the next header.
    lines = content.split("\n")
    in_section = False
    skips = set()
    for line in lines:
        if SKIP_SECTION_RE.match(line):
            in_section = True
            continue
        if in_section and re.match(r"^##+\s", line):
            break  # next section
        if in_section:
            for m in SKIP_ITEM_RE.finditer(line):
                skips.add(int(m.group(1)))
    return skips


def status_for(repo_dir: Path, problem_num: int, file_glob: str, display_name: str, skip_set: set[int]) -> str:
    """Classify a single (language, problem) cell."""
    if display_name == "ARM64" and problem_num > ARM64_CAP:
        return SCOPE_OUT

    n_str = f"{problem_num:03d}"
    file_path = repo_dir / file_glob.format(n=n_str)
    if not file_path.exists():
        # Intentional skip per repo's CLAUDE.md → PARKED, not MISSING
        if problem_num in skip_set:
            return PARKED
        return MISSING

    # File exists — check if PARKED
    try:
        content = file_path.read_text(errors="ignore")
    except Exception:
        return DONE  # can't read but it's there

    # Heuristic: very short file (<=2 non-comment lines) AND has PARKED comment
    nontrivial = [
        ln for ln in content.split("\n")
        if ln.strip() and not ln.strip().startswith(("//", "#", "/*", "*"))
    ]
    if len(nontrivial) <= 8:
        for pat in PARKED_PATTERNS:
            if pat.search(content):
                return PARKED

    return DONE


def collect_grid():
    """Returns: dict[(lang_name, problem_num)] -> status emoji."""
    grid = {}
    for display_name, repo_name, file_glob in LANGS:
        repo_dir = ROOT / repo_name
        skip_set = read_skip_list(repo_dir)
        for n in range(1, 1001):
            grid[(display_name, n)] = status_for(repo_dir, n, file_glob, display_name, skip_set)
    return grid


def per_language_stats(grid):
    rows = []
    for display_name, _, _ in LANGS:
        statuses = [grid[(display_name, n)] for n in range(1, 1001)]
        done = statuses.count(DONE)
        parked = statuses.count(PARKED)
        missing = statuses.count(MISSING)
        scope_out = statuses.count(SCOPE_OUT)
        in_scope = 1000 - scope_out
        coverage_pct = (done / in_scope * 100) if in_scope else 0
        rows.append((display_name, done, parked, missing, scope_out, coverage_pct))
    return rows


def century_heatmap(grid):
    """For each 100-block, show count of done per language."""
    centuries = [(c * 100 + 1, c * 100 + 100) for c in range(10)]
    header = "| Range | " + " | ".join(name for name, _, _ in LANGS) + " |"
    sep = "|" + "---|" * (len(LANGS) + 1)
    rows = [header, sep]
    for lo, hi in centuries:
        cells = []
        for display_name, _, _ in LANGS:
            statuses = [grid[(display_name, n)] for n in range(lo, hi + 1)]
            done = statuses.count(DONE)
            parked = statuses.count(PARKED)
            in_scope = 100 - statuses.count(SCOPE_OUT)
            covered = done + parked  # parked counts as "intentionally closed"
            if in_scope == 0:
                cells.append("⬛ —")  # Out of scope (e.g., ARM64 past 200)
            elif covered == in_scope:
                cells.append(f"🟩 **{done}**")  # all in-scope settled (done or parked)
            elif done >= in_scope * 0.5:
                cells.append(f"🟨 {done}/{in_scope}")
            elif done > 0:
                cells.append(f"🟥 {done}/{in_scope}")
            else:
                cells.append(f"🟥 0/{in_scope}")
        rows.append(f"| {lo:03d}–{hi:03d} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def detail_strip(grid, lo, hi):
    """Per-problem heatmap for a range. One row per language; one emoji per problem,
    grouped in blocks of 10 with spaces between."""
    out = []
    for display_name, _, _ in LANGS:
        cells = []
        for i, n in enumerate(range(lo, hi + 1)):
            cells.append(grid[(display_name, n)])
            if (i + 1) % 10 == 0:
                cells.append(" ")
        out.append(f"`{display_name:<6}` {''.join(cells).rstrip()}")
    return "\n\n".join(out)


def known_issues(grid):
    """Surface PARKED entries grouped by language."""
    out = []
    for display_name, _, _ in LANGS:
        parked = [n for n in range(1, 1001) if grid[(display_name, n)] == PARKED]
        if parked:
            out.append(f"- **{display_name}**: parked {parked}")
    return "\n".join(out) if out else "_(none detected)_"


def suggested_actions(grid):
    """Find lowest gaps suitable for next-session work, accounting for parked status."""
    out = []
    # Lowest absolute gap (any missing, any language)
    for n in range(1, 1001):
        missing_langs = [name for name, _, _ in LANGS if grid[(name, n)] == MISSING]
        if missing_langs:
            out.append(f"- **Lowest absolute gap:** problem **{n}** (missing from {missing_langs})")
            break
    # Lowest single-language gap
    for n in range(1, 1001):
        missing_langs = [name for name, _, _ in LANGS if grid[(name, n)] == MISSING]
        if len(missing_langs) == 1:
            out.append(f"- **Lowest single-language gap:** problem **{n}** (only {missing_langs[0]} missing)")
            break
    # Lowest broad gap (missing from ≥5 languages)
    for n in range(1, 1001):
        missing_langs = [name for name, _, _ in LANGS if grid[(name, n)] == MISSING]
        if len(missing_langs) >= 5:
            out.append(f"- **Lowest broad gap (≥5 langs):** problem **{n}** (missing from {missing_langs})")
            break
    # Per-language frontier (highest contiguous problem number from 1)
    out.append("")
    out.append("**Per-language contiguous frontier (highest n with no gap in 1..n):**")
    for display_name, _, _ in LANGS:
        frontier = 0
        for n in range(1, 1001):
            s = grid[(display_name, n)]
            if s in (DONE, PARKED, SCOPE_OUT):
                frontier = n
            else:
                break
        out.append(f"  - {display_name}: 1–**{frontier}**")
    return "\n".join(out) if out else "_(no gaps found)_"


def main():
    grid = collect_grid()
    stats = per_language_stats(grid)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    md = []
    md.append("# Project Euler — Coverage Dashboard")
    md.append("")
    md.append(f"_Generated: {timestamp}_")
    md.append("")
    md.append("Legend: 🟩 done · 🟨 parked / known issue · 🟥 missing · ⬛ out of scope")
    md.append("")
    md.append("## Per-Language Summary (problems 1–1000)")
    md.append("")
    md.append("| Language | 🟩 Done | 🟨 Parked | 🟥 Missing | ⬛ Out-of-scope | Coverage |")
    md.append("|---|---|---|---|---|---|")
    for name, done, parked, missing, scope_out, pct in stats:
        md.append(f"| **{name}** | {done} | {parked} | {missing} | {scope_out} | {pct:.1f}% |")
    md.append("")
    md.append("## Per-Century Coverage Heatmap")
    md.append("")
    md.append("Each cell shows: `<done>/100` followed by 🟩 (full) / 🟨 (≥50%) / 🟥 (some) / ⬛ (none)")
    md.append("")
    md.append(century_heatmap(grid))
    md.append("")
    md.append("## Detailed Problem Map")
    md.append("")
    md.append("Each row shows problems left-to-right in groups of 10. ")
    md.append("🟩 done · 🟨 parked · 🟥 missing · ⬛ out of scope.")
    md.append("")
    for lo in (1, 101, 201, 301, 401):
        md.append(f"### Problems {lo:03d}–{lo+99:03d}")
        md.append("")
        md.append("```")
        md.append(detail_strip(grid, lo, lo + 99))
        md.append("```")
        md.append("")

    md.append("## Known Parked / Issues")
    md.append("")
    md.append(known_issues(grid))
    md.append("")
    md.append("## Suggested Next Actions")
    md.append("")
    md.append(suggested_actions(grid))
    md.append("")
    md.append("---")
    md.append("")
    md.append("_Regenerate with: `python3 ProjectEuler.Benchmarks/scripts/coverage_report.py`_")

    OUTPUT.write_text("\n".join(md))
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
