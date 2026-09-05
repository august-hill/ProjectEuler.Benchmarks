# Methodology

This document specifies how every number in this repository is produced, and
defends the non-obvious choices. It is the normative reference: where older
narrative (README, JOURNEY.md) disagrees, this document wins.

## 1. The metric: per-invocation cost

Each measurement answers one question: **how long does one fresh invocation of
this solution take to produce the answer?**

- One OS process = one `solve()` call = one sample. No warm-up, no in-process
  repetition. The process boundary is the isolation guarantee: nothing can be
  cached, JIT-warmed, or amortized across samples.
- The reported time is the solution's *internal* timer (started immediately
  before `solve()`, stopped immediately after), so interpreter/runtime startup
  is excluded from the headline number. Startup is visible separately via the
  recorded subprocess wall time.
- Compile time is measured and published separately (`compile_time_ns`); it is
  never mixed into runtime.

**Why not warm iterations?** A tight-loop "average of 1000 runs" metric
rewards moving work out of the measured region (caches, lazy statics,
memoization) and measures a steady state no user of a one-shot program ever
experiences. The per-invocation metric is what a person running the program
once actually pays.

## 2. The process contract, and how it is enforced

The metric relies on a contract: **all work happens between timer-start and
timer-stop, on one thread** (unless the problem is parallel-class, §5). History
shows source review alone does not enforce this — work can hide in module
scope, static initializers, global constructors, or the compiler itself.

So the harness verifies the contract from *process observables* rather than
source patterns. For every sample it records, alongside the internal time:

- **subprocess wall time** (spawn → exit),
- **CPU time** (user + system, from `rusage`),
- **1-minute system load average** at sample start.

At write time, the contract is enforced from these observables:

1. **Untimed-work / concurrency check (CPU-based, load-robust)**: for
   serial-class problems, `cpu` must not exceed `time × 1.3 + startup-allowance`
   (native ≈ 250 ms; VM/JIT ≈ 750 ms; Python ≈ 2 s for `numpy` import). Real
   work outside the timed region — module scope, static initializers, global
   constructors — or undeclared parallelism *burns CPU*, so `cpu` rises above
   the ceiling and the row is recorded as a **failure**, not a flattering
   near-zero time. This check is **invariant to machine load**: CPU cycles are
   the same whether the box is idle or busy. It replaced a wall-based check
   (`wall − time > allowance`) that conflated untimed work with process-spawn
   and scheduling latency, and so flipped its verdict with system load —
   identical clean source (cpp p593) failed at load 5 and passed at load 1.5.
   Parallel-class problems (§5) legitimately run `cpu ≫ time` and are exempt.
2. **Wall-suspect flag (advisory, never fatal)**: `wall − time` exceeding the
   startup allowance is recorded as a non-fatal `wall-suspect` flag. It is the
   only untimed-work signal available for parallel-class problems (which get a
   generous ≈ 2 s allowance before it trips) and an audit hint elsewhere — but
   it never fails a row on its own, precisely because wall excess is load-driven.
3. **Compile-time-folding check**: a near-zero runtime on a non-trivial
   problem in an ahead-of-time language flags the row for review — work can
   also hide in compile-time evaluation, which no runtime observable can see.

These checks are structural, not advisory: a row that breaks the contract
cannot silently enter the dataset.

## 3. Sampling: magnitude-adaptive count, minimum reported

Every solution here is deterministic and (in serial-class) single-threaded:
there is one true cost, and **timing noise is strictly additive** — every
disturbance (scheduler preemption, page faults, first-exec signature
validation, timer granularity, thermal drift) can only make a run *slower*,
never faster.

Two consequences follow, and both are load-bearing.

### 3a. The reported statistic is the MINIMUM, not the median

Under one-sided additive noise the minimum sample is the maximum-likelihood
estimate of the true cost. The median is the correct estimator only when
noise is *symmetric*, which it is not here. `time_ns` is therefore the
minimum observed sample; `time_min_ns` and `time_max_ns` retain the full
observed spread.

This matters because the noise floor is near-constant in *absolute* terms
(~0.15 ms of process and scheduler overhead). On a 1.5 ms cell that is 10%;
on a 32 ms cell it is 0.5%. Reporting medians therefore inflated cheap cells
far more than expensive ones, which systematically **compressed the gap
between fast and slow languages** — measured at −9 to −11% for the compiled
languages versus −2 to −4% for the managed ones when switching to minimum.
Language *ordering* is unaffected by the choice; only the ratios are.

### 3b. Sample count scales with magnitude, inversely to cost

Measured across 3670 passing rows, median within-row min..max spread by
magnitude:

| magnitude | rows | median spread | p90 spread |
|---|---:|---:|---:|
| < 10 µs | 422 | 54.6% | 544% |
| 10 µs – 1 ms | 700 | 35.8% | 223% |
| 1 – 10 ms | 643 | 22.1% | 70% |
| 10 – 100 ms | 664 | 16.6% | 65% |
| 0.1 – 1 s | 598 | 4.7% | 17% |
| 1 – 10 s | 507 | 1.8% | 7.8% |
| > 10 s | 136 | 0.7% | 4.5% |

Relative noise grows as programs get cheaper, while sampling *cost* moves the
opposite way. So the schedule is inverted relative to a uniform rule:

| observed cost | samples |
|---|---:|
| < 1 ms | 15 |
| 1 – 10 ms | 11 |
| 10 – 100 ms | 7 |
| 0.1 – 1 s | 4 |
| ≥ 1 s | 2 |

At least 2 samples always run; further samples are added until the cell
reaches its target, bounded by the `--iters` cap and a 90 s per-cell wall
budget. Over a full pass this is **~26 minutes cheaper** than the previous
uniform rule, because trimming the multi-second tail from 2.5 samples to 2
outweighs everything added at the cheap end. Every row records its actual
count (`samples`); heterogeneous counts are by design.

### Why this replaced the previous rule (changed 2026-07-25)

The prior rule ran 2 samples, accepted them if they agreed within 5%, and
tie-broke to at most 3. It was well calibrated for multi-second programs —
where the sub-percent agreement it assumed genuinely holds — and badly
miscalibrated below 10 ms. **Two draws from a long-tailed distribution can
agree with each other while both sit far from the true cost**, so pairwise
agreement was not evidence of convergence at the cheap end: 30–34% of sub-ms
cells failed to corroborate at all, and the ones that *did* corroborate were
not thereby trustworthy. A single problem was observed being "corroborated"
at 946 µs and at 2.055 ms in separate passes, on a true cost near 1.08 ms.

The 5% pairwise check is retained only as a **diagnostic**: a cell that never
produces an agreeing pair even at 15 samples indicates a disturbed
measurement environment, which is fixed by investigating (see §4), not by
sampling further.

### 3c. Measurement floor

A single fresh-process invocation cannot resolve costs below roughly 1 µs —
the platform timer granularity is 41.67 ns and scheduler jitter exceeds the
signal. Cells measuring under 1 µs are reported as `<1 µs` rather than as a
specific figure; the stored `time_ns` is retained for auditing but the
published number does not claim precision it does not have.

## 4. Environment

- All numbers come from **one fixed machine** (Apple Silicon, macOS), and are
  only ever compared against other numbers from the same machine. Nothing
  here claims portability; the comparison is between languages, with hardware
  held constant.
- **Benchmark passes run solo**: no builds, agents, or other workloads
  concurrent with measurement. This is enforced by process discipline and
  audited by the recorded load average — correlated load is the one error
  source that sample corroboration cannot detect (two equally-slowed samples
  agree with each other), so it must be prevented upstream and made visible
  in the data.
- **Toolchains are held fixed and recorded.** Every run stores the exact
  compiler/runtime version string (`runs.compiler`, `run_history.compiler`),
  and RESULTS.md renders the per-language toolchain table from it. A compiler
  or runtime upgrade is a **re-bench event**, not a rolling change: bump the
  toolchains together at a chosen cadence (quarterly is the working rhythm —
  Rust ships every six weeks, chasing each release would mean a re-bench every
  six weeks), then re-measure every affected language column in full before
  the new numbers are compared with anything. If the `runs` table ever holds
  more than one toolchain for a language, the report flags that column as
  mixed and its ranking is provisional until the column is re-benched.

## 5. Concurrency policy: serial-class by default, symmetric parallel-class

The suite's implementation constitution is: **each solution should look like
what a competent, ordinary developer of that language would naturally
write.** That constitution collides with concurrency. In some languages the
natural solution to a large partitionable computation is parallel (a Go
developer reaches for goroutines in ten lines; a Rust developer swaps
`iter()` for `par_iter()`); in others the same step costs dozens of lines of
ceremony and a normal developer would not bother for a one-shot program. If
each language simply does what is "natural," the timing table silently
compares an 8-core implementation in one language against 1-core
implementations in the others — that gap measures implementer effort, not
the language.

The resolution is a **per-problem class**, recorded in `data/parallel.json`:

- **Serial-class (default)**: every language must be single-threaded. The
  harness enforces this via the CPU-time check (§2). Cross-language ratios
  on these problems compare languages on identical hardware exposure.
- **Parallel-class**: problems whose serial cost is large (guideline: > ~5 s)
  and whose work is naturally partitionable. For these, **every language in
  the problem's tier must field its idiomatic parallel implementation** — a
  problem enters the class for all languages at once or not at all.
  Asymmetric parallelism, where one language parallelizes and its comparators
  do not, is the one configuration that is never published.

What this preserves:

- **Comparability** — within any problem, all languages answered the same
  question on the same hardware.
- **The ergonomics signal** — how *easily* a language parallelizes is real
  and valuable information. It shows up honestly: in the published source
  sizes (ten lines of goroutines versus a page of thread plumbing), and in
  how close each runtime gets to ideal scaling on the same cores — rather
  than dishonestly, as an unlabeled wall-time advantage.
- **The foundation surface** — tier 1 (all ten languages, problems 1–200)
  stays entirely serial-class: several tier-1 languages (assembly, C without
  threads-by-convention) have no "natural" parallel idiom, and the 10-way
  comparison is the suite's most-cited artifact.

## 6. Rankings: geometric mean over the common set

Per tier, the headline ranking is the **geometric mean of per-problem times
over the tier's common set** — the problems every tier language passes —
with individual cells floored at 100 µs. The total (sum) over the same set
is published alongside as a secondary column.

**Why geomean over sum?** The sum is dominated by a handful of slow
problems: in tier 1, five problems carry ~60% of the leader's total, so a
sum-ranked table is mostly a contest on those five — which are precisely
where per-language algorithm divergence (not language speed) is largest. The
geometric mean weights every problem's *ratio* equally and answers "how fast
is this language on the typical problem." The sum remains meaningful ("run
the whole set back-to-back") and is kept, but it no longer decides ranks.

**Why the common set, when it shrinks the data?** Because it is
strategy-proof. Any scheme that scores languages on whichever problems they
happen to have solutions for rewards omitting one's worst problems — and
this suite *deliberately* omits some language/problem pairs on policy
grounds (a solution must reach the reference's full scale or be omitted).
Restricting rankings to the intersection makes selective coverage unable to
move a rank in either direction. Coverage itself is reported separately and
honestly (the coverage grid, including its gaps).

**Why the 100 µs floor?** Below that scale, per-problem ratios measure timer
granularity and fixed overheads, not computation; the floor keeps trivia
from swinging a geometric mean.

## 7. Failure honesty

- A row that breaks the process contract is recorded as a failure with its
  reason, and renders as a failure in every chart. There is no path by which
  a contract-breaking measurement appears as a fast time.
- Partial measurements (fewer samples than the standard) are marked in every
  table and chart (`*`).
- The dataset keeps append-only history (`run_history`) alongside the
  current-best table, so any published number can be traced to its samples,
  their spread, and the load conditions under which they were taken.
