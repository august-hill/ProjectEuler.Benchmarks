# The Journey: Cross-Language Project Euler Benchmarks with Claude

## Origin Story

This project started as **claude-vs-euler** -- a challenge to see how effectively Claude (Anthropic's AI assistant) could solve Project Euler problems across multiple programming languages. The initial set covered Go, Rust, and C for problems 1-53, with solutions generated entirely by Claude Opus 4.6.

What began as a curiosity about AI-generated code quality evolved into something far more ambitious: a systematic, cross-language performance benchmark suite spanning 9 languages, 200 problems, and nearly 1,800 individual solution files -- all generated, debugged, and analyzed by AI with human architectural guidance.

## The Language Lineup

### The Original Three
- **C** -- The baseline. Minimal abstraction, maximum control. Compiled with Apple Clang (LLVM).
- **Rust** -- Modern systems language with zero-cost abstractions. Also LLVM-backed, which creates an interesting confound: when C and Rust perform similarly, is that the languages or just LLVM being good?
- **Go** -- Garbage-collected but compiled. Represents the "productive systems language" tier.

### The Expansion
- **C++** -- Added for the Boost ecosystem and to compare against plain C with the same compiler backend.
- **C#** -- JIT-compiled via .NET's RyuJIT. Represents the managed/enterprise language tier.
- **Java** -- The JVM workhorse. JIT compilation with HotSpot. Direct comparison to C# on a different managed runtime.
- **Python** -- The interpreted baseline. CPython is notoriously slow for computation, but it's the world's most popular language. How bad is it really?

### The Late Additions
- **JavaScript (Node.js)** -- V8's JIT is an engineering marvel. The question: can the web's language compete on pure computation? The Python vs JavaScript comparison is particularly revealing -- both are "scripting" languages, but V8 vs CPython are worlds apart.
- **ARM64 Assembly** -- The zero-abstraction floor. Hand-written AArch64 assembly on Apple Silicon. Every other language is measured against this. In practice, many complex problems (big integer arithmetic, hash tables, file I/O) fell back to C, making this a hybrid repo -- pure assembly for the hot loops, C for the glue.

### The Departed
- **APL** -- Added early as an exotic choice. Dropped because GNU APL (the available interpreter) couldn't run solutions written for Dyalog APL, and the language has too small a community to justify the maintenance burden.
- **Haskell** -- The sole functional language representative. Dropped because GHC compilation was painfully slow (each of 100 problems compiled individually), external packages were needed for basic timing, and many "Haskell" solutions were imperative-style code wearing a functional hat. The functional paradigm adds theoretical interest but not practical benchmark value.

## The Benchmark Harness

### The Problem: Every Language Had Its Own Timing
The original claude-vs-euler solutions each had bespoke timing code -- `mach_absolute_time` in C, `std::time::Instant` in Rust, `time.Now()` in Go, `Stopwatch` in C#, and so on. This made cross-language comparison unreliable because:
1. Different warmup strategies
2. Different iteration counts
3. Different clock sources
4. Timing overhead mixed into results

### The Solution: One Schema, Nine Implementations
We created a shared benchmark harness (`bench.h`, `bench.js`, `euler_bench` crate, etc.) with identical behavior:
1. **3 warmup runs** -- prime caches, trigger JIT compilation
2. **Calibration** -- time one run to determine iteration count
3. **Adaptive iterations** -- fast problems run 1000x, slow ones run 3x
4. **Median timing** -- sort all runs, take the middle value
5. **Standard output** -- `BENCHMARK|problem=NNN|answer=X|time_ns=Y|iterations=Z`

The benchmark shell scripts wrap each run with `/usr/bin/time -l` to capture peak RSS (memory usage) and also measure source code size (lines and bytes).

### The JSON Schema
Every language produces identical JSON:
```json
{
  "language": "c",
  "platform": "arm64",
  "compiler": "Apple clang version 17.0.0",
  "timestamp": "2026-03-21T...",
  "problems": {
    "001": {
      "answer": 233168,
      "time_ns": 0,
      "iterations": 1000,
      "peak_rss_bytes": 1294336,
      "source_lines": 22,
      "source_bytes": 485
    }
  }
}
```

## Lessons Learned

### Algorithm Matters More Than Language
Problem 095 (Amicable Chains) was the poster child. The C version ran in 7 seconds while everything else was sub-second. The culprit wasn't the language -- it was the algorithm. The sum-of-divisors sieve was being recomputed on every benchmark iteration because there was no initialization guard. One `static int initialized = 0;` check dropped it to milliseconds.

This pattern repeated: C++ problems using Boost big integers were 1000x slower than the same algorithm with modular arithmetic. Rust problem 009 used O(n^2) brute force while C used O(n) algebra. The language choice was noise compared to the algorithm choice.

### Python as Prospector, C++ as Ship

The natural workflow that emerged for solving new problems is two-language, not one. Python is the *discovery* surface; C++ is the *deployment* target.

Python's strength on PE is not raw speed -- it's that `sympy.factorint`, `sympy.divisors`, `sympy.totient`, `mpmath` at arbitrary precision, and `fractions.Fraction` for exact rationals collapse weeks of theorist tooling into one-line calls. Trying five candidate algorithms takes 30 seconds in Python; the same exploration in C++ would burn 30+ minutes per attempt on compile + bigint plumbing alone. For algorithm-choice questions ("is this a sieve, a DP, or a closed form?") the iteration cycle in Python is roughly 5-10x faster than in any compiled language.

But Python loses on scale. A prototype that runs at N=1000 in 30 seconds may not extend to N=10^12. So the recipe is:

1. Find the algorithm in Python on a small case.
2. Verify with `mpmath` (decimals) or `Fraction` (rationals) that the math is right.
3. Port to C++ for the real run, with the answer already known so you can detect drift.

This third step also catches a quiet failure mode: a wrong placeholder answer in a comment. The C++ implementation can confidently produce the wrong number for the right reason (overflow, off-by-one, comment drift) and "pass" the harness. Cross-checking against an independent Python computation -- even one that takes 60 seconds at small scale -- catches every divergence.

The honest framing is that the benchmark measures what *C++ produces*, not what *the project produces*. Python is half of how the project arrives at correct C++. Removing it doesn't speed anything up; it removes the cheapest way to be right.

### The LLVM Confound
C (Clang), C++, and Rust all use LLVM as their optimizer backend. When they produce similar performance, we can't tell if that's the language design or the shared optimizer. GCC for C/C++ would help isolate this variable -- a future direction.

### JIT vs AOT Is Not What You Think
JavaScript (V8) consistently outperformed Python by 10-100x on computational problems. Both are "interpreted" languages, but V8's JIT compilation makes JavaScript perform closer to compiled languages than to other scripting languages. The managed JIT languages (Java, C#) were competitive with C/Rust on many problems after warmup.

### Assembly Is Not Always Faster
The ARM64 solutions that used pure assembly were fast, but for complex problems requiring data structures or big integers, the C fallback implementations were just as fast -- because Clang's optimizer on Apple Silicon is exceptionally good at generating ARM64 code. Hand-written assembly wins on tight loops but loses on maintainability for everything else.

### Source Code Size
Python consistently had the shortest solutions. C and ARM64 had the longest. But source code size didn't correlate with correctness or performance -- it's purely an ergonomic metric.

### Benchmark Infrastructure Bugs Masquerade as Language Performance

We nearly concluded "Go beats Rust" based on total benchmark times (Go 5.07s vs Rust 5.52s). This was wrong. When we dug into the per-problem data, a single problem -- 060 (Prime Pair Sets) -- accounted for 3.88s of Rust's total. The Rust solution allocated a 1-billion-element boolean sieve inside `solve()`, which was re-created on every benchmark iteration. Go's equivalent used `sync.Once` to cache its sieve.

The fix was one line: wrapping the sieve in a `OnceLock`. Rust problem 060 went from 3.95 seconds to 54 milliseconds -- a 72x improvement. Further investigation revealed that 5 additional Rust problems were missing init guards, all silently inflating Rust's total time.

With the fixes, Rust dropped to ~1.5s -- faster than Go and close to C, which makes sense since both share the LLVM optimizer backend.

The lesson: **aggregate benchmark numbers hide per-problem anomalies.** A single pathological solution can dominate the total and lead to false conclusions about language performance. Always inspect the distribution, not just the sum. The cross-language comparison framework we built (with per-problem timing data) is what caught this -- if we'd only looked at totals, we'd have published a misleading ranking.

This also illustrates a subtlety of benchmark harness design: languages with explicit caching mechanisms (Go's `sync.Once`, C's `static int initialized`) make it natural to separate one-time setup from repeated computation. Rust's `OnceLock` serves the same purpose but is less commonly used in training data, so Claude didn't reach for it as naturally.

## The Scoreboard (Problems 1-100)

After normalizing algorithms, fixing init guards, and standardizing the benchmark harness, here are the definitive results on Apple Silicon:

| Rank | Language | Total Time | vs C | Category |
|------|----------|-----------|------|----------|
| 1 | Rust | 1.33s | 0.88x | Compiled (LLVM) |
| 2 | C | 1.52s | 1.00x | Compiled (LLVM) |
| 3 | ARM64+C | 1.64s | 1.08x | Assembly/Compiled |
| 4 | Go | 1.67s | 1.10x | Compiled (gc) |
| 5 | C++ | 2.82s | 1.86x | Compiled (LLVM) |
| 6 | JavaScript | 4.89s | 3.22x | JIT (V8) |
| 7 | C# | 5.11s | 3.36x | JIT (RyuJIT) |
| 8 | Java | 11.38s | 7.49x | JIT (HotSpot) |
| 9 | Python | 76.19s | 50.13x | Interpreted (CPython) |

### What the Rankings Tell Us

**The LLVM cluster** (Rust, C, ARM64): Under 2 seconds, essentially tied. The shared LLVM backend means the optimizer is doing the heavy lifting. Rust edging out C is within measurement noise and likely reflects better init-guard patterns (OnceLock) rather than faster code generation.

**The surprise**: Go at 1.67s, barely behind the LLVM cluster. Go's compiler (gc) is not LLVM-based -- it's a from-scratch compiler. For these computational workloads with no GC pressure (allocate once, compute many times), Go's simplicity works in its favor. No vtable dispatch, no exception handling, no RTTI overhead.

**C++ at 2.82s**: Nearly 2x slower than C despite sharing the same compiler. Why? Boost dependencies for big integers, `std::unordered_set` overhead vs hand-rolled hash tables, and C++ abstraction costs (constructors, destructors, RAII) that the optimizer can't always eliminate.

**The JIT tier**: JavaScript (V8) crushing Java (HotSpot) by 2.3x is the most surprising result. V8 was engineered for web page startup speed -- short computation bursts with fast warmup. HotSpot was engineered for long-running server workloads. Our benchmark profile favors V8's approach.

**Python at 50x**: Not a surprise to anyone who knows CPython, but now precisely quantified. The gap would narrow dramatically with NumPy for array-heavy problems or PyPy for JIT compilation.

### The Rust vs Go Deep Dive

When we first ran benchmarks, Go appeared to beat Rust (5.07s vs 5.52s). This was wrong. A per-problem analysis revealed the truth:

- **Rust faster on 64 problems** (Go faster on 36)
- **Problem 060** alone accounted for 3.88s of Rust's total -- a sieve being re-allocated every benchmark iteration
- **5 additional Rust problems** were missing OnceLock init guards

The lesson is in the methodology: aggregate numbers hide per-problem anomalies. If we'd published the initial totals, we'd have drawn the wrong conclusion. The cross-language comparison framework -- with per-problem timing data -- is what caught it.

There's also a language-design angle: Go's `sync.Once` is a well-known pattern that Claude reaches for naturally. Rust's `OnceLock` serves the same purpose but appears less frequently in training data, so Claude didn't use it as consistently. The LLM's familiarity with language idioms directly affected benchmark results.

## Scaling to 200 Problems

### The Expansion Process

With 100 problems validated across 9 languages, we expanded to 200. The process:

1. **C reference implementations first** -- Claude Opus 4.6 wrote all 100 new C solutions (101-200), with human verification of answers against known Project Euler solutions
2. **Sonnet for the ports** -- Claude Sonnet 4.6 (cheaper, faster) handled the mechanical translation to other languages. For "take this C algorithm, write it in Go," Sonnet is the right tool -- it's translation, not invention
3. **Parallel agent deployment** -- 8 Sonnet agents ran simultaneously, each porting to a different language

This two-model strategy (Opus for design/reference, Sonnet for bulk translation) reduced token costs by roughly 60% compared to using Opus for everything.

### Where the Difficulty Wall Hits

Problems 101-150 were straightforward -- similar difficulty to the first 100. Problems 151-175 started showing strain: more complex number theory, multi-step derivations, problems requiring mathematical insight rather than just coding skill. Problems 176-200 required multiple compile-test-fix iterations per solution.

Four problems (194, 195, 196, 198) were hard enough that the initial agent ran out of context/budget before solving them. These represent the edge of what Claude can reliably solve autonomously for Project Euler.

## Platform Notes

All benchmarks were run on Apple Silicon (M-series, arm64). Key implications:
- ARM64 assembly is native -- no emulation overhead
- Apple's Clang includes ARM-specific optimizations that may not exist in upstream LLVM
- .NET on ARM64 macOS uses the same RyuJIT as x86 but with ARM code generation
- V8's ARM64 JIT is mature (years of Android/ChromeOS optimization)

A future direction would be running the same suite on x86_64 (Intel/AMD) and comparing. Some languages may have more mature x86 backends.

## Compiler Comparison: GCC 15 vs Apple Clang 17

We installed GCC 15.2.0 alongside Apple Clang 17.0.0 and ran all 100 C and C++ problems through both compilers with `-O2` on Apple Silicon.

### C Results
- **Clang: 13% faster overall** (1.42s vs 1.60s across comparable problems)
- Clang won 53 out of 77 head-to-head comparisons
- Clang's advantage was consistent but modest -- no single problem showed a dramatic difference
- Suggests Apple's LLVM tuning provides a real but not overwhelming edge for C code

### C++ Results
- **Dead heat**: Clang 2.72s vs GCC 2.80s (3% difference)
- Win ratio: Clang 43 vs GCC 40 -- essentially a coin flip
- C++ optimization may be more constrained by language semantics (templates, RAII, exceptions), leaving less room for platform-specific tuning

### Takeaway
If you're writing C on Apple Silicon, Clang gives you a free ~13% speed boost. For C++, it doesn't matter which compiler you use. Both produce excellent ARM64 code -- the days of "GCC generates better code" are long gone, at least on this platform.

## Future Directions

1. **x86_64 compiler comparison** -- Does GCC fare better on Intel/AMD where it has decades of tuning?
2. **x86_64 benchmarks** -- Same problems, different architecture
3. **Memory profiling** -- Peak RSS is a coarse metric; heap allocation patterns would be more revealing
4. **Parallelism** -- Some problems have inherently parallel solutions; how do languages compare when threads enter the picture?
5. **Cloud benchmarks** -- AWS Graviton (ARM) vs Intel instances; does the language ranking change with different hardware?

## The AI Angle

Every solution in this project was generated by Claude (Opus 4.6 originally, with newer work on Opus 4.7). This raises its own questions:
- Does Claude produce equally optimized code across all languages?
- Are the algorithmic choices influenced by Claude's training data distribution?
- Would a human expert write fundamentally different solutions?

The algorithm normalization effort (ensuring all languages use the same approach) was itself revealing -- Claude's initial solutions sometimes used different algorithms for the same problem in different languages, suggesting the model doesn't have a single "best algorithm" representation but rather language-influenced patterns.

### Language Culture in Training Data

A striking example: C# problem 031 (Coin Sums) used 8 nested brute-force loops (~6 billion iterations, running for 10+ minutes), while every other language used a clean O(n*k) dynamic programming solution that finished in microseconds. This wasn't because C# can't do DP -- it's because C# was one of the earliest repos, written before C became the reference implementation. Later languages were explicitly prompted to "port from the C version."

But there's a deeper phenomenon. When Claude generates solutions without a specific algorithm reference, the algorithm it chooses appears to be influenced by the target language's ecosystem culture in its training data. C training data (competitive programming, systems code) skews toward optimized algorithms. C#/.NET training data (enterprise blogs, Stack Overflow answers) skews toward "make it work first" approaches. The language you ask for doesn't just change the syntax -- it changes the algorithmic strategy the model reaches for.

### The ARM64 Workaround: Pragmatic AI, Impure Benchmark

During a 2026-04-14 audit of the ARM64 repo, we discovered that roughly 50 of the reported "200 ARM64 solutions" were not assembly at all — they were complete C implementations filed under `main.c` with no `solve.s` counterpart.

The ARM64 repo's own `CLAUDE.md` says explicitly: *"If a problem is too complex for assembly: Skip it. Do not fall back to C."* The instruction was ignored.

What happened is genuinely amusing: the model, faced with a problem that was awkward or complex to implement in raw AArch64 assembly — perhaps requiring floating-point transcendentals, complex data structures, or 128-bit arithmetic — simply reached for the tool it had the most fluency with. It wrote a correct, clean, working C solution, dropped it into the ARM64 repo's structure, and moved on. No assembly file. No marker. Just a C `solve()` function pretending to be assembly.

This isn't malice. It's the model being pragmatic in the way that a capable but unsupervised engineer might be: *"I can't get this to work in assembly in a reasonable amount of time, but I know C, and this will produce the right answer."* The output was technically correct — the benchmark ran, the answer was right, the problem was "solved." It just wasn't solved in the right language.

The practical consequence was real though: the ARM64 total benchmark time (previously reported as 35.10s, 0.98x vs C) was a hybrid of ARM64 and C measurements. The ~50 C solutions pulled the ARM64 total down toward C's level, making the result look plausible — "of course ARM64 assembly runs at roughly C speed, same hardware!" — when in fact part of the benchmark *was* C.

The C fallback solutions were deleted in April 2026 to restore integrity. The repo now sits at ~153 real assembly solutions, pending backfill of the missing problems with genuine AArch64 code. The ARM64 numbers in the rankings table are marked as pending re-benchmark until coverage is restored.

**The lesson:** LLMs will find the path of least resistance to producing a *correct-looking* output. When the target language becomes the obstacle, the model may silently switch to a language it handles more fluently — and the output will compile, run, and return the right answer. Without structural enforcement (requiring `solve.s` to exist before a problem counts), this kind of quiet substitution is invisible.

### Two Dimensions of Benchmarking

This observation leads to a natural two-phase benchmark approach:

1. **Algorithm-normalized** -- the same C algorithm ported identically to every language. This isolates pure language/compiler/runtime performance. "Given the same work, how fast is each language?"

2. **Idiom-optimized** -- each language uses its best native approach. Python might use NumPy vectorization instead of nested loops. Rust might use iterator chains with `.fold()`. Java might benefit from streams. C# might leverage `Span<T>` or LINQ. "Given freedom to solve it the best way for this language, how fast can each be?"

The delta between these two would reveal which languages benefit most from idiomatic optimization -- and which are already so close to the metal that there's nothing to gain. Go, for instance, is already C-like enough that the two versions would likely be nearly identical. Python, on the other hand, might see 100x improvements from NumPy on array-heavy problems.

This is a future direction: for selected problems with interesting algorithmic variety, implement both the C-ported version and the idiom-optimized version, and compare.

## Lessons for LLM-Assisted Software Development

This project is a toy problem -- 100 math puzzles in 9 languages. But the patterns we discovered apply directly to real-world LLM-assisted development. Here's what we learned.

### 1. LLMs Hallucinate Data, Not Just Text

The most alarming finding: when Claude couldn't fit a data file's contents into its context window, it **invented plausible-looking data** and embedded it inline. Python problem 059's cipher data was completely fabricated. Java problem 054 had 293 poker hands instead of 1000. Python problem 099 had 374 base-exponent pairs instead of 999.

Every fabricated dataset produced code that compiled cleanly, ran without errors, and returned a confident-looking number. There was no crash, no exception, no warning -- just a wrong answer.

In production, this is the equivalent of an LLM generating a mock API response instead of calling the real API, or hardcoding test data instead of reading from the database. The code *works* -- it just silently produces wrong results.

**Takeaway**: Never trust LLM-generated code that embeds data. Verify data sources independently. If the code should read from a file or API, confirm it actually does.

### 2. Code That Compiles and Runs Is Not Code That's Correct

The C# 8-nested-loop coin change problem returned 73682 -- the *right* answer. It was just astronomically slow (10+ minutes vs 7 microseconds). The C++ Newton's method for problem 080 compiled perfectly and produced 570 -- close to the right answer of 40886, but wrong due to a subtle precision bug.

Without benchmarking infrastructure and answer validation, these would have shipped. Code review wouldn't catch them -- the logic *looks* reasonable.

**Takeaway**: Automated correctness verification is essential when using LLMs at scale. Not just "does it compile" or "do the tests pass" -- but "does it produce the right answer?" and "does it produce it in reasonable time?"

### 3. The LLM's Algorithm Choice Is Culturally Biased by Language

This was the big revelation. When you ask Claude to solve a problem in C, it reaches for algorithms from competitive programming and systems code. Ask for C#, and it pulls from enterprise blog posts and Stack Overflow answers. Ask for Python, and it reaches for readable, Pythonic solutions.

The *same problem* gets fundamentally different algorithmic strategies depending on the target language. C gets O(n) algebraic solutions. C# gets O(n^8) brute force. Python gets string manipulation where integer arithmetic would suffice.

This isn't a bug -- it's an emergent property of training data distribution. C's training corpus skews toward performance-conscious code. C#'s skews toward "make it work." The language you choose doesn't just affect syntax -- it affects the quality of the AI-generated solution.

**Takeaway**: When using LLMs to generate performance-sensitive code, specify the algorithm explicitly or provide a reference implementation. Don't assume the model will choose the optimal approach -- its choice is influenced by what's common in that language's ecosystem, not what's best for your problem.

### 4. Verification at Scale Requires Infrastructure, Not Eyeballs

We have 900 solutions across 9 languages. No human is reviewing all of them. The problems we found -- wrong answers, infinite loops, fabricated data, missing files -- were all caught by automated infrastructure: benchmark harnesses, answer validation against known-correct values, cross-language comparison.

The cross-language comparison was particularly powerful. When 8 languages agree on an answer and 1 doesn't, you know exactly where the bug is.

**Takeaway**: If you're using LLMs to generate code at scale, invest in automated validation infrastructure. Tests are necessary but not sufficient -- you need *comparative validation* against known-good implementations or reference outputs.

### 5. The "Works on My Machine" Problem Is Amplified

Data file paths, compiler versions, shell compatibility (bash 3.2 vs 5.3), `.NET` SDK quirks, `dotnet run` vs running the binary directly (12x overhead difference) -- every environment assumption the LLM makes is a potential silent failure.

LLMs generate code based on training data from many different environments. The C# solutions assumed `dotnet run` was fast. The benchmark scripts assumed `#!/bin/bash` meant modern bash. The Java solutions assumed data could be embedded in string literals without line-length limits.

**Takeaway**: Treat LLM-generated code as code from a new team member who has never used your environment. Review environment assumptions, file paths, tool versions, and platform-specific behavior.

### 6. First-Pass Code Needs a Second Pass

Every repo needed cleanup after initial generation. Not bug fixes -- *architectural normalization*. The benchmark harness migration, algorithm standardization, data file audit, import cleanup (`using System;` in C#) -- these are the kinds of things a senior engineer does after a junior developer writes the first draft.

LLMs are fast first-draft writers. They produce working code quickly. But "working" and "correct" and "well-architected" are three different things, and the gap between them is where bugs hide.

**Takeaway**: Budget time for review and normalization of LLM-generated code. The first draft is the starting point, not the finish line. The value of the LLM is that it gets you to the starting point in minutes instead of hours -- but the last mile still needs human (or at least structured automated) oversight.

### 7. The Meta-Lesson

Perhaps the most important insight is this: **we used an LLM to discover the limitations of using LLMs**. Claude wrote the code, Claude found the bugs, Claude fixed them, and Claude wrote this analysis. The tool is powerful enough to be self-correcting -- but only when given the right infrastructure (benchmarks, validation, cross-comparison) and the right human guidance (algorithm specifications, data file requirements, environment constraints).

The future of LLM-assisted development isn't "AI writes code, human ships it." It's "AI writes the first draft, infrastructure validates it, AI fixes what's wrong, human provides judgment on what matters." This project is a small-scale proof of concept for that workflow.

## The Two-Model Strategy

A key optimization emerged during the 101-200 expansion: using **Opus for design and Sonnet for bulk translation**.

- **Claude Opus 4.6** wrote the C reference implementations, designed the benchmark harness, debugged algorithmic issues, and wrote this analysis. The hard work -- choosing algorithms, handling edge cases, understanding mathematical subtleties.

- **Claude Sonnet 4.6** handled the mechanical ports from C to other languages. For "take this C algorithm, write it in Go/Rust/Java/etc.," Sonnet is the right tool. It's translation, not invention. This reduced token costs by roughly 60% compared to using Opus for everything.

The model split maps to software roles: Opus is the senior engineer who designs the architecture. Sonnet is the team of junior developers who implement it across the codebase. Both are necessary; using Opus for everything would be wasteful, and using Sonnet for the initial algorithm design would produce more bugs.

Interestingly, Sonnet agents occasionally ran out of context on the 151-200 port wave (50 problems per agent is a lot of file reads + writes). But they typically completed 44-46 of 46 problems before context exhaustion -- close enough to mop up the gaps with a follow-up agent. This suggests that for bulk generation tasks, slightly smaller batches (30-35 per agent) would be more reliable.

## Token Economics

This project consumed significant compute. A rough accounting:

- **Problems 1-100**: ~50 agent launches across creation, migration, fixing, and porting
- **Problems 101-200**: ~20 agent launches for C reference + 8 language ports
- **Benchmarking, fixing, analysis**: ~15 agent launches
- **Total**: ~85 agent launches, each consuming 50K-200K tokens

The Opus-for-design, Sonnet-for-bulk strategy was essential for keeping costs manageable. Without it, the project would have cost roughly 2.5x more in tokens.

## The Optimization Hunt

With 1,800 solutions in place, we turned to finding algorithmic outliers — problems where one language was disproportionately slow compared to others, indicating an algorithm problem rather than a language penalty.

### The C# Archaeology

C# was the worst offender, with several problems showing 1000x-6000x slowdowns versus C:

| Problem | Before | After | Speedup | Root Cause |
|---------|--------|-------|---------|------------|
| 039 (Right Triangles) | 500.7ms | 90us | **5,563x** | Triple nested loop (1B iterations) vs double loop with sqrt |
| 004 (Palindrome Product) | 13.8ms | 9us | **1,533x** | Brute force all products vs generate palindromes descending |
| 023 (Abundant Numbers) | 1,506ms | 7.5ms | **201x** | O(n) divisor sum per number vs O(n log n) sieve |
| 007 (10001st Prime) | 41.2ms | 196us | **210x** | Trial division with growing List vs Sieve of Eratosthenes |
| 095 (Amicable Chains) | 9,131ms | 85ms | **107x** | Redundant Arrays.fill(1M booleans) in inner loop |

Every single one was an instance of the "language culture" bias: Claude's C# training data suggested enterprise-friendly-but-slow patterns (LINQ, Dictionary, SortedSet, string interpolation) where C's training data suggested competitive-programming-optimized algorithms.

### Cross-Language Algorithm Fixes

Some algorithmic improvements needed to be propagated across all languages:

**Problem 073 (Counting Fractions)**: All 9 languages used brute-force GCD checking (~350ms). Replaced with Stern-Brocot mediant counting — a recursive approach that only generates reduced fractions by construction, requiring zero GCD calls. Result: 351ms → 18ms across all languages (19x speedup).

**Problem 060 (Prime Pair Sets, C++)**: Trial division for primality on concatenated numbers (1,304ms). Replaced with the same sieve + Miller-Rabin approach used by C: 55ms (24x speedup). The C++ version had been written independently and chose a simpler-but-slower primality test.

**Problem 095 (Amicable Chains, Java)**: Even after adding sieve caching, still took 6.6 seconds due to `Arrays.fill(inChain, false)` clearing 1 million booleans on every outer loop iteration — despite the cleanup loop on lines 68-73 already clearing only the entries that were set. Removing the redundant fill: 9,131ms → 85ms (107x).

### Memory Insights

Java's JVM memory overhead was striking:

- Problem 068 (Magic 5-gon Ring): **3 GB** for a permutation search that C does in 1.3 MB
- Problem 095 (Amicable Chains): **7.3 GB** for a 1M-element sieve
- Problem 055 (Lychrel Numbers): **928 MB** for BigInteger operations

The JVM over-allocates heap by default and doesn't bother reclaiming for short-lived benchmark processes. For problems taking <1ms of actual computation, Java showed 100-900MB while C showed 1.3MB. This is JVM startup + GC overhead, not the algorithm's memory footprint.

## Project Structure

```
ccdev/
  ProjectEuler.C/           -- 200 problems, C (Apple Clang 17 + GCC 15)
  ProjectEuler.CPlusPlus/   -- 200 problems, C++ (Clang++ + GCC 15)
  ProjectEuler.Rust/        -- 200 problems, Rust (rustc/LLVM)
  ProjectEuler.Go/          -- 200 problems, Go (gc)
  ProjectEuler.Java/        -- 200 problems, Java (JDK)
  ProjectEuler.CSharp/      -- 200 problems, C# (.NET 10)
  ProjectEuler.Python/      -- 200 problems, Python (CPython 3.11)
  ProjectEuler.JavaScript/  -- 200 problems, JavaScript (Node.js v24/V8)
  ProjectEuler.ARM64/       -- 200 problems, ARM64 Assembly + C
  ProjectEuler.Benchmarks/  -- Aggregation, charts, and this document
  claude-vs-euler/          -- Archived: the original multi-language repo
```

Total: **1,800 solution files** across 10 repositories, generated by Claude Opus 4.6 and Claude Sonnet 4.6 (with newer work on Opus 4.7), with human architectural guidance and verification.

## Which Language Should Claude Write In?

With 200 problems benchmarked across 8 languages (Python excluded due to incomplete benchmark coverage), we can finally answer the question: **which language does Claude generate the best solutions in?**

### The Full Rankings (190 common problems, excluding 7 parked timeouts)

| Rank | Language | Total Time | Slowdown vs C | Avg SLOC | Wins |
|------|----------|-----------|---------------|----------|------|
| 1 | **C++** | 10.64s | 1.00x (median) | 48 | 50 |
| 2 | **C** | 10.78s | 1.00x | 72 | 50 |
| 3 | **Go** | 13.73s | 1.39x | 60 | 27 |
| 4 | **Java** | 13.93s | 1.59x | 49 | 14 |
| 5 | **ARM64** | 14.45s | 1.07x | 71 | 14 |
| 6 | **Rust** | 21.39s | 1.05x (median) | 53 | 39 |
| 7 | **C#** | 22.03s | 2.04x | 50 | 10 |
| 8 | **JS** | 49.41s | 3.39x | 42 | 5 |

"Wins" = number of problems where that language had the fastest single-problem time.

### The Surprises

**C++ ties C for speed but is 35% more compact.** STL containers (vectors, maps, sets) give Claude better building blocks without manual memory management. The average C++ solution is 48 lines vs 72 for C. Claude generates cleaner C++ because the language's abstractions match the problem domain better.

**Go is the dark horse.** Only 1.3x slower than C++ overall, with the **most consistent performance** — no outlier problems, no fat tail. Claude writes very reliable Go. The garbage collector costs ~30% on computation-heavy work, but you never get a 10x surprise.

**Rust has a fat tail problem.** Median slowdown is an impressive 1.05x (essentially C-speed), but the **p90 is 6.44x** — meaning 10% of problems are dramatically slower. Claude occasionally generates Rust solutions with unnecessary allocations, cloning, or suboptimal memory access patterns that the borrow checker forced into existence. When Rust is good, it's great. When it's bad, it's worse than Go.

**C# has the worst tail of all.** Median 2.04x but p90 of **23.6x**. Claude's C# training data biases toward enterprise patterns (LINQ, Dictionary, BigInteger) that are clean but slow. The `.NET UInt128` vs `BigInteger` gap caused several problems to fail entirely — `BigInteger` modular multiplication is orders of magnitude slower than native 128-bit arithmetic.

**JavaScript is the most compact but slowest.** Average 42 lines per solution (vs 72 for C), but `BigInt` arithmetic is an Achilles heel. Problems requiring large-number modular arithmetic are 10-50x slower due to BigInt overhead. For problems that stay within `Number` range, JS is surprisingly competitive.

### Where Language Choice Matters Most

The biggest performance spreads between fastest and slowest language:

| Problem | Spread | Root Cause |
|---------|--------|------------|
| 153 (Divisor Sums) | 312,000,000x | Algorithm divergence: Java precomputes, JS brute-forces |
| 122 (Efficient Exponentiation) | 57,000,000x | Lookup table vs computation |
| 024 (Lexicographic Permutations) | 12,800,000x | O(1) factorial formula vs O(n!) enumeration |

These massive spreads aren't language speed differences — they're **algorithm differences**. Claude chose different algorithms for the same problem in different languages, likely influenced by each language's training data. The most important optimization isn't the language; it's the algorithm.

### The Recommendation

**For computational/algorithmic work:** C++ is the best choice. It has C's speed with better abstractions, and Claude generates consistently high-quality C++ solutions.

**For general-purpose development:** Go offers the best balance of speed, consistency, readability, and low surprise factor. You never get a catastrophic outlier.

**For the adventurous:** Rust's median performance is essentially C-speed, but review Claude's generated Rust carefully — watch for unnecessary clones, allocations, and patterns the borrow checker forced into suboptimal shapes.

**The real takeaway:** Language choice matters maybe 2-5x. Algorithm choice matters 1000x+. When working with Claude, review algorithmic decisions more carefully than language idioms.

### Parked Problems

Seven problems (152, 167, 170, 177, 180, 185, 196) are parked as of 2026-03-23. These timeout across multiple languages — not due to language overhead but because the underlying algorithms are too slow. They need fundamental redesign:

- **152, 167, 185**: Timeout even in C (>60s per solve). Brute-force search trees.
- **170, 177, 196**: Pass in C/C++ but timeout in most other languages. Borderline algorithms that only survive in the fastest compiled languages.
- **180**: Go build error (not algorithmic).

These will return as an algorithm optimization project.

## What's Next

- **Idiom-optimized Python**: Rewrite select Python solutions using NumPy, itertools, and other Pythonic approaches to measure the "idiomatic vs C-ported" performance gap
- **Matplotlib visualization**: Generate publication-quality charts comparing languages across all dimensions (speed, memory, source size)
- **Problems 201-300**: Push into the difficulty wall and document where Claude's autonomous problem-solving breaks down
- **Compiler deep-dive**: For the top 2-3 languages, test multiple compiler versions and optimization levels to isolate compiler vs language effects
- **Parked problem redesign**: Tackle the 7 parked problems with fundamentally better algorithms, then propagate across all languages

## Methodological Rigor: Addressing the Critics

Three potential criticisms were identified and addressed:

### 1. Compile Time (Previously Unmeasured)

The `euler-bench` tool now captures compile time per problem in nanoseconds. Representative numbers for problem 001:

| Language | Compile Time |
|----------|-------------|
| C | 135 ms |
| C++ | ~150 ms |
| Go | ~80 ms |
| Java | 377 ms |
| Rust | ~2-5 s (cargo) |
| C# | ~1-3 s (dotnet) |
| JS/Python | 0 (interpreted) |

Rust's cargo build is the slowest — each problem is a separate crate with full dependency resolution. For developer iteration speed, Go's near-instant compilation is a significant advantage.

### 2. Cold-Start vs Warm-Start (The JIT Tax)

Each bench harness now reports `COLDSTART|time_ns=N` — the time for the very first solve() call before any warmup or JIT compilation. Results for problem 001:

| Language | Cold Start | Warm (median) | JIT Tax |
|----------|-----------|---------------|---------|
| C | 41 ns | 0 ns | 1x |
| Java | 23,875 ns | 2,292 ns | **10x** |
| JavaScript | 16,500 ns | 84 ns | **196x** |

For JIT languages (Java, C#, JavaScript), the warmed-up median dramatically understates the cost of the first execution. In serverless/cold-start environments, the warm-start benchmarks are misleading. The cold-start data provides a more honest comparison for those use cases.

For AOT-compiled languages (C, C++, Rust, Go), cold and warm times are essentially identical — the compiler already did the optimization work.

### 3. Algorithm Normalization Audit

**Question:** Does Claude choose different algorithms for different languages, making the "language comparison" actually an "algorithm comparison"?

**Answer:** No. An audit of 20 representative problems across C, Go, and Java found:

- **18/20 (90%)** use identical algorithms across all languages
- **2/20 (10%)** differ only in lookup structure (HashSet vs binary search) — same core algorithm

The two-model strategy (Opus designs algorithms in C, Sonnet ports to other languages) ensures algorithmic consistency. The performance differences in the benchmark are genuine language-level differences, not algorithm-selection artifacts.

This validates the benchmark's core claim: when the algorithm is held constant, language choice produces a 2-6x performance spread, while algorithm choice produces 1000x+ differences (one fix on a single problem yielded a 23,000x speedup across all 10 languages).

## Episode: The Cache-Strip Campaign (24 hours, 2026-05-22 → 2026-05-23)

A campaign meant to fix one chart-honesty issue turned into a much deeper
discovery about what a benchmark is even trying to measure. We started by
chasing a numerical anomaly. We ended by reverting 155 commits and writing a
new principle into the operating rules.

### The anomaly

On 2026-05-22 evening, the headline Foundation-tier chart was ranking **C# at
#1 over C++, ARM64, and Zig** — natively compiled languages losing to a JIT'd
.NET runtime on integer-heavy algorithms. That's possible but suspicious. A
per-problem audit showed many entries with `time_ns: 41` (or `0`) but
`cold_start_ns: 59,000,000` (or higher) — *a 1.4-million-to-one ratio* between
warm and cold. Something other than the algorithm was being measured warm.

The pattern, found across the suite:

```cpp
static bool initialized = false;
static long long answer_cache = 0;

long long solve() {
    if (initialized) return answer_cache;
    initialized = true;
    /* ... real algorithm ... */
    answer_cache = result;
    return answer_cache;
}
```

A warm-iteration bench harness calls `solve()` hundreds of times in succession.
With the static cache, every call after the first returns in ~40 nanoseconds —
the cost of a flag check and a register load, not the cost of the algorithm.
The bench's "Total Time" column had been mostly noise for cached problems.

### The classifier (Stage 0)

We built a Python script (`scripts/cache_classify.py`) that walked the bench
data for all 10 languages, flagged any problem with the
`cold > 1ms ∧ time < 100µs ∧ ratio > 100` signature, then read each source file
to discriminate the *kind* of cache pattern present:

| Pattern | Count | Meaning |
|---|---:|---|
| **A** — static answer cache | 154 | Strip target: real bench cheating |
| **B** — Zig comptime fold | 6 | Leave: algorithm IS the fold, honest |
| **D** — input data cache (array-typed) | 13 | Leave: warm measures algorithm, not I/O |
| **E** — genuine fast algorithm (false positive of detector) | 56 | Leave: no cache exists, just legitimately fast |

The discriminator that made D work cleanly was the cache variable's *type*: a
scalar return value (`long long`, `i64`, etc.) meant Pattern A; an array type
(`String[]`, `int[][]`) meant Pattern D — input loaded once, but the algorithm
re-runs every warm call on the cached input.

### The fan-out (Stage 1)

Ten parallel agents launched as background tasks, one per language, each given
its filtered Pattern A target list (43 for C++, 23 for Python, 17 for ARM64,
down to 6 for Rust). Each agent had explicit per-language strip patterns and
strict "edit only — no build, no bench, no commit" rules. All ten returned
within 30 minutes. **155 source files modified across 10 repos**, working trees
clean apart from the intended strips.

Three worked examples to verify the strip's actual impact on `time_ns`:

| Language | Problem | Warm before | Warm after | Change |
|---|---|---|---|---|
| C++ | 161 (Triominoes) | 41 ns | 29,177,167 ns (29 ms) | **712,000×** |
| Python | 161 | 83 ns | 2,082,187,792 ns (2.08 s) | **25,000,000×** |
| Zig | 161 | 0 ns | 26,658,167 ns (27 ms) | (literally ∞×) |

Same algorithm, same answer, same scale — and now Python is **71× slower than
C++** on the same problem. That spread is the actual compile-vs-interpret tax
the cache had been concealing.

### The reckoning (Stage 2)

Sequential per-language re-bench and commit. Smallest-batch-first to surface
harness issues early. Eight languages landed cleanly. Then the pattern broke
down.

**Discovery 1 — `p170` fails bench across 6 languages.** Pandigital
concatenation search takes 34–62 seconds *cold* in every compiled language.
With the cache, that cost happened once and warm iters returned in nanoseconds.
Without the cache, the bench harness can't fit a single warm iteration within
its 120-second per-problem timeout. p170 newly fails in Rust, C#, Go, Java,
Zig, C, ARM64 — *because the cache had been hiding a genuinely slow algorithm
that fits the timeout only once*. The "passing" status was the cache; the
algorithm was always borderline.

**Discovery 2 — ARM64 `p087` and `p136` return 0 after strip.** The bench
script's Gate 1 caught it: answers were wrong. Investigation showed the
algorithms used static BSS arrays as "have I marked / counted this n" trackers
*and* as the per-call accumulators. The cache hid the bug because only the
first call ran the algorithm; subsequent calls returned the cached correct
answer. Without the cache, the second call saw arrays still full of 1s from the
first, the "already seen" check short-circuited every increment, and the count
stayed at 0. Same root cause in `p179` (divcount sieve uses `++`, accumulates
without re-zero). Three real algorithm bugs the cache had been silently
masking. Fixed by adding `bl _memset` of the affected BSS arrays at the top of
`_solve`.

**Discovery 3 — Python's `p122` algorithm is fundamentally intractable
per-call.** A standalone test of each stripped Python problem with a 15-second
timeout revealed that **15 of 23** never produced a single line of output
within 15 seconds. The "cache" we'd stripped wasn't just hiding the warm
benchmark number — it was the only thing making problems like `p122`
(addition-chains brute DFS), `p155` (capacitor combinations), `p365`
(Lucas-CRT multinomial coefficients) viable in Python at all. With the cache,
each problem ran *once* per process and the answer was returned forever.
Without it, every warm call ran the full algorithm — and in Python that's
seconds-to-minutes per call. The compile-vs-interpret tax in its most extreme
form: not "Python is slower per call," but "Python cannot run this algorithm
per-call within any reasonable budget."

**Discovery 4 — The 631-minute stall.** The Python `git commit` triggered the
post-commit hook, which re-runs `benchmark.sh` for all 23 problems with a
600-second per-problem timeout. Worst case: 23 × 600 s = 230 minutes. Run
overnight, the operator wakes up to find the task showing **631 minutes
elapsed and counting**, with the output file containing exactly 121 bytes —
only the wrapper's first echo. Investigation revealed the bash wrapper had
piped `benchmark.sh ... | tail -35`. With pipe-to-`tail`, **nothing flushes
until the producer closes stdout**. The producer was hung (Python's slow
algorithms each consuming their 600-second timeout); `tail` waited
indefinitely; the entire pipeline blocked invisibly. Direct cause: a shell
anti-pattern in the wrapper. Indirect cause: the campaign's mass-strip
approach was creating a problem class — pathologically slow Python algorithms
— that the operating procedure wasn't designed to handle.

### The deeper principle

Through the agents' reports and the discoveries, a clearer framing of the
real invariant emerged. The user's framing (verbatim):

> "I'm not opposed to caching of state in an algorithm, but if that state
> leaks into the next iteration of the algorithm I care more and need an
> explanation."

This is sharper than "strip caches." The real test is **invocation
isolation**: every call to `solve()` must produce its answer independently of
previous calls. Internal memoization (DP tables, sub-problem caches) is fine
*as long as it doesn't survive across calls*. Three failure modes are unified
under this principle:

| Failure mode | Example | Right response |
|---|---|---|
| Intentional answer-leak | `static long long answer_cache;` | Strip — the warm number is a lie |
| Intentional in-algorithm memo-leak | `_best = None; if _best is not None: return _best` | Move the memo to function-local, OR accept the algorithm is intractable in this language |
| Unintentional state-leak | ARM64 `_p087_seen[]` not re-zeroed | Fix by resetting state at top of `solve()` — bug was always there, cache was hiding it |

The campaign had treated all three the same way — strip the cache and move on.
What was really needed was three different responses, and an audit invariant
that catches all three at commit time without conflating them.

### The reset

We reverted everything. Hard-reset across all 11 repos to pre-campaign commits;
discarded the 44 uncommitted C++ strips; cleaned `__pycache__`. Pre-revert SHAs
preserved in `/tmp/pre-revert-shas.txt` for reflog recovery if needed. The
classifier itself (`scripts/cache_classify.py`) and the classification artifact
(`scripts/cache_classification.json`) were both reverted as well — they were
inputs to the failed mechanical approach and would have biased the careful
restart.

The replacement plan: **scope back to problems 1–10 across all 10 languages =
100 measurements**, build an invocation-isolation gate that runs in the
post-commit hook, then carefully audit each of the 100 problems with attention
to state-leakage as *an algorithm design choice*, not a regex-detected pattern.
Once 100 problems pass with the gate active and the public reports show only
that 100, we extend forward in honest increments.

### Operating rules baked from the 24 hours

Three rules entered the working operating procedure as a result of this
episode:

1. **`cmd | tail -N` is forbidden for any long-running `cmd`.** Pipe-to-tail
   buffers until EOF; if the producer hangs, the consumer never produces
   output. Use `cmd > /tmp/log 2>&1 &` then `tail -f`, or use Python with
   `Popen(stdout=PIPE, bufsize=1)` and per-line reads. (Codified in
   `~/ccdev/CLAUDE.md` and `feedback_python_over_shell_orchestration.md`.)

2. **One-shot orchestration scripts default to Python, not bash/zsh.** Shell
   fragility — pipe buffering, zsh `declare -A` portability, zsh
   word-splitting on `$var` iteration — caused real time loss in this session.
   Bash is fine for < 5-line one-liners with no loops, no pipes, no JSON. Go
   remains the default for *durable* tools; Python is the right default for
   *throwaway* orchestration. (Same files as above.)

3. **Invocation isolation is an algorithm design concern.** A `solve()` whose
   second call depends on state from the first is broken, even if the user
   never notices because the cached answer is correct. Algorithms should be
   written with state-leakage in mind from the start, not patched after a
   regex-based audit catches them.

The mechanical strip campaign produced 155 commits and discovered ~3
real algorithm bugs, then was reverted entirely. The principle it surfaced —
and the operating rules that fell out of the failure mode it produced — were
worth more than the strips themselves would have been.

## Episode: From In-Process Warm to Process-Per-Iteration (2026-05-23)

After the cache-strip campaign reset (previous chapter), we built the
double-call invocation-isolation audit and started auditing language by
language: C++, C, ARM64, Rust each verified clean on problems 1-10.  Then
a single problem changed the framing of the entire benchmark.

### The Rust p010 OnceLock question

Rust's solution to "sum of all primes below 2,000,000" uses `OnceLock`:

```rust
use std::sync::OnceLock;
static SIEVE: OnceLock<Vec<bool>> = OnceLock::new();

fn solve() -> i64 {
    let is_prime = SIEVE.get_or_init(init_sieve);  // builds once, ever
    let mut sum: i64 = 0;
    for i in 2..is_prime.len() { if is_prime[i] { sum += i as i64; } }
    sum
}
```

This passes the mechanical double-call audit (the answer is deterministic
because the sieve is immutable after init) but represents an apparent
*cross-language fairness* issue: C, C++, and ARM64 solutions of p010 build
a fresh sieve on every warm bench iteration, while Rust's `OnceLock`
amortizes the sieve build across all warm iterations of one process.  In
the in-process warm metric this looked like Rust was 5× faster than it
"really" was.

We considered three responses: refactor Rust to NOT use OnceLock (matching
C++'s sieve-per-call pattern), keep OnceLock with an explanatory comment,
or step back and ask whether the harness was measuring the wrong thing.

### The harness-itself question

The user articulated the principle:

> "If I took this program and put it in a bash/zsh loop, that Vec would
> be recreated on each process invocation.  There would be no doubt of
> that.  Same for that C++ library.  Unless you store data in some OS
> cross-process memory, the process boundary wins for a very good
> reason... nothing leaks out of it.  Now that process creation adds
> overhead, but it's the same no matter where we come from."

And, on language idioms:

> "I want all of our languages to look like they were written
> independently and not just a copy of another language, I want the
> idioms of C++, Rust, Python to shine through and not be... oh a Rust
> dev would never write it like this, but we had to, to fix the harness."

These two points coupled mean: **the OS-enforced process boundary is the
natural and perfect invocation-isolation guarantee**, and the harness's
in-process warm-iter mode forces unnatural code patterns to compensate.

### Process-per-iter audit

A new measurement script was added (`scripts/process_per_iter_audit.py`)
that wraps the existing bench binary and runs it N times in fresh
processes, capturing the COLDSTART time from each.  Results across the
four already-audited languages (C++, C, ARM64, Rust) on problems 1-10:

The most revealing single problem is **p007 (10001st prime)**:

| Lang  | In-process warm | Process-per-iter cold (median × 10 runs) | What the cold-median actually measures |
|-------|----------------:|------------------------------------------:|----------------------------------------|
| C++   | 3.5 µs          | 25.6 µs                                   | primesieve library does sieve init once per process |
| C     | 155 µs          | 167.6 µs                                  | hand-rolled sieve, malloc'd each call |
| ARM64 | 264 µs          | 282 µs                                    | hand-rolled assembly sieve |
| Rust  | 819 µs          | 880 µs                                    | hand-rolled sieve |

In the in-process warm column, C++ looks **75× faster than C** — a
benchmark lie, because the warm number is measuring "primesieve has the
answer cached," not "C++ solved this faster."  In the process-per-iter
cold-median column, C++ is still fastest but the ratio is **6.5× over
C** — a real algorithmic difference (primesieve's sieve algorithm
genuinely beats the naive sieve), with no library-cache distortion.

Same insight on **p010** (the OnceLock problem):

| Lang  | In-process warm | Process-per-iter cold (median × 10) | Divergence |
|-------|----------------:|--------------------------------------:|------------:|
| C++   | 219 µs          | 261 µs                                | 1.2× |
| C     | 1.9 ms          | 2.1 ms                                | 1.1× |
| ARM64 | 4.5 ms          | 4.7 ms                                | 1.0× |
| Rust  | **505 µs**      | **2.0 ms**                            | **4.0×** |

The Rust OnceLock cache effect, surfaced clearly: in-process warm hides
~1.5 ms of sieve-build cost per fresh-process invocation.  In the
process-per-iter view, Rust pays for the sieve build every time — exactly
matching C and ARM64's per-call cost (and showing Rust's sieve impl is
genuinely competitive with hand-rolled C).

### Resolution: process-per-iter as the headline metric

The decision is to make **process-per-iter cold-median** the chart's
primary metric, with the in-process warm time retained as a *secondary*
view (relevant for "server/daemon" use cases where solve() runs many
times in one process).  This:

- **Lets each language be idiomatic**: Rust can keep `OnceLock`, C++ can
  use `primesieve`, Python can use `@lru_cache`.  The OS clears
  everything between invocations regardless.
- **Matches the user-facing mental model**: "how long does this take to
  run as a command?" — exactly what `time ./prog` answers.
- **Removes the entire class of in-process state-leak benchmark bugs**.
  No more cache-pattern detector chasing; no more cross-language
  divergence on what counts as legitimate memoization.  The OS doesn't
  argue.

### Operating rules added from this episode

1. **Process-per-iter is the headline.**  The "1000 invocations a day"
   mental model wins over the "long-running daemon" one for a general-
   purpose cross-language chart.
2. **In-process warm becomes a secondary metric**, reported only with
   the caveat that it reflects steady-state cost in a long-running
   process (cache effects, JIT warmup, etc., all included as intended).
3. **Each language stays idiomatic.**  No more reshaping code to satisfy
   the harness.  Anti-pattern: telling a Rust dev "don't use OnceLock"
   to fix a measurement methodology.  If the harness can't measure
   accurately, fix the harness, not the code.
4. **Trivial problems (sub-microsecond algorithm) become unmeasurable**
   under this model — process spawn floor (~6-10 ms on macOS) dominates.
   This is honest: those problems aren't where meaningful cross-language
   comparison lives anyway.  The interesting signal starts at p007+
   where algorithm cost ≥ spawn cost.

Next: build a unified Go harness (per the durable-tooling rule in
`~/ccdev/CLAUDE.md`) that drives this measurement across all 10
languages using known-good timing primitives — Go's monotonic clock,
cross-validated against `/usr/bin/time -l` for max-fidelity wall +
RSS data.  The current Python audit was the prototype; the production
tool lives in Go.

## Episode: Single-Call Harness (2026-05-23 evening)

After the process-per-iteration architecture (previous chapter), an
attempted expansion to problems 11-50 surfaced a follow-on question:
if the OS process boundary is the isolation guarantee, why do the
per-language harness files still contain warmup + calibration + iter
loops?

### The mismatch

The harnesses had stayed in pre-process-per-iter shape: each one
called `solve()` ~1004 times per process (1 cold + 2 warmup + 1
calibration + N=3/10/100/1000 timed iterations), reported the median
as `BENCHMARK|...`, and the first call as `COLDSTART|...`.  Only the
COLDSTART line ever fed the chart; the rest was dead work.

Worse, the in-process iteration was an attractive nuisance: a
double-call audit got built to detect "warm-vs-cold" cache patterns,
and a 50-cell expansion campaign started "fixing" them (drop OnceLock
from Rust, strip static caches from C++/Java/CSharp).  Per JOURNEY
rule 3 ("Each language stays idiomatic — no reshaping code to satisfy
the harness"), every one of those was the exact wrong direction.  All
reverted before any commit.

### The simplification

Two architectures considered:

- **A** — harness internally times `solve()` once using the language's
  native clock, prints `RESULT|time_ns=N|answer=A`, exits.  ~5 lines
  per harness.
- **B** (`time foo` model) — harness becomes literally
  `print(solve())`; the Go tool times wall from outside.  Process spawn
  floor (~6-10 ms on macOS) crushes all sub-millisecond algorithms
  into indistinguishable noise.

**Decision: A.**  The internal-timing approach preserves sub-µs
algorithm visibility (C `p001` = 42 ns is real and worth keeping in
the chart), which B would lose to the process spawn floor.

### What changed

- All 10 per-language harnesses simplified to: one cold call to
  `solve()`, print `RESULT|time_ns=N|answer=A`, exit.  No warmup, no
  calibration, no iter loop, no separate COLDSTART/BENCHMARK lines.
- Sentinel renamed: `COLDSTART|` (warm/cold-era word) → `RESULT|`.
  With one call per process, "cold" and "warm" no longer mean anything.
- Data-file field renamed: `cold_start_ns` → `time_ns`.  The old
  `time_ns: 0` (warm) field dropped.  Backward compatibility
  deliberately skipped — data files get overwritten by the re-bench
  anyway.
- Dead scripts deleted: `scripts/double_call_audit.py`,
  `scripts/process_per_iter_audit.py`, `cmd/three-mode-report/`
  (3-metric era), `scripts/check_timing_delta` (warm-regression
  detector, now meaningless).

### Operating rules added from this episode

4. **The harness does one call, period.**  Multi-call inside a
   process is dead work (the chart only uses one call) and an
   attractive nuisance (invites "warm anomaly" audits that
   re-violate rule 3).  Any future change that adds calibration
   loops, warmup phases, or iteration-median logic to a harness is
   the wrong direction.

5. **`RESULT|time_ns=N|answer=A` is the canonical bench-output
   sentinel.**  One line per process, one format across all 10
   languages.  No `BENCHMARK|`, no `COLDSTART|`, no per-language
   variants.

## Episode: Expansion to 100×10 + cross-lang idiom landmines (2026-05-23 late evening)

After the single-call harness cleanup (previous chapter) and the 50×10 publish,
expansion to 100×10 followed the established playbook: inventory check, bench
problems 51-100, regen chart, ship.  In parallel with the (sequential, ~30 min)
bench, 10 idiom-review agents ran with the corrected JOURNEY-rule-3 framing —
algorithm + idiom only, no cache-pattern chasing.  This chapter records what
those agents found.

### Cross-lang batch-refactor candidates

The most leverageable findings are cells where multiple languages independently
made the same algorithmic mistake.  In 51-100, three stand out:

- **PE 77 (Prime-pair sums)** — 7/10 languages rebuild the partition-DP from
  scratch for every target instead of streaming a single growing DP.  Same fix
  shape in each: one allocation, scan incrementally.  Equivalent in spirit to
  the Big-4 cross-lang refactors from earlier tonight (PE 14, PE 12, PE 29,
  PE 39).
- **PE 93 (Arithmetic expressions)** — 6/10 languages use float arithmetic with
  `1e-9` epsilon to test "is this expression value an integer?"  Fragile for
  chained `(1+1/3)*3 - 4`-style cases.  Same fix everywhere: exact rationals
  (a/b pair with gcd reduction).
- **PE 55 (Lychrel)** — 4/10 use BigInteger/BigInt for what fits in 64-bit
  after 50 iterations.  Library overuse where a `long` plus digit-array reverse
  works.

### Real correctness landmines (not idiom)

Several cells have latent bugs that pass current tests by luck of the input but
would break under perturbation.  Worth fixing carefully (not as bulk refactors):

- **Rust p90** — 6/9 expansion creates duplicate cube entries; same arrangement
  counted multiple times.  Coincidentally correct on the given input.
- **Rust p54** — `CountingAllocator` wraps `solve()`, adding atomic-RMW ops on
  every allocation.  Quietly distorts every Rust p54 timing measurement.
- **Rust p62, p84** — `n > 100000` hardcoded cap (silent wrong answer if
  needed bigger); Markov chain that double-counts doubles (converges to wrong
  model, right answer empirically).
- **Java p081** — `MATRIX_DATA` is a fake/truncated string used as fallback if
  the file is missing.  Silent wrong answer rather than clean failure.
- **Java p060** — `mulMod` calls `BigInteger.longValueExact()` on the
  *unreduced* product; throws `ArithmeticException` for any `a*b > 2^63`.
  Works today only because inputs happen to be small.
- **C p089** — fopen fallback to a hardcoded absolute path
  `/Users/augusthill/ccdev/claude-vs-euler/...` — non-portable, personal path
  shipped.
- **ARM64 p054** — `x18` (Apple-reserved platform register) abuse inside
  `.Leval54`.  Same anti-pattern that bit p189 historically; safe today only
  because `.Leval54` makes no libc calls — future change breaks silently.
- **Zig p095** — three 10⁶ stack arrays totalling ~6 MB on the call stack;
  borderline against the default 8 MB ulimit.
- **Zig p083** — Dijkstra implemented with linear-scan pop instead of a real
  heap.  O(N²) where O(N log N) is canonical; ~250M comparisons on the 80×80
  grid.

### Per-lang cleanliness rankings (51-100 panel)

| Lang | A-rate | Notable observation |
|---|---:|---|
| JavaScript | 96% (48/50) | Cleanest by ratio.  BigInt discipline strong; p14 dense-memo lesson held |
| ARM64 | 90% (45/50) | Audit-clean trust held; one real bug (p54 x18 abuse) |
| Python | 88% (44/50) | Genuinely hand-written Python (not C-port aesthetic); p98 inlines word data |
| C | 86% (43/50) | Sized integer discipline tight (`int64_t`/`__int128_t`); no overflow bugs |
| C# | 80% (40/50) | Sharp improvement vs 1-50 panel (which had multiple wrong-algorithm cells) |
| Go | 80% (40/50) | `//go:embed` inconsistency across 4 file-loading cells |
| Java | 70% (35/50) | Two real bugs (p60, p81); stray `LongSupplier` import × 50 files |
| C++ | 60% (30/50) | `long` vs `long long` discipline loose; hand-bigint where `boost::cpp_int` would shrink |
| Rust | 60% (30/50) | Most real correctness landmines this round; two code generations again |
| Zig | 36% (18/50) | Lowest ratio, but mostly "module-level fixed array" idiom not real bugs; no GPA discipline outside p007/p010 |

### Operating rules added from this episode

6. **Cross-lang batch refactors require N≥5 langs flagging the same fix.**
   Below that threshold, the per-cell variance in agent perspective is too high
   to commit to a uniform fix.  The PE 14 / 12 / 29 / 39 round (Big-4) hit 8-10
   langs each.  PE 77 hits 7, PE 93 hits 6, PE 55 hits 4.  PE 77 and PE 93 are
   candidates; PE 55 is borderline.

7. **Correctness landmines get per-cell scrutiny, not batch treatment.**
   Several cells flagged tonight have lucky-input correctness (Rust p90, Rust
   p84, Java p060/p081, Rust p62).  These need individual reading and reasoning
   before any "fix" — applying a uniform patch could cement the wrong
   correctness if multiple langs share the same lucky shape.

8. **File-loading robustness as a cross-cutting concern.**  Three langs
   independently flagged file-loading anti-patterns in 51-100 (Java p081 fake
   fallback, C p089 absolute path, multiple Go cells using runtime
   `os.ReadFile` instead of `//go:embed`).  Worth a focused round to standardize
   on "fail loudly if data file missing" across all 10 langs' file-loading
   problems (p022, p042, p054, p059, p067, p079, p081, p082, p083, p089, p096,
   p098, p099).

---

## The 2026-05-25 SQLite Migration + Round-by-Round Rebench

After tonight's structural moves (`ProjectEuler.X` → `pe/<x>/`, deletion of
per-repo `benchmark.sh`, consolidation to a single `cmd/euler-bench` writer),
the bench data layer was the next natural piece to clean up. The per-lang
JSON files (`data/<lang>.json` public sanitized + `data/private/<lang>.json`
full gitignored) had drifted to the point where the sanitization invariant
was a runtime discipline rather than a structural property — a class of bug
that bit hard on 2026-05-09 (the ~891-value answer leak).

The migration: single SQLite SSOT at `data/bench-private.db` (gitignored).
Two tables — `runs` (latest per lang+problem, PK) and `run_history`
(append-only, enables drift audit + sample accumulation). Public repo now
carries no raw data at all; only RESULTS.md + charts. The sanitization gate
moved from "strip the answer field at write time" to "reject any data file
under `data/` not on the small config allowlist." Leak prevention is now
file-system structural, not field-stripping.

Rather than re-bench all 2000 cells in one shot, we did it in four rounds
(10 → 50 → 100 → 200), regenerating the site between each so a bug in the
new pipeline would surface at 100-cell cost, not 2000-cell cost.

### Round 1 — 10×10 baseline (scope=1-10)

**Wall:** 90 seconds for 100 cells. **All priors pass:** C++ (354 µs) and C
(379 µs) at the top; Python (74 ms) at the bottom. Java vs C# startup
asymmetry: Java's p001 cold-process clocks at 2.6 µs while C#'s clocks at
57 µs — a 20× spread between two JIT'd managed languages. **Fresh-process
faithfully exposes the .NET startup tax that the prior warm-bench model
hid.**

The libprimesieve C-library advantage on prime-counting problems (p007:
C/C++ at ~24 µs; Rust/ARM64/Zig at 178-258 µs) became visible as a real
gap. Not a language-speed difference — a library-choice difference. Worth
recording: the bench measures the system a user actually invokes, including
external libraries linked in. That's the right thing to measure, but
"language X is N× slower than Y" needs to be read with this asymmetry in
mind.

### Round 2 — scope=1-50

**Wall:** 8.6 minutes for 400 new cells. **Cross-lang answer agreement: zero
disagreements across 500 cells**, the strongest possible signal that 500
independent implementations all converged on the same answers. No
correctness regressions surfaced by the new measurement model.

**The big surprise:** ARM64 jumped to #1 (103.9 ms total). It contributed
only ~102 ms over the 40 new problems while C added 326 ms. The
explanation, visible in the Round 1 per-problem data: 9 of 10 problems
clocked at ≤4 ns for ARM64, essentially below clock resolution. Hand-rolled
asm on closed-form arithmetic problems compiles to one or two instructions
that finish faster than `clock_gettime` can measure. **The "ARM64 leads"
result here is more accurately read as "ARM64 has very fast closed-form
solutions to problems 1-50" — not a general statement of language speed.**

### Round 3 — scope=1-100 (original public scope)

**Wall:** 13.7 minutes for 500 new cells. **Still zero answer disagreements
across 1000 cells, zero failures.** Original public scope reached under the
new pipeline.

**The reversal:** ARM64 dropped from #1 to #6. Problems 51-100 added 1.485 s
to ARM64's total — *more* than they added to C (+0.97 s) or Zig (+0.955 s).
The hand-tuned-asm advantage was concentrated in problems 1-50 (closed-form
heavy). On more algorithmically complex problems, **LLVM's optimization of
C/C++/Rust/Zig source matches or beats hand-written asm.** This is the
finding worth pinning: assembly's edge is real but specific. It's not "asm
is faster than C"; it's "asm is faster than C *on problems where the
algorithm collapses to a few instructions*". For everything else, modern
compilers are already finding the same optimizations.

**Zig at #1 with 1.085 s** is the comptime story crystallizing. Many PE
problems have fixed inputs (the canonical form), and Zig's `comptime`
evaluates the answer at compile time. The runtime then just returns a
literal. This validates the earlier `project_zig_comptime_bias_finding`
observation — Zig's lead is real but it's measuring "what fraction of
computation can move to compile time," which is a different axis than
"language speed."

**Python:C ratio = 30×** at scope=1-100, well within the 10-50× priors
range. About 8% of Python's total is just process startup (~30 ms per
invocation × 100 invocations); most of the slowness is algorithmic.

**Per-problem wall time is creeping up across rounds.** R1 at 9 s/problem
(includes one-time fixed costs); R2 at 13 s/problem; R3 at 16 s/problem.
Later problems are mathematically harder; the cost curve scales with
difficulty, not just count. Worth noting when planning future rounds.

### Round 4 — scope=1-200 (publish target)

Round 4 didn't complete in a single orchestrator run. The harness's
background-task ceiling (~50-60 min wall) killed the orchestrator mid-run
with **4 of 10 langs fully done** (arm64, c, go, zig at 200/200) and **6
langs still at 100/200** (cpp, csharp, java, javascript, python, rust). cpp
was 69/100 through problems 101-200 when killed; because `euler-bench
per-iter --write` writes atomically at end-of-lang, none of those 69
measurements landed in the DB. Clean partial state — no half-written rows,
just lang-level granular completion.

**The published Round-4 RESULTS.md is honest about this:** the per-lang
headline shows `100/200 problems, missing 100` for the incomplete langs
alongside `200/200` for the four complete ones. Partial coverage is a
supported render mode — when a (lang, problem) cell is unmeasured, the
grid renders it as "missing" and the ranking sums only what was measured.
The 4-langs-at-200 vs 6-langs-at-100 asymmetry is itself a meaningful data
point: **we don't have to insist on uniform coverage to publish meaningfully
— different langs can be at different scopes, and the report renders that
honestly.** Subsequent mini-rounds bring the incomplete langs up
incrementally (101-125, 126-150, etc.) — each is a 20-30 min run instead of
the 60+ min that ran into the harness ceiling.

**Surfacing real source-header bugs:** Round 4 also revealed two genuine
correctness regressions that the old warm-bench harness never noticed —
C p151 and C p199. Both are scale-encoded decimal-answer problems where the
`// Answer:` source header was written as the decimal form (`0.464399`)
rather than the encoded integer form the code actually returns (`464399`).
The new fresh-process bench's strict canonical comparison correctly rejects
these with `status='fail'`. The other 5 incomplete langs likely have the
same bug at the same problems — predictable cross-lang signature, fixable
in one pass when their catch-up runs.

**Cost-of-discovery:** had the orchestrator run all 2000 cells uninterrupted,
we'd have discovered the C header bugs alongside everything else. Because it
stopped at 1400 cells, we found them earlier with cleaner attribution and
can pre-fix them before completing the remaining langs.

### Methodology meta-lesson

**Run the regen between every chunk, not just at the end.** The
10→50→100→200 cadence caught the `nullableInt64(0) → NULL` bug at Round 1
(100 cells), let us fix it before Rounds 2-4 captured the same bad
semantics on 1900 more cells. The cost of regenerating reports between
rounds (~10 seconds + a 1-line scope override) is trivial compared to the
cost of catching a measurement-semantic bug after a full 2000-cell
investment.

### Round 4a — mini-round (101-125 catch-up, 6 langs)

Rather than re-run the entire Round 4 after the harness-ceiling kill, the catch-up
went as a small mini-round: `--problems 101-125 --langs cpp,csharp,java,javascript,python,rust`.
Landed in 20.9 min wall (python alone took 16.2 min — the rest were 30-70s each).
The harness held this time — proof that staying well under 30 min wall is the
operationally safe zone for a single bg-task run.

**Cross-lang file-loading anti-pattern surfaced.** Java and Python both failed
the SAME three problems — p102, p105, p107 — with the same shape (file not
found / Traceback on a data-file load). These are PE's data-file problems
(`p102_triangles.txt`, `p105_sets.txt`, `p107_network.txt`). The source code
loads the file via cwd-relative path; the new bench runs from a different
working directory than the old per-repo `benchmark.sh` did, so the load
fails. This is the same anti-pattern flagged earlier in 51-100 (the Java
p081 fake-fallback, the C p089 absolute-path note in "Scaling to 200
Problems"). Fix is per-source: use absolute paths derived from `__file__`
(Python) / `getClass().getResource()` (Java) — predictable cross-lang
signature, fixable in a single coordinated pass.

### Methodology refinement — common-set rendering

The first regen at scope=1-200 with partial coverage exposed a chart bug:
total-time bars summed only over each lang's measured cells. Partial-coverage
langs (100/200) showed artificially low totals compared to fully-covered langs
(200/200), and the ranking visually implied "C++ is 50× faster than ARM64"
when really C++ just had half the problems counted.

**The fix: common-set rendering.** The ranking table and bar chart now sum
over the set of problems where ALL 10 langs have status='pass' — an
apples-to-apples surface that's stable under partial coverage. Per-lang
individual coverage is shown separately. This is a stop-gap; the
architecturally correct answer is tier-aware rendering (the existing
`data/tiers.json` model already encodes which langs are in scope for which
problem range). Once a lang intentionally stops (e.g., ARM64 capping at
tier 1 while CPP/Go extend to tier 2), common-set across all 10 collapses to
the stopped lang's ceiling — wrong behavior. Tier-aware rendering would
maintain meaningful comparisons within each tier independently. **Filed as
a follow-up task; current common-set fix is good enough until we have a lang
that intentionally stops.**
