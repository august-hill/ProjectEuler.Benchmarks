# ProjectEuler.Benchmarks

Cross-language performance comparisons for [Project Euler](https://projecteuler.net/) solutions.

All benchmarks run on Apple Silicon (M-series) with warmup iterations.

## Language Repos

| Language | Repository |
|----------|------------|
| C | [ProjectEuler.C](https://github.com/august-hill/ProjectEuler.C) |
| C# | [ProjectEuler.CSharp](https://github.com/august-hill/ProjectEuler.CSharp) |
| C++ | [ProjectEuler.CPlusPlus](https://github.com/august-hill/ProjectEuler.CPlusPlus) |
| Go | [ProjectEuler.Go](https://github.com/august-hill/ProjectEuler.Go) |
| Python | [ProjectEuler.Python](https://github.com/august-hill/ProjectEuler.Python) |
| Rust | [ProjectEuler.Rust](https://github.com/august-hill/ProjectEuler.Rust) |

## Benchmarks

See [BENCHMARKS.md](./BENCHMARKS.md) for detailed performance comparisons.

### Key Takeaways

1. **Rust and C are generally within 20%** of each other for most problems
2. **Go adds ~50-100% overhead** vs Rust/C for compute-heavy tasks
3. **LLVM optimizations matter**: Problems 14, 44, 49 show Rust winning big
4. **C wins on simple loops**: Problems 23, 26, 35 show C's strength
5. **Algorithmic shortcuts dominate**: Problem 13's shortcut is 60x faster

## Methodology

- **Warmup**: 10 iterations (sufficient for AOT-compiled languages)
- **Benchmark iterations**: Varies per problem (10-10,000)
- **Timing**: Language-native high-resolution timers
  - Go: `time.Now()` / `time.Since()`
  - Rust: `std::time::Instant`
  - C: `mach_absolute_time()` (~42ns resolution on macOS)
  - C#: `System.Diagnostics.Stopwatch`
