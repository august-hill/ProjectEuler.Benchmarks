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

At write time, three corroboration checks run:

1. **Untimed-work check**: `wall − time` must not exceed a per-language
   startup allowance (native ≈ 250 ms; VM/JIT runtimes ≈ 750 ms;
   Python ≈ 2 s). A large excess means significant computation executed
   outside the timed region; the row is recorded as a **failure**, not a
   flattering near-zero time. Honest rows sit orders of magnitude below the
   allowance (measured baselines: 7–110 ms for compiled/managed languages,
   ~400 ms for Python including `numpy` import).
2. **Concurrency check**: for serial-class problems, `cpu / time` must stay
   near 1 (threshold 1.3). A ratio well above 1 means the solution ran in
   parallel; the row fails. Parallel-class problems (§5) are exempt and are
   instead expected to exceed it.
3. **Compile-time-folding check**: a near-zero runtime on a non-trivial
   problem in an ahead-of-time language flags the row for review — work can
   also hide in compile-time evaluation, which no runtime observable can see.

These checks are structural, not advisory: a row that breaks the contract
cannot silently enter the dataset.

## 3. Sampling: run 2, corroborate, tie-break to at most 3

Every solution here is deterministic and (in serial-class) single-threaded:
there is one true cost, and timing noise is strictly additive. The sampling
rule:

1. Run **2** fresh-process samples. If they agree within **5%**, accept the
   median (their midpoint) and stop.
2. Otherwise run a **third** and take the median of 3.
3. If no two of the three agree within 5%, the median is still recorded but
   the row carries a **no-corroboration warning** — on a deterministic
   program, three mutually inconsistent samples indicate a broken measurement
   environment (load, thermal), which is fixed by investigating and
   re-benching, not by sampling further.

**Why so few samples?** This matches practice for whole-program benchmarks:
SPEC CPU's reportable standard is 3 runs / median; Phoronix runs 3 with
bounded variance escalation. Large sample counts (10+) belong to
micro-benchmarking, where individual samples are nearly free and per-sample
noise is proportionally large. On this suite's quiet reference machine,
repeat samples of multi-second programs agree to a fraction of a percent —
extra confirmations refine a digit that no cross-language comparison reads.
Every row records its actual sample count (`samples`), its minimum, and its
maximum; heterogeneous sample counts are by design.

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
