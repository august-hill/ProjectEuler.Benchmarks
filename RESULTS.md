# Project Euler — Cross-Language Benchmarks

> **Scope: 2400 in-scope cells across 300 problems × tiered languages — 2044 measured (85.2% coverage).**
> The cross-language ranking below is computed over the **199-problem common set** (problems in 1-200 where every language has a passing measurement) — the apples-to-apples Foundation comparison surface.  Per-tier rankings and coverage detail appear further below.
> Growing carefully — each new problem and language is audited for state-leak
> safety, verified for answer correctness, and added only when it cleanly fits the
> measurement methodology.  See [JOURNEY.md](JOURNEY.md) for the full story of how
> we got here, including the reset from 200+ problems back to a verified 10×10
> core, then the disciplined expansion to today's 300-problem scope.

## Per-Invocation Cost — Foundation (Common Set, 199 of 200 problems)

We run each program 10 times in fresh OS processes (no warmup, no shared state).
Each invocation pays full startup + algorithm cost — the cost a real CLI / cron /
shell-loop user actually pays.  The median wall time across the 10 invocations is
the headline per-problem number, and the table sums over the 199-problem
common set so partial-coverage languages aren't artificially "faster" than fully-
covered ones.  Per-language individual coverage (which may be ≥ the common set) is
shown in the coverage block further down.

![Per-Invocation Cost](charts/per_iter_total.png)

| Rank | Language | Total (199-problem common set) | Lines of code | vs Fastest |
|------|----------|--------------------:|--------------:|-----------:|
| 1 | **C** | 22.47 s | 14,346 | 1.00× |
| 2 | **C++** | 22.75 s | 10,256 | 1.01× |
| 3 | **Zig** | 25.02 s | 13,310 | 1.11× |
| 4 | **Rust** | 29.22 s | 11,443 | 1.30× |
| 5 | **Go** | 31.49 s | 13,062 | 1.40× |
| 6 | **ARM64** | 34.10 s | 39,793 | 1.52× |
| 7 | **C#** | 39.45 s | 10,825 | 1.76× |
| 8 | **Java** | 43.42 s | 10,468 | 1.93× |
| 9 | **JavaScript** | 68.46 s | 9,123 | 3.05× |
| 10 | **Python** | 669.59 s | 8,459 | 29.80× |

## Per-Invocation Cost — Deep Coverage (Tier 2, problems 201-300, 4 languages)

Same per-invocation metric, restricted to the deeper subset of languages (C++, Go, Zig, Python) that intentionally pushed past problem 200. The other 6 Foundation languages are out of tier scope here — they're capped at 200 by the project's language-cap policy (see JOURNEY.md).

> _Tier 2 common-set is currently empty — no problem in 201-300 has passing measurements in all 4 deep-coverage languages yet. The ranking will populate as benching continues._

## Speed vs Code Size

How much code does each language need to solve these 200 Foundation problems, and how
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
chunked into bands of 100 (currently 3 bands), which keeps cells legibly sized as we extend
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

### Problems 001–100 — Foundation (10 langs)

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
| **p051** | 1.51 ms | 1.67 ms | 3.71 ms | 2.11 ms | 1.45 ms | 1.78 ms | 19.07 ms | 14.14 ms | 7.13 ms | 54.21 ms |
| **p052** | 1.04 ms | 21.57 ms | 89.68 ms | 34.18 ms | 1.02 ms | 48.01 ms | 16.04 ms | 24.10 ms | 80.35 ms | 99.46 ms |
| **p053** | 8.0 µs | 5.8 µs | 6.9 µs | 16.4 µs | 6.9 µs | 23.2 µs | 171.0 µs | 230.3 µs | 367.4 µs | 366.2 µs |
| **p054** | 89.0 µs | 653.5 µs | 1.67 ms | 699.0 µs | 324.4 µs | 5.07 ms | 7.86 ms | 27.62 ms | 4.44 ms | 5.32 ms |
| **p055** | 2.97 ms | 1.65 ms | 11.45 ms | 4.42 ms | 1.98 ms | 16.91 ms | 45.78 ms | 43.83 ms | 41.64 ms | 15.60 ms |
| **p056** | 2.21 ms | 2.42 ms | 6.98 ms | 1.97 ms | 2.68 ms | 3.75 ms | 59.33 ms | 30.82 ms | 50.20 ms | 53.73 ms |
| **p057** | 1.85 ms | 1.62 ms | 3.96 ms | 1.34 ms | 991.5 µs | 1.86 ms | 2.58 ms | 19.73 ms | 22.84 ms | 1.81 ms |
| **p058** | 35.10 ms | 26.99 ms | 26.58 ms | 46.40 ms | 26.34 ms | 26.25 ms | 76.40 ms | 28.30 ms | 50.30 ms | 909.99 ms |
| **p059** | 4.15 ms | 2.92 ms | 3.02 ms | 2.64 ms | 2.77 ms | 1.94 ms | 16.16 ms | 15.14 ms | 9.03 ms | 113.80 ms |
| **p060** | 746.69 ms | 365.35 ms | 360.32 ms | 346.78 ms | 361.33 ms | 402.88 ms | 416.33 ms | 459.87 ms | 412.20 ms | 634.81 ms |
| **p061** | 76.0 µs | 53.0 µs | 57.0 µs | 67.9 µs | 49.7 µs | 76.0 µs | 1.02 ms | 1.18 ms | 683.7 µs | 1.30 ms |
| **p062** | 2.68 ms | 1.11 ms | 1.39 ms | 714.8 µs | 907.8 µs | 3.79 ms | 3.73 ms | 7.41 ms | 8.93 ms | 6.13 ms |
| **p063** | 3.0 µs | 2.6 µs | 6.6 µs | 5.5 µs | 2.9 µs | 15.8 µs | 68.2 µs | 1.04 ms | 35.9 µs | 13.2 µs |
| **p064** | 3.14 ms | 1.96 ms | 1.97 ms | 2.67 ms | 1.97 ms | 2.49 ms | 2.49 ms | 3.31 ms | 3.12 ms | 24.88 ms |
| **p065** | 31.0 µs | 34.3 µs | 8.6 µs | 25.4 µs | 31.8 µs | 14.1 µs | 12.27 ms | 888.7 µs | 64.9 µs | 23.2 µs |
| **p066** | 133.0 µs | 53.90 ms | 596.4 µs | 55.97 ms | 54.91 ms | 2.56 ms | 6.63 ms | 7.99 ms | 1.78 ms | 2.33 ms |
| **p067** | 29.0 µs | 152.5 µs | 555.6 µs | 83.5 µs | 158.2 µs | 261.4 µs | 14.94 ms | 14.25 ms | 973.3 µs | 1.04 ms |
| **p068** | 16.03 ms | 11.39 ms | 10.45 ms | 11.53 ms | 11.42 ms | 19.71 ms | 73.22 ms | 79.69 ms | 45.20 ms | 953.29 ms |
| **p069** | 0 ns | 42 ns | 41 ns | 42 ns | 42 ns | 1.5 µs | 252.2 µs | 2.6 µs | 13.8 µs | 1.6 µs |
| **p070** | 309.46 ms | 229.54 ms | 244.43 ms | 193.90 ms | 230.23 ms | 311.13 ms | 388.22 ms | 474.35 ms | 789.04 ms | 11.87 s |
| **p071** | 1.06 ms | 2.36 ms | 2.40 ms | 1.82 ms | 2.33 ms | 2.54 ms | 1.24 ms | 3.39 ms | 3.03 ms | 74.84 ms |
| **p072** | 4.36 ms | 3.45 ms | 3.51 ms | 4.94 ms | 4.49 ms | 4.87 ms | 5.09 ms | 10.34 ms | 10.96 ms | 473.41 ms |
| **p073** | 14.87 ms | 17.92 ms | 18.18 ms | 17.39 ms | 17.39 ms | 23.44 ms | 39.71 ms | 18.49 ms | 66.37 ms | 945.34 ms |
| **p074** | 4.77 ms | 5.06 ms | 5.06 ms | 32.44 ms | 6.25 ms | 6.52 ms | 8.92 ms | 18.44 ms | 14.96 ms | 643.03 ms |
| **p075** | 8.22 ms | 5.91 ms | 3.81 ms | 4.72 ms | 6.81 ms | 6.13 ms | 7.73 ms | 10.74 ms | 13.13 ms | 118.45 ms |
| **p076** | 3.0 µs | 3.0 µs | 3.0 µs | 6.1 µs | 4.3 µs | 8.0 µs | 129.8 µs | 73.0 µs | 316.5 µs | 183.2 µs |
| **p077** | 32.0 µs | 52.1 µs | 59.0 µs | 52.0 µs | 31.9 µs | 73.3 µs | 5.04 ms | 348.4 µs | 1.61 ms | 4.36 ms |
| **p078** | 52.73 ms | 45.95 ms | 45.97 ms | 45.34 ms | 59.86 ms | 45.89 ms | 46.60 ms | 54.99 ms | 108.03 ms | 1.12 s |
| **p079** | 2.0 µs | 90.5 µs | 99.0 µs | 17.5 µs | 96.9 µs | 119.9 µs | 6.70 ms | 16.5 µs | 141.2 µs | 44.6 µs |
| **p080** | 16.70 ms | 4.06 ms | 7.96 ms | 10.00 ms | 4.91 ms | 384.2 µs | 9.54 ms | 11.86 ms | 620.3 µs | 1.58 ms |
| **p081** | 35.0 µs | 322.8 µs | 569.6 µs | 271.3 µs | 187.3 µs | 384.7 µs | 15.49 ms | 12.17 ms | 1.11 ms | 1.53 ms |
| **p082** | 44.0 µs | 262.5 µs | 537.7 µs | 221.2 µs | 179.2 µs | 335.1 µs | 19.71 ms | 11.33 ms | 1.26 ms | 1.57 ms |
| **p083** | 469.0 µs | 842.8 µs | 788.5 µs | 640.5 µs | 556.8 µs | 1.09 ms | 23.72 ms | 15.21 ms | 4.42 ms | 4.88 ms |
| **p084** | 144.0 µs | 102.9 µs | 131.6 µs | 14.50 ms | 107.1 µs | 238.5 µs | 6.78 ms | 2.01 ms | 1.76 ms | 10.63 ms |
| **p085** | 12.0 µs | 15.4 µs | 14.2 µs | 22.9 µs | 16.0 µs | 18.8 µs | 224.6 µs | 527.5 µs | 671.5 µs | 1.25 ms |
| **p086** | 3.05 ms | 2.06 ms | 2.95 ms | 2.48 ms | 3.00 ms | 2.94 ms | 2.77 ms | 5.52 ms | 11.18 ms | 270.37 ms |
| **p087** | 9.52 ms | 9.08 ms | 3.02 ms | 8.15 ms | 9.52 ms | 10.04 ms | 17.72 ms | 17.82 ms | 19.29 ms | 183.25 ms |
| **p088** | 1.22 ms | 1.05 ms | 1.98 ms | 1.77 ms | 1.05 ms | 1.53 ms | 11.93 ms | 3.21 ms | 3.79 ms | 94.74 ms |
| **p089** | 301.0 µs | 235.7 µs | 328.4 µs | 185.4 µs | 195.1 µs | 155.6 µs | 6.09 ms | 9.25 ms | 612.0 µs | 2.18 ms |
| **p090** | 122.0 µs | 73.8 µs | 151.9 µs | 101.2 µs | 106.9 µs | 238.5 µs | 1.64 ms | 2.89 ms | 4.63 ms | 4.08 ms |
| **p091** | 10.36 ms | 5.62 ms | 5.66 ms | 5.42 ms | 4.66 ms | 9.73 ms | 10.79 ms | 12.87 ms | 19.35 ms | 711.93 ms |
| **p092** | 116.86 ms | 44.53 ms | 44.85 ms | 44.69 ms | 45.36 ms | 59.03 ms | 113.26 ms | 131.35 ms | 151.06 ms | 4.55 s |
| **p093** | 10.58 ms | 8.55 ms | 6.76 ms | 19.86 ms | 7.85 ms | 14.38 ms | 74.39 ms | 17.24 ms | 36.93 ms | 147.86 ms |
| **p094** | 0 ns | 83 ns | 84 ns | 84 ns | 125 ns | 1.2 µs | 84.0 µs | 2.8 µs | 21.1 µs | 4.6 µs |
| **p095** | 96.73 ms | 76.40 ms | 73.61 ms | 82.29 ms | 76.29 ms | 109.40 ms | 88.60 ms | 110.15 ms | 106.62 ms | 2.79 s |
| **p096** | 4.15 ms | 1.81 ms | 2.01 ms | 1.49 ms | 1.30 ms | 4.48 ms | 29.72 ms | 15.57 ms | 6.17 ms | 170.81 ms |
| **p097** | 0 ns | 541 ns | 750 ns | 2.0 µs | 666 ns | 6.8 µs | 316.8 µs | 962.5 µs | 33.3 µs | 4.4 µs |
| **p098** | 1.57 ms | 10.41 ms | 9.38 ms | 4.54 ms | 3.34 ms | 9.12 ms | 46.16 ms | 41.73 ms | 77.87 ms | 41.11 ms |
| **p099** | 110.0 µs | 153.1 µs | 203.7 µs | 113.7 µs | 129.0 µs | 176.8 µs | 16.99 ms | 11.24 ms | 380.2 µs | 439.0 µs |
| **p100** | 0 ns | 42 ns | 125 ns | 42 ns | 125 ns | 1.9 µs | 68.0 µs | 2.2 µs | 13.7 µs | 3.7 µs |

### Problems 101–200 — Foundation (10 langs)

| Problem | ARM64 | C | C++ | Rust | Zig | Go | C# | Java | JavaScript | Python |
|---------|----:|----:|----:|----:|----:|----:|----:|----:|----:|----:|
| **p101** | 1.0 µs | 1.3 µs | 1.2 µs | 2.3 µs | 1.6 µs | 3.6 µs | 210.9 µs | 16.9 µs | 79.6 µs | 55.2 µs |
| **p102** | 153.0 µs | 482.3 µs | 486.8 µs | 203.1 µs | 173.2 µs | 189.9 µs | 13.06 ms | 11.30 ms | 1.02 ms | 999.6 µs |
| **p103** | 7.71 ms | 26.93 ms | 27.09 ms | 27.28 ms | 25.31 ms | 66.76 ms | 220.44 ms | 77.77 ms | 186.57 ms | 3.10 s |
| **p104** | 6.71 ms | 6.17 ms | 5.00 ms | 6.36 ms | 6.47 ms | 7.13 ms | 6.42 ms | 8.13 ms | 7.94 ms | 135.81 ms |
| **p105** | 3.21 ms | 19.67 ms | 20.06 ms | 21.28 ms | 19.90 ms | 21.38 ms | 36.10 ms | 38.22 ms | 36.03 ms | 896.30 ms |
| **p106** | 0 ns | 208 ns | 333 ns | 292 ns | 333 ns | 2.1 µs | 151.0 µs | 6.0 µs | 36.7 µs | 6.5 µs |
| **p107** | 146.0 µs | 167.3 µs | 179.6 µs | 51.5 µs | 145.2 µs | 142.1 µs | 13.83 ms | 10.21 ms | 646.6 µs | 498.9 µs |
| **p108** | 352.0 µs | 7.8 µs | 6.9 µs | 7.8 µs | 8.2 µs | 9.0 µs | 306.6 µs | 130.0 µs | 203.3 µs | 356.2 µs |
| **p109** | 32.0 µs | 4.3 µs | 4.1 µs | 20.8 µs | 9.7 µs | 30.7 µs | 677.5 µs | 686.7 µs | 1.52 ms | 1.64 ms |
| **p110** | 5.89 ms | 8.92 ms | 6.71 ms | 7.76 ms | 70.24 ms | 11.20 ms | 35.94 ms | 25.01 ms | 11.86 ms | 458.04 ms |
| **p111** | 936.0 µs | 1.44 ms | 1.13 ms | 1.46 ms | 1.17 ms | 1.25 ms | 10.49 ms | 17.31 ms | 12.21 ms | 11.58 ms |
| **p112** | 8.06 ms | 4.98 ms | 5.61 ms | 4.77 ms | 6.33 ms | 6.93 ms | 7.59 ms | 9.42 ms | 12.14 ms | 358.35 ms |
| **p113** | 0 ns | 41 ns | 125 ns | 42 ns | 42 ns | 1.2 µs | 106.2 µs | 742.9 µs | 36.3 µs | 3.0 µs |
| **p114** | 3.0 µs | 1.7 µs | 1.7 µs | 1.8 µs | 1.6 µs | 5.3 µs | 122.8 µs | 28.0 µs | 83.0 µs | 75.2 µs |
| **p115** | 657.0 µs | 173.9 µs | 175.2 µs | 304.5 µs | 186.5 µs | 857.3 µs | 2.22 ms | 2.33 ms | 1.32 ms | 16.03 ms |
| **p116** | 1.0 µs | 291 ns | 166 ns | 958 ns | 42 ns | 6.3 µs | 128.9 µs | 7.0 µs | 52.5 µs | 15.0 µs |
| **p117** | 0 ns | 125 ns | 291 ns | 542 ns | 125 ns | 3.1 µs | 132.9 µs | 4.8 µs | 38.0 µs | 12.0 µs |
| **p118** | 134.71 ms | 584.91 ms | 588.84 ms | 370.12 ms | 605.82 ms | 253.26 ms | 421.23 ms | 1.56 s | 1.29 s | 2.95 s |
| **p119** | 24.0 µs | 16.2 µs | 19.6 µs | 17.8 µs | 18.8 µs | 29.7 µs | 1.32 ms | 423.5 µs | 875.5 µs | 879.6 µs |
| **p120** | 431.0 µs | 412.2 µs | 493.4 µs | 414.0 µs | 418.7 µs | 585.5 µs | 797.5 µs | 2.09 ms | 1.60 ms | 24.02 ms |
| **p121** | 0 ns | 250 ns | 250 ns | 750 ns | 42 ns | 2.4 µs | 132.8 µs | 5.5 µs | 43.9 µs | 19.2 µs |
| **p122** | 1.92 s | 1.19 s | 1.19 s | 1.65 s | 1.19 s | 1.22 s | 1.56 s | 1.62 s | 2.73 s | 89.52 s |
| **p123** | 3.98 ms | 4.86 ms | 4.53 ms | 1.66 ms | 2.16 ms | 3.15 ms | 5.94 ms | 10.73 ms | 749.8 µs | 74.71 ms |
| **p124** | 7.84 ms | 7.25 ms | 5.40 ms | 2.45 ms | 6.86 ms | 13.01 ms | 9.55 ms | 17.27 ms | 16.67 ms | 36.21 ms |
| **p125** | 3.11 ms | 2.60 ms | 2.37 ms | 3.06 ms | 2.45 ms | 3.09 ms | 3.88 ms | 6.12 ms | 63.70 ms | 62.63 ms |
| **p126** | 3.42 ms | 2.39 ms | 2.18 ms | 2.45 ms | 2.30 ms | 4.63 ms | 7.81 ms | 8.90 ms | 12.92 ms | 932.49 ms |
| **p127** | 37.07 ms | 31.41 ms | 29.73 ms | 28.92 ms | 29.07 ms | 34.20 ms | 44.76 ms | 55.95 ms | 55.20 ms | 1.10 s |
| **p128** | 8.53 ms | 6.97 ms | 6.81 ms | 8.03 ms | 6.63 ms | 6.94 ms | 20.25 ms | 10.94 ms | 11.21 ms | 272.33 ms |
| **p129** | 9.69 ms | 10.41 ms | 9.93 ms | 10.34 ms | 12.54 ms | 9.74 ms | 10.37 ms | 10.28 ms | 10.59 ms | 139.64 ms |
| **p130** | 31.49 ms | 31.39 ms | 32.50 ms | 31.97 ms | 37.93 ms | 31.48 ms | 40.62 ms | 31.61 ms | 35.60 ms | 415.08 ms |
| **p131** | 42.0 µs | 31.5 µs | 40.0 µs | 38.4 µs | 31.2 µs | 32.1 µs | 295.4 µs | 245.6 µs | 224.1 µs | 1.20 ms |
| **p132** | 3.40 ms | 3.26 ms | 4.12 ms | 3.30 ms | 4.45 ms | 3.38 ms | 4.41 ms | 28.82 ms | 12.93 ms | 74.27 ms |
| **p133** | 2.89 ms | 2.10 ms | 2.84 ms | 3.26 ms | 2.37 ms | 2.21 ms | 3.40 ms | 26.33 ms | 11.20 ms | 22.24 ms |
| **p134** | 6.17 ms | 5.87 ms | 7.42 ms | 7.30 ms | 6.16 ms | 6.28 ms | 7.84 ms | 73.24 ms | 34.77 ms | 157.17 ms |
| **p135** | 4.66 ms | 3.46 ms | 3.74 ms | 3.67 ms | 3.11 ms | 4.60 ms | 4.38 ms | 8.62 ms | 9.37 ms | 353.35 ms |
| **p136** | 640.13 ms | 494.10 ms | 446.25 ms | 555.54 ms | 490.94 ms | 533.67 ms | 654.83 ms | 669.97 ms | 963.87 ms | 26.64 s |
| **p137** | 0 ns | 125 ns | 291 ns | 42 ns | 125 ns | 1.8 µs | 75.0 µs | 2.7 µs | 24.5 µs | 5.7 µs |
| **p138** | 0 ns | 42 ns | 42 ns | 42 ns | 83 ns | 1.5 µs | 52.4 µs | 1.8 µs | 11.8 µs | 2.9 µs |
| **p139** | 235.19 ms | 227.09 ms | 224.31 ms | 224.24 ms | 302.89 ms | 236.94 ms | 264.99 ms | 258.89 ms | 273.44 ms | 2.13 s |
| **p140** | 8.0 µs | 3.4 µs | 4.5 µs | 5.6 µs | 2.2 µs | 7.1 µs | 1.29 ms | 167.7 µs | 160.0 µs | 70.8 µs |
| **p141** | 1.48 s | 1.45 s | 1.44 s | 1.44 s | 1.97 s | 1.49 s | 1.60 s | 1.60 s | 1.76 s | 9.00 s* |
| **p142** | 2.26 ms | 2.77 ms | 2.05 ms | 2.60 ms | 2.48 ms | 2.16 ms | 2.88 ms | 6.01 ms | 9.04 ms | 110.37 ms |
| **p143** | 47.42 ms | 18.18 ms | 16.59 ms | 110.14 ms | 19.49 ms | 28.62 ms | 67.32 ms | 73.20 ms | 42.90 ms | 320.93 ms |
| **p144** | 14.0 µs | 11.6 µs | 9.1 µs | 12.5 µs | 13.0 µs | 13.3 µs | 142.6 µs | 59.2 µs | 142.8 µs | 134.1 µs |
| **p145** | 76.61 ms | 45.40 ms | 45.48 ms | 47.92 ms | 45.46 ms | 84.34 ms | 75.27 ms | 102.87 ms | 168.21 ms | 4.72 s |
| **p146** | 9.47 s | 2.85 s | 2.89 s* | 2.94 s* | 2.77 s | 2.93 s | 7.41 s* | 4.09 s* | 9.57 s* | 19.21 s* |
| **p147** | 5.09 ms | 1.43 ms | 1.99 ms | 6.17 ms | 2.63 ms | 3.34 ms | 4.80 ms | 7.64 ms | 9.26 ms | 528.01 ms |
| **p148** | 0 ns | 42 ns | 167 ns | 3.2 µs | 42 ns | 5.0 µs | 128.7 µs | 3.1 µs | 37.2 µs | 8.1 µs |
| **p149** | 42.95 ms | 44.93 ms | 37.89 ms | 78.41 ms | 48.34 ms | 52.98 ms | 70.81 ms | 87.47 ms | 98.05 ms | 2.01 s |
| **p150** | 127.03 ms | 158.85 ms | 158.33 ms | 179.99 ms | 123.28 ms | 226.44 ms | 232.78 ms | 242.33 ms | 553.92 ms | 16.64 s |
| **p151** | 11.0 µs | 1.9 µs | 2.7 µs | 3.6 µs | 1.8 µs | 3.9 µs | 605.3 µs | 52.2 µs | 83.0 µs | 41.8 µs |
| **p152** | 1.62 s | 783.50 ms | 754.11 ms | 707.69 ms | 766.73 ms | 1.22 s | 1.01 s | 887.04 ms | 5.66 s | 815.61 ms* |
| **p153** | 2.41 s | 2.38 s | 2.39 s* | 2.31 s* | 3.15 s | 2.43 s | 2.74 s* | 2.45 s* | 7.09 s* | 32.80 s* |
| **p154** | 3.47 s | 2.68 s | 2.69 s* | 4.04 s* | 3.10 s | 3.92 s | 5.31 s* | 6.20 s* | 9.36 s* | 292.18 s* |
| **p155** | 811.52 ms | 598.02 ms | 611.56 ms | 1.10 s | 612.28 ms | 837.06 ms | 1.31 s | 3.06 s | 982.12 ms | 7.34 s* |
| **p156** | 143.76 ms | 90.24 ms | 88.25 ms | 79.98 ms | 77.07 ms | 126.54 ms | 249.35 ms | 107.89 ms | 1.06 s | 7.37 s |
| **p157** | 6.53 ms | 5.66 ms | 6.12 ms | 5.60 ms | 4.87 ms | 5.30 ms | 7.18 ms | 6.99 ms | 8.91 ms | 234.05 ms |
| **p158** | 0 ns | 41 ns | 42 ns | 125 ns | 42 ns | 1.2 µs | 73.9 µs | 3.3 µs | 18.1 µs | 7.7 µs |
| **p159** | 13.19 ms | 19.29 ms | 11.74 ms | 15.30 ms | 12.28 ms | 19.70 ms | 17.21 ms | 27.06 ms | 1.51 ms | 869.70 ms |
| **p160** | 287.0 µs | 245.7 µs | 246.0 µs | 206.0 µs | 309.5 µs | 248.3 µs | 1.10 ms | 1.59 ms | 4.22 ms | 3.07 ms |
| **p161** | 47.17 ms | 29.87 ms | 27.98 ms | 26.66 ms | 27.07 ms | 46.05 ms | 55.89 ms | 80.92 ms | 146.29 ms | 2.07 s |
| **p162** | 0 ns | 41 ns | 42 ns | 1.2 µs | 42 ns | 8.0 µs | 2.16 ms | 816.2 µs | 28.7 µs | 9.3 µs |
| **p163** | 150.42 ms | 115.47 ms | 125.49 ms | 145.47 ms | 144.29 ms | 167.05 ms | 318.99 ms | 243.46 ms | 543.77 ms | 2.71 s |
| **p164** | 6.0 µs | 5.8 µs | 4.6 µs | 6.8 µs | 5.2 µs | 6.8 µs | 595.1 µs | 139.9 µs | 261.8 µs | 333.1 µs |
| **p165** | 660.91 ms | 607.31 ms | 553.40 ms | 418.99 ms | 608.29 ms | 879.32 ms | 743.63 ms | 1.88 s | 2.69 s | 6.95 s* |
| **p166** | 171.29 ms | 24.53 ms | 24.29 ms | 87.76 ms | 17.02 ms | 162.78 ms | 157.58 ms | 180.46 ms | 205.74 ms | 8.91 s |
| **p167** | 129.05 ms | 122.85 ms | 127.29 ms | 126.88 ms | 138.54 ms | 130.05 ms | 139.25 ms | 161.03 ms | 236.92 ms | 7.37 s |
| **p168** | 32.0 µs | 25.5 µs | 21.7 µs | 31.5 µs | 27.3 µs | 33.1 µs | 248.5 µs | 197.8 µs | 274.0 µs | 533.3 µs |
| **p169** | 1.0 µs | 167 ns | 208 ns | 2.0 µs | 208 ns | 10.7 µs | 411.8 µs | 533.3 µs | 40.0 µs | 13.9 µs |
| **p170** | 39.50 s | 39.45 s | 38.41 s* | 24.67 s* | 38.48 s | 40.38 s | 392.34 ms* | 56.12 s* | 7.70 ms* | — |
| **p171** | 2.90 ms | 1.46 ms | 2.05 ms | 2.20 ms | 2.14 ms | 3.20 ms | 4.00 ms | 7.25 ms | 20.31 ms | 150.21 ms |
| **p172** | 3.0 µs | 2.1 µs | 3.3 µs | 4.1 µs | 2.5 µs | 6.5 µs | 614.7 µs | 41.0 µs | 122.8 µs | 118.7 µs |
| **p173** | 10.02 ms | 536.7 µs | 634.2 µs | 621.5 µs | 590.8 µs | 740.6 µs | 1.11 ms | 9.07 ms | 3.50 ms | 92.81 ms |
| **p174** | 3.50 ms | 2.68 ms | 2.63 ms | 2.73 ms | 2.09 ms | 3.08 ms | 3.20 ms | 5.94 ms | 5.67 ms | 166.08 ms |
| **p175** | 0 ns | 208 ns | 125 ns | 1.4 µs | 125 ns | 1.5 µs | 155.0 µs | 3.4 µs | 30.5 µs | 4.0 µs |
| **p176** | 285.0 µs | 16.5 µs | 11.2 µs | 27.2 µs | 62.0 µs | 40.1 µs | 733.4 µs | 346.5 µs | 391.3 µs | 392.5 µs |
| **p177** | 6.55 s | 4.57 s | 4.60 s* | 9.18 s* | 5.07 s | 10.05 s | 6.75 s* | 11.44 s* | 15.08 s* | 12.78 s* |
| **p178** | 351.0 µs | 589.2 µs | 481.2 µs | 580.0 µs | 509.8 µs | 536.4 µs | 1.91 ms | 3.16 ms | 6.78 ms | 11.14 ms |
| **p179** | 192.94 ms | 260.81 ms | 245.28 ms | 244.51 ms | 281.21 ms | 441.64 ms | 379.50 ms | 307.46 ms | 16.82 ms | 11.61 s |
| **p180** | 9.13 ms | 22.94 ms | 21.62 ms | 15.39 ms | 23.36 ms | 29.96 ms | 33.91 ms | 75.84 ms | 132.27 ms | 138.05 ms |
| **p181** | 3.46 ms | 7.51 ms | 8.95 ms | 9.26 ms | 7.99 ms | 17.16 ms | 22.49 ms | 29.97 ms | 5.8 µs | 1.45 s |
| **p182** | 203.40 ms | 202.46 ms | 200.60 ms | 202.36 ms | 278.88 ms | 206.15 ms | 233.53 ms | 209.03 ms | 478.53 ms | 421.37 ms |
| **p183** | 936.0 µs | 735.8 µs | 1.02 ms | 714.2 µs | 828.7 µs | 867.2 µs | 1.44 ms | 1.97 ms | 1.39 ms | 4.12 ms |
| **p184** | 2.83 ms | 3.61 ms | 3.36 ms | 2.03 ms | 2.52 ms | 5.85 ms | 6.29 ms | 13.92 ms | 12.33 ms | 56.41 ms |
| **p185** | 94.79 ms | 219.9 µs | 159.25 ms | 426.6 µs | 47.87 ms | 25.32 ms | 1.39 s | 572.82 ms | 154.80 ms | 967.15 ms |
| **p186** | 32.91 ms | 39.25 ms | 39.51 ms | 46.57 ms | 44.76 ms | 76.42 ms | 51.78 ms | 68.69 ms | 137.74 ms | 1.71 s |
| **p187** | 397.35 ms | 431.12 ms | 390.52 ms | 353.55 ms | 366.35 ms | 398.51 ms | 448.70 ms | 464.09 ms | 514.60 ms | 8.23 s |
| **p188** | 6.0 µs | 2.8 µs | 3.4 µs | 3.4 µs | 3.2 µs | 22.2 µs | 169.0 µs | 17.1 µs | 72.8 µs | 33.6 µs |
| **p189** | 116.94 ms | 133.45 ms | 130.56 ms | 147.60 ms | 170.35 ms | 313.10 ms | 435.33 ms | 335.28 ms | 609.88 ms | 17.83 s |
| **p190** | 2.0 µs | 1.3 µs | 1.3 µs | 1.1 µs | 1.3 µs | 4.0 µs | 86.2 µs | 20.2 µs | 29.4 µs | 28.2 µs |
| **p191** | 1.0 µs | 792 ns | 666 ns | 833 ns | 792 ns | 2.5 µs | 496.6 µs | 19.8 µs | 67.6 µs | 44.6 µs |
| **p192** | 19.04 ms | 18.85 ms | 18.61 ms | 18.83 ms | 29.24 ms | 48.78 ms | 54.80 ms | 68.30 ms | 68.69 ms | 425.42 ms |
| **p193** | 309.78 ms | 251.43 ms | 262.41 ms | 306.14 ms | 255.11 ms | 358.61 ms | 321.62 ms | 324.36 ms | 1.21 s | 8.34 s |
| **p194** | 4.0 µs | 1.8 µs | 2.3 µs | 2.3 µs | 4.7 µs | 3.7 µs | 323.8 µs | 46.2 µs | 204.3 µs | 6.3 µs |
| **p195** | 233.82 ms | 229.28 ms | 226.20 ms | 224.39 ms | 313.32 ms | 231.73 ms | 244.36 ms | 237.90 ms | 279.37 ms | 1.07 s |
| **p196** | 151.93 ms | 137.90 ms | 337.22 ms | 138.70 ms | 140.27 ms | 159.54 ms | 203.78 ms | 210.87 ms | 291.55 ms | 1.47 s |
| **p197** | 29.0 µs | 22.0 µs | 18.2 µs | 22.5 µs | 41.5 µs | 77.4 µs | 104.4 µs | 295.8 µs | 128.2 µs | 96.6 µs |
| **p198** | 131.20 ms | 136.01 ms | 113.03 ms | 121.75 ms | 418.20 ms | 311.53 ms | 467.51 ms | 608.24 ms | 786.18 ms | 11.76 s |
| **p199** | 2.05 ms | 694.6 µs | 743.6 µs | 593.3 µs | 649.2 µs | 1.63 ms | 1.85 ms | 1.41 ms | 3.42 ms | 27.38 ms |
| **p200** | 76.67 ms | 10.53 ms | 11.19 ms | 10.12 ms | 10.04 ms | 10.23 ms | 50.04 ms | 52.36 ms | 42.71 ms | 162.67 ms |

### Problems 201–300 — Deep Coverage (4 langs)

| Problem | C++ | Zig | Go | Python |
|---------|----:|----:|----:|----:|
| **p201** | 658.36 ms | — | — | — |
| **p202** | 4.7 µs | — | — | — |
| **p203** | 133.0 µs | — | — | — |
| **p204** | 14.26 ms | — | — | — |
| **p205** | 4.3 µs | — | — | — |
| **p206** | 50.69 ms | — | — | — |
| **p207** | 416.2 µs | — | — | — |
| **p208** | 11.99 ms | — | — | — |
| **p209** | 1.8 µs | — | — | — |
| **p210** | 464.57 ms | — | — | — |
| **p211** | 3.78 s | — | — | — |
| **p212** | 6.03 s | — | — | — |
| **p213** | — | — | — | — |
| **p214** | 533.59 ms | — | — | — |
| **p215** | 5.43 ms | — | — | — |
| **p216** | 4.76 s | — | — | — |
| **p217** | 1.32 ms | — | — | — |
| **p218** | 616.52 ms | — | — | — |
| **p219** | 2.6 µs | — | — | — |
| **p220** | 1.6 µs | — | — | — |
| **p221** | 20.94 ms | — | — | — |
| **p222** | 20.0 µs | — | — | — |
| **p223** | 5.53 s | — | — | — |
| **p224** | 2.07 s | — | — | — |
| **p225** | 15.87 ms | — | — | — |
| **p226** | 497.15 ms | — | — | — |
| **p227** | — | — | — | — |
| **p228** | 13.2 µs | — | — | — |
| **p229** | 4.62 s | — | — | — |
| **p230** | 4.7 µs | — | — | — |
| **p231** | 49.37 ms | — | — | — |
| **p232** | 303.3 µs | — | — | — |
| **p233** | 28.74 ms | — | — | — |
| **p234** | 3.22 ms | — | — | — |
| **p235** | 11.5 µs | — | — | — |
| **p236** | — | — | — | — |
| **p237** | 39.3 µs | — | — | — |
| **p238** | — | — | — | — |
| **p239** | 583 ns | — | — | — |
| **p240** | 50.5 µs | — | — | — |
| **p241** | — | — | — | — |
| **p242** | 1.5 µs | — | — | — |
| **p243** | 1.9 µs | — | — | — |
| **p244** | 16.30 ms | — | — | — |
| **p245** | 1.03 s | — | — | — |
| **p246** | 1.80 s | — | — | — |
| **p247** | 137.25 ms | — | — | — |
| **p248** | 747.81 ms | — | — | — |
| **p249** | 1.11 s | — | — | — |
| **p250** | 105.56 ms | — | — | — |
| **p251** | — | — | — | — |
| **p252** | — | — | — | — |
| **p253** | — | — | — | — |
| **p254** | — | — | — | — |
| **p255** | — | — | — | — |
| **p256** | — | — | — | — |
| **p257** | — | — | — | — |
| **p258** | — | — | — | — |
| **p259** | — | — | — | — |
| **p260** | — | — | — | — |
| **p261** | — | — | — | — |
| **p262** | — | — | — | — |
| **p263** | — | — | — | — |
| **p264** | — | — | — | — |
| **p265** | — | — | — | — |
| **p266** | — | — | — | — |
| **p267** | — | — | — | — |
| **p268** | — | — | — | — |
| **p269** | — | — | — | — |
| **p270** | — | — | — | — |
| **p271** | — | — | — | — |
| **p272** | — | — | — | — |
| **p273** | — | — | — | — |
| **p274** | — | — | — | — |
| **p275** | — | — | — | — |
| **p276** | — | — | — | — |
| **p277** | — | — | — | — |
| **p278** | — | — | — | — |
| **p279** | — | — | — | — |
| **p280** | — | — | — | — |
| **p281** | — | — | — | — |
| **p282** | — | — | — | — |
| **p283** | — | — | — | — |
| **p284** | — | — | — | — |
| **p285** | — | — | — | — |
| **p286** | — | — | — | — |
| **p287** | — | — | — | — |
| **p288** | — | — | — | — |
| **p289** | — | — | — | — |
| **p290** | — | — | — | — |
| **p291** | — | — | — | — |
| **p292** | — | — | — | — |
| **p293** | — | — | — | — |
| **p294** | — | — | — | — |
| **p295** | — | — | — | — |
| **p296** | — | — | — | — |
| **p297** | — | — | — | — |
| **p298** | — | — | — | — |
| **p299** | — | — | — | — |
| **p300** | — | — | — | — |

> \* — *partial measurement*: cell was bench'd with fewer than the suite-standard 10 iterations (typically 1 or 3, for heavy problems where iters=10 would exceed the per-chunk wall budget). The median is still meaningful for >1s problems, but the variance estimate is degraded. These cells are queued for a future uniform-iters=10 re-bench pass.

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

> Of the 300 problems benchmarked, **roughly 20-25% of cells** are fully
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
cmd/euler-bench/euler-bench per-iter --lang all --problems 1-300 --iters 10 --write
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

