# The Journey: Cross-Language Project Euler Benchmarks with Claude

## Origin Story

This project started as **claude-vs-euler** -- a challenge to see how effectively Claude (Anthropic's AI assistant) could solve Project Euler problems across multiple programming languages. The initial set covered Go, Rust, and C for problems 1-53, with solutions generated entirely by Claude Opus 4.6.

What began as a curiosity about AI-generated code quality evolved into something more ambitious: a systematic, cross-language performance benchmark suite spanning 9 languages and 100 problems.

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

## Project Structure

```
ccdev/
  ProjectEuler.C/           -- 100 problems, C (Clang)
  ProjectEuler.CPlusPlus/   -- 100 problems, C++ (Clang++)
  ProjectEuler.Rust/        -- 100 problems, Rust (rustc/LLVM)
  ProjectEuler.Go/          -- 100 problems, Go (gc)
  ProjectEuler.Java/        -- 100 problems, Java (JDK)
  ProjectEuler.CSharp/      -- 100 problems, C# (.NET)
  ProjectEuler.Python/      -- 100 problems, Python (CPython)
  ProjectEuler.JavaScript/  -- 100 problems, JavaScript (Node.js/V8)
  ProjectEuler.ARM64/       -- 100 problems, ARM64 Assembly + C
  ProjectEuler.Benchmarks/  -- Aggregation, analysis, and this document
  claude-vs-euler/          -- Archived: the original multi-language repo
```

```
ccdev/
  ProjectEuler.C/           -- 100 problems, C (Clang)
  ProjectEuler.CPlusPlus/   -- 100 problems, C++ (Clang++)
  ProjectEuler.Rust/        -- 100 problems, Rust (rustc/LLVM)
  ProjectEuler.Go/          -- 100 problems, Go (gc)
  ProjectEuler.Java/        -- 100 problems, Java (JDK)
  ProjectEuler.CSharp/      -- 100 problems, C# (.NET)
  ProjectEuler.Python/      -- 100 problems, Python (CPython)
  ProjectEuler.JavaScript/  -- 100 problems, JavaScript (Node.js/V8)
  ProjectEuler.ARM64/       -- 100 problems, ARM64 Assembly + C
  ProjectEuler.Benchmarks/  -- Aggregation, analysis, and this document
  claude-vs-euler/          -- Archived: the original multi-language repo
```
