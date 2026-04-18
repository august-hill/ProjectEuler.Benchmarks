# Project Euler Cross-Language Benchmark: Three-Mode Analysis

*Generated from benchmark data collected on 2026-04-18T00:40:02Z*

Platform: arm64  
Common problem set: **151 problems** (the intersection of all 10 languages with a passing entry)

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

All times are summed over the 151-problem common set.

| Language | Hot total | Cold total | Total (compile+cold) | Hot rank | Cold rank | Total rank |
|----------|-----------|------------|----------------------|----------|-----------|------------|
| ARM64      |       4.25 s |     4.25 s * |             4.25 s * |        2 |         2 |          2 |
| C          |       6.42 s |     7.30 s * |             59.9 s * |        4 |         4 |          5 |
| C#         |       6.43 s |       12.5 s |               12.5 s |        5 |         6 |          3 |
| C++        |       4.46 s |       6.68 s |              209.3 s |        3 |         3 |          8 |
| Go         |       7.10 s |       7.81 s |              224.8 s |        6 |         5 |          9 |
| Java       |       17.8 s |       30.6 s |              151.7 s |        8 |         9 |          7 |
| JavaScript |       12.8 s |       23.3 s |               23.3 s |        7 |         8 |          4 |
| Python     |       68.3 s |      805.6 s |              805.6 s |       10 |        10 |         10 |
| Rust       |       21.7 s |     21.4 s * |            135.4 s * |        9 |         7 |          6 |
| Zig        |       2.60 s |     3.04 s * |             3.40 s * |        1 |         1 |          1 |

*\* Cold column uses `subprocess_wall_ns` when nonzero (full user-perceived cold start including interpreter/runtime startup), otherwise falls back to `cold_start_ns`, then `time_ns` as a lower-bound proxy. Languages with entries marked * had some cold=0 problems where warm time was used as a proxy.*

---

## Section B: Per-Mode Leaderboards

Showing all languages sorted by total time in each mode. Slowdown is relative to the fastest language in that mode.

### Hot Mode (median warm iteration)

| Rank | Language | Total | Slowdown |
|------|----------|-------|----------|
|    1 | Zig        |     2.60 s |     1.00x |
|    2 | ARM64      |     4.25 s |     1.63x |
|    3 | C++        |     4.46 s |     1.72x |
|    4 | C          |     6.42 s |     2.47x |
|    5 | C#         |     6.43 s |     2.47x |
|    6 | Go         |     7.10 s |     2.73x |
|    7 | JavaScript |     12.8 s |     4.93x |
|    8 | Java       |     17.8 s |     6.85x |
|    9 | Rust       |     21.7 s |     8.34x |
|   10 | Python     |     68.3 s |    26.24x |

### Cold Mode (first invocation)

| Rank | Language | Total | Slowdown |
|------|----------|-------|----------|
|    1 | Zig        |     3.04 s |     1.00x |
|    2 | ARM64      |     4.25 s |     1.40x |
|    3 | C++        |     6.68 s |     2.20x |
|    4 | C          |     7.30 s |     2.40x |
|    5 | Go         |     7.81 s |     2.57x |
|    6 | C#         |     12.5 s |     4.12x |
|    7 | Rust       |     21.4 s |     7.04x |
|    8 | JavaScript |     23.3 s |     7.68x |
|    9 | Java       |     30.6 s |    10.08x |
|   10 | Python     |    805.6 s |   264.97x |

### Total Mode (compile + cold start)

| Rank | Language | Total | Slowdown |
|------|----------|-------|----------|
|    1 | Zig        |     3.40 s |     1.00x |
|    2 | ARM64      |     4.25 s |     1.25x |
|    3 | C#         |     12.5 s |     3.68x |
|    4 | JavaScript |     23.3 s |     6.87x |
|    5 | C          |     59.9 s |    17.62x |
|    6 | Rust       |    135.4 s |    39.82x |
|    7 | Java       |    151.7 s |    44.63x |
|    8 | C++        |    209.3 s |    61.56x |
|    9 | Go         |    224.8 s |    66.13x |
|   10 | Python     |    805.6 s |   237.00x |

---

## Section C: Hot/Cold Quadrant Analysis

Each language is placed in (hot rank, cold rank) space using its median rank
across all 151 common problems. Lower rank = faster.

| Language | Median hot rank | Median cold rank | Quadrant |
|----------|-----------------|------------------|----------|
| ARM64      |             5.0 |              2.0 | Fast-fast (AOT compiled) |
| C          |             3.0 |              3.0 | Fast-fast (AOT compiled) |
| C#         |             7.0 |              8.0 | Slow-slow (interpreter) |
| C++        |             4.0 |              5.0 | Fast-fast (AOT compiled) |
| Go         |             6.0 |              6.0 | Slow-slow (interpreter) |
| Java       |             7.0 |              8.0 | Slow-slow (interpreter) |
| JavaScript |             8.0 |              8.0 | Slow-slow (interpreter) |
| Python     |            10.0 |             10.0 | Slow-slow (interpreter) |
| Rust       |             5.0 |              4.0 | Fast-fast (AOT compiled) |
| Zig        |             2.0 |              2.0 | Fast-fast (AOT compiled) |

### ASCII Art: Median Hot Rank vs Median Cold Rank

X-axis: median hot rank (left = fast, right = slow)
Y-axis: median cold rank (top = fast, bottom = slow)
Grid is 10x10; each cell is ~1.0 rank units.

```
     hot rank -->
     1 2 3 4 5 6 7 8 9 10
     --------------------
c  1|....................
   2|..Zg....AS..........
   3|....C ..............
   4|........Rs..........
   5|......C+............
o  6|..........Go........
   7|....................
   8|............JaJS....
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

### Problem 189

| Language | Hot time | Cold time | Hot rank | Cold rank | Rank delta |
|----------|----------|-----------|----------|-----------|------------|
| Python     |     83 ns |     18.1 s |        1 |        10 | +9 |
| ARM64      |    115 ms |     115 ms |        2 |         1 | -1 |
| C++        |    170 ms |     151 ms |        3 |         2 | -1 |
| Zig        |    174 ms |     174 ms |        4 |         4 | 0 |
| Rust       |    190 ms |     194 ms |        5 |         5 | 0 |
| C          |    193 ms |     166 ms |        6 |         3 | -3 |
| Java       |    309 ms |     370 ms |        7 |         6 | -1 |
| Go         |    415 ms |     415 ms |        8 |         7 | -1 |
| C#         |    466 ms |     474 ms |        9 |         8 | -1 |
| JavaScript |    862 ms |     889 ms |       10 |         9 | -1 |

### Problem 163

| Language | Hot time | Cold time | Hot rank | Cold rank | Rank delta |
|----------|----------|-----------|----------|-----------|------------|
| C          |    122 ms |     122 ms |        1 |         2 | +1 |
| C++        |    127 ms |     127 ms |        2 |         3 | +1 |
| Zig        |    144 ms |     149 ms |        3 |         4 | +1 |
| Rust       |    148 ms |     165 ms |        4 |         6 | +2 |
| ARM64      |    161 ms |     161 ms |        5 |         5 | 0 |
| Go         |    171 ms |     175 ms |        6 |         7 | +1 |
| C#         |    188 ms |     323 ms |        7 |         9 | +2 |
| Java       |    229 ms |     235 ms |        8 |         8 | 0 |
| JavaScript |    527 ms |     562 ms |        9 |        10 | +1 |
| Python     |    2.77 s |      36 ms |       10 |         1 | -9 |

### Problem 200

| Language | Hot time | Cold time | Hot rank | Cold rank | Rank delta |
|----------|----------|-----------|----------|-----------|------------|
| Python     |     83 ns |     201 ms |        1 |        10 | +9 |
| Go         |    7.6 ms |      10 ms |        2 |         4 | +2 |
| Zig        |    8.1 ms |     8.1 ms |        3 |         1 | -2 |
| C++        |    8.1 ms |      10 ms |        4 |         3 | -1 |
| C          |    8.1 ms |     9.8 ms |        5 |         2 | -3 |
| Rust       |    9.1 ms |      12 ms |        6 |         5 | -1 |
| Java       |     15 ms |      65 ms |        7 |         8 | +1 |
| C#         |     18 ms |      51 ms |        8 |         7 | -1 |
| JavaScript |     40 ms |      44 ms |        9 |         6 | -3 |
| ARM64      |     73 ms |      73 ms |       10 |         9 | -1 |

### Problem 159

| Language | Hot time | Cold time | Hot rank | Cold rank | Rank delta |
|----------|----------|-----------|----------|-----------|------------|
| Python     |     83 ns |     917 ms |        1 |        10 | +9 |
| C++        |     51 µs |      13 ms |        2 |         4 | +2 |
| C          |     52 µs |      26 ms |        3 |         7 | +4 |
| Zig        |     52 µs |      52 µs |        4 |         1 | -3 |
| Go         |    434 µs |      32 ms |        5 |         8 | +3 |
| Java       |    664 µs |      36 ms |        6 |         9 | +3 |
| C#         |    665 µs |      23 ms |        7 |         6 | -1 |
| JavaScript |    830 µs |     2.1 ms |        8 |         2 | -6 |
| ARM64      |     12 ms |      12 ms |        9 |         3 | -6 |
| Rust       |     14 ms |      23 ms |       10 |         5 | -5 |

### Problem 156

| Language | Hot time | Cold time | Hot rank | Cold rank | Rank delta |
|----------|----------|-----------|----------|-----------|------------|
| Python     |     42 ns |     7.50 s |        1 |        10 | +9 |
| Zig        |     79 ms |      79 ms |        2 |         1 | -1 |
| Rust       |    102 ms |     110 ms |        3 |         2 | -1 |
| C          |    109 ms |     116 ms |        4 |         3 | -1 |
| C#         |    114 ms |     282 ms |        5 |         8 | +3 |
| C++        |    117 ms |     127 ms |        6 |         4 | -2 |
| ARM64      |    143 ms |     143 ms |        7 |         6 | -1 |
| Go         |    148 ms |     160 ms |        8 |         7 | -1 |
| Java       |    159 ms |     128 ms |        9 |         5 | -4 |
| JavaScript |    1.48 s |     1.32 s |       10 |         9 | -1 |

### Problem 187

| Language | Hot time | Cold time | Hot rank | Cold rank | Rank delta |
|----------|----------|-----------|----------|-----------|------------|
| Python     |     83 ns |     8.28 s |        1 |        10 | +9 |
| ARM64      |     53 µs |      53 µs |        2 |         1 | -1 |
| Zig        |     53 µs |      53 µs |        3 |         2 | -1 |
| Go         |     77 µs |     403 ms |        4 |         3 | -1 |
| Java       |     81 µs |     589 ms |        5 |         9 | +4 |
| C++        |     83 µs |     450 ms |        6 |         5 | -1 |
| C          |     83 µs |     570 ms |        7 |         8 | +1 |
| C#         |     86 µs |     428 ms |        8 |         4 | -4 |
| Rust       |    380 ms |     451 ms |        9 |         6 | -3 |
| JavaScript |    493 ms |     569 ms |       10 |         7 | -3 |

### Problem 074

| Language | Hot time | Cold time | Hot rank | Cold rank | Rank delta |
|----------|----------|-----------|----------|-----------|------------|
| Rust       |     78 µs |      40 ms |        1 |         9 | +8 |
| C++        |    706 µs |      11 ms |        2 |         5 | +3 |
| ARM64      |    4.5 ms |     4.5 ms |        3 |         1 | -2 |
| C          |    5.0 ms |     5.2 ms |        4 |         3 | -1 |
| Zig        |    5.1 ms |     5.1 ms |        5 |         2 | -3 |
| Go         |    8.7 ms |     7.1 ms |        6 |         4 | -2 |
| C#         |     10 ms |      14 ms |        7 |         6 | -1 |
| Java       |     13 ms |      20 ms |        8 |         8 | 0 |
| JavaScript |     14 ms |      18 ms |        9 |         7 | -2 |
| Python     |    660 ms |     9.26 s |       10 |        10 | 0 |

---

## Data Quality Notes

| Language | hot=0 entries (cold used as proxy) | cold=0 entries (hot used as proxy) |
|----------|-------------------------------------|-------------------------------------|
| ARM64      |                                  48 |                                 298 |
| C          |                                  32 |                                  14 |
| C#         |                                   4 |                                   0 |
| C++        |                                  20 |                                   0 |
| Go         |                                  14 |                                   0 |
| Java       |                                   0 |                                   0 |
| JavaScript |                                   0 |                                   0 |
| Python     |                                   0 |                                   0 |
| Rust       |                                  12 |                                   2 |
| Zig        |                                 114 |                                 298 |

