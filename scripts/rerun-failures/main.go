// rerun-failures scans benchmark_results.json across all language repos,
// finds problems with status "fail", and re-runs their benchmarks.
// The merge logic in each repo's benchmark.sh handles updating the JSON.
//
// Usage:
//   go run .                     # re-run all failures across all languages
//   go run . --lang c,rust       # re-run failures in specific languages only
//   go run . --skip-parked       # skip known-parked problems (152,167,170,177,180,185,196)
//   go run . --dry-run           # show what would be run without executing
//   go run . --parallel          # run all languages concurrently
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"sync"
)

type BenchmarkResults struct {
	Language string                     `json:"language"`
	Problems map[string]ProblemResult   `json:"problems"`
}

type ProblemResult struct {
	Status string `json:"status"`
	Error  string `json:"error,omitempty"`
	Answer any    `json:"answer,omitempty"`
	TimeNs int64  `json:"time_ns,omitempty"`
}

var repos = map[string]string{
	"c":      "ProjectEuler.C",
	"cpp":    "ProjectEuler.CPlusPlus",
	"rust":   "ProjectEuler.Rust",
	"go":     "ProjectEuler.Go",
	"java":   "ProjectEuler.Java",
	"csharp": "ProjectEuler.CSharp",
	"js":     "ProjectEuler.JavaScript",
	"arm64":  "ProjectEuler.ARM64",
	"python": "ProjectEuler.Python",
}

var parkedProblems = map[string]bool{
	"152": true, "167": true, "170": true,
	"177": true, "180": true, "185": true, "196": true,
}

func main() {
	langFilter := flag.String("lang", "", "comma-separated languages to process (e.g. c,rust,go)")
	skipParked := flag.Bool("skip-parked", false, "skip parked problems (152,167,170,177,180,185,196)")
	dryRun := flag.Bool("dry-run", false, "show what would be run without executing")
	parallel := flag.Bool("parallel", false, "run all languages concurrently")
	flag.Parse()

	// Determine base directory (parent of ProjectEuler.Benchmarks)
	exe, err := os.Executable()
	if err != nil {
		// Fall back: assume we're run from within the Benchmarks repo
		exe, _ = os.Getwd()
	}
	baseDir := filepath.Dir(filepath.Dir(filepath.Dir(filepath.Dir(exe))))

	// If that doesn't look right, try relative to cwd
	if _, err := os.Stat(filepath.Join(baseDir, "ProjectEuler.C")); err != nil {
		cwd, _ := os.Getwd()
		// Walk up from cwd until we find ProjectEuler.C
		for d := cwd; d != "/"; d = filepath.Dir(d) {
			if _, err := os.Stat(filepath.Join(d, "ProjectEuler.C")); err == nil {
				baseDir = d
				break
			}
		}
	}

	// Build language list
	activeLangs := make([]string, 0)
	if *langFilter != "" {
		for _, l := range strings.Split(*langFilter, ",") {
			l = strings.TrimSpace(strings.ToLower(l))
			if _, ok := repos[l]; !ok {
				fmt.Fprintf(os.Stderr, "unknown language: %s\nvalid: c, cpp, rust, go, java, csharp, js, arm64, python\n", l)
				os.Exit(1)
			}
			activeLangs = append(activeLangs, l)
		}
	} else {
		for lang := range repos {
			activeLangs = append(activeLangs, lang)
		}
	}
	sort.Strings(activeLangs)

	// Scan for failures
	type rerunJob struct {
		lang     string
		repoDir  string
		problems []string
	}
	var jobs []rerunJob

	totalFailures := 0
	totalSkipped := 0

	for _, lang := range activeLangs {
		repoName := repos[lang]
		repoDir := filepath.Join(baseDir, repoName)
		resultsPath := filepath.Join(repoDir, "benchmark_results.json")

		data, err := os.ReadFile(resultsPath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "  %s: no benchmark_results.json, skipping\n", lang)
			continue
		}

		var results BenchmarkResults
		if err := json.Unmarshal(data, &results); err != nil {
			fmt.Fprintf(os.Stderr, "  %s: invalid JSON, skipping\n", lang)
			continue
		}

		var failures []string
		skipped := 0
		for prob, result := range results.Problems {
			if result.Status != "fail" {
				continue
			}
			if *skipParked && parkedProblems[prob] {
				skipped++
				continue
			}
			failures = append(failures, prob)
		}
		sort.Strings(failures)

		totalFailures += len(failures)
		totalSkipped += skipped

		if len(failures) == 0 {
			status := "all passing"
			if skipped > 0 {
				status = fmt.Sprintf("all passing (%d parked skipped)", skipped)
			}
			fmt.Printf("  %-8s %s\n", lang, status)
			continue
		}

		fmt.Printf("  %-8s %d failures: %s", lang, len(failures), strings.Join(failures, ","))
		if skipped > 0 {
			fmt.Printf(" (+%d parked skipped)", skipped)
		}
		fmt.Println()

		jobs = append(jobs, rerunJob{lang: lang, repoDir: repoDir, problems: failures})
	}

	fmt.Printf("\nTotal: %d failures to re-run", totalFailures)
	if totalSkipped > 0 {
		fmt.Printf(", %d parked skipped", totalSkipped)
	}
	fmt.Println()

	if len(jobs) == 0 {
		fmt.Println("Nothing to re-run.")
		return
	}

	if *dryRun {
		fmt.Println("\nDry run — commands that would be executed:")
		for _, job := range jobs {
			probList := strings.Join(job.problems, ",")
			fmt.Printf("  cd %s && ./benchmark.sh --problems %s\n", job.repoDir, probList)
		}
		return
	}

	fmt.Println()

	runJob := func(job rerunJob) {
		probList := strings.Join(job.problems, ",")
		fmt.Printf(">>> [%s] running %d problems: %s\n", job.lang, len(job.problems), probList)

		cmd := exec.Command("./benchmark.sh", "--problems", probList)
		cmd.Dir = job.repoDir
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr

		if err := cmd.Run(); err != nil {
			fmt.Fprintf(os.Stderr, ">>> [%s] benchmark.sh failed: %v\n", job.lang, err)
		} else {
			fmt.Printf(">>> [%s] done\n", job.lang)
		}
	}

	if *parallel {
		var wg sync.WaitGroup
		for _, job := range jobs {
			wg.Add(1)
			go func(j rerunJob) {
				defer wg.Done()
				runJob(j)
			}(job)
		}
		wg.Wait()
	} else {
		for _, job := range jobs {
			runJob(job)
		}
	}

	fmt.Println("\nDone. Results merged into each repo's benchmark_results.json.")
}
