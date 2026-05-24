# Project Euler — Cross-Language Benchmarks

> **Currently: 50 problems × 10 languages = 500 measurements.**
> Growing carefully — each new problem and language is audited for state-leak
> safety, verified for answer correctness, and added only when it cleanly fits the
> measurement methodology.  See [JOURNEY.md](JOURNEY.md) for the full story of how
> we got here, including the reset from 200+ problems back to a verified 10×10 core.

## Per-Invocation Cost (Total, Problems 1–50)

We run each program 10 times in fresh OS processes (no warmup, no shared state).
Each invocation pays full startup + algorithm cost — the cost a real CLI / cron /
shell-loop user actually pays.  The median wall time across the 10 invocations is
the headline per-problem number, and we sum across the 50 problems for the total.

![Per-Invocation Cost](charts/per_iter_total.png)

| Rank | Language | Total (50 problems) | Lines of code | vs Fastest |
|------|----------|--------------------:|--------------:|-----------:|
| 1 | **Zig** | 136.13 ms | 2,580 | 1.00× |
| 2 | **C** | 337.49 ms | 2,525 | 2.48× |
| 3 | **Rust** | 343.40 ms | 2,159 | 2.52× |
| 4 | **JavaScript** | 404.99 ms | 1,684 | 2.97× |
| 5 | **Java** | 458.83 ms | 2,119 | 3.37× |
| 6 | **ARM64** | 494.75 ms | 6,592 | 3.63× |
| 7 | **Go** | 568.92 ms | 2,328 | 4.18× |
| 8 | **C++** | 571.51 ms | 2,014 | 4.20× |
| 9 | **C#** | 1.60 s | 2,295 | 11.73× |
| 10 | **Python** | 11.36 s | 1,467 | 83.43× |

## Speed vs Code Size

How much code does each language need to solve these 50 problems, and how
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

Rows sorted fastest-to-slowest (top to bottom).  At our current 50×10 scope
every cell is green — that's exactly the audit gate we're holding to as we
extend to more problems.

## Per-Problem Detail

Median wall time per fresh-process invocation, for each (language, problem).  Rows
are sorted by total (fastest language at top).

| Language | p001 | p002 | p003 | p004 | p005 | p006 | p007 | p008 | p009 | p010 | p011 | p012 | p013 | p014 | p015 | p016 | p017 | p018 | p019 | p020 | p021 | p022 | p023 | p024 | p025 | p026 | p027 | p028 | p029 | p030 | p031 | p032 | p033 | p034 | p035 | p036 | p037 | p038 | p039 | p040 | p041 | p042 | p043 | p044 | p045 | p046 | p047 | p048 | p049 | p050 |
|----------|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|
| **Zig** | 42 ns | 42 ns | 708 ns | 3.8 µs | 417 ns | 42 ns | 219.1 µs | 1.6 µs | 250 ns | 2.77 ms | 2.4 µs | 1.40 ms | 42 ns | 8.94 ms | 42 ns | 477.2 µs | 2.2 µs | 42 ns | 4.7 µs | 31.9 µs | 1.52 ms | 1.03 ms | 8.56 ms | 292 ns | 6.85 ms | 652.8 µs | 6.08 ms | 41 ns | 542.9 µs | 1.50 ms | 1.0 µs | 1.16 ms | 2.0 µs | 9.92 ms | 2.32 ms | 4.94 ms | 1.95 ms | 215.1 µs | 104.0 µs | 291 ns | 8.55 ms | 227.1 µs | 11.18 ms | 36.45 ms | 44.6 µs | 3.98 ms | 8.36 ms | 104.0 µs | 2.58 ms | 3.45 ms |
| **C** | 41 ns | 41 ns | 583 ns | 3.2 µs | 416 ns | 42 ns | 29.9 µs | 2.7 µs | 250 ns | 355.6 µs | 1.5 µs | 1.45 ms | 42 ns | 10.72 ms | 42 ns | 491.2 µs | 2.2 µs | 250 ns | 5.0 µs | 26.2 µs | 1.52 ms | 1.58 ms | 8.58 ms | 167 ns | 6.46 ms | 612.9 µs | 7.44 ms | 42 ns | 12.4 µs | 1.41 ms | 708 ns | 12.59 ms | 8.2 µs | 9.68 ms | 3.10 ms | 54.81 ms | 2.57 ms | 1.94 ms | 3.4 µs | 9.34 ms | 7.78 ms | 308.6 µs | 10.36 ms | 50.25 ms | 48.7 µs | 3.97 ms | 6.95 ms | 146.5 µs | 119.30 ms | 3.63 ms |
| **Rust** | 42 ns | 83 ns | 94.8 µs | 17.8 µs | 583 ns | 42 ns | 245.7 µs | 10.6 µs | 291 ns | 1.08 ms | 42 ns | 1.35 ms | 39.4 µs | 7.23 ms | 42 ns | 57.9 µs | 2.0 µs | 250 ns | 4.8 µs | 23.4 µs | 1.82 ms | 711.1 µs | 92.96 ms | 708 ns | 7.09 ms | 5.66 ms | 7.85 ms | 875 ns | 4.38 ms | 2.37 ms | 2.2 µs | 13.35 ms | 7.7 µs | 9.10 ms | 28.86 ms | 79.01 ms | 2.73 ms | 1.70 ms | 3.5 µs | 7.56 ms | 7.61 ms | 119.6 µs | 10.76 ms | 15.65 ms | 48.2 µs | 5.56 ms | 7.00 ms | 169.5 µs | 18.53 ms | 2.66 ms |
| **JavaScript** | 19.0 µs | 12.1 µs | 49.2 µs | 96.8 µs | 29.0 µs | 7.1 µs | 2.69 ms | 99.4 µs | 27.0 µs | 10.11 ms | 148.0 µs | 1.65 ms | 42.8 µs | 20.94 ms | 12.2 µs | 42.6 µs | 172.9 µs | 41.0 µs | 127.3 µs | 41.6 µs | 2.49 ms | 1.53 ms | 16.19 ms | 37.3 µs | 486.8 µs | 1.26 ms | 13.49 ms | 24.8 µs | 1.27 ms | 6.00 ms | 67.3 µs | 9.54 ms | 236.8 µs | 34.33 ms | 8.88 ms | 65.25 ms | 7.28 ms | 1.54 ms | 93.0 µs | 10.21 ms | 14.54 ms | 938.0 µs | 35.42 ms | 56.05 ms | 707.2 µs | 9.81 ms | 11.36 ms | 1.16 ms | 47.98 ms | 10.45 ms |
| **Java** | 2.5 µs | 2.8 µs | 8.0 µs | 307.3 µs | 5.5 µs | 1.9 µs | 1.62 ms | 55.0 µs | 6.0 µs | 8.17 ms | 65.7 µs | 2.09 ms | 1.99 ms | 13.65 ms | 2.1 µs | 962.7 µs | 76.8 µs | 21.2 µs | 181.6 µs | 879.7 µs | 2.15 ms | 14.19 ms | 14.66 ms | 4.7 µs | 84.61 ms | 1.91 ms | 14.54 ms | 14.1 µs | 4.75 ms | 4.19 ms | 18.6 µs | 26.50 ms | 116.0 µs | 25.63 ms | 11.10 ms | 38.47 ms | 9.93 ms | 3.82 ms | 26.6 µs | 5.75 ms | 18.79 ms | 8.88 ms | 27.42 ms | 40.33 ms | 1.30 ms | 6.82 ms | 12.43 ms | 15.88 ms | 21.23 ms | 13.25 ms |
| **ARM64** | 0 ns | 0 ns | 1.0 µs | 3.0 µs | 1.0 µs | 0 ns | 306.0 µs | 4.0 µs | 1.0 µs | 5.45 ms | 3.0 µs | 63.71 ms | 2.0 µs | 179.38 ms | 0 ns | 476.0 µs | 3.0 µs | 1.0 µs | 7.0 µs | 16.0 µs | 2.39 ms | 1.33 ms | 11.22 ms | 0 ns | 7.45 ms | 1.04 ms | 8.46 ms | 1.0 µs | 55.31 ms | 1.81 ms | 2.0 µs | 1.48 ms | 15.0 µs | 11.43 ms | 3.64 ms | 5.66 ms | 3.27 ms | 207.0 µs | 2.60 ms | 1.33 ms | 8.49 ms | 27.0 µs | 15.84 ms | 84.68 ms | 77.0 µs | 4.84 ms | 7.82 ms | 132.0 µs | 1.22 ms | 3.61 ms |
| **Go** | 1.5 µs | 1.4 µs | 2.1 µs | 4.8 µs | 1.8 µs | 1.8 µs | 477.5 µs | 5.7 µs | 1.8 µs | 4.72 ms | 3.1 µs | 677.0 µs | 68.1 µs | 205.86 ms | 1.5 µs | 585.0 µs | 5.5 µs | 2.2 µs | 6.7 µs | 20.0 µs | 1.58 ms | 728.2 µs | 10.14 ms | 1.9 µs | 122.9 µs | 1.57 ms | 6.02 ms | 1.9 µs | 6.30 ms | 2.15 ms | 6.0 µs | 17.42 ms | 11.1 µs | 13.63 ms | 4.20 ms | 42.22 ms | 2.64 ms | 1.04 ms | 9.7 µs | 4.29 ms | 11.13 ms | 291.2 µs | 20.58 ms | 166.18 ms | 52.3 µs | 4.08 ms | 5.98 ms | 416.7 µs | 28.41 ms | 5.28 ms |
| **C++** | 166 ns | 167 ns | 34.7 µs | 32.0 µs | 542 ns | 42 ns | 24.4 µs | 3.0 µs | 334 ns | 375.9 µs | 500 ns | 1.47 ms | 19.7 µs | 252.19 ms | 167 ns | 626.8 µs | 2.5 µs | 292 ns | 4.3 µs | 27.6 µs | 1.51 ms | 1.28 ms | 29.33 ms | 625 ns | 5.88 ms | 733.4 µs | 9.73 ms | 83 ns | 2.28 ms | 1.41 ms | 708 ns | 7.46 ms | 8.2 µs | 9.62 ms | 5.55 ms | 63.08 ms | 3.69 ms | 559.8 µs | 2.8 µs | 3.78 ms | 17.54 ms | 315.7 µs | 9.92 ms | 40.85 ms | 49.2 µs | 3.76 ms | 93.61 ms | 125.4 µs | 213.0 µs | 4.41 ms |
| **C#** | 54.8 µs | 64.0 µs | 80.6 µs | 136.5 µs | 1.70 ms | 27.1 µs | 696.7 µs | 179.2 µs | 521.2 µs | 9.73 ms | 662.8 µs | 3.38 ms | 466.1 µs | 58.52 ms | 58.2 µs | 2.48 ms | 12.38 ms | 3.84 ms | 299.4 µs | 2.76 ms | 168.50 ms | 23.76 ms | 8.49 ms | 416.85 ms | 4.58 ms | 1.91 ms | 118.17 ms | 3.29 ms | 22.00 ms | 3.19 ms | 223.2 µs | 9.54 ms | 248.2 µs | 19.98 ms | 176.76 ms | 13.36 ms | 7.29 ms | 21.05 ms | 683.2 µs | 6.24 ms | 24.75 ms | 16.80 ms | 255.46 ms | 129.27 ms | 407.0 µs | 7.93 ms | 10.89 ms | 671.1 µs | 18.55 ms | 7.94 ms |
| **Python** | 1.6 µs | 3.0 µs | 5.59 ms | 55.36 ms | 4.5 µs | 916 ns | 1.38 ms | 852.1 µs | 4.64 ms | 5.27 ms | 223.6 µs | 21.13 ms | 4.3 µs | 6.15 s | 2.0 µs | 25.8 µs | 168.9 µs | 17.6 µs | 142.3 µs | 16.0 µs | 25.56 ms | 3.72 ms | 578.16 ms | 10.2 µs | 22.43 ms | 7.59 ms | 406.94 ms | 34.9 µs | 2.66 ms | 215.86 ms | 49.7 µs | 42.23 ms | 351.5 µs | 1.77 s | 100.18 ms | 146.76 ms | 75.41 ms | 4.04 ms | 82.9 µs | 17.55 ms | 61.0 µs | 1.12 ms | 921.46 ms | 161.44 ms | 3.60 ms | 20.36 ms | 395.76 ms | 642.8 µs | 77.64 ms | 109.16 ms |

## Method

For each (language, problem):

1. Build the binary (or `as` + `cc` for ARM64, `dotnet build` for C#, etc.).
2. Run the binary 10 times, each in a fresh OS process.  No warmup; no shared state.
3. Each invocation prints `RESULT|time_ns=N|answer=A` — one line per process,
   captured by the bench tool.  The answer is compared against the canonical
   (each source file's `// Answer:` header comment); the bench aborts on mismatch.
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

### Note on Zig timings (comptime-fold bias)

> Of the 10 problems benchmarked, **5 (p001, p002, p005, p006, p009)** are fully
> constant-foldable under Zig's `-O ReleaseFast` flag: the inputs are compile-time
> literals and the arithmetic is pure, so the optimizer reduces `solve()` to a
> constant return.  Those 5 cells in the Zig column measure "the cost of returning
> an immediate," not algorithm execution.  The remaining 5 (p003, p004, p007,
> p008, p010) do nontrivial runtime work and are honest timings.
>
> This is a systematic methodological bias that pulls Zig's aggregate ranking
> downward relative to languages whose optimizers don't fold as aggressively at
> these problem sizes.  Other compiled langs (C, C++ at `-O2`, Rust at `-O3`, Go,
> ARM64) also fold trivial closed-form cases; Zig is just particularly aggressive
> about it.  We flag it here for transparency rather than as a knock on Zig — the
> timings are real measurements of what `-O ReleaseFast` produces.

### Language idioms: stdlib vs ecosystem packages

Every language has a package ecosystem (Boost / vcpkg for C++, cargo / crates.io
for Rust, NuGet for C#, pip for Python, etc.), and *what a native developer would
write* almost always includes the well-known libraries for that ecosystem.
Forcing every language to stdlib-only would penalize languages whose ecosystems
are central to how they're actually used in practice.

Where a single library dominates the ecosystem for the problem domain, we use it:

| Language | Ecosystem package used | Rationale |
|----------|------------------------|-----------|
| **C++** | `primesieve` (Kim Walisch) | Best-in-class C++ prime library; commonly linked alongside Boost/abseil in C++ projects doing prime work. |
| **C** | `libprimesieve` (C bindings) | Same library, exposed via C API — `#include <primesieve.h>`, link `-lprimesieve`. |
| **Rust** | `primal` (Huon Wilson) | The dominant prime crate on crates.io; what a Rust dev doing prime work reaches for. |
| **Python** | `numpy` | The standard numerical-Python library; `primes[i*i::i] = False` slice assignment IS the Pythonic sieve. |
| **Go** | stdlib only | Go culture is stdlib-first; no single prime package dominates the ecosystem. |
| **Zig** | stdlib only | Zig's package ecosystem is young; stdlib-only is current idiom. |
| **Java** | stdlib only | Apache Commons Math has primes, but Java culture is split between stdlib-only and Commons; we keep it stdlib for now. |
| **C#** | stdlib only | `Open.Numeric.Primes` exists but isn't dominant; most C# devs roll their own sieve at this scale. |
| **JavaScript** | stdlib (Node) only | `Uint8Array` typed-array sieve IS the perf-aware JS idiom; no npm package is dominant. |
| **ARM64** | libc (`malloc`/`free`) | The "ecosystem" for asm IS the platform's libc; that's what we use. |

**Implication for the chart**: C++'s ~340 µs total reflects both "C++ language
speed" and "primesieve is a well-optimized library."  If we measured
hand-rolled C++ against hand-rolled Rust/Go/Zig, the gap would shrink.  We
report C++ at its ecosystem-aware best, because *that's how C++ devs actually
write C++*.  Same principle applies symmetrically to every other lang.

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

