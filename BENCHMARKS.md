# Performance Benchmarks

All benchmarks run on Apple Silicon (M-series) with warmup iterations and benchmarking iterations as noted.

---

## Quick Reference: Fastest Language Per Problem

| Problem | Winner | Margin |
|---------|--------|--------|
| 10 | Rust/C | 2x faster than Go |
| 14 | **Rust** | 10x faster (LLVM optimization) |
| 23 | **C** | 11x faster |
| 26 | **C** | 8x faster |
| 35 | **C** | 10x faster |
| 44 | **Rust** | 2.6x faster |
| 49 | **Rust** | 7x faster |

Most problems: Rust and C are within 20% of each other.

---

## Problems 1-11 (Go, Rust, C)

### Problem 1: Multiples of 3 or 5
| Language | Brute Force | Arithmetic Formula |
|----------|-------------|-------------------|
| Go | 13.33 µs | 42 ns |
| Rust | 750 ns | ~0 ns |
| C | 2.00 µs | ~0 ns |

*Closed-form arithmetic is instant; brute force shows Go overhead*

### Problem 2: Even Fibonacci
| Language | Even Recurrence |
|----------|-----------------|
| Go | 83 ns |
| Rust | 42 ns |
| C | ~0 ns |

*All blazing fast*

### Problem 3: Largest Prime Factor
| Language | Optimized Trial (6k±1) | Pollard's Rho |
|----------|------------------------|---------------|
| Go | 667 ns | 71.5 µs |
| Rust | 833 ns | 78.0 µs |
| C | ~0 ns | 28.0 µs |

### Problem 4: Largest Palindrome Product
| Language | Divisible by 11 |
|----------|-----------------|
| Go | 3.4 µs |
| Rust | 1.4 µs |
| C | 2.0 µs |

### Problem 5: Smallest Multiple
| Language | Iterative LCM |
|----------|---------------|
| Go | 417 ns |
| Rust | 334 ns |
| C | ~0 ns |

### Problem 6: Sum Square Difference
All languages: ~0 ns (direct formula)

### Problem 7: 10001st Prime
| Language | Sieve |
|----------|-------|
| Go | 455 µs |
| Rust | 256 µs |
| C | 258 µs |

### Problem 8: Largest Product in Series
| Language | Time |
|----------|------|
| Go | 1.52 µs |
| Rust | 0.90 µs |
| C | 0.85 µs |

### Problem 9: Special Pythagorean Triplet
| Language | Optimized |
|----------|-----------|
| Go | 267 ns |
| Rust | 144 ns |
| C | 135 ns |

### Problem 10: Summation of Primes
| Language | Time |
|----------|------|
| Go | 3.82 ms |
| Rust | 2.00 ms |
| C | 1.98 ms |

*Rust/C ~2x faster than Go*

### Problem 11: Largest Product in Grid
| Language | Time |
|----------|------|
| Go | 1.80 µs |
| Rust | 0.91 µs |
| C | 1.21 µs |

---

## Problems 12-15 (Go, Rust, C)

### Problem 12: Highly Divisible Triangular Number
| Language | Time |
|----------|------|
| C | 36.33 ms |
| C# (.NET 10) | 37.16 ms |
| Rust | 37.19 ms |
| Go | 37.70 ms |

*All essentially identical (~37ms)*

### Problem 13: Large Sum
| Language | Time | Notes |
|----------|------|-------|
| C | ~0 ns | Shortcut (first 15 digits) |
| Rust | 940 ns | Shortcut (first 15 digits) |
| Go | 34 µs | Full BigInt |

*Shortcut is 36-60x faster than full precision*

### Problem 14: Longest Collatz Sequence
| Language | Time |
|----------|------|
| **Rust** | **13.36 ms** |
| C | 132.59 ms |
| Go | 160.40 ms |

*Rust's LLVM optimizer is 10x faster here!*

### Problem 15: Lattice Paths
| Language | Time |
|----------|------|
| C | ~0 ns |
| Rust | 23.27 ns |
| Go | 29.59 ns |

*All blazing fast (simple math formula C(40,20))*

---

## Problems 16-17 (Go, Rust, C)

### Problem 16: Power Digit Sum (2^1000)
| Language | Time |
|----------|------|
| Rust | 265 µs |
| C | 326 µs |
| Go | 463 µs |

*Big integer arithmetic - Rust wins*

### Problem 17: Number Letter Counts
| Language | Time |
|----------|------|
| C | 1.37 µs |
| Rust | 1.40 µs |
| Go | 2.60 µs |

---

## Problems 18-53+ (Rust, C only)

### Problem 18: Maximum Path Sum I
| Language | Time |
|----------|------|
| Rust | 40 ns |
| C | 99 ns |

### Problem 19: Counting Sundays
| Language | Time |
|----------|------|
| Rust | 0.35 ns |
| C | ~0 ns |

*Compiler optimizes away the loop*

### Problem 20: Factorial Digit Sum (100!)
| Language | Time |
|----------|------|
| Rust | 16.3 µs |
| C | 18.0 µs |

### Problem 21: Amicable Numbers
| Language | Time |
|----------|------|
| C | 1.09 ms |
| Rust | 1.38 ms |

### Problem 22: Names Scores
| Language | Time |
|----------|------|
| Rust | 490 µs |
| C | (file error) |

### Problem 23: Non-Abundant Sums
| Language | Time |
|----------|------|
| **C** | **6.98 ms** |
| Rust | 79.2 ms |

*C is 11x faster!*

### Problem 24: Lexicographic Permutations
| Language | Time |
|----------|------|
| C | 21 ns |
| Rust | 69 ns |

### Problem 25: 1000-digit Fibonacci Number
| Language | Time |
|----------|------|
| C | 4.72 ms |
| Rust | 5.75 ms |

### Problem 26: Reciprocal Cycles
| Language | Time |
|----------|------|
| **C** | **480 µs** |
| Rust | 3.85 ms |

*C is 8x faster!*

### Problem 27: Quadratic Primes
| Language | Time |
|----------|------|
| C | 4.77 ms |
| Rust | 6.15 ms |

### Problem 28: Number Spiral Diagonals
| Language | Time |
|----------|------|
| C | ~0 ns |
| Rust | 972 ns |

### Problem 29: Distinct Powers
| Language | Time |
|----------|------|
| Rust | 61.1 ms |
| C | 67.0 ms |

### Problem 30: Digit Fifth Powers
| Language | Time |
|----------|------|
| C | 1.11 ms |
| Rust | 1.87 ms |

### Problem 31: Coin Sums
| Language | Time |
|----------|------|
| C | ~0 ns |
| Rust | 1.55 µs |

### Problem 32: Pandigital Products
| Language | Time |
|----------|------|
| Rust | 11.2 ms |
| C | 11.8 ms |

### Problem 33: Digit Cancelling Fractions
| Language | Time |
|----------|------|
| C | ~0 ns |
| Rust | 6.07 µs |

### Problem 34: Digit Factorials
| Language | Time |
|----------|------|
| Rust | 9.40 ms |
| C | 10.3 ms |

### Problem 35: Circular Primes
| Language | Time |
|----------|------|
| **C** | **2.08 ms** |
| Rust | 21.7 ms |

*C is 10x faster!*

### Problem 36: Double-base Palindromes
| Language | Time |
|----------|------|
| C | 54.6 ms |
| Rust | 66.2 ms |

### Problem 38: Pandigital Multiples
| Language | Time |
|----------|------|
| Rust | 1.14 ms |
| C | 1.36 ms |

### Problem 39: Integer Right Triangles
| Language | Time |
|----------|------|
| Rust | 81.0 µs |
| C | 83.8 µs |

### Problem 40: Champernowne's Constant
| Language | Time |
|----------|------|
| Rust | 5.62 ms |
| C | 7.69 ms |

### Problem 41: Pandigital Prime
| Language | Time |
|----------|------|
| Rust | 5.94 ms |
| C | 5.92 ms |

### Problem 42: Coded Triangle Numbers
| Language | Time |
|----------|------|
| Rust | 62.5 µs |
| C | (file error) |

### Problem 43: Sub-string Divisibility
| Language | Time |
|----------|------|
| Rust | 9.70 ms |
| C | 9.89 ms |

### Problem 44: Pentagon Numbers
| Language | Time |
|----------|------|
| **Rust** | **15.4 ms** |
| C | 40.7 ms |

*Rust 2.6x faster!*

### Problem 45: Triangular, Pentagonal, Hexagonal
| Language | Time |
|----------|------|
| Rust | 34.2 µs |
| C | 36.4 µs |

### Problem 46: Goldbach's Other Conjecture
| Language | Time |
|----------|------|
| C | 2.87 ms |
| Rust | 4.26 ms |

### Problem 47: Distinct Prime Factors
| Language | Time |
|----------|------|
| Rust | 5.70 ms |
| C | 5.79 ms |

### Problem 48: Self Powers
| Language | Time |
|----------|------|
| C | 113 µs |
| Rust | 119 µs |

### Problem 49: Prime Permutations
| Language | Time |
|----------|------|
| **Rust** | **16.7 ms** |
| C | 118 ms |

*Rust 7x faster!*

### Problem 50: Consecutive Prime Sum
| Language | Time |
|----------|------|
| Rust | 2.45 ms |
| C | 2.61 ms |

### Problem 51: Prime Digit Replacements
| Language | Time |
|----------|------|
| C | 1.05 ms |
| Rust | 1.30 ms |

### Problem 52: Permuted Multiples
| Language | Time |
|----------|------|
| C | 21.6 ms |
| Rust | 27.7 ms |

### Problem 53: Combinatoric Selections
| Language | Time |
|----------|------|
| C | 3.75 µs |
| Rust | 8.33 µs |

---

## Special Problems (058, 063, 092, 097)

### Problem 58: Spiral Primes
| Language | Time |
|----------|------|
| Rust | ~0 ns |
| C | ~0 ns |

*Compiler optimization*

### Problem 63: Powerful Digit Counts
| Language | Time |
|----------|------|
| C | 1.61 µs |
| Rust | 2.72 µs |

### Problem 92: Square Digit Chains
| Language | Time |
|----------|------|
| Rust | 43.9 ms |
| C | 43.9 ms |

### Problem 97: Large Non-Mersenne Prime
| Language | Time |
|----------|------|
| C | 281 ns |
| Rust | 335 ns |

---

## Key Takeaways

1. **Rust and C are generally within 20%** of each other for most problems
2. **Go adds ~50-100% overhead** vs Rust/C for compute-heavy tasks
3. **LLVM optimizations matter**: Problems 14, 44, 49 show Rust winning big
4. **C wins on simple loops**: Problems 23, 26, 35 show C's strength
5. **Algorithmic shortcuts dominate**: Problem 13's shortcut is 60x faster
6. **Simple math is free**: Many problems solve in <1µs with formulas

---

*Last updated: 2026-01-18*
