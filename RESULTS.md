# Project Euler — Cross-Language Benchmarks

> **Currently: 10 problems × 10 languages = 100 measurements.**
> Growing carefully — each new problem and language is audited for state-leak
> safety, verified for answer correctness, and added only when it cleanly fits the
> measurement methodology.  See [JOURNEY.md](JOURNEY.md) for the full story of how
> we got here, including the reset from 200+ problems back to a verified 10×10 core.

## Per-Invocation Cost (Total, Problems 1–10)

We run each program 10 times in fresh OS processes (no warmup, no shared state).
Each invocation pays full startup + algorithm cost — the cost a real CLI / cron /
shell-loop user actually pays.  The median wall time across the 10 invocations is
the headline per-problem number, and we sum across the 10 problems for the total.

![Per-Invocation Cost](charts/per_iter_total.png)

| Rank | Language | Total (10 problems) | vs Fastest |
|------|----------|--------------------:|-----------:|
| 1 | **C++** | 338.7 µs | 1.00× |
| 2 | **C** | 2.25 ms | 6.65× |
| 3 | **Rust** | 2.49 ms | 7.34× |
| 4 | **Zig** | 2.79 ms | 8.23× |
| 5 | **Go** | 4.28 ms | 12.63× |
| 6 | **ARM64** | 5.07 ms | 14.96× |
| 7 | **Java** | 9.89 ms | 29.21× |
| 8 | **JavaScript** | 13.07 ms | 38.60× |
| 9 | **C#** | 15.83 ms | 46.75× |
| 10 | **Python** | 75.82 ms | 223.87× |

## Per-Problem Detail

Median wall time per fresh-process invocation, for each (language, problem).  Rows
are sorted by total (fastest language at top).

| Language | p001 | p002 | p003 | p004 | p005 | p006 | p007 | p008 | p009 | p010 |
|----------|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|
| **C++** | 84 ns | 84 ns | 27.1 µs | 25.0 µs | 333 ns | 83 ns | 21.6 µs | 3.1 µs | 333 ns | 261.0 µs |
| **C** | 41 ns | 42 ns | 750 ns | 3.5 µs | 375 ns | 41 ns | 170.7 µs | 1.2 µs | 250 ns | 2.07 ms |
| **Rust** | 42 ns | 83 ns | 28.0 µs | 13.6 µs | 417 ns | 41 ns | 385.6 µs | 10.7 µs | 250 ns | 2.05 ms |
| **Zig** | 42 ns | 83 ns | 833 ns | 3.9 µs | 625 ns | 83 ns | 524.5 µs | 1.8 µs | 292 ns | 2.25 ms |
| **Go** | 2.0 µs | 1.7 µs | 2.3 µs | 4.9 µs | 2.2 µs | 1.4 µs | 348.3 µs | 5.1 µs | 2.0 µs | 3.91 ms |
| **ARM64** | 2.0 µs | 0 ns | 1.0 µs | 2.0 µs | 1.0 µs | 0 ns | 289.0 µs | 3.0 µs | 1.0 µs | 4.77 ms |
| **Java** | 3.2 µs | 3.5 µs | 8.2 µs | 295.8 µs | 4.7 µs | 2.4 µs | 1.57 ms | 59.5 µs | 6.6 µs | 7.93 ms |
| **JavaScript** | 16.3 µs | 11.7 µs | 54.8 µs | 91.3 µs | 28.8 µs | 6.8 µs | 2.65 ms | 95.7 µs | 27.7 µs | 10.09 ms |
| **C#** | 247.8 µs | 246.5 µs | 306.4 µs | 314.8 µs | 2.06 ms | 222.0 µs | 1.08 ms | 415.0 µs | 769.0 µs | 10.18 ms |
| **Python** | 1.4 µs | 2.0 µs | 7.67 ms | 55.93 ms | 5.1 µs | 1.2 µs | 1.38 ms | 864.8 µs | 4.66 ms | 5.30 ms |

## Method

For each (language, problem):

1. Build the binary (or `as` + `cc` for ARM64, `dotnet build` for C#, etc.).
2. Run the binary 10 times, each in a fresh OS process.  No warmup; no shared state.
3. Each invocation prints `BENCHMARK|problem=NNN|answer=X|time_ns=Y`.  The answer
   is compared against the canonical (each source file's `// Answer:` header
   comment); the benchmark aborts on mismatch.
4. We report the **median** wall time across the 10 invocations.

That's the entire metric.  No "hot" vs "cold" — just per-invocation cost, which
is what every CLI / cron / shell-loop user actually pays.

### What's intentionally not measured

- **In-process warm iterations.**  Server / daemon scenarios are a different
  question — they'd reward language-internal caches (Rust `OnceLock`, primesieve
  internal state, `@lru_cache`, etc.) in ways that don't match the per-invocation
  reality.  See [JOURNEY.md](JOURNEY.md) for the full reasoning behind dropping the
  warm-iter metric.
- **Compile time as a separate column.**  Build cost is part of the user's
  experience for compiled languages, but in our "shell-loop" model the binary is
  already built once.  Build time is observed and recorded for diagnostic use but
  not part of the headline.

### Why the OS process boundary IS the audit tool

Every language has *some* way to cache state for re-use within one process: Rust's
`OnceLock`, C++ libraries' internal lazy-init, Python's `@lru_cache`, Java's static
`final` precomputed tables.  These are *idiomatic, valuable patterns in their
languages*.  We don't want to rule them out — we want each language to look like a
native would write it.

The process boundary makes that work fairly: when each invocation is a fresh OS
process, *every* in-process cache starts empty.  No language gets an unfair
amortization advantage.  No source-code refactoring is required to maintain cross-
language honesty — the OS enforces it for free.

## Sub-Millisecond Floor

On Apple Silicon, process spawn (`fork` + `exec`) costs ~5–10 ms.  Problems where
the algorithm takes < 1 ms (currently p001–p006 in most languages) are effectively
measuring spawn cost, not algorithmic merit.  That **is** what a CLI user pays, so
the number is still meaningful — but the cross-language signal on these problems
mostly reflects runtime startup cost.  The interesting algorithmic signal starts
around p007+.

## Reproducibility

```bash
cd ProjectEuler.Benchmarks
cmd/euler-bench/euler-bench per-iter --lang all --problems 1-10 --iters 10 --write
python3 report.py
```

Sanitization invariant: `data/<lang>.json` files NEVER contain an `answer` field,
regardless of problem number.  Full data including answers lives in `data/private/`
(gitignored), used locally for verification.  See `scripts/sanitization_gate.py`.

## Methodology Story

See [JOURNEY.md](JOURNEY.md) for the full story.  Recent chapters cover:
- The 24-hour cache-strip campaign and its reset (155 source edits reverted)
- The shift from in-process warm iterations to fresh-process per-invocation cost
- The invocation-isolation principle and why the OS is the audit tool
- The data-architecture refactor (single Go writer, no `flock`, no hook chain)

