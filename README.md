# Project Euler — Cross-Language Benchmarks

**Per-invocation cost of solving Project Euler problems in 10 programming languages.**

Solutions written by [Claude](https://claude.ai) (Opus + Sonnet) across C, C++,
Rust, Go, Zig, Java, C#, JavaScript, Python, and ARM64 Assembly.  Benchmarked on
Apple Silicon.  See [JOURNEY.md](JOURNEY.md) for the full story of how this
project came together — and how it recently reset.

![Per-Invocation Cost](charts/per_iter_total.png)

## Current scope: 10 problems × 10 languages = 100 measurements

We're rebuilding from a verified core.  Every (language, problem) in scope has
passed an audit for state-leak safety, answer correctness, and methodology fit.
We'll extend the scope carefully — each new addition gets the same audit before
it appears in these numbers.

**See [RESULTS.md](RESULTS.md)** for the rankings, the per-problem detail grid,
and the full methodology.

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
cd ProjectEuler.Benchmarks
cmd/euler-bench/euler-bench per-iter --lang all --problems 1-10 --iters 10 --write
python3 report.py
```

The Go tool ([`cmd/euler-bench/`](cmd/euler-bench/)) is the single source of
truth for measurement — one binary builds, runs, validates answers, and writes
sanitized data atomically.  No flock, no hook chain, no per-language scripts.
See JOURNEY.md for the data-architecture refactor story.

## Trust + safety

This repo is **public**; the lang repos are **private**.  Per the project's
[PE compliance rules](CLAUDE.md), `data/<lang>.json` files NEVER contain an
`answer` field, for any problem.  Full data with answers lives in `data/private/`
(gitignored, local-only) for verification + debugging.  Triple-layer defense:

1. The `euler-bench per-iter --write` writer has no code path that emits answers
   to public files.
2. A post-write readback assertion fails loudly if any answer key reaches a
   public file.
3. A pre-commit hook ([`scripts/sanitization_gate.py`](scripts/sanitization_gate.py))
   runs the same check independently.

## Repo layout

| Path | What |
|------|------|
| `RESULTS.md` | The numbers — rankings, per-problem grid, methodology |
| `JOURNEY.md` | The story — how we got here, what we learned, what we tried that didn't work |
| `cmd/euler-bench/` | The Go benchmark + write tool (`run`, `failures`, `status`, `collect`, `per-iter`) |
| `report.py` | Markdown + chart generator (reads `data/`, writes `RESULTS.md` + `charts/`) |
| `data/<lang>.json` | Public bench data (sanitized) |
| `data/private/` | Full bench data (gitignored) |
| `scripts/sanitization_gate.py` | Pre-commit hook: enforce no-answer-in-public-data |
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
