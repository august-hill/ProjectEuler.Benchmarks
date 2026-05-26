# Project Euler — Cross-Language Benchmarks

**Per-invocation cost of solving Project Euler problems in 10 programming languages.**

Solutions written by [Claude](https://claude.ai) (Opus + Sonnet) across C, C++,
Rust, Go, Zig, Java, C#, JavaScript, Python, and ARM64 Assembly.  Benchmarked on
Apple Silicon.  See [JOURNEY.md](JOURNEY.md) for the full story — including the
reset from 200+ problems back to a verified 10×10 core and the disciplined
expansion since.

![Per-Invocation Cost — Foundation](charts/per_iter_total.png)

## Current scope: tiered 3-tier model

The suite uses an explicit **tier model** — different languages cover different
problem ranges, so cross-language comparisons stay apples-to-apples within each
tier.  Live definitions in [`data/tiers.json`](data/tiers.json).

| Tier | Problem range | Languages in scope | Role |
|------|---------------|---------------------|------|
| **Foundation** | 1–200 | All 10 (ARM64, C, C++, C#, Go, Java, JS, Python, Rust, Zig) | Apples-to-apples 10-language comparison — the headline ranking |
| **Deep Coverage** | 201–400 | C++, Go, Python, Rust, Zig | Deeper comparison among the 5 languages that intentionally extend past 200 |
| **Frontier** | 401+ | C++, Go | Exploration zone — C++ as deep-frontier reference, Go as verification pair |

Foundation problems are the apples-to-apples cross-language comparison surface.
Deep Coverage extends 5 of those languages to harder problems; the other 5 are
intentionally capped at 200 to keep the 10-language story clean.  Frontier work
ships as paired C++/Go implementations (the verification protocol — see
[JOURNEY.md](JOURNEY.md)).

**See [RESULTS.md](RESULTS.md)** for per-tier rankings, the tier-aware coverage
heatmap, and full methodology.  Per-problem detail tables live under
[`per_problem/`](per_problem/), one page per 100-problem band.

## What we measure

One thing: **how long does it take to run, from a fresh OS process**.

For each (language, problem):

1. Build the binary.
2. Run it 10 times, each in a fresh `fork` + `exec` invocation.
3. Compare the answer against the canonical (each source file's `// Answer:`
   header comment).  Abort on mismatch.
4. Report the median wall time across the 10 runs.

This matches what a real CLI user, cron job, or shell-loop invocation pays.  It
doesn't reward language-internal caches (Rust `OnceLock`, primesieve internal
state, `@lru_cache`) that disappear at process exit anyway — the OS clears them
between invocations, so each language is honestly measured at its actual
per-invocation cost.

## What we don't measure (and why)

- **In-process warm iterations.**  A "1000 iterations in a tight loop" metric is
  meaningful for server / daemon scenarios, but those are a different question
  with different right answers.  See [JOURNEY.md](JOURNEY.md) — particularly the
  "From In-Process Warm to Process-Per-Iteration" chapter — for the full
  reasoning behind retiring that metric.
- **Compile time as a headline number.**  Build cost is real but in our model
  the binary is built once and invoked many times.  Recorded as diagnostic data,
  not part of the ranking.

## Reproducibility

```bash
cd benchmarks

# Foundation tier (all 10 langs, 1-200) — the apples-to-apples surface
cmd/euler-bench/euler-bench per-iter --lang all --problems 1-200 --iters 10 --write

# Deep Coverage tier (5 langs, 201-400) — language extension
cmd/euler-bench/euler-bench per-iter --lang cpp,go,python,rust,zig --problems 201-400 --iters 10 --write

# Regen RESULTS.md + per-band detail pages + all charts (PNG + SVG)
python3 report.py
```

The Go tool ([`cmd/euler-bench/`](cmd/euler-bench/)) is the single source of
truth for measurement — one binary builds, runs, validates answers, and writes
sanitized data atomically.  No flock, no hook chain, no per-language scripts.
`report.py` consumes [`data/tiers.json`](data/tiers.json) via the shared
[`scripts/tiers.py`](scripts/tiers.py) helper, so changing the tier model is a
config edit, not a code refactor.

## Trust + safety

This repo is **public**; the lang repos are **private**.  Per the project's
[PE compliance rules](CLAUDE.md), **the public repo carries no raw bench data
at all** — only rendered narrative (RESULTS.md, JOURNEY.md, this README,
per-band detail pages) and charts.  All measurements (including answer values)
live in the gitignored SQLite SSOT `data/bench-private.db`.

This is a structural invariant, not a field-stripping discipline: leak
prevention is enforced at the file-system boundary by `.gitignore` plus a
pre-commit hook ([`scripts/sanitization_gate.py`](scripts/sanitization_gate.py))
that rejects any staged file under `data/` not on the small config allowlist
(`tiers.json`, `parked.json`, `difficulty.json`, `levels.json`).

## Repo layout

| Path | What |
|------|------|
| `RESULTS.md` | Per-tier rankings, coverage heatmap, methodology |
| `per_problem/per_problem_*.md` | Per-band timing detail tables (one page per 100-problem band) |
| `JOURNEY.md` | The story — how we got here, what we learned, what we tried that didn't work |
| `cmd/euler-bench/` | The Go bench + write tool (`run`, `failures`, `status`, `per-iter`) — single SSOT writer |
| `report.py` | Markdown + chart generator (reads SQLite SSOT, writes `RESULTS.md` + `per_problem/*` + `charts/`) |
| `data/bench-private.db` | SQLite SSOT (gitignored) — `runs` + `run_history` tables |
| `data/tiers.json` | Tier model SSOT — which languages are in scope for which problem range |
| `data/{parked,difficulty,levels}.json` | Other config (parked problems, PE-site metadata) |
| `scripts/tiers.py` | Shared tier helper — `load_tiers`, `langs_in_tier`, `in_scope`, etc. |
| `scripts/sanitization_gate.py` | Pre-commit hook: rejects any raw bench data file outside the config allowlist |
| `charts/per_iter_total.png` | Foundation per-invocation total (10 langs over the common set) |
| `charts/per_iter_total_tier2.png` | Deep Coverage per-invocation total (5 langs over the tier-2 common set) |
| `charts/per_iter_speed_vs_size.png` | Foundation speed vs source lines |
| `charts/per_iter_speed_vs_size_tier2.png` | Deep Coverage speed vs source lines |
| `charts/per_iter_coverage_grid.png` | Tier-aware coverage heatmap (3 bands × variable lang rows) |
| `archive/legacy/` | Pre-2026-05-23 site (three-mode-report era + per-tier coverage) — historical reference only |

## License + contact

Project Euler problems and answers belong to Project Euler.  Per their
[publishing policy](https://projecteuler.net/about#publish), solution discussion
above problem 100 is restricted.  This repo strictly observes that boundary —
machine-readable answer values appear in *no* public file regardless of problem
number.  Discussion in MDs (story, methodology, scope explanations) follows the
≤100 rule.

Solutions were generated and audited by [Claude](https://claude.ai).  Methodology
discussion + the open question of what we should add next live in the GitHub
issues of the public repo.
