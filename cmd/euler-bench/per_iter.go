// per_iter — process-per-iteration benchmark.
//
// What it measures: the cost a user actually pays when invoking a bench
// binary as a fresh OS process N times.  Models the "cron-job at scale"
// or shell loop scenario:
//
//	for i in $(seq 1 N); do time ./main_bench; done
//
// Each invocation is independent: OS-enforced process boundaries clear all
// in-process state.  Each binary internally times its single solve() call
// using the language's native clock and prints `RESULT|time_ns=N|answer=A`.
//
// Per (lang, problem):
//  1. Build the binary using existing Lang.BuildArgs adapters.
//  2. Run N times.  For each invocation:
//     - parse RESULT|time_ns=N|answer=A from stdout (internal timing),
//     - record wall via Go's monotonic clock as a sanity check.
//  3. Aggregate time_ns: median, min, max across the N samples.
//  4. Report.
//
// Usage:
//
//	euler-bench per-iter --lang cpp --problems 1-100 --iters 10
//	euler-bench per-iter --lang all --problems 1-100
//	euler-bench per-iter --lang cpp,c,arm64,rust --problems 7,10 --iters 30
package main

import (
	"bytes"
	"context"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"time"
)

// RESULT line: time_ns and answer both required.  Single canonical sentinel
// across all 10 languages — see JOURNEY.md "Single-Call Harness" chapter.
var resultRe = regexp.MustCompile(`(?m)^RESULT\|time_ns=(\d+)\|answer=(.+)$`)

type perIterResult struct {
	Lang          string
	Problem       string
	Answer        string
	TimeSamplesNs []int64 // internal time_ns from RESULT line
	WallSamplesNs []int64 // Go-perceived wall (process spawn → exit), sanity-check secondary
	CompileTimeNs int64   // single measurement: wall time of the build phase
	PeakRSSBytes  int64   // max RSS observed across iters (bytes on Darwin, KB on Linux — see captureRSS)
	CPUSamplesNs  []int64 // rusage user+sys per sample (process-contract gate input)
	LoadAvgMax    float64 // max 1-min system loadavg observed across samples
	BuildErr      string
	RunErr        string
}

func (r *perIterResult) timeMedianNs() int64 { return medianI64(r.TimeSamplesNs) }
func (r *perIterResult) timeMinNs() int64    { return minI64(r.TimeSamplesNs) }
func (r *perIterResult) timeMaxNs() int64    { return maxI64(r.TimeSamplesNs) }
func (r *perIterResult) wallMedianNs() int64 { return medianI64(r.WallSamplesNs) }
func (r *perIterResult) cpuMedianNs() int64  { return medianI64(r.CPUSamplesNs) }

// corroborated reports whether some pair of time samples agrees within 5%
// (METHODOLOGY.md §3). With 1 sample it is vacuously false; callers only
// consult it when the sampling rule has finished.
func (r *perIterResult) corroborated() bool { return pairAgrees(r.TimeSamplesNs) }

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

// Sampling rule (METHODOLOGY.md §3): run 2 fresh-process samples; if they
// agree within corroborationFrac, accept and stop. Otherwise add samples one
// at a time up to the cap (default 3) and take the median. If no two samples
// agree even then, the row is still written but carries a no-corroboration
// warning — on a deterministic single-threaded program, mutually inconsistent
// samples indicate a broken measurement environment, which is fixed by
// investigating and re-benching, not by sampling further. Grounding: SPEC CPU
// reportable runs = 3/median; Phoronix = 3 + bounded variance escalation.
const corroborationFrac = 0.05

// pairAgrees reports whether any two samples lie within corroborationFrac of
// each other (sorted adjacent-pair check).
func pairAgrees(samples []int64) bool {
	if len(samples) < 2 {
		return false
	}
	s := append([]int64(nil), samples...)
	sort.Slice(s, func(i, j int) bool { return s[i] < s[j] })
	for i := 1; i < len(s); i++ {
		if float64(s[i]-s[i-1]) <= corroborationFrac*float64(s[i-1]) {
			return true
		}
	}
	return false
}

// sampleLoadavg returns the 1-minute system load average, or 0 on failure.
// Recorded per sample as the environment audit trail (METHODOLOGY.md §4).
func sampleLoadavg() float64 {
	out, err := exec.Command("sysctl", "-n", "vm.loadavg").Output()
	if err != nil {
		return 0
	}
	fields := strings.Fields(strings.Trim(strings.TrimSpace(string(out)), "{}"))
	if len(fields) == 0 {
		return 0
	}
	v, err := strconv.ParseFloat(fields[0], 64)
	if err != nil {
		return 0
	}
	return v
}

// runPerIterOne builds (lang, problem) and runs the binary up to `iters`
// times under the corroborate-or-tie-break sampling rule; `fixed` forces
// exactly `iters` samples. The recorded sample count is always the honest n.
func runPerIterOne(lang *Lang, baseDir, problem string, iters int, fixed bool) *perIterResult {
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

	// Build. Wrap the whole phase with a wall-clock timer so we can report
	// per-problem compile cost in the published data (was previously a
	// per-repo benchmark.sh-only metric).
	buildStart := time.Now()
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
	} else if lang.BatchBuild != nil {
		if failed := lang.BatchBuild(repoDir, []string{problem}); len(failed) > 0 {
			r.BuildErr = fmt.Sprintf("BatchBuild reported failures: %v", failed)
			return r
		}
	}
	r.CompileTimeNs = time.Since(buildStart).Nanoseconds()

	defer cleanup(lang, probDir)

	runBin, runArgs := lang.RunArgs(repoDir, probDir)

	// Per-problem hard timeout (tiered by series; EULER_BENCH_MAX_SECS overrides,
	// for testing the kill path without waiting a full tier budget).
	timeoutSecs, _ := strconv.Atoi(benchTimeoutSecs(problem))
	if ov := os.Getenv("EULER_BENCH_MAX_SECS"); ov != "" {
		if v, e := strconv.Atoi(ov); e == nil && v > 0 {
			timeoutSecs = v
		}
	}

	// Run N times in fresh processes.
	for i := 0; i < iters; i++ {
		fullArgs := append([]string{runBin}, runArgs...)
		// Hard deadline with own process group + group-SIGKILL on expiry: a runaway
		// solve (and anything it spawned) can't survive holding the stdout pipe open
		// and deadlock cmd.Run() — the p519 15.8h hang (2026-07-04). WaitDelay forces
		// the pipes closed so Run() always returns even if a child lingers.
		ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeoutSecs)*time.Second)
		cmd := exec.CommandContext(ctx, fullArgs[0], fullArgs[1:]...)
		cmd.Dir = workDir
		cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
		cmd.Cancel = func() error {
			if cmd.Process != nil {
				return syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL) // negative pid = whole group
			}
			return nil
		}
		cmd.WaitDelay = 10 * time.Second
		var stdout, stderr bytes.Buffer
		cmd.Stdout = &stdout
		cmd.Stderr = &stderr

		t0 := time.Now()
		err := cmd.Run()
		wall := time.Since(t0).Nanoseconds()
		timedOut := ctx.Err() == context.DeadlineExceeded
		cancel()

		// Capture max RSS + CPU time for this subprocess (cmd.ProcessState is
		// non-nil after Run returns regardless of err). RSS: worst-case
		// footprint across iters. CPU: user+sys per sample — the process-
		// contract gate compares it against the reported time_ns
		// (METHODOLOGY.md §2). Darwin reports Maxrss in bytes; Linux in KB.
		var sampleCPUNs int64
		if cmd.ProcessState != nil {
			if rusage, ok := cmd.ProcessState.SysUsage().(*syscall.Rusage); ok {
				rss := int64(rusage.Maxrss)
				if runtime.GOOS == "linux" {
					rss *= 1024
				}
				if rss > r.PeakRSSBytes {
					r.PeakRSSBytes = rss
				}
				sampleCPUNs = rusage.Utime.Nano() + rusage.Stime.Nano()
			}
		}
		if la := sampleLoadavg(); la > r.LoadAvgMax {
			r.LoadAvgMax = la
		}

		if err != nil {
			if timedOut {
				r.RunErr = fmt.Sprintf("timeout: exceeded %ds budget", timeoutSecs)
				break // a runaway won't corroborate; don't burn more budget retrying
			}
			r.RunErr = fmt.Sprintf("iter %d: %v (stderr: %s)", i+1, err, truncate(stderr.String(), 80))
			continue
		}

		// Parse RESULT line — the single source for time_ns + answer.
		rm := resultRe.FindSubmatch(stdout.Bytes())
		if rm == nil {
			r.RunErr = fmt.Sprintf("iter %d: no RESULT line", i+1)
			continue
		}
		timeNs, _ := strconv.ParseInt(string(rm[1]), 10, 64)
		r.Answer = strings.TrimSpace(string(rm[2]))
		r.TimeSamplesNs = append(r.TimeSamplesNs, timeNs)
		r.WallSamplesNs = append(r.WallSamplesNs, wall)
		r.CPUSamplesNs = append(r.CPUSamplesNs, sampleCPUNs)

		if !fixed && len(r.TimeSamplesNs) >= 2 && pairAgrees(r.TimeSamplesNs) {
			break
		}
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
	langFilter := fs.String("lang", "", "comma-separated lang keys (or 'all')")
	probSpec := fs.String("problems", "1-10", "problem range/list: '1-10', '1,3,7', '1'")
	iters := fs.Int("iters", 3, "sample CAP per problem. Rule (METHODOLOGY.md §3): run 2; if within 5% done; "+
		"else tie-break samples up to this cap, median, and a no-corroboration warning if still inconsistent")
	fixed := fs.Bool("fixed", false, "run exactly -iters samples with no early stop (diagnostics only)")
	write := fs.Bool("write", false,
		"upsert results into data/bench-private.db (the SQLite SSOT, gitignored). "+
			"Two tables: runs (latest per lang+problem) + run_history (append-only). "+
			"Existing rows for unmeasured problems are preserved.")
	if err := fs.Parse(args); err != nil {
		os.Exit(2)
	}

	if *iters < 1 {
		fmt.Fprintf(os.Stderr, "--iters must be >= 1 (got %d); bumping to 1\n", *iters)
		*iters = 1
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
			r := runPerIterOne(lang, baseDir, p, *iters, *fixed)
			grid[key][p] = r
			switch {
			case r.BuildErr != "":
				fmt.Printf("    p%s  BUILD FAIL: %s\n", p, r.BuildErr)
			case len(r.TimeSamplesNs) == 0:
				fmt.Printf("    p%s  NO DATA: %s\n", p, r.RunErr)
			default:
				fmt.Printf("    p%s  time-med=%8s  wall-med=%8s  (n=%d)\n",
					p, fmtNs(r.timeMedianNs()), fmtNs(r.wallMedianNs()), len(r.TimeSamplesNs))
			}
		}
	}

	// Cross-language summary
	fmt.Println()
	fmt.Println(strings.Repeat("=", 100))
	fmt.Println("CROSS-LANG SUMMARY")
	fmt.Println(strings.Repeat("=", 100))
	fmt.Println("  time-med:  median time_ns across N fresh-process invocations (internal clock)")
	fmt.Println("  wall-med:  median Go-perceived wall (process spawn → exit), sanity-check secondary")
	fmt.Println()

	for _, p := range problems {
		fmt.Printf("\n  p%s:\n", p)
		fmt.Printf("    %-8s  %10s  %10s\n", "lang", "time-med", "wall-med")
		fmt.Printf("    %-8s  %10s  %10s\n", "--------", "----------", "----------")
		for _, k := range langKeys {
			r := grid[k][p]
			if r == nil {
				continue
			}
			if r.BuildErr != "" || len(r.TimeSamplesNs) == 0 {
				note := r.BuildErr
				if note == "" {
					note = r.RunErr
				}
				fmt.Printf("    %-8s  %s\n", k, truncate(note, 70))
				continue
			}
			fmt.Printf("    %-8s  %10s  %10s\n",
				k, fmtNs(r.timeMedianNs()), fmtNs(r.wallMedianNs()))
		}
	}

	// --write: persist results.
	if !*write {
		return
	}
	fmt.Println()
	fmt.Println(strings.Repeat("=", 100))
	fmt.Println("WRITE  (--write was specified)")
	fmt.Println(strings.Repeat("=", 100))

	totalMismatches := 0
	for _, key := range langKeys {
		lang := langByKey(key)
		if lang == nil {
			continue
		}
		var results []*perIterResult
		for _, p := range problems {
			if r, ok := grid[key][p]; ok {
				results = append(results, r)
			}
		}
		mismatches, err := writeBenchResults(lang, baseDir, results)
		if err != nil {
			fmt.Fprintf(os.Stderr, "  %s: WRITE FAILED: %v\n", key, err)
			continue
		}
		fmt.Printf("  %s: wrote %d rows to data/bench-private.db  (%d mismatches)\n",
			key, len(results), mismatches)
		totalMismatches += mismatches
	}
	if totalMismatches > 0 {
		fmt.Println()
		fmt.Printf("⚠  %d answer mismatches across all langs — see data files' `error` fields.\n", totalMismatches)
		os.Exit(1)
	}
}
