# Project Euler — Cross-Language Benchmarks

> **Currently: 50 problems × 10 languages = 500 measurements.**
> Growing carefully — each new problem and language is audited for state-leak
> safety, verified for answer correctness, and added only when it cleanly fits the
> measurement methodology.  See [JOURNEY.md](JOURNEY.md) for the full story of how
> we got here, including the reset from 200+ problems back to a verified 10×10
> core, then the disciplined expansion to today's 50×10 scope.

## Per-Invocation Cost (Total, Problems 1–50)

We run each program 10 times in fresh OS processes (no warmup, no shared state).
Each invocation pays full startup + algorithm cost — the cost a real CLI / cron /
shell-loop user actually pays.  The median wall time across the 10 invocations is
the headline per-problem number, and we sum across the 50 problems for the total.

![Per-Invocation Cost](charts/per_iter_total.png)

| Rank | Language | Total (50 problems) | Lines of code | vs Fastest |
|------|----------|--------------------:|--------------:|-----------:|
| 1 | **ARM64** | 103.89 ms | 6,958 | 1.00× |
| 2 | **Zig** | 129.99 ms | 2,580 | 1.25× |
| 3 | **C** | 326.34 ms | 2,525 | 3.14× |
| 4 | **C++** | 330.00 ms | 2,010 | 3.18× |
| 5 | **Rust** | 342.37 ms | 2,159 | 3.30× |
| 6 | **Go** | 373.42 ms | 2,354 | 3.59× |
| 7 | **JavaScript** | 411.53 ms | 1,684 | 3.96× |
| 8 | **Java** | 463.37 ms | 2,119 | 4.46× |
| 9 | **C#** | 1.61 s | 2,295 | 15.51× |
| 10 | **Python** | 11.55 s | 1,467 | 111.19× |

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

**🔍 [Open the SVG version](https://raw.githubusercontent.com/august-hill/ProjectEuler.Benchmarks/main/charts/per_iter_coverage_grid.svg)** — same chart, with a
hover tooltip on every cell (`p347 Zig: 2.3 ms`).  The link goes direct to
`raw.githubusercontent.com` because GitHub's `/blob/` viewer no longer renders
inline SVG previews; tooltips also don't fire inside the inline `![](...)`
image above because browsers treat `<img>` SVGs as opaque.

Rows are in fixed tier order (native → managed → interpreted) so the chart
doesn't reshuffle between snapshots as ranking-by-total drifts.  Problems are
chunked into bands of 100 (currently 1 band), which keeps cells legibly sized as we extend
toward the 1000-problem target.  Native compiled rows (ARM64 / C / C++ / Rust /
Zig) sit near the top in mostly bright-green territory; managed-runtime rows
(C# / Java / JavaScript) carry darker greens and scattered amber from JIT
startup; Python at the bottom shows the heaviest amber load.  Vertical amber
bars that cut across multiple languages (currently visible near p061 and p071)
flag *intrinsically hard* problems — the algorithm cost dominates regardless of
language.  No red or black cells: the audit gate is holding.

## Per-Problem Detail

Median wall time per fresh-process invocation, for each (language, problem).
Problems are chunked into bands of 100 (matching the heatmap above) so
each table stays narrow enough for GitHub's markdown renderer.  Columns are in
fixed tier order (native → managed → interpreted).

### Problems 001–050

| Problem | ARM64 | C | C++ | Rust | Zig | Go | C# | Java | JavaScript | Python |
|---------|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|
| **p001** | 0 ns | 42 ns | 167 ns | 41 ns | 42 ns | 1.6 µs | 65.9 µs | 2.6 µs | 18.0 µs | 1.5 µs |
| **p002** | 0 ns | 42 ns | 167 ns | 83 ns | 42 ns | 1.3 µs | 85.9 µs | 2.7 µs | 11.5 µs | 3.1 µs |
| **p003** | 0 ns | 667 ns | 27.1 µs | 80.4 µs | 750 ns | 1.7 µs | 89.2 µs | 8.3 µs | 49.6 µs | 5.73 ms |
| **p004** | 2.0 µs | 3.4 µs | 25.5 µs | 14.0 µs | 3.1 µs | 4.7 µs | 189.1 µs | 315.2 µs | 98.5 µs | 56.40 ms |
| **p005** | 1.0 µs | 333 ns | 375 ns | 584 ns | 500 ns | 2.1 µs | 1.92 ms | 5.4 µs | 29.0 µs | 5.2 µs |
| **p006** | 0 ns | 42 ns | 125 ns | 42 ns | 42 ns | 1.8 µs | 60.1 µs | 2.0 µs | 7.3 µs | 1.1 µs |
| **p007** | 247.0 µs | 22.8 µs | 24.8 µs | 258.2 µs | 177.6 µs | 453.8 µs | 812.2 µs | 1.61 ms | 2.86 ms | 1.39 ms |
| **p008** | 4.0 µs | 2.8 µs | 2.4 µs | 14.2 µs | 1.7 µs | 4.5 µs | 174.0 µs | 56.4 µs | 98.8 µs | 877.2 µs |
| **p009** | 0 ns | 208 ns | 292 ns | 208 ns | 208 ns | 1.3 µs | 504.7 µs | 6.0 µs | 26.5 µs | 4.81 ms |
| **p010** | 1.49 ms | 350.1 µs | 308.7 µs | 1.14 ms | 2.13 ms | 4.70 ms | 9.93 ms | 8.26 ms | 10.35 ms | 5.35 ms |
| **p011** | 3.0 µs | 1.4 µs | 625 ns | 42 ns | 1.5 µs | 3.9 µs | 638.8 µs | 64.2 µs | 148.9 µs | 225.9 µs |
| **p012** | 1.15 ms | 1.08 ms | 1.46 ms | 1.31 ms | 1.09 ms | 989.6 µs | 3.39 ms | 2.15 ms | 1.70 ms | 21.62 ms |
| **p013** | 2.0 µs | 42 ns | 15.4 µs | 48.0 µs | 42 ns | 44.5 µs | 432.1 µs | 2.01 ms | 42.3 µs | 5.0 µs |
| **p014** | 9.30 ms | 10.74 ms | 13.22 ms | 7.53 ms | 7.58 ms | 11.00 ms | 59.73 ms | 13.78 ms | 20.78 ms | 6.28 s |
| **p015** | 0 ns | 42 ns | 83 ns | 42 ns | 42 ns | 1.8 µs | 56.4 µs | 2.3 µs | 11.7 µs | 2.0 µs |
| **p016** | 354.0 µs | 368.9 µs | 435.9 µs | 39.6 µs | 362.8 µs | 600.0 µs | 2.37 ms | 973.5 µs | 33.8 µs | 25.2 µs |
| **p017** | 3.0 µs | 1.7 µs | 1.8 µs | 2.2 µs | 2.2 µs | 4.1 µs | 12.01 ms | 84.4 µs | 169.5 µs | 169.2 µs |
| **p018** | 1.0 µs | 208 ns | 292 ns | 458 ns | 41 ns | 2.2 µs | 3.92 ms | 23.8 µs | 34.7 µs | 19.1 µs |
| **p019** | 6.0 µs | 4.2 µs | 3.4 µs | 7.6 µs | 4.7 µs | 6.7 µs | 233.1 µs | 196.5 µs | 113.8 µs | 141.4 µs |
| **p020** | 20.0 µs | 23.8 µs | 22.4 µs | 20.1 µs | 20.4 µs | 13.2 µs | 2.38 ms | 929.9 µs | 36.3 µs | 17.0 µs |
| **p021** | 1.71 ms | 1.41 ms | 1.56 ms | 1.90 ms | 1.69 ms | 1.21 ms | 170.34 ms | 2.22 ms | 2.46 ms | 25.94 ms |
| **p022** | 1.56 ms | 1.36 ms | 1.58 ms | 581.4 µs | 754.1 µs | 736.5 µs | 25.68 ms | 14.80 ms | 1.52 ms | 3.79 ms |
| **p023** | 10.99 ms | 7.21 ms | 29.22 ms | 93.89 ms | 8.46 ms | 10.48 ms | 8.64 ms | 14.59 ms | 16.04 ms | 584.18 ms |
| **p024** | 0 ns | 208 ns | 542 ns | 667 ns | 250 ns | 1.8 µs | 419.48 ms | 5.2 µs | 39.1 µs | 12.0 µs |
| **p025** | 601.0 µs | 4.83 ms | 5.78 ms | 6.01 ms | 7.17 ms | 123.4 µs | 4.39 ms | 85.74 ms | 509.0 µs | 22.61 ms |
| **p026** | 1.24 ms | 652.2 µs | 679.2 µs | 5.04 ms | 451.4 µs | 1.53 ms | 1.97 ms | 1.99 ms | 1.29 ms | 7.71 ms |
| **p027** | 6.67 ms | 5.72 ms | 10.36 ms | 7.64 ms | 5.92 ms | 5.75 ms | 119.87 ms | 14.72 ms | 13.16 ms | 414.22 ms |
| **p028** | 1.0 µs | 41 ns | 42 ns | 708 ns | 42 ns | 1.8 µs | 3.17 ms | 14.6 µs | 24.6 µs | 36.5 µs |
| **p029** | 24.0 µs | 10.7 µs | 2.32 ms | 5.58 ms | 351.9 µs | 5.48 ms | 22.52 ms | 5.04 ms | 1.30 ms | 2.70 ms |
| **p030** | 1.78 ms | 1.57 ms | 1.50 ms | 1.93 ms | 1.39 ms | 1.70 ms | 3.04 ms | 4.20 ms | 5.77 ms | 218.16 ms |
| **p031** | 1.0 µs | 834 ns | 625 ns | 1.9 µs | 750 ns | 5.7 µs | 216.0 µs | 18.3 µs | 66.3 µs | 47.0 µs |
| **p032** | 1.58 ms | 12.12 ms | 6.69 ms | 13.24 ms | 1.18 ms | 17.09 ms | 9.49 ms | 27.05 ms | 9.14 ms | 42.78 ms |
| **p033** | 9.0 µs | 8.2 µs | 8.2 µs | 5.5 µs | 1.8 µs | 11.5 µs | 236.8 µs | 120.8 µs | 226.4 µs | 365.2 µs |
| **p034** | 11.03 ms | 9.96 ms | 10.44 ms | 9.36 ms | 9.11 ms | 13.99 ms | 19.72 ms | 26.09 ms | 34.04 ms | 1.79 s |
| **p035** | 2.80 ms | 2.55 ms | 4.17 ms | 29.86 ms | 2.30 ms | 3.80 ms | 177.77 ms | 11.28 ms | 8.76 ms | 102.10 ms |
| **p036** | 4.30 ms | 54.29 ms | 62.49 ms | 80.25 ms | 5.14 ms | 43.11 ms | 13.41 ms | 38.41 ms | 65.83 ms | 150.62 ms |
| **p037** | 2.31 ms | 2.90 ms | 4.02 ms | 2.40 ms | 1.33 ms | 2.51 ms | 7.03 ms | 10.04 ms | 7.28 ms | 77.73 ms |
| **p038** | 168.0 µs | 1.40 ms | 400.1 µs | 1.77 ms | 192.8 µs | 826.3 µs | 21.53 ms | 3.77 ms | 1.62 ms | 4.06 ms |
| **p039** | 5.0 µs | 2.3 µs | 2.8 µs | 3.3 µs | 82.0 µs | 7.8 µs | 709.0 µs | 27.3 µs | 90.9 µs | 92.4 µs |
| **p040** | 1.21 ms | 7.84 ms | 2.94 ms | 7.57 ms | 334 ns | 3.51 ms | 6.36 ms | 5.82 ms | 10.67 ms | 17.73 ms |
| **p041** | 8.47 ms | 7.49 ms | 17.55 ms | 6.93 ms | 8.36 ms | 11.28 ms | 25.16 ms | 19.01 ms | 15.32 ms | 61.5 µs |
| **p042** | 29.0 µs | 211.3 µs | 265.4 µs | 86.7 µs | 166.0 µs | 272.2 µs | 18.31 ms | 9.27 ms | 1.09 ms | 1.19 ms |
| **p043** | 16.08 ms | 10.33 ms | 9.88 ms | 10.36 ms | 10.68 ms | 20.20 ms | 255.07 ms | 26.90 ms | 36.99 ms | 934.07 ms |
| **p044** | 3.86 ms | 50.19 ms | 40.58 ms | 15.69 ms | 37.49 ms | 167.73 ms | 131.82 ms | 40.08 ms | 56.95 ms | 162.79 ms |
| **p045** | 58.0 µs | 37.9 µs | 38.5 µs | 37.9 µs | 44.8 µs | 52.1 µs | 420.2 µs | 1.34 ms | 741.0 µs | 3.62 ms |
| **p046** | 4.73 ms | 4.00 ms | 4.01 ms | 5.08 ms | 4.06 ms | 4.31 ms | 7.82 ms | 6.92 ms | 9.81 ms | 20.71 ms |
| **p047** | 6.19 ms | 6.01 ms | 93.04 ms | 5.93 ms | 6.62 ms | 6.12 ms | 10.97 ms | 12.51 ms | 12.13 ms | 398.50 ms |
| **p048** | 122.0 µs | 148.3 µs | 141.1 µs | 169.8 µs | 105.5 µs | 507.7 µs | 686.2 µs | 16.47 ms | 1.29 ms | 664.8 µs |
| **p049** | 1.12 ms | 117.74 ms | 227.1 µs | 17.98 ms | 2.13 ms | 28.33 ms | 18.78 ms | 21.27 ms | 49.93 ms | 78.34 ms |
| **p050** | 2.65 ms | 3.76 ms | 4.54 ms | 2.59 ms | 3.42 ms | 4.90 ms | 8.15 ms | 13.18 ms | 10.81 ms | 112.54 ms |

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

> Of the 50 problems benchmarked, **roughly 20-25% of cells** are fully
> constant-foldable under Zig's `-O ReleaseFast` flag: the inputs are compile-time
> literals and the arithmetic is pure, so the optimizer reduces `solve()` to a
> constant return.  Known fold-candidates include p001, p002, p005, p006, p009,
> p013, p017, p018, p019, p024, p028, p031, p033, p040, p045, p063, p069, p094,
> p097, p100.  Those cells in the Zig column measure "the cost of returning an
> immediate," not algorithm execution.  The remaining ~75% do nontrivial runtime
> work and are honest timings.
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
cd pe/benchmarks
cmd/euler-bench/euler-bench per-iter --lang all --problems 1-50 --iters 10 --write
python3 report.py
```

Sanitization invariant: the public repo carries no raw bench data files —
only this rendered narrative and the charts.  All measurements live in the
gitignored SQLite SSOT `data/bench-private.db`.  See `scripts/sanitization_gate.py`.

## Methodology Story

See [JOURNEY.md](JOURNEY.md) for the full story.  Recent chapters cover:
- The 24-hour cache-strip campaign and its reset (155 source edits reverted)
- The shift from in-process warm iterations to fresh-process per-invocation cost
- The invocation-isolation principle and why the OS is the audit tool
- The data-architecture refactor (single Go writer, no `flock`, no hook chain)

