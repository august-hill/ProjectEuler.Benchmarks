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

| Rank | Language | Total (10 problems) | Lines of code | vs Fastest |
|------|----------|--------------------:|--------------:|-----------:|
| 1 | **C++** | 345.8 µs | 268 | 1.00× |
| 2 | **C** | 2.28 ms | 391 | 6.60× |
| 3 | **Rust** | 2.55 ms | 264 | 7.37× |
| 4 | **Zig** | 2.78 ms | 363 | 8.04× |
| 5 | **Go** | 4.36 ms | 366 | 12.61× |
| 6 | **ARM64** | 5.07 ms | 717 | 14.67× |
| 7 | **Java** | 10.20 ms | 356 | 29.50× |
| 8 | **JavaScript** | 13.36 ms | 254 | 38.64× |
| 9 | **C#** | 16.15 ms | 307 | 46.71× |
| 10 | **Python** | 75.95 ms | 247 | 219.61× |

## Speed vs Code Size

How much code does each language need to solve these 10 problems, and how
fast does that code run?  Bottom-left = fast and concise; top-right = slow
and verbose.  ARM64's outlier position (most lines) is expected — assembly
trades verbosity for direct hardware control.

![Speed vs Code Size](charts/per_iter_speed_vs_size.png)

## Coverage + Speed Heatmap

One cell per (language, problem).  Color shows whether the cell passes the
invocation-isolation + answer-correctness audit and how fast it runs:

- 🟢 **Green** — pass; lighter green = faster, darker green = slower
- 🟡 **Yellow** — pass but > 100 ms (slow algorithm or heavy startup)
- 🔴 **Red** — fail (wrong answer, build error, timeout)
- ⚫ **Black** — missing entry (no measurement)

![Coverage + Speed Heatmap](charts/per_iter_coverage_grid.png)

Rows sorted fastest-to-slowest (top to bottom).  At our current 10×10 scope
every cell is green — that's exactly the audit gate we're holding to as we
extend to more problems.

## Per-Problem Detail

Median wall time per fresh-process invocation, for each (language, problem).  Rows
are sorted by total (fastest language at top).

| Language | p001 | p002 | p003 | p004 | p005 | p006 | p007 | p008 | p009 | p010 |
|----------|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|
| **C++** | 42 ns | 125 ns | 28.0 µs | 26.0 µs | 333 ns | 42 ns | 24.5 µs | 3.1 µs | 292 ns | 263.4 µs |
| **C** | 42 ns | 42 ns | 667 ns | 3.4 µs | 375 ns | 42 ns | 178.2 µs | 1.8 µs | 250 ns | 2.10 ms |
| **Rust** | 42 ns | 84 ns | 28.3 µs | 14.2 µs | 416 ns | 42 ns | 390.2 µs | 10.5 µs | 250 ns | 2.11 ms |
| **Zig** | 41 ns | 42 ns | 625 ns | 4.0 µs | 500 ns | 42 ns | 556.4 µs | 2.1 µs | 333 ns | 2.22 ms |
| **Go** | 1.8 µs | 2.1 µs | 2.5 µs | 5.6 µs | 2.2 µs | 2.0 µs | 356.3 µs | 5.4 µs | 2.1 µs | 3.98 ms |
| **ARM64** | 2.0 µs | 0 ns | 1.0 µs | 3.0 µs | 1.0 µs | 0 ns | 282.0 µs | 4.0 µs | 1.0 µs | 4.78 ms |
| **Java** | 2.6 µs | 3.4 µs | 8.9 µs | 317.3 µs | 5.2 µs | 2.2 µs | 1.58 ms | 54.5 µs | 6.5 µs | 8.22 ms |
| **JavaScript** | 20.7 µs | 12.7 µs | 53.2 µs | 98.6 µs | 31.1 µs | 8.0 µs | 2.73 ms | 96.3 µs | 28.7 µs | 10.28 ms |
| **C#** | 300.1 µs | 283.7 µs | 320.0 µs | 440.7 µs | 2.02 ms | 276.9 µs | 1.02 ms | 491.9 µs | 704.2 µs | 10.29 ms |
| **Python** | 1.7 µs | 3.3 µs | 7.65 ms | 56.01 ms | 4.7 µs | 917 ns | 1.36 ms | 877.4 µs | 4.72 ms | 5.32 ms |

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

### How each language is built

Every compiled language uses release / optimized builds — no debug-mode
measurements:

| Language | Build command | Optimization |
|----------|---------------|--------------|
| C | `gcc -O2 -std=c11 -I.. main.c -o main_bench -lm` | `-O2` |
| C++ | `g++ -O2 -std=c++17 -I../include main.cpp -o main_bench -lm` | `-O2` |
| ARM64 | `as ... && cc -O2 -o main_bench main.c solve.o -lm` | `-O2` on the C harness; the `.s` file is hand-tuned |
| Rust | `cargo build --release` | `opt-level=3 + lto=true` (per repo's `[profile.release]`) |
| Go | `go build -o main_bench main.go` | default (Go optimizes by default; no `-N` debug flag) |
| Zig | `zig build-exe -O ReleaseFast ...` | `ReleaseFast` |
| C# | `dotnet build -c Release` | `Release` |
| Java | `javac Main.java` | none at compile; JVM JIT optimizes at runtime |
| JavaScript | (no build) | V8 JIT optimizes at runtime |
| Python | (no build) | none — interpreter |

Note: Java/JS/C# show a runtime startup penalty in the per-invocation cost
because their JIT/runtime warm-up happens *every* fresh process.  This is
the honest cost of the language model under a CLI-invocation workload.

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

