# Project Euler — Cross-Language Benchmarks

> **Currently: 100 problems × 10 languages = 1000 measurements.**
> Growing carefully — each new problem and language is audited for state-leak
> safety, verified for answer correctness, and added only when it cleanly fits the
> measurement methodology.  See [JOURNEY.md](JOURNEY.md) for the full story of how
> we got here, including the reset from 200+ problems back to a verified 10×10
> core, then the disciplined expansion to today's 100×10 scope.

## Per-Invocation Cost (Total, Problems 1–100)

We run each program 10 times in fresh OS processes (no warmup, no shared state).
Each invocation pays full startup + algorithm cost — the cost a real CLI / cron /
shell-loop user actually pays.  The median wall time across the 10 invocations is
the headline per-problem number, and we sum across the 100 problems for the total.

![Per-Invocation Cost](charts/per_iter_total.png)

| Rank | Language | Total (100 problems) | Lines of code | vs Fastest |
|------|----------|--------------------:|--------------:|-----------:|
| 1 | **Zig** | 1.09 s | 6,436 | 1.00× |
| 2 | **C** | 1.29 s | 6,124 | 1.18× |
| 3 | **C++** | 1.32 s | 4,679 | 1.21× |
| 4 | **Rust** | 1.32 s | 5,534 | 1.21× |
| 5 | **Go** | 1.48 s | 5,796 | 1.36× |
| 6 | **ARM64** | 1.57 s | 19,164 | 1.44× |
| 7 | **Java** | 2.19 s | 4,667 | 2.00× |
| 8 | **JavaScript** | 2.56 s | 3,896 | 2.35× |
| 9 | **C#** | 3.30 s | 4,728 | 3.03× |
| 10 | **Python** | 38.41 s | 3,427 | 35.19× |

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

### Problems 001–100

| Problem | ARM64 | C | C++ | Rust | Zig | Go | C# | Java | JavaScript | Python |
|---------|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|
| **p001** | 0 ns | 41 ns | 166 ns | 42 ns | 42 ns | 1.5 µs | 54.8 µs | 2.5 µs | 19.0 µs | 1.6 µs |
| **p002** | 0 ns | 41 ns | 167 ns | 83 ns | 42 ns | 1.4 µs | 64.0 µs | 2.8 µs | 12.1 µs | 3.0 µs |
| **p003** | 1.0 µs | 583 ns | 34.7 µs | 94.8 µs | 708 ns | 2.1 µs | 80.6 µs | 8.0 µs | 49.2 µs | 5.59 ms |
| **p004** | 3.0 µs | 3.2 µs | 32.0 µs | 17.8 µs | 3.8 µs | 4.8 µs | 136.5 µs | 307.3 µs | 96.8 µs | 55.36 ms |
| **p005** | 1.0 µs | 416 ns | 542 ns | 583 ns | 417 ns | 1.8 µs | 1.70 ms | 5.5 µs | 29.0 µs | 4.5 µs |
| **p006** | 0 ns | 42 ns | 42 ns | 42 ns | 42 ns | 1.8 µs | 27.1 µs | 1.9 µs | 7.1 µs | 916 ns |
| **p007** | 306.0 µs | 29.9 µs | 24.4 µs | 245.7 µs | 219.1 µs | 477.5 µs | 696.7 µs | 1.62 ms | 2.69 ms | 1.38 ms |
| **p008** | 4.0 µs | 2.7 µs | 3.0 µs | 10.6 µs | 1.6 µs | 5.7 µs | 179.2 µs | 55.0 µs | 99.4 µs | 852.1 µs |
| **p009** | 1.0 µs | 250 ns | 334 ns | 291 ns | 250 ns | 1.8 µs | 521.2 µs | 6.0 µs | 27.0 µs | 4.64 ms |
| **p010** | 5.45 ms | 355.6 µs | 375.9 µs | 1.08 ms | 2.77 ms | 4.72 ms | 9.73 ms | 8.17 ms | 10.11 ms | 5.27 ms |
| **p011** | 3.0 µs | 1.5 µs | 500 ns | 42 ns | 2.4 µs | 3.1 µs | 662.8 µs | 65.7 µs | 148.0 µs | 223.6 µs |
| **p012** | 1.41 ms | 1.45 ms | 1.47 ms | 1.35 ms | 1.40 ms | 677.0 µs | 3.38 ms | 2.09 ms | 1.65 ms | 21.13 ms |
| **p013** | 2.0 µs | 42 ns | 19.7 µs | 39.4 µs | 42 ns | 68.1 µs | 466.1 µs | 1.99 ms | 42.8 µs | 4.3 µs |
| **p014** | 9.77 ms | 11.15 ms | 13.21 ms | 8.54 ms | 8.96 ms | 9.99 ms | 57.72 ms | 13.61 ms | 20.74 ms | 6.13 s |
| **p015** | 0 ns | 42 ns | 167 ns | 42 ns | 42 ns | 1.5 µs | 58.2 µs | 2.1 µs | 12.2 µs | 2.0 µs |
| **p016** | 476.0 µs | 491.2 µs | 626.8 µs | 57.9 µs | 477.2 µs | 585.0 µs | 2.48 ms | 962.7 µs | 42.6 µs | 25.8 µs |
| **p017** | 3.0 µs | 2.2 µs | 2.5 µs | 2.0 µs | 2.2 µs | 5.5 µs | 12.38 ms | 76.8 µs | 172.9 µs | 168.9 µs |
| **p018** | 1.0 µs | 250 ns | 292 ns | 250 ns | 42 ns | 2.2 µs | 3.84 ms | 21.2 µs | 41.0 µs | 17.6 µs |
| **p019** | 7.0 µs | 5.0 µs | 4.3 µs | 4.8 µs | 4.7 µs | 6.7 µs | 299.4 µs | 181.6 µs | 127.3 µs | 142.3 µs |
| **p020** | 16.0 µs | 26.2 µs | 27.6 µs | 23.4 µs | 31.9 µs | 20.0 µs | 2.76 ms | 879.7 µs | 41.6 µs | 16.0 µs |
| **p021** | 2.39 ms | 1.52 ms | 1.51 ms | 1.82 ms | 1.52 ms | 1.58 ms | 168.50 ms | 2.15 ms | 2.49 ms | 25.56 ms |
| **p022** | 1.33 ms | 1.58 ms | 1.28 ms | 711.1 µs | 1.03 ms | 728.2 µs | 23.76 ms | 14.19 ms | 1.53 ms | 3.72 ms |
| **p023** | 11.22 ms | 8.58 ms | 29.33 ms | 92.96 ms | 8.56 ms | 10.14 ms | 8.49 ms | 14.66 ms | 16.19 ms | 578.16 ms |
| **p024** | 0 ns | 167 ns | 625 ns | 708 ns | 292 ns | 1.9 µs | 416.85 ms | 4.7 µs | 37.3 µs | 10.2 µs |
| **p025** | 858.0 µs | 6.46 ms | 5.88 ms | 7.09 ms | 6.85 ms | 122.9 µs | 4.58 ms | 84.61 ms | 486.8 µs | 22.43 ms |
| **p026** | 1.04 ms | 612.9 µs | 733.4 µs | 5.66 ms | 652.8 µs | 1.57 ms | 1.91 ms | 1.91 ms | 1.26 ms | 7.59 ms |
| **p027** | 8.46 ms | 7.44 ms | 9.73 ms | 7.85 ms | 6.08 ms | 6.02 ms | 118.17 ms | 14.54 ms | 13.49 ms | 406.94 ms |
| **p028** | 1.0 µs | 42 ns | 83 ns | 875 ns | 41 ns | 1.9 µs | 3.29 ms | 14.1 µs | 24.8 µs | 34.9 µs |
| **p029** | 30.0 µs | 12.4 µs | 2.28 ms | 4.38 ms | 542.9 µs | 6.30 ms | 22.00 ms | 4.75 ms | 1.27 ms | 2.66 ms |
| **p030** | 1.81 ms | 1.41 ms | 1.41 ms | 2.37 ms | 1.50 ms | 2.15 ms | 3.19 ms | 4.19 ms | 6.00 ms | 215.86 ms |
| **p031** | 2.0 µs | 708 ns | 708 ns | 2.2 µs | 1.0 µs | 6.0 µs | 223.2 µs | 18.6 µs | 67.3 µs | 49.7 µs |
| **p032** | 1.48 ms | 12.59 ms | 7.46 ms | 13.35 ms | 1.16 ms | 17.42 ms | 9.54 ms | 26.50 ms | 9.54 ms | 42.23 ms |
| **p033** | 15.0 µs | 8.2 µs | 8.2 µs | 7.7 µs | 2.0 µs | 11.1 µs | 248.2 µs | 116.0 µs | 236.8 µs | 351.5 µs |
| **p034** | 11.43 ms | 9.68 ms | 9.62 ms | 9.10 ms | 9.92 ms | 13.63 ms | 19.98 ms | 25.63 ms | 34.33 ms | 1.77 s |
| **p035** | 3.64 ms | 3.10 ms | 5.55 ms | 28.86 ms | 2.32 ms | 4.20 ms | 176.76 ms | 11.10 ms | 8.88 ms | 100.18 ms |
| **p036** | 5.66 ms | 54.81 ms | 63.08 ms | 79.01 ms | 4.94 ms | 42.22 ms | 13.36 ms | 38.47 ms | 65.25 ms | 146.76 ms |
| **p037** | 3.27 ms | 2.57 ms | 3.69 ms | 2.73 ms | 1.95 ms | 2.64 ms | 7.29 ms | 9.93 ms | 7.28 ms | 75.41 ms |
| **p038** | 207.0 µs | 1.94 ms | 559.8 µs | 1.70 ms | 215.1 µs | 1.04 ms | 21.05 ms | 3.82 ms | 1.54 ms | 4.04 ms |
| **p039** | 5.0 µs | 3.4 µs | 2.8 µs | 3.5 µs | 104.0 µs | 9.7 µs | 683.2 µs | 26.6 µs | 93.0 µs | 82.9 µs |
| **p040** | 1.33 ms | 9.34 ms | 3.78 ms | 7.56 ms | 291 ns | 4.29 ms | 6.24 ms | 5.75 ms | 10.21 ms | 17.55 ms |
| **p041** | 8.49 ms | 7.78 ms | 17.54 ms | 7.61 ms | 8.55 ms | 11.13 ms | 24.75 ms | 18.79 ms | 14.54 ms | 61.0 µs |
| **p042** | 27.0 µs | 308.6 µs | 315.7 µs | 119.6 µs | 227.1 µs | 291.2 µs | 16.80 ms | 8.88 ms | 938.0 µs | 1.12 ms |
| **p043** | 15.84 ms | 10.36 ms | 9.92 ms | 10.76 ms | 11.18 ms | 20.58 ms | 255.46 ms | 27.42 ms | 35.42 ms | 921.46 ms |
| **p044** | 2.97 ms | 50.25 ms | 40.85 ms | 15.65 ms | 36.45 ms | 166.18 ms | 129.27 ms | 40.33 ms | 56.05 ms | 161.44 ms |
| **p045** | 77.0 µs | 48.7 µs | 49.2 µs | 48.2 µs | 44.6 µs | 52.3 µs | 407.0 µs | 1.30 ms | 707.2 µs | 3.60 ms |
| **p046** | 4.84 ms | 3.97 ms | 3.76 ms | 5.56 ms | 3.98 ms | 4.08 ms | 7.93 ms | 6.82 ms | 9.81 ms | 20.36 ms |
| **p047** | 7.82 ms | 6.95 ms | 93.61 ms | 7.00 ms | 8.36 ms | 5.98 ms | 10.89 ms | 12.43 ms | 11.36 ms | 395.76 ms |
| **p048** | 132.0 µs | 146.5 µs | 125.4 µs | 169.5 µs | 104.0 µs | 416.7 µs | 671.1 µs | 15.88 ms | 1.16 ms | 642.8 µs |
| **p049** | 1.22 ms | 119.30 ms | 213.0 µs | 18.53 ms | 2.58 ms | 28.41 ms | 18.55 ms | 21.23 ms | 47.98 ms | 77.64 ms |
| **p050** | 3.61 ms | 3.63 ms | 4.41 ms | 2.66 ms | 3.45 ms | 5.28 ms | 7.94 ms | 13.25 ms | 10.45 ms | 109.16 ms |
| **p051** | 1.48 ms | 1.46 ms | 3.56 ms | 1.77 ms | 1.17 ms | 2.06 ms | 18.85 ms | 13.72 ms | 6.95 ms | 55.75 ms |
| **p052** | 1.03 ms | 21.82 ms | 89.71 ms | 34.01 ms | 1.26 ms | 47.94 ms | 15.76 ms | 23.08 ms | 79.49 ms | 100.05 ms |
| **p053** | 8.0 µs | 7.5 µs | 7.5 µs | 11.2 µs | 6.1 µs | 28.0 µs | 169.0 µs | 238.8 µs | 412.6 µs | 356.0 µs |
| **p054** | 118.0 µs | 716.3 µs | 1.30 ms | 772.7 µs | 370.3 µs | 5.19 ms | 7.95 ms | 26.55 ms | 4.35 ms | 5.27 ms |
| **p055** | 3.47 ms | 2.06 ms | 11.36 ms | 4.84 ms | 1.72 ms | 17.05 ms | 45.34 ms | 43.51 ms | 41.48 ms | 15.49 ms |
| **p056** | 2.79 ms | 3.09 ms | 5.41 ms | 2.45 ms | 1.96 ms | 3.80 ms | 58.44 ms | 30.96 ms | 49.24 ms | 53.83 ms |
| **p057** | 1.98 ms | 1.39 ms | 4.92 ms | 1.24 ms | 975.0 µs | 2.09 ms | 2.94 ms | 19.35 ms | 22.78 ms | 1.82 ms |
| **p058** | 35.41 ms | 26.78 ms | 26.45 ms | 45.85 ms | 27.06 ms | 25.78 ms | 73.88 ms | 27.81 ms | 49.88 ms | 905.66 ms |
| **p059** | 3.91 ms | 2.76 ms | 2.29 ms | 2.24 ms | 2.58 ms | 1.96 ms | 16.60 ms | 14.63 ms | 8.83 ms | 113.78 ms |
| **p060** | 737.09 ms | 358.15 ms | 351.69 ms | 329.26 ms | 356.47 ms | 385.61 ms | 396.89 ms | 428.16 ms | 407.73 ms | 627.30 ms |
| **p061** | 76.0 µs | 60.1 µs | 70.2 µs | 70.8 µs | 47.7 µs | 66.3 µs | 1.03 ms | 1.06 ms | 704.1 µs | 1.30 ms |
| **p062** | 3.70 ms | 1.47 ms | 1.59 ms | 913.8 µs | 1.27 ms | 3.84 ms | 3.67 ms | 7.39 ms | 8.78 ms | 6.17 ms |
| **p063** | 3.0 µs | 2.7 µs | 5.5 µs | 4.2 µs | 2.2 µs | 16.3 µs | 70.6 µs | 948.5 µs | 37.6 µs | 13.5 µs |
| **p064** | 3.07 ms | 2.60 ms | 2.01 ms | 2.05 ms | 2.33 ms | 2.20 ms | 2.50 ms | 3.22 ms | 3.11 ms | 25.06 ms |
| **p065** | 30.0 µs | 37.9 µs | 9.1 µs | 28.8 µs | 31.8 µs | 13.5 µs | 9.70 ms | 897.6 µs | 69.5 µs | 24.1 µs |
| **p066** | 165.0 µs | 54.61 ms | 783.6 µs | 56.50 ms | 55.36 ms | 2.47 ms | 5.97 ms | 8.22 ms | 1.82 ms | 2.28 ms |
| **p067** | 35.0 µs | 174.2 µs | 649.7 µs | 86.5 µs | 116.0 µs | 267.8 µs | 14.68 ms | 13.71 ms | 1.00 ms | 1.04 ms |
| **p068** | 15.64 ms | 10.54 ms | 10.09 ms | 11.47 ms | 11.21 ms | 19.31 ms | 71.42 ms | 78.20 ms | 43.15 ms | 948.39 ms |
| **p069** | 0 ns | 41 ns | 42 ns | 42 ns | 41 ns | 1.5 µs | 182.5 µs | 2.8 µs | 14.9 µs | 1.6 µs |
| **p070** | 305.33 ms | 222.98 ms | 238.14 ms | 190.52 ms | 234.58 ms | 288.49 ms | 371.99 ms | 453.84 ms | 774.89 ms | 11.94 s |
| **p071** | 1.03 ms | 1.90 ms | 2.44 ms | 2.32 ms | 2.59 ms | 2.37 ms | 1.26 ms | 3.21 ms | 3.11 ms | 74.19 ms |
| **p072** | 5.41 ms | 4.41 ms | 4.30 ms | 4.17 ms | 4.60 ms | 4.81 ms | 5.06 ms | 10.09 ms | 10.97 ms | 461.66 ms |
| **p073** | 14.69 ms | 18.08 ms | 17.85 ms | 17.30 ms | 17.59 ms | 23.30 ms | 39.07 ms | 18.27 ms | 65.84 ms | 941.41 ms |
| **p074** | 6.01 ms | 5.46 ms | 6.03 ms | 31.71 ms | 6.60 ms | 6.80 ms | 8.96 ms | 17.56 ms | 14.90 ms | 645.34 ms |
| **p075** | 7.80 ms | 4.68 ms | 4.34 ms | 5.48 ms | 6.92 ms | 5.21 ms | 7.63 ms | 12.76 ms | 12.96 ms | 119.82 ms |
| **p076** | 4.0 µs | 3.9 µs | 3.1 µs | 4.8 µs | 4.2 µs | 7.2 µs | 124.8 µs | 68.0 µs | 331.3 µs | 192.4 µs |
| **p077** | 30.0 µs | 50.9 µs | 59.1 µs | 55.0 µs | 32.1 µs | 72.6 µs | 5.04 ms | 309.3 µs | 1.65 ms | 4.26 ms |
| **p078** | 52.21 ms | 45.23 ms | 47.02 ms | 45.40 ms | 61.73 ms | 45.61 ms | 46.59 ms | 54.12 ms | 106.45 ms | 1.12 s |
| **p079** | 1.0 µs | 101.0 µs | 104.5 µs | 14.4 µs | 104.8 µs | 118.9 µs | 6.23 ms | 15.9 µs | 139.0 µs | 47.2 µs |
| **p080** | 16.45 ms | 4.00 ms | 6.31 ms | 8.65 ms | 4.93 ms | 408.1 µs | 8.99 ms | 11.95 ms | 620.8 µs | 1.57 ms |
| **p081** | 35.0 µs | 288.1 µs | 523.4 µs | 275.6 µs | 214.1 µs | 393.9 µs | 14.30 ms | 10.64 ms | 1.13 ms | 1.48 ms |
| **p082** | 54.0 µs | 287.1 µs | 458.5 µs | 253.0 µs | 195.3 µs | 394.3 µs | 17.20 ms | 11.06 ms | 1.26 ms | 1.50 ms |
| **p083** | 538.0 µs | 674.7 µs | 862.4 µs | 713.1 µs | 508.6 µs | 1.43 ms | 20.08 ms | 14.33 ms | 4.41 ms | 4.73 ms |
| **p084** | 147.0 µs | 132.5 µs | 132.8 µs | 14.27 ms | 134.5 µs | 260.2 µs | 6.11 ms | 1.98 ms | 1.67 ms | 10.61 ms |
| **p085** | 16.0 µs | 15.3 µs | 14.0 µs | 20.9 µs | 16.1 µs | 15.5 µs | 206.2 µs | 526.4 µs | 639.9 µs | 1.26 ms |
| **p086** | 3.92 ms | 2.34 ms | 2.43 ms | 2.42 ms | 2.90 ms | 3.01 ms | 2.74 ms | 5.40 ms | 11.14 ms | 267.28 ms |
| **p087** | 8.83 ms | 9.21 ms | 2.65 ms | 7.18 ms | 8.82 ms | 10.00 ms | 17.81 ms | 16.69 ms | 18.38 ms | 176.52 ms |
| **p088** | 1.54 ms | 1.32 ms | 1.90 ms | 1.29 ms | 1.47 ms | 1.51 ms | 12.01 ms | 3.18 ms | 3.75 ms | 94.90 ms |
| **p089** | 324.0 µs | 246.7 µs | 282.4 µs | 358.4 µs | 177.3 µs | 168.4 µs | 5.97 ms | 8.71 ms | 610.8 µs | 2.20 ms |
| **p090** | 162.0 µs | 95.3 µs | 162.5 µs | 89.0 µs | 99.8 µs | 223.3 µs | 1.56 ms | 2.84 ms | 4.51 ms | 3.99 ms |
| **p091** | 10.18 ms | 4.52 ms | 5.08 ms | 4.18 ms | 5.88 ms | 9.40 ms | 10.54 ms | 12.50 ms | 19.21 ms | 708.41 ms |
| **p092** | 116.03 ms | 44.14 ms | 44.36 ms | 44.14 ms | 44.32 ms | 58.28 ms | 111.58 ms | 129.62 ms | 148.83 ms | 4.63 s |
| **p093** | 10.98 ms | 9.32 ms | 8.00 ms | 19.56 ms | 8.97 ms | 14.03 ms | 72.21 ms | 17.01 ms | 36.86 ms | 145.50 ms |
| **p094** | 0 ns | 83 ns | 125 ns | 83 ns | 84 ns | 1.5 µs | 74.8 µs | 2.7 µs | 20.0 µs | 5.0 µs |
| **p095** | 78.46 ms | 72.31 ms | 70.54 ms | 75.75 ms | 71.50 ms | 101.15 ms | 80.52 ms | 101.95 ms | 99.88 ms | 2.64 s |
| **p096** | 4.28 ms | 1.55 ms | 1.90 ms | 1.86 ms | 1.70 ms | 5.61 ms | 28.53 ms | 15.31 ms | 6.10 ms | 169.93 ms |
| **p097** | 1.0 µs | 541 ns | 750 ns | 1.7 µs | 584 ns | 7.9 µs | 259.0 µs | 865.7 µs | 33.6 µs | 4.2 µs |
| **p098** | 1.78 ms | 9.93 ms | 9.09 ms | 3.34 ms | 4.50 ms | 8.52 ms | 43.69 ms | 40.22 ms | 75.67 ms | 40.88 ms |
| **p099** | 147.0 µs | 177.2 µs | 251.2 µs | 109.4 µs | 116.5 µs | 154.3 µs | 15.03 ms | 11.19 ms | 356.8 µs | 405.7 µs |
| **p100** | 0 ns | 83 ns | 125 ns | 84 ns | 83 ns | 1.6 µs | 57.4 µs | 2.2 µs | 13.0 µs | 3.8 µs |

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
cmd/euler-bench/euler-bench per-iter --lang all --problems 1-100 --iters 10 --write
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

