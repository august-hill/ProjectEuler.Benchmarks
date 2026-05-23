// per_iter — process-per-iteration benchmark.
//
// What it measures: the cost a user actually pays when invoking a bench
// binary as a fresh OS process N times.  Models the "cron-job at scale"
// or shell loop scenario:
//
//	for i in $(seq 1 N); do time ./main_bench; done
//
// Each invocation is independent: OS-enforced process boundaries clear all
// in-process state.  No language-internal caches (primesieve, Rust
// OnceLock, Python @lru_cache) carry over.  No harness warmup amortizes
// startup.  This is the honest cross-language metric for the "CLI utility"
// or "REST endpoint without warm cache" use case.
//
// Compared against the existing in-process warm metric (the BENCHMARK
// line's time_ns), which represents steady-state cost within one
// long-running process — relevant for daemon/server scenarios but
// systematically under-reports per-invocation cost when language idioms
// (lazy statics, lib-internal caches) are at play.
//
// Per (lang, problem):
//  1. Build the binary using existing Lang.BuildArgs adapters.
//  2. Run N times.  For each invocation:
//     - measure wall via Go's monotonic clock (time.Now → time.Since),
//     - parse COLDSTART line from stdout (binary's self-reported first-call cost),
//     - parse BENCHMARK line (binary's self-reported steady-state warm cost).
//  3. Aggregate cold + wall: median, min, max across the N samples.
//  4. Report.
//
// Usage:
//
//	euler-bench per-iter --lang cpp --problems 1-10 --iters 10
//	euler-bench per-iter --lang all --problems 1-10
//	euler-bench per-iter --lang cpp,c,arm64,rust --problems 7,10 --iters 30
package main

import (
	"bytes"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

// COLDSTART line: time_ns required; answer optional (only langs whose
// harness is patched to emit it will have it).
var coldStartRe = regexp.MustCompile(`(?m)^COLDSTART\|time_ns=(\d+)(\|answer=(.+))?$`)

// BENCHMARK line: existing format, answer and time_ns both required.
var benchmarkRe = regexp.MustCompile(`(?m)^BENCHMARK\|problem=\d+\|answer=([^|]+)\|time_ns=(\d+)`)

type perIterResult struct {
	Lang          string
	Problem       string
	Answer        string
	InProcWarmNs  int64
	ColdSamplesNs []int64
	WallSamplesNs []int64
	BuildErr      string
	RunErr        string
}

func (r *perIterResult) coldMedianNs() int64 { return medianI64(r.ColdSamplesNs) }
func (r *perIterResult) coldMinNs() int64    { return minI64(r.ColdSamplesNs) }
func (r *perIterResult) coldMaxNs() int64    { return maxI64(r.ColdSamplesNs) }
func (r *perIterResult) wallMedianNs() int64 { return medianI64(r.WallSamplesNs) }

// divergence: cold-median / in-process-warm.  >1 means the warm metric
// under-reports per-invocation cost.  Used to surface language-internal
// caches that survive across in-process warm iterations but not across
// processes.
func (r *perIterResult) divergence() float64 {
	if r.InProcWarmNs <= 0 {
		return 0
	}
	return float64(r.coldMedianNs()) / float64(r.InProcWarmNs)
}

func medianI64(s []int64) int64 {
	if len(s) == 0 {
		return 0
	}
	cp := append([]int64(nil), s...)
	sort.Slice(cp, func(i, j int) bool { return cp[i] < cp[j] })
	return cp[len(cp)/2]
}
func minI64(s []int64) int64 {
	if len(s) == 0 {
		return 0
	}
	m := s[0]
	for _, v := range s[1:] {
		if v < m {
			m = v
		}
	}
	return m
}
func maxI64(s []int64) int64 {
	if len(s) == 0 {
		return 0
	}
	m := s[0]
	for _, v := range s[1:] {
		if v > m {
			m = v
		}
	}
	return m
}

// fmtNs picks the right unit for human-readable nanoseconds.
func fmtNs(ns int64) string {
	switch {
	case ns < 1_000:
		return fmt.Sprintf("%dns", ns)
	case ns < 1_000_000:
		return fmt.Sprintf("%.1fµs", float64(ns)/1_000)
	case ns < 1_000_000_000:
		return fmt.Sprintf("%.1fms", float64(ns)/1_000_000)
	default:
		return fmt.Sprintf("%.2fs", float64(ns)/1_000_000_000)
	}
}

func parseProblemSpec(spec string) []string {
	var out []string
	for _, part := range strings.Split(spec, ",") {
		part = strings.TrimSpace(part)
		if strings.Contains(part, "-") {
			bits := strings.SplitN(part, "-", 2)
			lo, e1 := strconv.Atoi(strings.TrimSpace(bits[0]))
			hi, e2 := strconv.Atoi(strings.TrimSpace(bits[1]))
			if e1 != nil || e2 != nil {
				continue
			}
			for i := lo; i <= hi; i++ {
				out = append(out, fmt.Sprintf("%03d", i))
			}
		} else {
			n, err := strconv.Atoi(part)
			if err == nil {
				out = append(out, fmt.Sprintf("%03d", n))
			}
		}
	}
	return out
}

// runPerIterOne builds (lang, problem) and runs the binary `iters` times.
// Returns aggregate timing data and any error encountered.
func runPerIterOne(lang *Lang, baseDir, problem string, iters int) *perIterResult {
	r := &perIterResult{Lang: lang.Key, Problem: problem}

	repoDir := filepath.Join(baseDir, lang.Repo)

	var probDir, workDir string
	if lang.SrcSubdir {
		probDir = filepath.Join(repoDir, "problem_"+problem)
		workDir = probDir
		if _, err := os.Stat(probDir); err != nil {
			r.BuildErr = "no problem dir"
			return r
		}
	} else {
		// Python — flat structure, work from repoDir
		probDir = filepath.Join(repoDir, "problem_"+problem)
		workDir = repoDir
		// For Python the "src file" is at repoDir/problem_NNN.py
		srcFile := filepath.Join(repoDir, "problem_"+problem+".py")
		if _, err := os.Stat(srcFile); err != nil {
			r.BuildErr = "no problem_NNN.py"
			return r
		}
	}

	// PreBuild hook (Java: copy Bench.java)
	if lang.PreBuild != nil {
		if err := lang.PreBuild(repoDir, probDir, problem); err != nil {
			r.BuildErr = "prebuild: " + err.Error()
			return r
		}
	}

	// Build
	if lang.BuildArgs != nil {
		argSets := lang.BuildArgs(repoDir, probDir)
		if lang.SequentialBuild {
			for _, args := range argSets {
				cmd := exec.Command(args[0], args[1:]...)
				cmd.Dir = probDir
				cmd.Stderr = nil
				cmd.Stdout = nil
				if err := cmd.Run(); err != nil {
					r.BuildErr = "seq-build step failed"
					return r
				}
			}
		} else {
			if err := tryBuild(argSets, probDir); err != nil {
				r.BuildErr = "build: " + err.Error()
				return r
			}
		}
	}

	// Cleanup is run on return regardless of outcome.
	defer cleanup(lang, probDir)

	// Get the run command
	runBin, runArgs := lang.RunArgs(repoDir, probDir)

	// Run N times
	for i := 0; i < iters; i++ {
		fullArgs := append([]string{runBin}, runArgs...)
		cmd := exec.Command(fullArgs[0], fullArgs[1:]...)
		cmd.Dir = workDir
		var stdout, stderr bytes.Buffer
		cmd.Stdout = &stdout
		cmd.Stderr = &stderr

		t0 := time.Now()
		err := cmd.Run()
		wall := time.Since(t0).Nanoseconds()

		if err != nil {
			r.RunErr = fmt.Sprintf("iter %d: %v (stderr: %s)", i+1, err, truncate(stderr.String(), 80))
			continue
		}

		// Parse the BENCHMARK line (always required — that's the source of truth
		// for the answer + warm time)
		bm := benchmarkRe.FindSubmatch(stdout.Bytes())
		if bm == nil {
			r.RunErr = fmt.Sprintf("iter %d: no BENCHMARK line", i+1)
			continue
		}
		warmNs, _ := strconv.ParseInt(string(bm[2]), 10, 64)
		r.InProcWarmNs = warmNs
		r.Answer = strings.TrimSpace(string(bm[1]))

		// Parse COLDSTART (optional — only patched harnesses emit answer;
		// time_ns is always there).  Record the time even if answer is absent.
		cs := coldStartRe.FindSubmatch(stdout.Bytes())
		if cs == nil {
			r.RunErr = fmt.Sprintf("iter %d: no COLDSTART line", i+1)
			continue
		}
		coldNs, _ := strconv.ParseInt(string(cs[1]), 10, 64)
		r.ColdSamplesNs = append(r.ColdSamplesNs, coldNs)
		r.WallSamplesNs = append(r.WallSamplesNs, wall)
	}

	return r
}

func truncate(s string, n int) string {
	s = strings.ReplaceAll(s, "\n", " ")
	if len(s) <= n {
		return s
	}
	return s[:n] + "…"
}

// cmdPerIter is the entry point for the `per-iter` subcommand.
func cmdPerIter(args []string) {
	fs := flag.NewFlagSet("per-iter", flag.ExitOnError)
	langFilter := fs.String("lang", "", "comma-separated lang keys (or 'all') — default: all configured")
	probSpec := fs.String("problems", "1-10", "problem range/list: '1-10', '1,3,7', '1'")
	iters := fs.Int("iters", 10, "fresh-process invocations per problem")
	if err := fs.Parse(args); err != nil {
		os.Exit(2)
	}

	var langKeys []string
	if *langFilter == "" || *langFilter == "all" {
		langKeys = allLangKeys()
	} else {
		langKeys = parseLangs(*langFilter)
	}
	problems := parseProblemSpec(*probSpec)
	if len(problems) == 0 {
		fmt.Fprintf(os.Stderr, "no problems parsed from %q\n", *probSpec)
		os.Exit(2)
	}

	baseDir := findBaseDir()

	fmt.Printf("=== euler-bench per-iter  langs=%v  problems=%v  iters=%d\n\n",
		langKeys, problems, *iters)

	grid := make(map[string]map[string]*perIterResult)
	for _, key := range langKeys {
		lang := langByKey(key)
		if lang == nil {
			continue
		}
		grid[key] = make(map[string]*perIterResult)
		fmt.Printf("--- %s:\n", lang.Display)
		for _, p := range problems {
			r := runPerIterOne(lang, baseDir, p, *iters)
			grid[key][p] = r
			switch {
			case r.BuildErr != "":
				fmt.Printf("    p%s  BUILD FAIL: %s\n", p, r.BuildErr)
			case len(r.ColdSamplesNs) == 0:
				fmt.Printf("    p%s  NO DATA: %s\n", p, r.RunErr)
			default:
				fmt.Printf("    p%s  warm=%7s  cold-med=%7s  wall-med=%7s  div=%6.1fx  (n=%d)\n",
					p, fmtNs(r.InProcWarmNs), fmtNs(r.coldMedianNs()),
					fmtNs(r.wallMedianNs()), r.divergence(), len(r.ColdSamplesNs))
			}
		}
	}

	// Cross-language summary
	fmt.Println()
	fmt.Println(strings.Repeat("=", 100))
	fmt.Println("CROSS-LANG SUMMARY")
	fmt.Println(strings.Repeat("=", 100))
	fmt.Println("  warm:      in-process steady state (BENCHMARK line time_ns)")
	fmt.Println("  cold-med:  median COLDSTART across N fresh-process invocations")
	fmt.Println("  wall-med:  median Go-perceived wall (process spawn → exit)")
	fmt.Println("  div:       cold-med / warm — divergence between metrics")
	fmt.Println()

	for _, p := range problems {
		fmt.Printf("\n  p%s:\n", p)
		fmt.Printf("    %-8s  %10s  %10s  %10s  %7s\n",
			"lang", "warm", "cold-med", "wall-med", "div")
		fmt.Printf("    %-8s  %10s  %10s  %10s  %7s\n",
			"--------", "----------", "----------", "----------", "-------")
		for _, k := range langKeys {
			r := grid[k][p]
			if r == nil {
				continue
			}
			if r.BuildErr != "" || len(r.ColdSamplesNs) == 0 {
				note := r.BuildErr
				if note == "" {
					note = r.RunErr
				}
				fmt.Printf("    %-8s  %s\n", k, truncate(note, 70))
				continue
			}
			fmt.Printf("    %-8s  %10s  %10s  %10s  %6.1fx\n",
				k, fmtNs(r.InProcWarmNs), fmtNs(r.coldMedianNs()),
				fmtNs(r.wallMedianNs()), r.divergence())
		}
	}

	// Highlight notable divergences
	fmt.Println()
	fmt.Println(strings.Repeat("=", 100))
	fmt.Println("NOTABLE DIVERGENCES (cold-median / in-process warm > 3×)")
	fmt.Println(strings.Repeat("=", 100))
	notable := false
	for _, k := range langKeys {
		for _, p := range problems {
			r := grid[k][p]
			if r == nil || len(r.ColdSamplesNs) == 0 || r.InProcWarmNs <= 0 {
				continue
			}
			if r.divergence() > 3.0 {
				notable = true
				hidden := r.coldMedianNs() - r.InProcWarmNs
				fmt.Printf("  %-8s p%s  warm=%-9s cold-med=%-9s  div=%4.1fx  hides %s of real cost\n",
					k, p, fmtNs(r.InProcWarmNs), fmtNs(r.coldMedianNs()),
					r.divergence(), fmtNs(hidden))
			}
		}
	}
	if !notable {
		fmt.Println("  (none)")
	}
}
