package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"runtime"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

// BenchmarkResults is the top-level JSON structure (compatible with aggregate.py).
type BenchmarkResults struct {
	Language  string                    `json:"language"`
	Platform  string                    `json:"platform"`
	Compiler  string                    `json:"compiler"`
	Timestamp string                    `json:"timestamp"`
	Problems  map[string]ProblemResult  `json:"problems"`
}

type ProblemResult struct {
	Answer      json.Number `json:"answer,omitempty"`
	TimeNs      int64       `json:"time_ns,omitempty"`
	Iterations  int         `json:"iterations,omitempty"`
	Status      string      `json:"status"`
	Error       string      `json:"error,omitempty"`
	PeakRSS     int64       `json:"peak_rss_bytes,omitempty"`
	SourceLines int         `json:"source_lines,omitempty"`
	SourceBytes int         `json:"source_bytes,omitempty"`
}

var benchRe = regexp.MustCompile(`^BENCHMARK\|problem=(\d+)\|answer=([^|]+)\|time_ns=(\d+)\|iterations=(\d+)`)

type benchLine struct {
	Problem    string
	Answer     string
	TimeNs     int64
	Iterations int
}

func parseBenchmarkLine(stdout []byte) *benchLine {
	scanner := bufio.NewScanner(bytes.NewReader(stdout))
	for scanner.Scan() {
		m := benchRe.FindStringSubmatch(scanner.Text())
		if m != nil {
			timeNs, _ := strconv.ParseInt(m[3], 10, 64)
			iters, _ := strconv.Atoi(m[4])
			return &benchLine{Problem: m[1], Answer: m[2], TimeNs: timeNs, Iterations: iters}
		}
	}
	return nil
}

func parseRSS(stderr []byte) int64 {
	// macOS /usr/bin/time -l format: "  NNN  maximum resident set size"
	scanner := bufio.NewScanner(bytes.NewReader(stderr))
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if strings.Contains(line, "maximum resident set size") {
			fields := strings.Fields(line)
			if len(fields) > 0 {
				v, _ := strconv.ParseInt(fields[0], 10, 64)
				return v
			}
		}
	}
	return 0
}

func countSource(paths []string) (lines, bytes int) {
	for _, p := range paths {
		data, err := os.ReadFile(p)
		if err != nil {
			continue
		}
		bytes += len(data)
		lines += countLines(data)
	}
	return
}

func countLines(data []byte) int {
	n := 0
	for _, b := range data {
		if b == '\n' {
			n++
		}
	}
	if len(data) > 0 && data[len(data)-1] != '\n' {
		n++
	}
	return n
}

func getCompilerVersion(args []string) string {
	if len(args) == 0 {
		return "unknown"
	}
	cmd := exec.Command(args[0], args[1:]...)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return "unknown"
	}
	// Take first line
	line := strings.TrimSpace(strings.SplitN(string(out), "\n", 2)[0])
	return line
}

// discoverProblems finds all problem numbers in a repo.
func discoverProblems(lang *Lang, repoDir string) ([]string, error) {
	var nums []string
	if lang.SrcSubdir {
		entries, err := filepath.Glob(filepath.Join(repoDir, "problem_*"))
		if err != nil {
			return nil, err
		}
		for _, e := range entries {
			base := filepath.Base(e)
			if !strings.HasPrefix(base, "problem_") {
				continue
			}
			num := strings.TrimPrefix(base, "problem_")
			// Check source file exists
			src := filepath.Join(e, lang.SrcFile)
			if _, err := os.Stat(src); err == nil {
				nums = append(nums, num)
			}
		}
	} else {
		// Python: flat files problem_NNN.py
		entries, err := filepath.Glob(filepath.Join(repoDir, "problem_*.py"))
		if err != nil {
			return nil, err
		}
		for _, e := range entries {
			base := filepath.Base(e)
			num := strings.TrimPrefix(base, "problem_")
			num = strings.TrimSuffix(num, ".py")
			nums = append(nums, num)
		}
	}
	sort.Strings(nums)
	return nums, nil
}

func sourceFiles(lang *Lang, repoDir, problem string) []string {
	var files []string
	if lang.SrcSubdir {
		probDir := filepath.Join(repoDir, "problem_"+problem)
		files = append(files, filepath.Join(probDir, lang.SrcFile))
		if lang.ExtraSourceFiles != nil {
			files = append(files, lang.ExtraSourceFiles(probDir)...)
		}
	} else {
		files = append(files, filepath.Join(repoDir, "problem_"+problem+".py"))
	}
	return files
}

// runOneProblem builds, runs, and parses results for a single problem.
func runOneProblem(lang *Lang, repoDir, problem string) ProblemResult {
	probDir := filepath.Join(repoDir, "problem_"+problem)

	// PreBuild hook (Java: copy Bench.java)
	if lang.PreBuild != nil {
		if err := lang.PreBuild(repoDir, probDir, problem); err != nil {
			return ProblemResult{Status: "fail", Error: "prebuild: " + err.Error()}
		}
	}

	// Build
	if lang.BuildArgs != nil {
		argSets := lang.BuildArgs(repoDir, probDir)

		// Sequential build: run each step in order (ARM64: assemble, then link)
		if lang.SequentialBuild {
			for _, args := range argSets {
				cmd := exec.Command(args[0], args[1:]...)
				cmd.Dir = probDir
				if err := cmd.Run(); err != nil {
					return ProblemResult{Status: "fail", Error: "compile error"}
				}
			}
		} else {
			// Normal: try each arg set until one succeeds (C++ fallback)
			if err := tryBuild(argSets, probDir); err != nil {
				return ProblemResult{Status: "fail", Error: "compile error"}
			}
		}
	}

	// Get run command
	var runBin string
	var runArgs []string
	var workDir string

	if lang.RunArgs != nil {
		runBin, runArgs = lang.RunArgs(repoDir, probDir)
	}

	if lang.SrcSubdir {
		workDir = probDir
	} else {
		workDir = repoDir
	}

	// Execute with gtimeout + /usr/bin/time
	fullArgs := []string{"120", "/usr/bin/time", "-l", runBin}
	fullArgs = append(fullArgs, runArgs...)
	cmd := exec.Command("gtimeout", fullArgs...)
	cmd.Dir = workDir

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	_ = cmd.Run() // ignore exit code — timeout returns non-zero

	// Parse BENCHMARK line
	bl := parseBenchmarkLine(stdout.Bytes())
	if bl == nil {
		cleanup(lang, probDir)
		return ProblemResult{Status: "fail", Error: "no output"}
	}

	// Parse RSS
	rss := parseRSS(stderr.Bytes())

	// Source metrics
	srcFiles := sourceFiles(lang, repoDir, problem)
	sloc, sbytes := countSource(srcFiles)

	cleanup(lang, probDir)

	return ProblemResult{
		Answer:      json.Number(bl.Answer),
		TimeNs:      bl.TimeNs,
		Iterations:  bl.Iterations,
		Status:      "pass",
		PeakRSS:     rss,
		SourceLines: sloc,
		SourceBytes: sbytes,
	}
}

func cleanup(lang *Lang, probDir string) {
	for _, f := range lang.CleanFiles {
		os.Remove(filepath.Join(probDir, f))
	}
}

// runBenchmarks runs benchmarks for a language and returns results.
func runBenchmarks(lang *Lang, repoDir string, problems []string) *BenchmarkResults {
	compiler := getCompilerVersion(lang.CompilerCmd)

	res := &BenchmarkResults{
		Language:  lang.Key,
		Platform:  runtime.GOARCH,
		Compiler:  compiler,
		Timestamp: time.Now().UTC().Format("2006-01-02T15:04:05Z"),
		Problems:  make(map[string]ProblemResult),
	}

	fmt.Printf("  %s Benchmarks (%d problems)\n", lang.Display, len(problems))
	fmt.Printf("  Compiler: %s\n\n", compiler)

	// Batch build (C# only)
	failedSet := map[string]bool{}
	if lang.BatchBuild != nil {
		fmt.Printf("  Building all projects...\n")
		failed := lang.BatchBuild(repoDir, problems)
		for _, p := range failed {
			failedSet[p] = true
			res.Problems[p] = ProblemResult{Status: "fail", Error: "build failed"}
		}
		fmt.Printf("  Build complete. %d failures.\n\n", len(failed))
	}

	pass, fail := 0, 0
	for _, prob := range problems {
		if failedSet[prob] {
			fail++
			fmt.Printf("  FAIL %s: build failed\n", prob)
			continue
		}

		// Check source exists
		var srcPath string
		if lang.SrcSubdir {
			srcPath = filepath.Join(repoDir, "problem_"+prob, lang.SrcFile)
		} else {
			srcPath = filepath.Join(repoDir, "problem_"+prob+".py")
		}
		if _, err := os.Stat(srcPath); err != nil {
			fmt.Printf("  SKIP %s: no source\n", prob)
			continue
		}

		result := runOneProblem(lang, repoDir, prob)
		res.Problems[prob] = result

		if result.Status == "pass" {
			pass++
			fmt.Printf("  %s: answer=%s  time=%s  rss=%s  sloc=%d\n",
				prob, result.Answer, formatTime(result.TimeNs),
				formatBytes(result.PeakRSS), result.SourceLines)
		} else {
			fail++
			fmt.Printf("  FAIL %s: %s\n", prob, result.Error)
		}
	}

	fmt.Printf("\n  Results: %d passed, %d failed\n", pass, fail)
	return res
}

// mergeResults merges new results into old, preserving old entries not in new.
func mergeResults(old, new *BenchmarkResults) *BenchmarkResults {
	merged := &BenchmarkResults{
		Language:  new.Language,
		Platform:  new.Platform,
		Compiler:  new.Compiler,
		Timestamp: new.Timestamp,
		Problems:  make(map[string]ProblemResult),
	}
	for k, v := range old.Problems {
		merged.Problems[k] = v
	}
	for k, v := range new.Problems {
		merged.Problems[k] = v
	}
	return merged
}

func loadResults(path string) (*BenchmarkResults, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var res BenchmarkResults
	if err := json.Unmarshal(data, &res); err != nil {
		return nil, err
	}
	return &res, nil
}

func saveResults(path string, res *BenchmarkResults) error {
	data, err := json.MarshalIndent(res, "", "    ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0644)
}

// generateMarkdown creates a per-repo BENCHMARKS.md
func generateMarkdown(lang *Lang, res *BenchmarkResults, repoDir string) error {
	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("# %s Benchmarks\n\n", lang.Display))
	sb.WriteString(fmt.Sprintf("Platform: %s | Compiler: %s | Date: %s\n\n",
		res.Platform, res.Compiler, res.Timestamp[:10]))
	sb.WriteString("| # | Answer | Time | Peak RSS | SLOC |\n")
	sb.WriteString("|---|--------|------|----------|------|\n")

	// Sort problem keys
	keys := make([]string, 0, len(res.Problems))
	for k := range res.Problems {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	var totalNs int64
	count := 0
	for _, k := range keys {
		p := res.Problems[k]
		if p.TimeNs == 0 && p.Status != "pass" {
			continue
		}
		totalNs += p.TimeNs
		count++
		rssMB := float64(p.PeakRSS) / (1024 * 1024)
		sb.WriteString(fmt.Sprintf("| %s | %s | %s | %.1f MB | %d |\n",
			k, p.Answer, formatTime(p.TimeNs), rssMB, p.SourceLines))
	}

	sb.WriteString(fmt.Sprintf("\n## Summary\n\n"))
	sb.WriteString(fmt.Sprintf("- Problems benchmarked: %d\n", count))
	sb.WriteString(fmt.Sprintf("- Total time: %.2fs\n", float64(totalNs)/1e9))

	return os.WriteFile(filepath.Join(repoDir, "BENCHMARKS.md"), []byte(sb.String()), 0644)
}

func formatTime(ns int64) string {
	if ns < 1000 {
		return fmt.Sprintf("%d ns", ns)
	} else if ns < 1000000 {
		return fmt.Sprintf("%.1f us", float64(ns)/1000)
	} else if ns < 1000000000 {
		return fmt.Sprintf("%.1f ms", float64(ns)/1000000)
	}
	return fmt.Sprintf("%.2f s", float64(ns)/1000000000)
}

func formatBytes(b int64) string {
	if b == 0 {
		return "0B"
	}
	mb := float64(b) / (1024 * 1024)
	if mb < 1 {
		return fmt.Sprintf("%.0fKB", float64(b)/1024)
	}
	return fmt.Sprintf("%.1fMB", mb)
}

