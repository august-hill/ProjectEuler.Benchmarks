# Project Euler Cross-Language Benchmark: Three-Mode Analysis

*Generated from benchmark data collected on 2026-04-12T05:30:26Z*

Platform: arm64  
Common problem set: **188 problems** (the intersection of all 10 languages with a passing entry)

---

## Methodology

Three measurements are reported for each language:

| Mode | Field | What it measures |
|------|-------|------------------|
| **Hot** | `time_ns` | Median wall time over 1000 warm iterations with the binary already in memory. Favors JIT'd languages (JVM, .NET) because compilation is fully amortized. The right measure for long-running servers or batch jobs that restart infrequently. |
| **Cold** | `subprocess_wall_ns` (preferred) or `cold_start_ns` | First-invocation wall time with no prior warmup. `subprocess_wall_ns` is the external wall time from `cmd.Run()` start to finish, capturing interpreter/runtime startup (Python ~30-80 ms, JVM ~150-300 ms, .NET ~100-200 ms). `cold_start_ns` is the time of the first `solve()` call inside the process (misses interpreter startup). The right measure for CLI tools, lambdas, and anything invoked once per task. |
| **Total** | `compile_time_ns + cold_start_ns` | Full "I cloned the repo, built it, and ran it once" time. Includes the language's ahead-of-time compiler (or build step) where applicable. Zero for interpreted languages (no separate compile step). The right measure for CI/CD pipelines and ephemeral environments. |

**Cold measurement priority:** `subprocess_wall_ns` is used when available and nonzero (it captures the full user-perceived cold start including interpreter/runtime startup). If absent, `cold_start_ns` is used as a fallback. If both are zero, the warm `time_ns` is used as a lower-bound proxy.

**Note on `time_ns = 0`:** When a problem runs faster than the timer resolution, `time_ns` is recorded as 0. These entries use `cold_start_ns` as a proxy for the hot time, which is a conservative overestimate.

---

## Section A: Per-Language Totals Across Common Problems

All times are summed over the 188-problem common set.

| Language | Hot total | Cold total | Total (compile+cold) | Hot rank | Cold rank | Total rank |
|----------|-----------|------------|----------------------|----------|-----------|------------|
| ARM64      |       12.1 s |     13.1 s * |             90.1 s * |        4 |         3 |          5 |
| C          |       11.8 s |     13.5 s * |             77.9 s * |        3 |         4 |          4 |
| C#         |       12.3 s |       20.3 s |               20.3 s |        5 |         6 |          2 |
| C++        |       10.0 s |       13.1 s |              266.5 s |        2 |         2 |          8 |
| Go         |       13.5 s |       14.9 s |              295.5 s |        6 |         5 |          9 |
| Java       |       20.4 s |       38.1 s |              189.4 s |        7 |         8 |          7 |
| JavaScript |       29.0 s |       42.2 s |               42.2 s |        9 |         9 |          3 |
| Python     |       88.1 s |     1090.9 s |             1090.9 s |       10 |        10 |         10 |
| Rust       |       28.9 s |     28.3 s * |            171.2 s * |        8 |         7 |          6 |
| Zig        |       8.68 s |     9.11 s * |             9.47 s * |        1 |         1 |          1 |

*\* Cold column uses `subprocess_wall_ns` when nonzero (full user-perceived cold start including interpreter/runtime startup), otherwise falls back to `cold_start_ns`, then `time_ns` as a lower-bound proxy. Languages with entries marked * had some cold=0 problems where warm time was used as a proxy.*

---

## Section B: Per-Mode Leaderboards

Showing all languages sorted by total time in each mode. Slowdown is relative to the fastest language in that mode.

### Hot Mode (median warm iteration)

| Rank | Language | Total | Slowdown |
|------|----------|-------|----------|
|    1 | Zig        |     8.68 s |     1.00x |
|    2 | C++        |     10.0 s |     1.15x |
|    3 | C          |     11.8 s |     1.37x |
|    4 | ARM64      |     12.1 s |     1.39x |
|    5 | C#         |     12.3 s |     1.41x |
|    6 | Go         |     13.5 s |     1.56x |
|    7 | Java       |     20.4 s |     2.35x |
|    8 | Rust       |     28.9 s |     3.34x |
|    9 | JavaScript |     29.0 s |     3.35x |
|   10 | Python     |     88.1 s |    10.15x |

### Cold Mode (first invocation)

| Rank | Language | Total | Slowdown |
|------|----------|-------|----------|
|    1 | Zig        |     9.11 s |     1.00x |
|    2 | C++        |     13.1 s |     1.44x |
|    3 | ARM64      |     13.1 s |     1.44x |
|    4 | C          |     13.5 s |     1.48x |
|    5 | Go         |     14.9 s |     1.64x |
|    6 | C#         |     20.3 s |     2.22x |
|    7 | Rust       |     28.3 s |     3.10x |
|    8 | Java       |     38.1 s |     4.18x |
|    9 | JavaScript |     42.2 s |     4.63x |
|   10 | Python     |   1090.9 s |   119.76x |

### Total Mode (compile + cold start)

| Rank | Language | Total | Slowdown |
|------|----------|-------|----------|
|    1 | Zig        |     9.47 s |     1.00x |
|    2 | C#         |     20.3 s |     2.14x |
|    3 | JavaScript |     42.2 s |     4.45x |
|    4 | C          |     77.9 s |     8.22x |
|    5 | ARM64      |     90.1 s |     9.52x |
|    6 | Rust       |    171.2 s |    18.08x |
|    7 | Java       |    189.4 s |    20.01x |
|    8 | C++        |    266.5 s |    28.15x |
|    9 | Go         |    295.5 s |    31.20x |
|   10 | Python     |   1090.9 s |   115.22x |

---

## Section C: Hot/Cold Quadrant Analysis

Each language is placed in (hot rank, cold rank) space using its median rank
across all 188 common problems. Lower rank = faster.

| Language | Median hot rank | Median cold rank | Quadrant |
|----------|-----------------|------------------|----------|
| ARM64      |             4.0 |              3.0 | Fast-fast (AOT compiled) |
| C          |             3.0 |              3.0 | Fast-fast (AOT compiled) |
| C#         |             7.0 |              8.0 | Slow-slow (interpreter) |
| C++        |             3.0 |              4.0 | Fast-fast (AOT compiled) |
| Go         |             6.0 |              6.0 | Slow-slow (interpreter) |
| Java       |             6.0 |              8.0 | Slow-slow (interpreter) |
| JavaScript |             8.0 |              8.0 | Slow-slow (interpreter) |
| Python     |            10.0 |             10.0 | Slow-slow (interpreter) |
| Rust       |             5.0 |              4.0 | Fast-fast (AOT compiled) |
| Zig        |             2.0 |              1.0 | Fast-fast (AOT compiled) |

### ASCII Art: Median Hot Rank vs Median Cold Rank

X-axis: median hot rank (left = fast, right = slow)
Y-axis: median cold rank (top = fast, bottom = slow)
Grid is 10x10; each cell is ~1.0 rank units.

```
     hot rank -->
     1 2 3 4 5 6 7 8 9 10
     --------------------
c  1|..Zg................
   2|....................
   3|....C AS............
   4|....C+..Rs..........
   5|....................
o  6|..........Go........
   7|....................
   8|..........JaC#JS....
   9|....................
v 10|..................Py

```

**Quadrant definitions** (midpoint = 5.5):

- **Fast-fast** (hot < mid, cold < mid): AOT-compiled languages with minimal runtime overhead. Win both modes.
- **JIT tax** (hot < mid, cold >= mid): Fast in hot mode due to JIT optimization, but pay a visible cold-start penalty. Typical of JVM and .NET.
- **Slow-hot / fast-cold** (hot >= mid, cold < mid): Rare. Would indicate a language with cheap cold start but slow steady-state throughput.
- **Slow-slow** (hot >= mid, cold >= mid): Interpreters or inherently slow runtimes in both modes.

---

## Section D: Problems Where the Ranking Disagrees Most Between Modes

The following problems exhibit the largest rank swings between hot and cold measurement.
They are the clearest illustration of why methodology choice matters.

### Problem 153

| Language | Hot time | Cold time | Hot rank | Cold rank | Rank delta |
|----------|----------|-----------|----------|-----------|------------|
| Python     |     83 ns |     33.3 s |        1 |        10 | +9 |
| Java       |    125 ns |     3.19 s |        2 |         7 | +5 |
| ARM64      |    2.81 s |     2.70 s |        3 |         1 | -2 |
| C          |    2.85 s |     2.95 s |        4 |         2 | -2 |
| C#         |    2.93 s |     3.05 s |        5 |         3 | -2 |
| C++        |    3.05 s |     3.17 s |        6 |         6 | 0 |
| Go         |    3.06 s |     3.07 s |        7 |         4 | -3 |
| Zig        |    3.15 s |     3.15 s |        8 |         5 | -3 |
| Rust       |    3.84 s |     3.61 s |        9 |         8 | -1 |
| JavaScript |    12.7 s |     14.3 s |       10 |         9 | -1 |

### Problem 159

| Language | Hot time | Cold time | Hot rank | Cold rank | Rank delta |
|----------|----------|-----------|----------|-----------|------------|
| Python     |     83 ns |     917 ms |        1 |        10 | +9 |
| ARM64      |     51 µs |      15 ms |        2 |         4 | +2 |
| C++        |     51 µs |      13 ms |        3 |         3 | 0 |
| C          |     52 µs |      26 ms |        4 |         7 | +3 |
| Zig        |     52 µs |      52 µs |        5 |         1 | -4 |
| Go         |    434 µs |      32 ms |        6 |         8 | +2 |
| Java       |    664 µs |      36 ms |        7 |         9 | +2 |
| C#         |    665 µs |      23 ms |        8 |         6 | -2 |
| JavaScript |    830 µs |     2.1 ms |        9 |         2 | -7 |
| Rust       |     14 ms |      23 ms |       10 |         5 | -5 |

### Problem 200

| Language | Hot time | Cold time | Hot rank | Cold rank | Rank delta |
|----------|----------|-----------|----------|-----------|------------|
| Python     |     83 ns |     201 ms |        1 |        10 | +9 |
| Go         |    7.6 ms |      10 ms |        2 |         4 | +2 |
| Zig        |    8.1 ms |     8.1 ms |        3 |         1 | -2 |
| ARM64      |    8.1 ms |      16 ms |        4 |         6 | +2 |
| C++        |    8.1 ms |      10 ms |        5 |         3 | -2 |
| C          |    8.1 ms |     9.8 ms |        6 |         2 | -4 |
| Rust       |    9.1 ms |      12 ms |        7 |         5 | -2 |
| Java       |     15 ms |      65 ms |        8 |         9 | +1 |
| C#         |     18 ms |      51 ms |        9 |         8 | -1 |
| JavaScript |     40 ms |      44 ms |       10 |         7 | -3 |

### Problem 179

| Language | Hot time | Cold time | Hot rank | Cold rank | Rank delta |
|----------|----------|-----------|----------|-----------|------------|
| Python     |     83 ns |     12.3 s |        1 |        10 | +9 |
| C++        |    694 µs |     253 ms |        2 |         4 | +2 |
| ARM64      |    840 µs |     307 ms |        3 |         5 | +2 |
| C          |    1.1 ms |     307 ms |        4 |         6 | +2 |
| Go         |    5.5 ms |     459 ms |        5 |         7 | +2 |
| Java       |    9.0 ms |     527 ms |        6 |         8 | +2 |
| C#         |     13 ms |     608 ms |        7 |         9 | +2 |
| JavaScript |     17 ms |      18 ms |        8 |         1 | -7 |
| Zig        |    248 ms |     248 ms |        9 |         2 | -7 |
| Rust       |    264 ms |     248 ms |       10 |         3 | -7 |

### Problem 187

| Language | Hot time | Cold time | Hot rank | Cold rank | Rank delta |
|----------|----------|-----------|----------|-----------|------------|
| Python     |     83 ns |     8.28 s |        1 |        10 | +9 |
| Zig        |     53 µs |      53 µs |        2 |         1 | -1 |
| Go         |     77 µs |     403 ms |        3 |         2 | -1 |
| Java       |     81 µs |     589 ms |        4 |         9 | +5 |
| ARM64      |     83 µs |     532 ms |        5 |         6 | +1 |
| C++        |     83 µs |     450 ms |        6 |         4 | -2 |
| C          |     83 µs |     570 ms |        7 |         8 | +1 |
| C#         |     86 µs |     428 ms |        8 |         3 | -5 |
| Rust       |    380 ms |     451 ms |        9 |         5 | -4 |
| JavaScript |    493 ms |     569 ms |       10 |         7 | -3 |

### Problem 189

| Language | Hot time | Cold time | Hot rank | Cold rank | Rank delta |
|----------|----------|-----------|----------|-----------|------------|
| Python     |     83 ns |     18.1 s |        1 |        10 | +9 |
| ARM64      |    165 ms |     159 ms |        2 |         2 | 0 |
| C++        |    170 ms |     151 ms |        3 |         1 | -2 |
| Zig        |    174 ms |     174 ms |        4 |         4 | 0 |
| Rust       |    190 ms |     194 ms |        5 |         5 | 0 |
| C          |    193 ms |     166 ms |        6 |         3 | -3 |
| Java       |    309 ms |     370 ms |        7 |         6 | -1 |
| Go         |    415 ms |     415 ms |        8 |         7 | -1 |
| C#         |    466 ms |     474 ms |        9 |         8 | -1 |
| JavaScript |    862 ms |     889 ms |       10 |         9 | -1 |

### Problem 156

| Language | Hot time | Cold time | Hot rank | Cold rank | Rank delta |
|----------|----------|-----------|----------|-----------|------------|
| Python     |     42 ns |     7.50 s |        1 |        10 | +9 |
| Zig        |     79 ms |      79 ms |        2 |         1 | -1 |
| Rust       |    102 ms |     110 ms |        3 |         3 | 0 |
| C          |    109 ms |     116 ms |        4 |         4 | 0 |
| C#         |    114 ms |     282 ms |        5 |         8 | +3 |
| C++        |    117 ms |     127 ms |        6 |         5 | -1 |
| ARM64      |    123 ms |      94 ms |        7 |         2 | -5 |
| Go         |    148 ms |     160 ms |        8 |         7 | -1 |
| Java       |    159 ms |     128 ms |        9 |         6 | -3 |
| JavaScript |    1.48 s |     1.32 s |       10 |         9 | -1 |

---

## Data Quality Notes

| Language | hot=0 entries (cold used as proxy) | cold=0 entries (hot used as proxy) |
|----------|-------------------------------------|-------------------------------------|
| ARM64      |                                  98 |                                  30 |
| C          |                                  40 |                                  14 |
| C#         |                                   6 |                                   0 |
| C++        |                                  24 |                                   0 |
| Go         |                                  18 |                                   0 |
| Java       |                                   0 |                                   0 |
| JavaScript |                                   0 |                                   0 |
| Python     |                                   0 |                                   0 |
| Rust       |                                  14 |                                   2 |
| Zig        |                                 142 |                                 374 |

