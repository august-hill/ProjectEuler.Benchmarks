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
| 1 | **C** | 392.7 µs | 349 | 1.00× |
| 2 | **C++** | 471.3 µs | 256 | 1.20× |
| 3 | **Rust** | 1.45 ms | 219 | 3.70× |
| 4 | **Zig** | 2.99 ms | 372 | 7.62× |
| 5 | **Go** | 5.22 ms | 340 | 13.28× |
| 6 | **ARM64** | 5.77 ms | 721 | 14.69× |
| 7 | **Java** | 10.18 ms | 336 | 25.91× |
| 8 | **JavaScript** | 13.14 ms | 254 | 33.47× |
| 9 | **C#** | 13.18 ms | 307 | 33.57× |
| 10 | **Python** | 73.09 ms | 244 | 186.13× |

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
| **C** | 41 ns | 41 ns | 583 ns | 3.2 µs | 416 ns | 42 ns | 29.9 µs | 2.7 µs | 250 ns | 355.6 µs |
| **C++** | 166 ns | 167 ns | 34.7 µs | 32.0 µs | 542 ns | 42 ns | 24.4 µs | 3.0 µs | 334 ns | 375.9 µs |
| **Rust** | 42 ns | 83 ns | 94.8 µs | 17.8 µs | 583 ns | 42 ns | 245.7 µs | 10.6 µs | 291 ns | 1.08 ms |
| **Zig** | 42 ns | 42 ns | 708 ns | 3.8 µs | 417 ns | 42 ns | 219.1 µs | 1.6 µs | 250 ns | 2.77 ms |
| **Go** | 1.5 µs | 1.4 µs | 2.1 µs | 4.8 µs | 1.8 µs | 1.8 µs | 477.5 µs | 5.7 µs | 1.8 µs | 4.72 ms |
| **ARM64** | 0 ns | 0 ns | 1.0 µs | 3.0 µs | 1.0 µs | 0 ns | 306.0 µs | 4.0 µs | 1.0 µs | 5.45 ms |
| **Java** | 2.5 µs | 2.8 µs | 8.0 µs | 307.3 µs | 5.5 µs | 1.9 µs | 1.62 ms | 55.0 µs | 6.0 µs | 8.17 ms |
| **JavaScript** | 19.0 µs | 12.1 µs | 49.2 µs | 96.8 µs | 29.0 µs | 7.1 µs | 2.69 ms | 99.4 µs | 27.0 µs | 10.11 ms |
| **C#** | 54.8 µs | 64.0 µs | 80.6 µs | 136.5 µs | 1.70 ms | 27.1 µs | 696.7 µs | 179.2 µs | 521.2 µs | 9.73 ms |
| **Python** | 1.6 µs | 3.0 µs | 5.59 ms | 55.36 ms | 4.5 µs | 916 ns | 1.38 ms | 852.1 µs | 4.64 ms | 5.27 ms |

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

