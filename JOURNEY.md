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

Every solution in this project was generated by Claude Opus 4.6. This raises its own questions:
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

Total: **1,800 solution files** across 10 repositories, all generated by Claude Opus 4.6 and Claude Sonnet 4.6, with human architectural guidance and verification.

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

This validates the benchmark's core claim: when the algorithm is held constant, language choice produces a 2-6x performance spread, while algorithm choice (as demonstrated by the problem 173 sqrt fix) produces 1000x+ differences.
