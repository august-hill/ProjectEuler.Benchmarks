# CLAUDE.md — ProjectEuler.Benchmarks

## This repo is PUBLIC

This is the only public repo in the 10-language Project Euler suite. The other 10 language repos (`ProjectEuler.{C,CPlusPlus,CSharp,Go,Java,JavaScript,Python,Rust,Zig,ARM64}`) are intentionally private. This repo serves as the public-facing benchmark report — methodology, aggregate timings, and project narrative — without revealing how any problem >100 was solved.

## Sanitization rules (CRITICAL — public repo)

PE's publishing rule (projecteuler.net/about#publish) restricts public solution discussion to problems 1–100. Everything in this repo is constrained by that:

### Allowed in this repo
- **Problem numbers** (`p221`, `problem_435`, etc.) — bare references are fine
- **Timing data** (ns, ms, ratios) — pure numbers reveal no algorithm
- **Methodology** — benchmark harness, single-call (per-invocation) cost metric
- **Aggregate analysis** — language-vs-language ratios, fastest-on-average, etc.
- **Project narrative** — JOURNEY.md, README.md, story content
- **Narrative discussion of ≤100 answers / techniques / code** — PE permits this; MDs and narrative content may reference these freely

### NEVER allowed in the public repo: raw bench data files (post-2026-05-25 SQLite migration)
- **No `data/*.json` bench files. No `*.db` files.** The public repo carries ONLY rendered narrative (RESULTS.md, JOURNEY.md, README.md) and charts/*.png|svg. All raw bench data lives in the **gitignored** `data/bench-private.db` (SQLite, with answer column).
- The `sanitization_gate.py` pre-commit hook enforces this at the file-system boundary: any staged file under `data/` not on the small config-allowlist (`tiers.json`, `parked.json`, `difficulty.json`, `levels.json`) gets rejected. Leak prevention is now structural, not field-stripping.
- Policy history: 2026-05-09 sanitization-regression leaked ~891 answer values via a per-field stripping bug. 2026-05-23 tightened "strip for >100" to "strip for all." 2026-05-25 moved SSOT to SQLite — no public raw data → no field-stripping bug class possible.

### NEVER allowed in this repo (for problems >100)
- **Answer values in any form** — no answers in MDs, RESULTS, READMEs, scripts. (For ≤100 narrative use is OK per the rule above.)
- **Algorithm or technique names** — don't say "Pollard rho for p347", "Tonelli-Shanks for p516", "linearity of expectation for p491", etc.
- **Solution code** — no `.cpp` / `.py` / `.go` source files
- **Hints that narrow approach** — e.g. "this benefits from int128" already leaks that the answer fits in 128 bits

## Pre-commit checklist

Before committing changes to this repo, scan for:
- `grep -rE '"answer"' data/` — should return nothing for problems >100
- New MDs/scripts that pair a specific problem number >100 with technique vocabulary
- `data/*.json.bak` or similar backup files (these should be gitignored)

## Pre-publish ranking sanity check (added 2026-05-22)

Before any `git push origin main` that updates **RESULTS.md** or **charts/*.png**, spot-check the headline ranking against established priors. Publishing a misleading ranking to a public repo and then walking it back costs more than a 30-second sanity check.

**Expected priors for hot-loop computational benchmarks:**
- Compiled native langs (C, C++, Rust, Zig, ARM64) should cluster in the **top half** of the speed ranking.
- Managed langs (C#, Java) typically 2-5× slower than the fastest native; **never #1**.
- JavaScript: similar to managed langs, sometimes faster on numeric work due to V8 typed-array optimizations.
- Python: 10-50× slower than native for computation-heavy workloads; should be last or near-last on speed.

**If the chart violates these priors, the chart is wrong before the priors are.** Likely root causes (see auto-memory for details):
- `solve()` cache pattern — warm bench iterations measure cache-return instead of real algorithm cost (see [[project_pe_cache_pattern_campaign]]).
- Per-lang harness asymmetry — one lang's cold-start measurement includes work others' do not (see [[project_pe_arm64_relative_output_bug]] for the historical example).
- Algorithm-choice diversity — same problem benchmarked with different algorithms across langs.
- Stale entries from old harness versions.

**The check:** after running `python3 report.py` (the regen entrypoint per README:56), inspect the "Per-lang coverage in scope" block it prints to stdout — also reproduced as the rank table at the top of RESULTS.md. If a managed lang is in the top 3, OR a compiled lang is ranked below #6, **investigate before pushing.** Add a caveat to RESULTS.md if the issue can't be resolved in-session; do not push the ranking as authoritative.

**Reference incident:** 2026-05-22 session 477aafc3 pushed a chart with C# at #1 over ARM64/Zig/C++. User caught it on review; investigation surfaced two structural bugs. Caveated chart now in place; multi-session cache-strip campaign queued.

## History notes

**2026-04-18 cleanup (commit `2a24766`)**: stripped answers and technique mentions for problems >100 from the live tree. Pre-`2a24766` git history was NOT rewritten — the trade-off was accepted because archaeology is unlikely. That pre-`2a24766` history still contains pre-cleanup data.

**2026-05-09 sanitization-regression rewrite**: a refresh commit (former `dcf10e5`) mistakenly republished `data/*.json` with `"answer"` fields for problems >100 — ~891 leaked values were live for ~30 minutes before detection. History was rewritten via reset + clean recommit + force-push: the bad SHA was replaced by a sanitized equivalent. The leak likely persists in: GitHub's object database (~90 days until garbage collection), GitHub Search index until next reindex, and the GitHub Archive Project's daily snapshot. Going forward, the pre-commit ritual in `feedback_pe_data_sanitization.md` (in author's auto-memory) is mandatory before any `data/*.json` change.

## Verification protocol (cross-cutting reminder)

This repo doesn't run verification itself, but the suite's policy is: **no submission to projecteuler.net**; verify by independent **Go and C++ implementations** agreeing (2026-05-22 change — Python's wall cost above level 4 displaced it as C++'s pair; see `data/tiers.json` for the tiered language model). The 10 language CLAUDE.md files contain the full PE Project Rules block — apply them when working on any sibling repo.
