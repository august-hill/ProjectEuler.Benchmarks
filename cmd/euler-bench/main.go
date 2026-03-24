// euler-bench is a unified benchmark tool for the Project Euler cross-language suite.
// It replaces 9 per-repo benchmark.sh scripts with a single Go binary.
//
// Usage:
//
//	euler-bench run [--lang c,rust] [--problems 001,002] [--parallel]
//	euler-bench failures [--skip-parked] [--dry-run] [--parallel]
//	euler-bench status [--lang c,rust]
//	euler-bench collect [--output-dir PATH]
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
)

var parkedProblems = map[string]bool{
	"152": true, "167": true, "170": true,
	"177": true, "180": true, "185": true, "196": true,
}

func findBaseDir() string {
	// Walk up from cwd until we find ProjectEuler.C
	cwd, _ := os.Getwd()
	for d := cwd; d != "/"; d = filepath.Dir(d) {
		if _, err := os.Stat(filepath.Join(d, "ProjectEuler.C")); err == nil {
			return d
		}
	}
	// Try parent of parent (if run from cmd/euler-bench/)
	return cwd
}

func parseLangs(filter string) []string {
	if filter == "" {
		return allLangKeys()
	}
	var result []string
	for _, l := range strings.Split(filter, ",") {
		l = strings.TrimSpace(strings.ToLower(l))
		if langByKey(l) == nil {
			fmt.Fprintf(os.Stderr, "unknown language: %s\nvalid: %s\n", l, strings.Join(allLangKeys(), ", "))
			os.Exit(1)
		}
		result = append(result, l)
	}
	return result
}

func main() {
	if len(os.Args) < 2 {
		printUsage()
		os.Exit(1)
	}

	switch os.Args[1] {
	case "run":
		cmdRun(os.Args[2:])
	case "failures":
		cmdFailures(os.Args[2:])
	case "status":
		cmdStatus(os.Args[2:])
	case "collect":
		cmdCollect(os.Args[2:])
	case "help", "--help", "-h":
		printUsage()
	default:
		fmt.Fprintf(os.Stderr, "unknown command: %s\n", os.Args[1])
		printUsage()
		os.Exit(1)
	}
}

func printUsage() {
	fmt.Println(`euler-bench — unified benchmark tool for Project Euler cross-language suite

Commands:
  run        Build and benchmark solutions
  failures   Re-run failed benchmarks
  status     Show pass/fail counts per language
  collect    Copy results to Benchmarks/data/ for aggregation

Run "euler-bench <command> --help" for command-specific flags.`)
}

func cmdRun(args []string) {
	fs := flag.NewFlagSet("run", flag.ExitOnError)
	langFilter := fs.String("lang", "", "comma-separated languages (default: all)")
	probFilter := fs.String("problems", "", "comma-separated problem numbers (default: all)")
	parallel := fs.Bool("parallel", false, "run languages concurrently")
	noMerge := fs.Bool("no-merge", false, "don't merge with existing results")
	noMarkdown := fs.Bool("no-markdown", false, "skip BENCHMARKS.md generation")
	fs.Parse(args)

	baseDir := findBaseDir()
	langs := parseLangs(*langFilter)

	var probList []string
	if *probFilter != "" {
		probList = strings.Split(*probFilter, ",")
	}

	runOne := func(langKey string) {
		lang := langByKey(langKey)
		repoDir := filepath.Join(baseDir, lang.Repo)
		if _, err := os.Stat(repoDir); err != nil {
			fmt.Fprintf(os.Stderr, "  %s: repo not found at %s\n", langKey, repoDir)
			return
		}

		problems := probList
		if len(problems) == 0 {
			var err error
			problems, err = discoverProblems(lang, repoDir)
			if err != nil {
				fmt.Fprintf(os.Stderr, "  %s: %v\n", langKey, err)
				return
			}
		}

		results := runBenchmarks(lang, repoDir, problems)

		// Merge
		outputPath := filepath.Join(repoDir, "benchmark_results.json")
		if !*noMerge {
			if old, err := loadResults(outputPath); err == nil {
				results = mergeResults(old, results)
			}
		}

		if err := saveResults(outputPath, results); err != nil {
			fmt.Fprintf(os.Stderr, "  %s: failed to save: %v\n", langKey, err)
			return
		}
		fmt.Printf("  Written to: %s\n", outputPath)

		if !*noMarkdown {
			if err := generateMarkdown(lang, results, repoDir); err != nil {
				fmt.Fprintf(os.Stderr, "  %s: markdown generation failed: %v\n", langKey, err)
			} else {
				fmt.Printf("  Generated BENCHMARKS.md\n")
			}
		}
		fmt.Println()
	}

	if *parallel {
		var wg sync.WaitGroup
		for _, l := range langs {
			wg.Add(1)
			go func(key string) {
				defer wg.Done()
				runOne(key)
			}(l)
		}
		wg.Wait()
	} else {
		for _, l := range langs {
			runOne(l)
		}
	}
}

func cmdFailures(args []string) {
	fs := flag.NewFlagSet("failures", flag.ExitOnError)
	langFilter := fs.String("lang", "", "comma-separated languages (default: all)")
	skipParked := fs.Bool("skip-parked", false, "skip parked problems")
	dryRun := fs.Bool("dry-run", false, "show what would be run")
	parallel := fs.Bool("parallel", false, "run languages concurrently")
	fs.Parse(args)

	baseDir := findBaseDir()
	langs := parseLangs(*langFilter)

	type job struct {
		langKey  string
		repoDir  string
		problems []string
	}
	var jobs []job
	totalFail, totalSkipped := 0, 0

	for _, langKey := range langs {
		lang := langByKey(langKey)
		repoDir := filepath.Join(baseDir, lang.Repo)
		outputPath := filepath.Join(repoDir, "benchmark_results.json")

		res, err := loadResults(outputPath)
		if err != nil {
			fmt.Printf("  %-12s no results file\n", langKey)
			continue
		}

		var failures []string
		skipped := 0
		for prob, r := range res.Problems {
			if r.Status != "fail" {
				continue
			}
			if *skipParked && parkedProblems[prob] {
				skipped++
				continue
			}
			failures = append(failures, prob)
		}
		sort.Strings(failures)

		totalFail += len(failures)
		totalSkipped += skipped

		if len(failures) == 0 {
			msg := "all passing"
			if skipped > 0 {
				msg = fmt.Sprintf("all passing (%d parked skipped)", skipped)
			}
			fmt.Printf("  %-12s %s\n", langKey, msg)
			continue
		}

		fmt.Printf("  %-12s %d failures: %s", langKey, len(failures), strings.Join(failures, ","))
		if skipped > 0 {
			fmt.Printf(" (+%d parked skipped)", skipped)
		}
		fmt.Println()

		jobs = append(jobs, job{langKey: langKey, repoDir: repoDir, problems: failures})
	}

	fmt.Printf("\nTotal: %d failures to re-run", totalFail)
	if totalSkipped > 0 {
		fmt.Printf(", %d parked skipped", totalSkipped)
	}
	fmt.Println()

	if len(jobs) == 0 {
		fmt.Println("Nothing to re-run.")
		return
	}

	if *dryRun {
		fmt.Println("\nDry run — would execute:")
		for _, j := range jobs {
			fmt.Printf("  euler-bench run --lang %s --problems %s\n", j.langKey, strings.Join(j.problems, ","))
		}
		return
	}

	fmt.Println()

	runJob := func(j job) {
		lang := langByKey(j.langKey)
		fmt.Printf(">>> [%s] running %d problems\n", j.langKey, len(j.problems))

		results := runBenchmarks(lang, j.repoDir, j.problems)

		outputPath := filepath.Join(j.repoDir, "benchmark_results.json")
		if old, err := loadResults(outputPath); err == nil {
			results = mergeResults(old, results)
		}
		if err := saveResults(outputPath, results); err != nil {
			fmt.Fprintf(os.Stderr, ">>> [%s] save failed: %v\n", j.langKey, err)
		}
		_ = generateMarkdown(lang, results, j.repoDir)
		fmt.Printf(">>> [%s] done\n\n", j.langKey)
	}

	if *parallel {
		var wg sync.WaitGroup
		for _, j := range jobs {
			wg.Add(1)
			go func(jb job) {
				defer wg.Done()
				runJob(jb)
			}(j)
		}
		wg.Wait()
	} else {
		for _, j := range jobs {
			runJob(j)
		}
	}
}

func cmdStatus(args []string) {
	fs := flag.NewFlagSet("status", flag.ExitOnError)
	langFilter := fs.String("lang", "", "comma-separated languages (default: all)")
	fs.Parse(args)

	baseDir := findBaseDir()
	langs := parseLangs(*langFilter)

	fmt.Printf("%-12s %6s %6s %6s %10s\n", "Language", "Total", "Pass", "Fail", "Parked")
	fmt.Println(strings.Repeat("-", 46))

	for _, langKey := range langs {
		lang := langByKey(langKey)
		repoDir := filepath.Join(baseDir, lang.Repo)
		outputPath := filepath.Join(repoDir, "benchmark_results.json")

		res, err := loadResults(outputPath)
		if err != nil {
			fmt.Printf("%-12s %6s\n", langKey, "N/A")
			continue
		}

		total := len(res.Problems)
		pass, fail, parked := 0, 0, 0
		for prob, r := range res.Problems {
			if r.Status == "pass" {
				pass++
			} else if r.Status == "fail" {
				if parkedProblems[prob] {
					parked++
				} else {
					fail++
				}
			}
		}
		fmt.Printf("%-12s %6d %6d %6d %10d\n", langKey, total, pass, fail, parked)
	}
}

func cmdCollect(args []string) {
	fs := flag.NewFlagSet("collect", flag.ExitOnError)
	outputDir := fs.String("output-dir", "", "output directory (default: ProjectEuler.Benchmarks/data/)")
	fs.Parse(args)

	baseDir := findBaseDir()
	dataDir := *outputDir
	if dataDir == "" {
		dataDir = filepath.Join(baseDir, "ProjectEuler.Benchmarks", "data")
	}

	os.MkdirAll(dataDir, 0755)

	for _, lang := range languages {
		src := filepath.Join(baseDir, lang.Repo, "benchmark_results.json")
		dst := filepath.Join(dataDir, lang.Key+".json")

		data, err := os.ReadFile(src)
		if err != nil {
			fmt.Printf("  %-12s skipped (no results)\n", lang.Key)
			continue
		}

		// Validate JSON
		var js json.RawMessage
		if json.Unmarshal(data, &js) != nil {
			fmt.Printf("  %-12s skipped (invalid JSON)\n", lang.Key)
			continue
		}

		if err := os.WriteFile(dst, data, 0644); err != nil {
			fmt.Fprintf(os.Stderr, "  %-12s failed: %v\n", lang.Key, err)
			continue
		}
		fmt.Printf("  %-12s -> %s\n", lang.Key, dst)
	}
	fmt.Println("Done.")
}
