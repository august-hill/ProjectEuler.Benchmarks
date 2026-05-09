# CLAUDE.md — ProjectEuler.Benchmarks

## This repo is PUBLIC

This is the only public repo in the 10-language Project Euler suite. The other 10 language repos (`ProjectEuler.{C,CPlusPlus,CSharp,Go,Java,JavaScript,Python,Rust,Zig,ARM64}`) are intentionally private. This repo serves as the public-facing benchmark report — methodology, aggregate timings, and project narrative — without revealing how any problem >100 was solved.

## Sanitization rules (CRITICAL — public repo)

PE's publishing rule (projecteuler.net/about#publish) restricts public solution discussion to problems 1–100. Everything in this repo is constrained by that:

### Allowed in this repo
- **Problem numbers** (`p221`, `problem_435`, etc.) — bare references are fine
- **Timing data** (ns, ms, ratios) — pure numbers reveal no algorithm
- **Methodology** — benchmark harness, warmup strategy, three-metric schema
- **Aggregate analysis** — language-vs-language ratios, fastest-on-average, etc.
- **Project narrative** — JOURNEY.md, README.md, story content
- **Anything for problems ≤100** — PE permits public discussion; answers, techniques, and code are all fine for these

### NEVER allowed in this repo (for problems >100)
- **Answer values** — no `answer` field in `data/*.json`, no answers in MDs
- **Algorithm or technique names** — don't say "Pollard rho for p347", "Tonelli-Shanks for p516", "linearity of expectation for p491", etc.
- **Solution code** — no `.cpp` / `.py` / `.go` source files
- **Hints that narrow approach** — e.g. "this benefits from int128" already leaks that the answer fits in 128 bits

## Pre-commit checklist

Before committing changes to this repo, scan for:
- `grep -rE '"answer"' data/` — should return nothing for problems >100
- New MDs/scripts that pair a specific problem number >100 with technique vocabulary
- `data/*.json.bak` or similar backup files (these should be gitignored)

## History notes

**2026-04-18 cleanup (commit `2a24766`)**: stripped answers and technique mentions for problems >100 from the live tree. Pre-`2a24766` git history was NOT rewritten — the trade-off was accepted because archaeology is unlikely. That pre-`2a24766` history still contains pre-cleanup data.

**2026-05-09 sanitization-regression rewrite**: a refresh commit (former `dcf10e5`) mistakenly republished `data/*.json` with `"answer"` fields for problems >100 — ~891 leaked values were live for ~30 minutes before detection. History was rewritten via reset + clean recommit + force-push: the bad SHA was replaced by a sanitized equivalent. The leak likely persists in: GitHub's object database (~90 days until garbage collection), GitHub Search index until next reindex, and the GitHub Archive Project's daily snapshot. Going forward, the pre-commit ritual in `feedback_pe_data_sanitization.md` (in author's auto-memory) is mandatory before any `data/*.json` change.

## Verification protocol (cross-cutting reminder)

This repo doesn't run verification itself, but the suite's policy is: **no submission to projecteuler.net**; verify by independent Python and C++ implementations agreeing. The 10 language CLAUDE.md files contain the full PE Project Rules block — apply them when working on any sibling repo.
