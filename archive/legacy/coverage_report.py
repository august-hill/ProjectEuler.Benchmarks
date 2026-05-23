#!/usr/bin/env python3
"""Generate COVERAGE.md — a visual dashboard of Project Euler coverage across
all 10 language repos, organized by tier.

Tier model (see ``data/tiers.json``):
- Tier 1 Foundation: all 10 langs, problems 1-200 (apples-to-apples surface).
- Tier 2 Deep Coverage: C++, Go, Zig, Python, problems 201-300.
- Tier 3 Frontier: C++, Go, problems 301+.

Out-of-scope cells render as ⬛ via :func:`tiers.in_scope`. Historical
exceptions (e.g., Rust's existing 201+ work) are NOT shown in tier sections
where the lang isn't in scope; they remain committed in their repos.

Run from anywhere; outputs to ProjectEuler.Benchmarks/COVERAGE.md.
"""
from __future__ import annotations
import datetime
import re
import sys
from pathlib import Path

# Allow `import tiers` regardless of where this script is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tiers import (
    load_tiers, tier_for_problem, langs_in_tier, in_scope,
    tier_label, tier_problem_range, tier_range_label, TIER_ORDER,
)

ROOT = Path("/Users/augusthill/ccdev")
OUTPUT = ROOT / "ProjectEuler.Benchmarks" / "COVERAGE.md"

# (display_name, tier_key, repo_name, solution_file_glob)
# tier_key matches the lowercase lang keys in tiers.json.
LANGS = [
    ("C",     "c",          "ProjectEuler.C",          "problem_{n}/main.c"),
    ("C++",   "cpp",        "ProjectEuler.CPlusPlus",  "problem_{n}/main.cpp"),
    ("C#",    "csharp",     "ProjectEuler.CSharp",     "problem_{n}/Program.cs"),
    ("Go",    "go",         "ProjectEuler.Go",         "problem_{n}/main.go"),
    ("Java",  "java",       "ProjectEuler.Java",       "problem_{n}/Main.java"),
    ("JS",    "javascript", "ProjectEuler.JavaScript", "problem_{n}/main.js"),
    ("Py",    "python",     "ProjectEuler.Python",     "problem_{n}.py"),
    ("Rust",  "rust",       "ProjectEuler.Rust",       "problem_{n}/src/main.rs"),
    ("Zig",   "zig",        "ProjectEuler.Zig",        "problem_{n}/main.zig"),
    ("ARM64", "arm64",      "ProjectEuler.ARM64",      "problem_{n}/solve.s"),
]

DONE = "🟩"
PARKED = "🟨"
MISSING = "🟥"
SCOPE_OUT = "⬛"  # out of scope for this lang's max tier (e.g., ARM64 past 200)

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


def status_for(repo_dir: Path, problem_num: int, file_glob: str,
               tier_key: str, tiers: dict, skip_set: set[int]) -> str:
    """Classify a single (language, problem) cell with tier awareness."""
    if not in_scope(tier_key, problem_num, tiers):
        return SCOPE_OUT

    n_str = f"{problem_num:03d}"
    file_path = repo_dir / file_glob.format(n=n_str)
    if not file_path.exists():
        # Intentional skip per repo's CLAUDE.md → PARKED, not MISSING
        if problem_num in skip_set:
            return PARKED
        return MISSING

    # File exists — check if PARKED via short-file + marker heuristic.
    try:
        content = file_path.read_text(errors="ignore")
    except Exception:
        return DONE  # can't read but it's there

    # Heuristic: very short file (≤8 non-comment lines) AND has PARKED marker
    nontrivial = [
        ln for ln in content.split("\n")
        if ln.strip() and not ln.strip().startswith(("//", "#", "/*", "*"))
    ]
    if len(nontrivial) <= 8:
        for pat in PARKED_PATTERNS:
            if pat.search(content):
                return PARKED

    return DONE


def collect_grid(tiers: dict) -> dict:
    """Returns: dict[(display_name, problem_num)] -> status emoji."""
    grid = {}
    for display_name, tier_key, repo_name, file_glob in LANGS:
        repo_dir = ROOT / repo_name
        skip_set = read_skip_list(repo_dir)
        for n in range(1, 1001):
            grid[(display_name, n)] = status_for(repo_dir, n, file_glob,
                                                  tier_key, tiers, skip_set)
    return grid


def per_language_stats(grid: dict) -> list[tuple]:
    """Overall per-lang stats across all tiers the lang is in scope for."""
    rows = []
    for display_name, _, _, _ in LANGS:
        statuses = [grid[(display_name, n)] for n in range(1, 1001)]
        done = statuses.count(DONE)
        parked = statuses.count(PARKED)
        missing = statuses.count(MISSING)
        scope_out = statuses.count(SCOPE_OUT)
        in_scope_n = 1000 - scope_out
        coverage_pct = (done / in_scope_n * 100) if in_scope_n else 0
        rows.append((display_name, done, parked, missing, scope_out, coverage_pct))
    return rows


def tier_section(tier_key: str, tiers: dict, grid: dict) -> str:
    """Render one tier's heatmap + detail strip + tier-scoped stats."""
    lo, hi = tier_problem_range(tier_key, tiers)
    # Clamp upper bound for detail rendering (no point past p1000).
    hi_render = hi if hi is not None else 1000
    tier_langs_lower = set(langs_in_tier(tier_key, tiers))

    # Filter LANGS to those in this tier (preserve display order from LANGS).
    in_tier_rows = [(d, tk, r, g) for d, tk, r, g in LANGS if tk in tier_langs_lower]

    out = []
    out.append(f"## {tier_label(tier_key, tiers)} — problems {tier_range_label(tier_key, tiers)}")
    out.append("")
    out.append(f"_{tiers[tier_key]['description']}_")
    out.append("")
    out.append(f"**{len(in_tier_rows)} languages in scope:** "
               + ", ".join(d for d, _, _, _ in in_tier_rows))
    out.append("")

    # Per-tier stats table
    out.append("| Language | 🟩 Done | 🟨 Parked | 🟥 Missing | Coverage |")
    out.append("|---|---|---|---|---|")
    for display_name, _, _, _ in in_tier_rows:
        done = parked = missing = 0
        for n in range(lo, hi_render + 1):
            s = grid[(display_name, n)]
            if s == DONE: done += 1
            elif s == PARKED: parked += 1
            elif s == MISSING: missing += 1
        in_scope_n = done + parked + missing
        pct = (done / in_scope_n * 100) if in_scope_n else 0
        out.append(f"| **{display_name}** | {done} | {parked} | {missing} | {pct:.1f}% |")
    out.append("")

    # Per-century heatmap scoped to this tier's range
    out.append("### Per-century heatmap (in-tier languages only)")
    out.append("")
    century_lo = ((lo - 1) // 100) * 100 + 1
    century_hi = hi_render
    header = "| Range | " + " | ".join(d for d, _, _, _ in in_tier_rows) + " |"
    sep = "|" + "---|" * (len(in_tier_rows) + 1)
    out.append(header)
    out.append(sep)
    for c_lo in range(century_lo, century_hi + 1, 100):
        c_hi = min(c_lo + 99, hi_render)
        if c_lo < lo:
            c_lo = lo  # don't include below-tier problems in the first century
        cells = []
        for display_name, _, _, _ in in_tier_rows:
            statuses = [grid[(display_name, n)] for n in range(c_lo, c_hi + 1)]
            done_c = statuses.count(DONE)
            parked_c = statuses.count(PARKED)
            in_scope_c = len(statuses) - statuses.count(SCOPE_OUT)
            covered = done_c + parked_c
            if in_scope_c == 0:
                cells.append("⬛ —")
            elif covered == in_scope_c:
                cells.append(f"🟩 **{done_c}**")
            elif done_c >= in_scope_c * 0.5:
                cells.append(f"🟨 {done_c}/{in_scope_c}")
            elif done_c > 0:
                cells.append(f"🟥 {done_c}/{in_scope_c}")
            else:
                cells.append(f"🟥 0/{in_scope_c}")
        out.append(f"| {c_lo:03d}–{c_hi:03d} | " + " | ".join(cells) + " |")
    out.append("")

    # Per-problem detail strip (only for the tier's range, only in-tier langs)
    out.append("### Per-problem detail")
    out.append("")
    out.append("```")
    for display_name, _, _, _ in in_tier_rows:
        cells = []
        for i, n in enumerate(range(lo, hi_render + 1)):
            cells.append(grid[(display_name, n)])
            if (i + 1) % 10 == 0:
                cells.append(" ")
        out.append(f"{display_name:<6} {''.join(cells).rstrip()}")
    out.append("```")
    out.append("")
    return "\n".join(out)


def known_issues(grid: dict) -> str:
    """Surface PARKED entries grouped by language (across all tiers)."""
    out = []
    for display_name, _, _, _ in LANGS:
        parked = [n for n in range(1, 1001) if grid[(display_name, n)] == PARKED]
        if parked:
            out.append(f"- **{display_name}**: parked {parked}")
    return "\n".join(out) if out else "_(none detected)_"


def suggested_actions(tiers: dict, grid: dict) -> str:
    """Per-tier next-action suggestions."""
    out = []
    for tier_key in TIER_ORDER:
        if tier_key not in tiers:
            continue
        lo, hi = tier_problem_range(tier_key, tiers)
        hi_render = hi if hi is not None else 1000
        tier_langs_lower = set(langs_in_tier(tier_key, tiers))
        in_tier_display = [d for d, tk, _, _ in LANGS if tk in tier_langs_lower]

        # Lowest absolute gap within this tier
        first_gap = None
        for n in range(lo, hi_render + 1):
            missing_langs = [d for d in in_tier_display if grid[(d, n)] == MISSING]
            if missing_langs:
                first_gap = (n, missing_langs)
                break
        out.append(f"**{tier_label(tier_key, tiers)} ({tier_range_label(tier_key, tiers)}):**")
        if first_gap is None:
            out.append("  - _(no gaps in tier)_")
        else:
            n, langs = first_gap
            out.append(f"  - Lowest gap: problem **{n}** (missing from {langs})")
            # Per-lang frontier within this tier
            for display_name in in_tier_display:
                frontier = lo - 1
                for n2 in range(lo, hi_render + 1):
                    s = grid[(display_name, n2)]
                    if s in (DONE, PARKED, SCOPE_OUT):
                        frontier = n2
                    else:
                        break
                out.append(f"  - {display_name}: contiguous through **{frontier}**")
        out.append("")
    return "\n".join(out)


def main():
    tiers = load_tiers()
    grid = collect_grid(tiers)
    stats = per_language_stats(grid)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    md = []
    md.append("# Project Euler — Coverage Dashboard")
    md.append("")
    md.append(f"_Generated: {timestamp}_")
    md.append("")
    md.append("Legend: 🟩 done · 🟨 parked / known issue · 🟥 missing · ⬛ out of scope")
    md.append("")
    md.append("Coverage is reported in three tiers — see `data/tiers.json` for definitions. "
              "Historical exceptions (existing committed solves beyond a language's max tier) "
              "stay in the source repos but do not contribute to tier-comparison stats.")
    md.append("")

    md.append("## Per-Language Summary (across all tiers in scope)")
    md.append("")
    md.append("| Language | 🟩 Done | 🟨 Parked | 🟥 Missing | ⬛ Out-of-scope | Coverage |")
    md.append("|---|---|---|---|---|---|")
    for name, done, parked, missing, scope_out, pct in stats:
        md.append(f"| **{name}** | {done} | {parked} | {missing} | {scope_out} | {pct:.1f}% |")
    md.append("")

    # Per-tier sections
    for tier_key in TIER_ORDER:
        if tier_key not in tiers:
            continue
        md.append(tier_section(tier_key, tiers, grid))

    md.append("## Known Parked / Issues")
    md.append("")
    md.append(known_issues(grid))
    md.append("")
    md.append("## Suggested Next Actions")
    md.append("")
    md.append(suggested_actions(tiers, grid))
    md.append("")
    md.append("---")
    md.append("")
    md.append("_Regenerate with: `python3 ProjectEuler.Benchmarks/scripts/coverage_report.py`_")

    OUTPUT.write_text("\n".join(md))
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
