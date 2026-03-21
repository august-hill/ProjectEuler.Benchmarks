# ProjectEuler.Benchmarks

Cross-language performance comparisons for the first 100 [Project Euler](https://projecteuler.net/) problems.

## About This Project

This repository contains benchmark results comparing **9 programming languages** solving the same 100 problems with equivalent algorithms. All solutions were generated using [Claude Code](https://claude.ai/claude-code) powered by **Anthropic's Claude Opus 4.6**.

### The Question

**Does your choice of programming language actually matter for computational, algorithmic work?**

When an LLM generates equivalent solutions across languages — from low-level C to array-oriented APL — how much does the language itself contribute to (or detract from) performance? Are we paying a real cost for higher-level abstractions, or are modern compilers and runtimes close enough that the algorithm dominates?

### Language Repos

| Language | Repository | Paradigm |
|----------|------------|----------|
| [APL](https://github.com/august-hill/ProjectEuler.APL) | ProjectEuler.APL | Array-oriented |
| [C](https://github.com/august-hill/ProjectEuler.C) | ProjectEuler.C | Imperative |
| [C#](https://github.com/august-hill/ProjectEuler.CSharp) | ProjectEuler.CSharp | Object-oriented |
| [C++](https://github.com/august-hill/ProjectEuler.CPlusPlus) | ProjectEuler.CPlusPlus | Multi-paradigm |
| [Go](https://github.com/august-hill/ProjectEuler.Go) | ProjectEuler.Go | Imperative/CSP |
| [Haskell](https://github.com/august-hill/ProjectEuler.Haskell) | ProjectEuler.Haskell | Functional |
| [Java](https://github.com/august-hill/ProjectEuler.Java) | ProjectEuler.Java | Object-oriented |
| [Python](https://github.com/august-hill/ProjectEuler.Python) | ProjectEuler.Python | Multi-paradigm |
| [Rust](https://github.com/august-hill/ProjectEuler.Rust) | ProjectEuler.Rust | Systems |

## Benchmarks

See [BENCHMARKS.md](./BENCHMARKS.md) for detailed performance comparisons.

## Methodology

- **Platform**: Apple Silicon (M-series)
- **Warmup**: 10 iterations (sufficient for AOT-compiled languages; more for JIT)
- **Benchmark iterations**: Varies per problem (10-10,000)
- **Timing**: Language-native high-resolution timers
  - C: `mach_absolute_time()` (~42ns resolution on macOS)
  - C++: `std::chrono::high_resolution_clock`
  - C#: `System.Diagnostics.Stopwatch`
  - Go: `time.Now()` / `time.Since()`
  - Rust: `std::time::Instant`
  - Java: `System.nanoTime()`
  - Python: `time.perf_counter_ns()`
  - Haskell: `System.Clock` / `criterion`
  - APL: `⎕AI` (Dyalog)

## Generated with Claude

All solutions and benchmarks were generated using Claude Opus 4.6 via [Claude Code](https://claude.ai/claude-code).
