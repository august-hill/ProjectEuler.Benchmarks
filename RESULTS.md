# Project Euler — Cross-Language Benchmarks

> **Currently: 100 problems × 10 languages = 1000 measurements.**
> Growing carefully — each new problem and language is audited for state-leak
> safety, verified for answer correctness, and added only when it cleanly fits the
> measurement methodology.  See [JOURNEY.md](JOURNEY.md) for the full story of how
> we got here, including the reset from 200+ problems back to a verified 10×10 core.

## Per-Invocation Cost (Total, Problems 1–100)

We run each program 10 times in fresh OS processes (no warmup, no shared state).
Each invocation pays full startup + algorithm cost — the cost a real CLI / cron /
shell-loop user actually pays.  The median wall time across the 10 invocations is
the headline per-problem number, and we sum across the 100 problems for the total.

![Per-Invocation Cost](charts/per_iter_total.png)

| Rank | Language | Total (100 problems) | Lines of code | vs Fastest |
|------|----------|--------------------:|--------------:|-----------:|
| 1 | **Zig** | 1.10 s | 6,377 | 1.00× |
| 2 | **C** | 1.30 s | 6,091 | 1.18× |
| 3 | **C++** | 1.32 s | 4,648 | 1.20× |
| 4 | **Rust** | 1.33 s | 5,490 | 1.21× |
| 5 | **Go** | 1.48 s | 5,762 | 1.35× |
| 6 | **Java** | 2.20 s | 4,677 | 2.01× |
| 7 | **ARM64** | 2.46 s | 19,281 | 2.24× |
| 8 | **JavaScript** | 2.56 s | 3,901 | 2.33× |
| 9 | **C#** | 3.27 s | 4,681 | 2.98× |
| 10 | **Python** | 38.69 s | 3,428 | 35.23× |

## Speed vs Code Size

How much code does each language need to solve these 100 problems, and how
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

Rows sorted fastest-to-slowest (top to bottom).  At our current 100×10 scope
every cell is green — that's exactly the audit gate we're holding to as we
extend to more problems.

## Per-Problem Detail

Median wall time per fresh-process invocation, for each (language, problem).  Rows
are sorted by total (fastest language at top).

| Language | p001 | p002 | p003 | p004 | p005 | p006 | p007 | p008 | p009 | p010 | p011 | p012 | p013 | p014 | p015 | p016 | p017 | p018 | p019 | p020 | p021 | p022 | p023 | p024 | p025 | p026 | p027 | p028 | p029 | p030 | p031 | p032 | p033 | p034 | p035 | p036 | p037 | p038 | p039 | p040 | p041 | p042 | p043 | p044 | p045 | p046 | p047 | p048 | p049 | p050 | p051 | p052 | p053 | p054 | p055 | p056 | p057 | p058 | p059 | p060 | p061 | p062 | p063 | p064 | p065 | p066 | p067 | p068 | p069 | p070 | p071 | p072 | p073 | p074 | p075 | p076 | p077 | p078 | p079 | p080 | p081 | p082 | p083 | p084 | p085 | p086 | p087 | p088 | p089 | p090 | p091 | p092 | p093 | p094 | p095 | p096 | p097 | p098 | p099 | p100 |
|----------|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|
| **Zig** | 42 ns | 42 ns | 708 ns | 3.8 µs | 417 ns | 42 ns | 219.1 µs | 1.6 µs | 250 ns | 2.77 ms | 2.4 µs | 1.40 ms | 42 ns | 8.94 ms | 42 ns | 477.2 µs | 2.2 µs | 42 ns | 4.7 µs | 31.9 µs | 1.52 ms | 1.03 ms | 8.56 ms | 292 ns | 6.85 ms | 652.8 µs | 6.08 ms | 41 ns | 542.9 µs | 1.50 ms | 1.0 µs | 1.16 ms | 2.0 µs | 9.92 ms | 2.32 ms | 4.94 ms | 1.95 ms | 215.1 µs | 104.0 µs | 291 ns | 8.55 ms | 227.1 µs | 11.18 ms | 36.45 ms | 44.6 µs | 3.98 ms | 8.36 ms | 104.0 µs | 2.58 ms | 3.45 ms | 1.17 ms | 1.26 ms | 6.1 µs | 379.1 µs | 1.72 ms | 1.96 ms | 975.0 µs | 27.06 ms | 2.58 ms | 365.52 ms | 47.7 µs | 1.16 ms | 2.2 µs | 2.33 ms | 31.8 µs | 55.36 ms | 116.0 µs | 11.21 ms | 41 ns | 234.58 ms | 2.59 ms | 4.60 ms | 17.59 ms | 6.60 ms | 6.92 ms | 4.2 µs | 33.3 µs | 61.73 ms | 104.8 µs | 4.93 ms | 194.1 µs | 195.3 µs | 3.02 ms | 118.1 µs | 16.1 µs | 2.90 ms | 8.82 ms | 1.47 ms | 198.4 µs | 99.8 µs | 5.88 ms | 44.32 ms | 3.11 ms | 84 ns | 72.77 ms | 1.70 ms | 584 ns | 4.50 ms | 116.5 µs | 83 ns |
| **C** | 41 ns | 41 ns | 583 ns | 3.2 µs | 416 ns | 42 ns | 29.9 µs | 2.7 µs | 250 ns | 355.6 µs | 1.5 µs | 1.45 ms | 42 ns | 10.72 ms | 42 ns | 491.2 µs | 2.2 µs | 250 ns | 5.0 µs | 26.2 µs | 1.52 ms | 1.58 ms | 8.58 ms | 167 ns | 6.46 ms | 612.9 µs | 7.44 ms | 42 ns | 12.4 µs | 1.41 ms | 708 ns | 12.59 ms | 8.2 µs | 9.68 ms | 3.10 ms | 54.81 ms | 2.57 ms | 1.94 ms | 3.4 µs | 9.34 ms | 7.78 ms | 308.6 µs | 10.36 ms | 50.25 ms | 48.7 µs | 3.97 ms | 6.95 ms | 146.5 µs | 119.30 ms | 3.63 ms | 1.46 ms | 21.82 ms | 7.5 µs | 811.2 µs | 2.06 ms | 3.09 ms | 1.39 ms | 26.78 ms | 2.76 ms | 371.67 ms | 60.1 µs | 1.39 ms | 2.7 µs | 2.60 ms | 37.9 µs | 54.61 ms | 174.2 µs | 10.54 ms | 41 ns | 222.98 ms | 1.90 ms | 4.41 ms | 18.08 ms | 5.46 ms | 4.68 ms | 3.9 µs | 26.1 µs | 45.23 ms | 101.0 µs | 4.00 ms | 287.6 µs | 287.1 µs | 679.3 µs | 131.6 µs | 15.3 µs | 2.34 ms | 9.21 ms | 1.32 ms | 230.3 µs | 95.3 µs | 4.52 ms | 44.14 ms | 3.15 ms | 83 ns | 76.19 ms | 1.55 ms | 541 ns | 9.93 ms | 177.2 µs | 83 ns |
| **C++** | 166 ns | 167 ns | 34.7 µs | 32.0 µs | 542 ns | 42 ns | 24.4 µs | 3.0 µs | 334 ns | 375.9 µs | 500 ns | 1.47 ms | 19.7 µs | 12.31 ms | 167 ns | 626.8 µs | 2.5 µs | 292 ns | 4.3 µs | 27.6 µs | 1.51 ms | 1.28 ms | 29.33 ms | 625 ns | 5.88 ms | 733.4 µs | 9.73 ms | 83 ns | 2.28 ms | 1.41 ms | 708 ns | 7.46 ms | 8.2 µs | 9.62 ms | 5.55 ms | 63.08 ms | 3.69 ms | 559.8 µs | 2.8 µs | 3.78 ms | 17.54 ms | 315.7 µs | 9.92 ms | 40.85 ms | 49.2 µs | 3.76 ms | 93.61 ms | 125.4 µs | 213.0 µs | 4.41 ms | 3.56 ms | 89.71 ms | 7.5 µs | 1.42 ms | 11.36 ms | 5.41 ms | 4.92 ms | 26.45 ms | 2.29 ms | 354.80 ms | 70.2 µs | 1.86 ms | 5.5 µs | 2.01 ms | 9.1 µs | 783.6 µs | 649.7 µs | 10.09 ms | 42 ns | 238.14 ms | 2.44 ms | 4.30 ms | 17.85 ms | 6.03 ms | 4.34 ms | 3.1 µs | 29.9 µs | 47.02 ms | 104.5 µs | 6.31 ms | 523.1 µs | 458.5 µs | 735.0 µs | 131.5 µs | 14.0 µs | 2.43 ms | 2.65 ms | 1.90 ms | 273.6 µs | 162.5 µs | 5.08 ms | 44.36 ms | 3.13 ms | 125 ns | 72.55 ms | 1.90 ms | 750 ns | 9.09 ms | 251.2 µs | 125 ns |
| **Rust** | 42 ns | 83 ns | 94.8 µs | 17.8 µs | 583 ns | 42 ns | 245.7 µs | 10.6 µs | 291 ns | 1.08 ms | 42 ns | 1.35 ms | 39.4 µs | 7.23 ms | 42 ns | 57.9 µs | 2.0 µs | 250 ns | 4.8 µs | 23.4 µs | 1.82 ms | 711.1 µs | 92.96 ms | 708 ns | 7.09 ms | 5.66 ms | 7.85 ms | 875 ns | 4.38 ms | 2.37 ms | 2.2 µs | 13.35 ms | 7.7 µs | 9.10 ms | 28.86 ms | 79.01 ms | 2.73 ms | 1.70 ms | 3.5 µs | 7.56 ms | 7.61 ms | 119.6 µs | 10.76 ms | 15.65 ms | 48.2 µs | 5.56 ms | 7.00 ms | 169.5 µs | 18.53 ms | 2.66 ms | 1.77 ms | 34.01 ms | 11.2 µs | 612.6 µs | 4.84 ms | 2.45 ms | 1.24 ms | 45.85 ms | 2.24 ms | 342.48 ms | 70.8 µs | 1.79 ms | 4.2 µs | 2.05 ms | 28.8 µs | 56.50 ms | 86.5 µs | 11.47 ms | 42 ns | 190.52 ms | 2.32 ms | 4.17 ms | 17.30 ms | 31.71 ms | 5.48 ms | 4.8 µs | 33.4 µs | 45.40 ms | 14.4 µs | 8.65 ms | 205.8 µs | 253.0 µs | 508.5 µs | 116.3 µs | 20.9 µs | 2.42 ms | 7.18 ms | 1.29 ms | 193.2 µs | 89.0 µs | 4.18 ms | 44.14 ms | 24.10 ms | 83 ns | 79.81 ms | 1.86 ms | 1.7 µs | 3.34 ms | 109.4 µs | 84 ns |
| **Go** | 1.5 µs | 1.4 µs | 2.1 µs | 4.8 µs | 1.8 µs | 1.8 µs | 477.5 µs | 5.7 µs | 1.8 µs | 4.72 ms | 3.1 µs | 677.0 µs | 68.1 µs | 10.57 ms | 1.5 µs | 585.0 µs | 5.5 µs | 2.2 µs | 6.7 µs | 20.0 µs | 1.58 ms | 728.2 µs | 10.14 ms | 1.9 µs | 122.9 µs | 1.57 ms | 6.02 ms | 1.9 µs | 6.30 ms | 2.15 ms | 6.0 µs | 17.42 ms | 11.1 µs | 13.63 ms | 4.20 ms | 42.22 ms | 2.64 ms | 1.04 ms | 9.7 µs | 4.29 ms | 11.13 ms | 291.2 µs | 20.58 ms | 166.18 ms | 52.3 µs | 4.08 ms | 5.98 ms | 416.7 µs | 28.41 ms | 5.28 ms | 2.06 ms | 47.94 ms | 28.0 µs | 4.73 ms | 17.05 ms | 3.80 ms | 2.09 ms | 25.78 ms | 1.96 ms | 385.50 ms | 66.3 µs | 3.68 ms | 16.3 µs | 2.20 ms | 13.5 µs | 2.47 ms | 267.8 µs | 19.31 ms | 1.5 µs | 288.49 ms | 2.37 ms | 4.81 ms | 23.30 ms | 6.80 ms | 5.21 ms | 7.2 µs | 63.0 µs | 45.61 ms | 118.9 µs | 408.1 µs | 376.0 µs | 394.3 µs | 1.32 ms | 239.5 µs | 15.5 µs | 3.01 ms | 10.00 ms | 1.51 ms | 157.2 µs | 223.3 µs | 9.40 ms | 58.28 ms | 10.11 ms | 1.5 µs | 105.52 ms | 5.61 ms | 7.9 µs | 8.52 ms | 154.3 µs | 1.6 µs |
| **Java** | 2.5 µs | 2.8 µs | 8.0 µs | 307.3 µs | 5.5 µs | 1.9 µs | 1.62 ms | 55.0 µs | 6.0 µs | 8.17 ms | 65.7 µs | 2.09 ms | 1.99 ms | 13.65 ms | 2.1 µs | 962.7 µs | 76.8 µs | 21.2 µs | 181.6 µs | 879.7 µs | 2.15 ms | 14.19 ms | 14.66 ms | 4.7 µs | 84.61 ms | 1.91 ms | 14.54 ms | 14.1 µs | 4.75 ms | 4.19 ms | 18.6 µs | 26.50 ms | 116.0 µs | 25.63 ms | 11.10 ms | 38.47 ms | 9.93 ms | 3.82 ms | 26.6 µs | 5.75 ms | 18.79 ms | 8.88 ms | 27.42 ms | 40.33 ms | 1.30 ms | 6.82 ms | 12.43 ms | 15.88 ms | 21.23 ms | 13.25 ms | 13.72 ms | 23.08 ms | 238.8 µs | 28.43 ms | 43.51 ms | 30.96 ms | 19.35 ms | 27.81 ms | 14.63 ms | 434.26 ms | 1.06 ms | 7.29 ms | 948.5 µs | 3.22 ms | 897.6 µs | 8.22 ms | 13.71 ms | 78.20 ms | 2.8 µs | 453.84 ms | 3.21 ms | 10.09 ms | 18.27 ms | 17.56 ms | 12.76 ms | 68.0 µs | 306.6 µs | 54.12 ms | 15.9 µs | 11.95 ms | 11.09 ms | 11.06 ms | 15.01 ms | 2.04 ms | 526.4 µs | 5.40 ms | 16.69 ms | 3.18 ms | 8.75 ms | 2.84 ms | 12.50 ms | 129.62 ms | 17.13 ms | 2.7 µs | 108.37 ms | 15.31 ms | 865.7 µs | 40.22 ms | 11.19 ms | 2.2 µs |
| **ARM64** | 0 ns | 0 ns | 1.0 µs | 3.0 µs | 1.0 µs | 0 ns | 306.0 µs | 4.0 µs | 1.0 µs | 5.45 ms | 3.0 µs | 63.71 ms | 2.0 µs | 179.38 ms | 0 ns | 476.0 µs | 3.0 µs | 1.0 µs | 7.0 µs | 16.0 µs | 2.39 ms | 1.33 ms | 11.22 ms | 0 ns | 7.45 ms | 1.04 ms | 8.46 ms | 1.0 µs | 55.31 ms | 1.81 ms | 2.0 µs | 1.48 ms | 15.0 µs | 11.43 ms | 3.64 ms | 5.66 ms | 3.27 ms | 207.0 µs | 2.60 ms | 1.33 ms | 8.49 ms | 27.0 µs | 15.84 ms | 84.68 ms | 77.0 µs | 4.84 ms | 7.82 ms | 132.0 µs | 1.22 ms | 3.61 ms | 1.48 ms | 1.03 ms | 8.0 µs | 111.0 µs | 3.47 ms | 2.79 ms | 1.98 ms | 35.41 ms | 3.91 ms | 734.46 ms | 76.0 µs | 3.36 ms | 3.0 µs | 3.07 ms | 30.0 µs | 63.41 ms | 35.0 µs | 15.64 ms | 0 ns | 305.33 ms | 1.03 ms | 5.41 ms | 400.61 ms | 6.01 ms | 7.80 ms | 4.0 µs | 31.0 µs | 52.21 ms | 1.0 µs | 56.52 ms | 43.0 µs | 54.0 µs | 459.0 µs | 278.0 µs | 16.0 µs | 3.92 ms | 8.83 ms | 1.54 ms | 257.0 µs | 162.0 µs | 10.18 ms | 116.03 ms | 10.55 ms | 0 ns | 80.44 ms | 4.28 ms | 1.0 µs | 23.79 ms | 147.0 µs | 0 ns |
| **JavaScript** | 19.0 µs | 12.1 µs | 49.2 µs | 96.8 µs | 29.0 µs | 7.1 µs | 2.69 ms | 99.4 µs | 27.0 µs | 10.11 ms | 148.0 µs | 1.65 ms | 42.8 µs | 20.94 ms | 12.2 µs | 42.6 µs | 172.9 µs | 41.0 µs | 127.3 µs | 41.6 µs | 2.49 ms | 1.53 ms | 16.19 ms | 37.3 µs | 486.8 µs | 1.26 ms | 13.49 ms | 24.8 µs | 1.27 ms | 6.00 ms | 67.3 µs | 9.54 ms | 236.8 µs | 34.33 ms | 8.88 ms | 65.25 ms | 7.28 ms | 1.54 ms | 93.0 µs | 10.21 ms | 14.54 ms | 938.0 µs | 35.42 ms | 56.05 ms | 707.2 µs | 9.81 ms | 11.36 ms | 1.16 ms | 47.98 ms | 10.45 ms | 6.95 ms | 79.49 ms | 412.6 µs | 4.38 ms | 41.48 ms | 49.24 ms | 22.78 ms | 49.88 ms | 8.83 ms | 409.35 ms | 704.1 µs | 9.21 ms | 37.6 µs | 3.11 ms | 69.5 µs | 1.82 ms | 1.00 ms | 43.15 ms | 14.9 µs | 774.89 ms | 3.11 ms | 10.97 ms | 65.84 ms | 14.90 ms | 12.96 ms | 331.3 µs | 664.8 µs | 106.45 ms | 139.0 µs | 620.8 µs | 1.11 ms | 1.26 ms | 4.49 ms | 1.71 ms | 639.9 µs | 11.14 ms | 18.38 ms | 3.75 ms | 620.5 µs | 4.51 ms | 19.21 ms | 148.83 ms | 36.81 ms | 20.0 µs | 97.67 ms | 6.10 ms | 33.6 µs | 75.67 ms | 356.8 µs | 13.0 µs |
| **C#** | 54.8 µs | 64.0 µs | 80.6 µs | 136.5 µs | 1.70 ms | 27.1 µs | 696.7 µs | 179.2 µs | 521.2 µs | 9.73 ms | 662.8 µs | 3.38 ms | 466.1 µs | 58.52 ms | 58.2 µs | 2.48 ms | 12.38 ms | 3.84 ms | 299.4 µs | 2.76 ms | 168.50 ms | 23.76 ms | 8.49 ms | 416.85 ms | 4.58 ms | 1.91 ms | 118.17 ms | 3.29 ms | 22.00 ms | 3.19 ms | 223.2 µs | 9.54 ms | 248.2 µs | 19.98 ms | 176.76 ms | 13.36 ms | 7.29 ms | 21.05 ms | 683.2 µs | 6.24 ms | 24.75 ms | 16.80 ms | 255.46 ms | 129.27 ms | 407.0 µs | 7.93 ms | 10.89 ms | 671.1 µs | 18.55 ms | 7.94 ms | 18.85 ms | 15.76 ms | 169.0 µs | 7.98 ms | 45.34 ms | 58.44 ms | 2.94 ms | 73.88 ms | 16.60 ms | 399.21 ms | 1.03 ms | 3.69 ms | 70.6 µs | 2.50 ms | 9.70 ms | 5.97 ms | 14.68 ms | 71.42 ms | 182.5 µs | 371.99 ms | 1.26 ms | 5.06 ms | 39.07 ms | 8.96 ms | 7.63 ms | 124.8 µs | 5.02 ms | 46.59 ms | 6.23 ms | 8.99 ms | 15.59 ms | 17.20 ms | 20.59 ms | 5.94 ms | 206.2 µs | 2.74 ms | 17.81 ms | 12.01 ms | 5.78 ms | 1.56 ms | 10.54 ms | 111.58 ms | 33.84 ms | 74.8 µs | 80.50 ms | 28.53 ms | 259.0 µs | 43.69 ms | 15.03 ms | 57.4 µs |
| **Python** | 1.6 µs | 3.0 µs | 5.59 ms | 55.36 ms | 4.5 µs | 916 ns | 1.38 ms | 852.1 µs | 4.64 ms | 5.27 ms | 223.6 µs | 21.13 ms | 4.3 µs | 6.15 s | 2.0 µs | 25.8 µs | 168.9 µs | 17.6 µs | 142.3 µs | 16.0 µs | 25.56 ms | 3.72 ms | 578.16 ms | 10.2 µs | 22.43 ms | 7.59 ms | 406.94 ms | 34.9 µs | 2.66 ms | 215.86 ms | 49.7 µs | 42.23 ms | 351.5 µs | 1.77 s | 100.18 ms | 146.76 ms | 75.41 ms | 4.04 ms | 82.9 µs | 17.55 ms | 61.0 µs | 1.12 ms | 921.46 ms | 161.44 ms | 3.60 ms | 20.36 ms | 395.76 ms | 642.8 µs | 77.64 ms | 109.16 ms | 55.75 ms | 100.05 ms | 356.0 µs | 5.41 ms | 15.49 ms | 53.83 ms | 1.82 ms | 905.66 ms | 113.78 ms | 633.02 ms | 1.30 ms | 6.35 ms | 13.5 µs | 25.06 ms | 24.1 µs | 2.28 ms | 1.04 ms | 948.39 ms | 1.6 µs | 11.94 s | 74.19 ms | 461.66 ms | 941.41 ms | 645.34 ms | 119.82 ms | 192.4 µs | 855.2 µs | 1.12 s | 47.2 µs | 1.57 ms | 1.49 ms | 1.50 ms | 4.77 ms | 10.63 ms | 1.26 ms | 267.28 ms | 176.52 ms | 94.90 ms | 2.20 ms | 3.99 ms | 708.41 ms | 4.63 s | 148.58 ms | 5.0 µs | 2.89 s | 169.93 ms | 4.2 µs | 40.88 ms | 405.7 µs | 3.8 µs |

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

> Of the 100 problems benchmarked, **roughly 20-25% of cells** are fully
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

