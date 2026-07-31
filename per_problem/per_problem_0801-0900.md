# Per-Problem Detail — Problems 0801–0900 (Frontier, 3 langs)

⬅ [Back to RESULTS](../RESULTS.md)

Minimum internal time per fresh-process invocation (magnitude-adaptive
samples, METHODOLOGY.md §3), one row per problem, one column per language
in tier-1 display order (native → managed → interpreted).

| Problem | C++ | Rust | Go |
|---------|----:|----:|----:|
| **p0801** | — | — | — |
| **p0802** | — | — | — |
| **p0803** | — | — | — |
| **p0804** | 225.33 ms | — | 192.56 ms |
| **p0805** | — | — | — |
| **p0806** | — | — | — |
| **p0807** | — | — | — |
| **p0808** | ✗ fail | — | — |
| **p0809** | — | — | — |
| **p0810** | 9.57 s | — | 8.93 s |
| **p0811** | — | — | — |
| **p0812** | — | — | — |
| **p0813** | 217.2 µs | 94.4 µs | 94.0 µs |
| **p0814** | — | — | — |
| **p0815** | — | — | — |
| **p0816** | 141.06 ms | — | — |
| **p0817** | 15.86 ms | 29.25 ms | 27.02 ms |
| **p0818** | — | — | — |
| **p0819** | — | — | — |
| **p0820** | 867.81 ms | — | — |
| **p0821** | — | — | — |
| **p0822** | 471.61 ms | — | — |
| **p0823** | — | — | — |
| **p0824** | — | — | — |
| **p0825** | — | — | — |
| **p0826** | — | — | — |
| **p0827** | — | — | — |
| **p0828** | 357.42 ms | — | — |
| **p0829** | — | — | — |
| **p0830** | — | — | — |
| **p0831** | — | — | — |
| **p0832** | 60.9 µs | 48.1 µs | 42.2 µs |
| **p0833** | — | — | — |
| **p0834** | 113.55 ms | — | 168.93 ms |
| **p0835** | 4.0 µs | 3.1 µs | 11.0 µs~ |
| **p0836** | <1 µs~ | — | — |
| **p0837** | — | — | — |
| **p0838** | — | 229.17 ms | — |
| **p0839** | 124.46 ms | 111.08 ms | 120.46 ms |
| **p0840** | 866.25 ms | 1.39 s | 1.17 s |
| **p0841** | — | — | — |
| **p0842** | — | — | — |
| **p0843** | — | — | — |
| **p0844** | — | — | — |
| **p0845** | 490.2 µs | — | — |
| **p0846** | — | — | — |
| **p0847** | — | — | — |
| **p0848** | — | — | — |
| **p0849** | — | — | — |
| **p0850** | — | — | — |
| **p0851** | — | — | — |
| **p0852** | — | — | — |
| **p0853** | 45.6 µs | — | — |
| **p0854** | — | — | — |
| **p0855** | — | — | — |
| **p0856** | — | 2.33 ms | — |
| **p0857** | — | — | — |
| **p0858** | — | — | — |
| **p0859** | — | — | — |
| **p0860** | 128.91 ms | — | — |
| **p0861** | — | — | — |
| **p0862** | 1.43 ms | — | — |
| **p0863** | — | — | — |
| **p0864** | — | — | — |
| **p0865** | — | — | — |
| **p0866** | 5.1 µs | — | — |
| **p0867** | — | — | — |
| **p0868** | 1.7 µs | — | 5.8 µs~ |
| **p0869** | — | 381.19 ms | — |
| **p0870** | — | — | — |
| **p0871** | — | — | — |
| **p0872** | <1 µs~ | — | — |
| **p0873** | 4.91 s | 2.14 s | 2.33 s |
| **p0874** | — | — | — |
| **p0875** | — | — | — |
| **p0876** | — | — | — |
| **p0877** | <1 µs | — | 1.1 µs~ |
| **p0878** | — | — | — |
| **p0879** | 24.73 ms | — | 32.63 ms |
| **p0880** | — | — | — |
| **p0881** | 1.26 ms | — | — |
| **p0882** | — | — | — |
| **p0883** | — | — | — |
| **p0884** | 21.59 s | 9.10 s | 21.23 s |
| **p0885** | 65.72 ms | — | — |
| **p0886** | — | — | — |
| **p0887** | 24.5 µs | 26.6 µs | 22.7 µs |
| **p0888** | — | — | — |
| **p0889** | — | — | — |
| **p0890** | — | — | — |
| **p0891** | — | — | — |
| **p0892** | — | — | — |
| **p0893** | 9.18 s | 11.41 s | 11.46 s |
| **p0894** | — | — | — |
| **p0895** | — | — | — |
| **p0896** | — | — | — |
| **p0897** | — | — | — |
| **p0898** | — | — | — |
| **p0899** | 1.0 µs | — | — |
| **p0900** | — | — | — |

> ✗ — *process-contract failure* (METHODOLOGY.md §2): the row is recorded as a failure with its reason class (untimed-work / parallel-execution) — there is no path by which a contract-breaking measurement appears as a fast time.

> ~ — *wide spread*: observed samples span more than 3× the reported figure. Since noise here is one-sided and the reported figure is the MINIMUM, a wide spread does not make the number too high — it means the machine was disturbed at some point while that cell was sampled. The threshold is calibrated to the sampling schedule, because observing more samples mechanically widens min..max (METHODOLOGY.md §3b).

⬅ [Back to RESULTS](../RESULTS.md)
