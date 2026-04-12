// three-mode-report generates a markdown analysis of Project Euler benchmark
// data across three measurement modes: hot (median warm), cold (first invocation),
// and total (compile + cold). This surfaces per-audience performance stories that
// a single hot-only leaderboard obscures.
package main

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// --- Data types ---

type ProblemEntry struct {
	Answer           interface{} `json:"answer"`
	TimeNS           int64       `json:"time_ns"`
	ColdStartNS      int64       `json:"cold_start_ns"`
	SubprocessWallNS int64       `json:"subprocess_wall_ns"`
	CompileTimeNS    int64       `json:"compile_time_ns"`
	Iterations       int         `json:"iterations"`
	Status           string      `json:"status"`
	PeakRSSBytes     int64       `json:"peak_rss_bytes"`
	SourceLines      int         `json:"source_lines"`
	SourceBytes      int         `json:"source_bytes"`
}

type BenchmarkFile struct {
	Language string                  `json:"language"`
	Platform string                  `json:"platform"`
	Compiler string                  `json:"compiler"`
	Timestamp string                 `json:"timestamp"`
	Problems map[string]ProblemEntry `json:"problems"`
}

// --- Time formatting ---

func fmtNS(ns int64) string {
	if ns <= 0 {
		return "0 ns"
	}
	switch {
	case ns < 1_000:
		return fmt.Sprintf("%d ns", ns)
	case ns < 10_000:
		return fmt.Sprintf("%.1f µs", float64(ns)/1e3)
	case ns < 1_000_000:
		return fmt.Sprintf("%.0f µs", float64(ns)/1e3)
	case ns < 10_000_000:
		return fmt.Sprintf("%.1f ms", float64(ns)/1e6)
	case ns < 1_000_000_000:
		return fmt.Sprintf("%.0f ms", float64(ns)/1e6)
	case ns < 10_000_000_000:
		return fmt.Sprintf("%.2f s", float64(ns)/1e9)
	default:
		return fmt.Sprintf("%.1f s", float64(ns)/1e9)
	}
}

// --- Aggregate types ---

type LangTotals struct {
	HotTotal   int64
	ColdTotal  int64
	TotalTotal int64 // compile + cold
}

// --- Main ---

func main() {
	// Locate all benchmark result files relative to this binary's typical run location.
	// We search upward from the script directory or use known absolute paths.
	langFiles := map[string]string{
		"ARM64":      findRepo("ProjectEuler.ARM64"),
		"C":          findRepo("ProjectEuler.C"),
		"C++":        findRepo("ProjectEuler.CPlusPlus"),
		"C#":         findRepo("ProjectEuler.CSharp"),
		"Go":         findRepo("ProjectEuler.Go"),
		"Java":       findRepo("ProjectEuler.Java"),
		"JavaScript": findRepo("ProjectEuler.JavaScript"),
		"Python":     findRepo("ProjectEuler.Python"),
		"Rust":       findRepo("ProjectEuler.Rust"),
		"Zig":        findRepo("ProjectEuler.Zig"),
	}

	// Load data
	allData := map[string]BenchmarkFile{}
	for lang, path := range langFiles {
		if path == "" {
			fmt.Fprintf(os.Stderr, "warning: could not locate benchmark_results.json for %s\n", lang)
			continue
		}
		f, err := os.Open(path)
		if err != nil {
			fmt.Fprintf(os.Stderr, "warning: cannot open %s: %v\n", path, err)
			continue
		}
		var bf BenchmarkFile
		if err := json.NewDecoder(f).Decode(&bf); err != nil {
			fmt.Fprintf(os.Stderr, "warning: cannot parse %s: %v\n", path, err)
			f.Close()
			continue
		}
		f.Close()
		allData[lang] = bf
	}

	langs := sortedKeys(allData)

	// Find the common problem set: problems where ALL loaded languages have a
	// passing entry.
	problemCoverage := map[string]int{}
	for _, bf := range allData {
		for prob, entry := range bf.Problems {
			if entry.Status == "pass" {
				problemCoverage[prob]++
			}
		}
	}
	nLangs := len(langs)
	var commonProblems []string
	for prob, count := range problemCoverage {
		if count == nLangs {
			commonProblems = append(commonProblems, prob)
		}
	}
	sort.Strings(commonProblems)

	// Data quality tracking
	hotProxyCount := map[string]int{}   // hot_ns=0 but pass -> used cold as proxy
	coldMissingCount := map[string]int{} // cold_ns=0 and pass -> cold unavailable

	// Helper: effective hot time for a language/problem entry.
	// If time_ns==0 (under iteration budget resolution), use cold_start_ns as proxy.
	effectiveHot := func(lang string, e ProblemEntry) int64 {
		if e.TimeNS == 0 {
			hotProxyCount[lang]++
			return e.ColdStartNS
		}
		return e.TimeNS
	}

	// Helper: effective cold time.
	// Priority: subprocess_wall_ns (user-perceived, includes interpreter/runtime startup)
	// > cold_start_ns (first solve() call, misses interpreter startup for Python/JVM/.NET)
	// > time_ns (warm median, used as proxy when cold data is unavailable)
	effectiveCold := func(lang string, e ProblemEntry) int64 {
		if e.SubprocessWallNS > 0 {
			return e.SubprocessWallNS
		}
		if e.ColdStartNS > 0 {
			return e.ColdStartNS
		}
		coldMissingCount[lang]++
		if e.TimeNS > 0 {
			return e.TimeNS
		}
		return 0
	}

	// Per-language totals over common problems
	totals := map[string]LangTotals{}
	for _, lang := range langs {
		bf := allData[lang]
		var lt LangTotals
		for _, prob := range commonProblems {
			e := bf.Problems[prob]
			lt.HotTotal += effectiveHot(lang, e)
			cold := effectiveCold(lang, e)
			lt.ColdTotal += cold
			lt.TotalTotal += e.CompileTimeNS + cold
		}
		totals[lang] = lt
	}

	// Per-problem per-language measurements for ranking analysis
	// hotTimes[prob][lang], coldTimes[prob][lang]
	hotTimes := map[string]map[string]int64{}
	coldTimes := map[string]map[string]int64{}
	for _, prob := range commonProblems {
		hotTimes[prob] = map[string]int64{}
		coldTimes[prob] = map[string]int64{}
		for _, lang := range langs {
			e := allData[lang].Problems[prob]
			hotTimes[prob][lang] = effectiveHot(lang, e)
			coldTimes[prob][lang] = effectiveCold(lang, e)
		}
	}

	// Per-problem ranks
	hotRanks := map[string]map[string]int{}  // [prob][lang] = rank (1=fastest)
	coldRanks := map[string]map[string]int{}
	for _, prob := range commonProblems {
		hotRanks[prob] = rankMap(langs, hotTimes[prob])
		coldRanks[prob] = rankMap(langs, coldTimes[prob])
	}

	// Per-language median rank across problems
	medianHotRank := map[string]float64{}
	medianColdRank := map[string]float64{}
	for _, lang := range langs {
		var hr, cr []float64
		for _, prob := range commonProblems {
			hr = append(hr, float64(hotRanks[prob][lang]))
			cr = append(cr, float64(coldRanks[prob][lang]))
		}
		medianHotRank[lang] = median(hr)
		medianColdRank[lang] = median(cr)
	}

	// Problems with largest hot/cold rank disagreement (measured by max rank
	// delta across all languages for that problem)
	type ProblemFlip struct {
		Problem string
		MaxDiff int
		Details []string // lang: hot rank -> cold rank
	}
	var flips []ProblemFlip
	for _, prob := range commonProblems {
		maxDiff := 0
		var details []string
		for _, lang := range langs {
			diff := hotRanks[prob][lang] - coldRanks[prob][lang]
			if diff < 0 {
				diff = -diff
			}
			if diff > maxDiff {
				maxDiff = diff
			}
			if diff >= 3 {
				sign := "+"
				raw := hotRanks[prob][lang] - coldRanks[prob][lang]
				if raw > 0 {
					sign = "+"
				} else {
					sign = ""
				}
				details = append(details,
					fmt.Sprintf("%s: hot #%d -> cold #%d (%s%d)",
						lang, hotRanks[prob][lang], coldRanks[prob][lang], sign, raw))
			}
		}
		flips = append(flips, ProblemFlip{prob, maxDiff, details})
	}
	sort.Slice(flips, func(i, j int) bool { return flips[i].MaxDiff > flips[j].MaxDiff })

	// Now build the report ---------------------------------------------------
	var sb strings.Builder
	w := func(format string, args ...interface{}) {
		fmt.Fprintf(&sb, format, args...)
	}

	w("# Project Euler Cross-Language Benchmark: Three-Mode Analysis\n\n")
	w("*Generated from benchmark data collected on %s*\n\n", allData["C++"].Timestamp)
	w("Platform: %s  \n", allData["C++"].Platform)
	w("Common problem set: **%d problems** (the intersection of all %d languages with a passing entry)\n\n",
		len(commonProblems), nLangs)
	w("---\n\n")

	// --- Section E first as methodology context ---
	w("## Methodology\n\n")
	w("Three measurements are reported for each language:\n\n")
	w("| Mode | Field | What it measures |\n")
	w("|------|-------|------------------|\n")
	w("| **Hot** | `time_ns` | Median wall time over %d warm iterations with the binary already in memory. Favors JIT'd languages (JVM, .NET) because compilation is fully amortized. The right measure for long-running servers or batch jobs that restart infrequently. |\n", 1000)
	w("| **Cold** | `subprocess_wall_ns` (preferred) or `cold_start_ns` | First-invocation wall time with no prior warmup. `subprocess_wall_ns` is the external wall time from `cmd.Run()` start to finish, capturing interpreter/runtime startup (Python ~30-80 ms, JVM ~150-300 ms, .NET ~100-200 ms). `cold_start_ns` is the time of the first `solve()` call inside the process (misses interpreter startup). The right measure for CLI tools, lambdas, and anything invoked once per task. |\n")
	w("| **Total** | `compile_time_ns + cold_start_ns` | Full \"I cloned the repo, built it, and ran it once\" time. Includes the language's ahead-of-time compiler (or build step) where applicable. Zero for interpreted languages (no separate compile step). The right measure for CI/CD pipelines and ephemeral environments. |\n")
	w("\n")
	w("**Cold measurement priority:** `subprocess_wall_ns` is used when available and nonzero (it captures the full user-perceived cold start including interpreter/runtime startup). If absent, `cold_start_ns` is used as a fallback. If both are zero, the warm `time_ns` is used as a lower-bound proxy.\n\n")
	w("**Note on `time_ns = 0`:** When a problem runs faster than the timer resolution, `time_ns` is recorded as 0. These entries use `cold_start_ns` as a proxy for the hot time, which is a conservative overestimate.\n\n")
	w("---\n\n")

	// --- Section A: Per-language totals ---
	w("## Section A: Per-Language Totals Across Common Problems\n\n")
	w("All times are summed over the %d-problem common set.\n\n", len(commonProblems))

	// Compute ranks for the three modes
	hotRankTotals := rankTotals(langs, totals, func(lt LangTotals) int64 { return lt.HotTotal })
	coldRankTotals := rankTotals(langs, totals, func(lt LangTotals) int64 { return lt.ColdTotal })
	totalRankTotals := rankTotals(langs, totals, func(lt LangTotals) int64 { return lt.TotalTotal })

	w("| Language | Hot total | Cold total | Total (compile+cold) | Hot rank | Cold rank | Total rank |\n")
	w("|----------|-----------|------------|----------------------|----------|-----------|------------|\n")
	for _, lang := range langs {
		lt := totals[lang]
		note := ""
		if coldMissingCount[lang] > 0 {
			note = " *"
		}
		w("| %-10s | %12s | %12s | %20s | %8d | %9d | %10d |\n",
			lang,
			fmtNS(lt.HotTotal),
			fmtNS(lt.ColdTotal)+note,
			fmtNS(lt.TotalTotal)+note,
			hotRankTotals[lang],
			coldRankTotals[lang],
			totalRankTotals[lang],
		)
	}
	w("\n*\\* Cold column uses `subprocess_wall_ns` when nonzero (full user-perceived cold start including interpreter/runtime startup), otherwise falls back to `cold_start_ns`, then `time_ns` as a lower-bound proxy. Languages with entries marked * had some cold=0 problems where warm time was used as a proxy.*\n\n")
	w("---\n\n")

	// --- Section B: Per-mode leaderboards ---
	w("## Section B: Per-Mode Leaderboards\n\n")
	w("Showing all languages sorted by total time in each mode. Slowdown is relative to the fastest language in that mode.\n\n")

	// Hot leaderboard
	hotSorted := make([]string, len(langs))
	copy(hotSorted, langs)
	sort.Slice(hotSorted, func(i, j int) bool {
		return totals[hotSorted[i]].HotTotal < totals[hotSorted[j]].HotTotal
	})
	hotWinner := totals[hotSorted[0]].HotTotal

	w("### Hot Mode (median warm iteration)\n\n")
	w("| Rank | Language | Total | Slowdown |\n")
	w("|------|----------|-------|----------|\n")
	for i, lang := range hotSorted {
		slowdown := float64(totals[lang].HotTotal) / float64(hotWinner)
		w("| %4d | %-10s | %10s | %8.2fx |\n", i+1, lang, fmtNS(totals[lang].HotTotal), slowdown)
	}
	w("\n")

	// Cold leaderboard
	coldSorted := make([]string, len(langs))
	copy(coldSorted, langs)
	sort.Slice(coldSorted, func(i, j int) bool {
		return totals[coldSorted[i]].ColdTotal < totals[coldSorted[j]].ColdTotal
	})
	coldWinner := totals[coldSorted[0]].ColdTotal

	w("### Cold Mode (first invocation)\n\n")
	w("| Rank | Language | Total | Slowdown |\n")
	w("|------|----------|-------|----------|\n")
	for i, lang := range coldSorted {
		slowdown := float64(totals[lang].ColdTotal) / float64(coldWinner)
		w("| %4d | %-10s | %10s | %8.2fx |\n", i+1, lang, fmtNS(totals[lang].ColdTotal), slowdown)
	}
	w("\n")

	// Total leaderboard
	totalSorted := make([]string, len(langs))
	copy(totalSorted, langs)
	sort.Slice(totalSorted, func(i, j int) bool {
		return totals[totalSorted[i]].TotalTotal < totals[totalSorted[j]].TotalTotal
	})
	totalWinner := totals[totalSorted[0]].TotalTotal

	w("### Total Mode (compile + cold start)\n\n")
	w("| Rank | Language | Total | Slowdown |\n")
	w("|------|----------|-------|----------|\n")
	for i, lang := range totalSorted {
		slowdown := float64(totals[lang].TotalTotal) / float64(totalWinner)
		w("| %4d | %-10s | %10s | %8.2fx |\n", i+1, lang, fmtNS(totals[lang].TotalTotal), slowdown)
	}
	w("\n")
	w("---\n\n")

	// --- Section C: Quadrant insight ---
	w("## Section C: Hot/Cold Quadrant Analysis\n\n")
	w("Each language is placed in (hot rank, cold rank) space using its median rank\n")
	w("across all %d common problems. Lower rank = faster.\n\n", len(commonProblems))

	w("| Language | Median hot rank | Median cold rank | Quadrant |\n")
	w("|----------|-----------------|------------------|----------|\n")

	midpoint := float64(nLangs+1) / 2.0
	for _, lang := range langs {
		hr := medianHotRank[lang]
		cr := medianColdRank[lang]
		q := quadrant(hr, cr, midpoint)
		w("| %-10s | %15.1f | %16.1f | %s |\n", lang, hr, cr, q)
	}
	w("\n")

	// ASCII art chart
	w("### ASCII Art: Median Hot Rank vs Median Cold Rank\n\n")
	w("X-axis: median hot rank (left = fast, right = slow)\n")
	w("Y-axis: median cold rank (top = fast, bottom = slow)\n")
	w("Grid is %dx%d; each cell is ~%.1f rank units.\n\n", nLangs, nLangs, 1.0)

	asciiChart := buildASCIIChart(langs, medianHotRank, medianColdRank, nLangs)
	w("```\n")
	w("%s\n", asciiChart)
	w("```\n\n")

	w("**Quadrant definitions** (midpoint = %.1f):\n\n", midpoint)
	w("- **Fast-fast** (hot < mid, cold < mid): AOT-compiled languages with minimal runtime overhead. Win both modes.\n")
	w("- **JIT tax** (hot < mid, cold >= mid): Fast in hot mode due to JIT optimization, but pay a visible cold-start penalty. Typical of JVM and .NET.\n")
	w("- **Slow-hot / fast-cold** (hot >= mid, cold < mid): Rare. Would indicate a language with cheap cold start but slow steady-state throughput.\n")
	w("- **Slow-slow** (hot >= mid, cold >= mid): Interpreters or inherently slow runtimes in both modes.\n")
	w("\n---\n\n")

	// --- Section D: The methodology-matters problems ---
	w("## Section D: Problems Where the Ranking Disagrees Most Between Modes\n\n")
	w("The following problems exhibit the largest rank swings between hot and cold measurement.\n")
	w("They are the clearest illustration of why methodology choice matters.\n\n")

	top := 7
	if len(flips) < top {
		top = len(flips)
	}
	for _, flip := range flips[:top] {
		if flip.MaxDiff < 3 {
			break
		}
		w("### Problem %s\n\n", flip.Problem)
		w("| Language | Hot time | Cold time | Hot rank | Cold rank | Rank delta |\n")
		w("|----------|----------|-----------|----------|-----------|------------|\n")
		// sort by hot rank for readability
		probLangs := make([]string, len(langs))
		copy(probLangs, langs)
		sort.Slice(probLangs, func(i, j int) bool {
			return hotRanks[flip.Problem][probLangs[i]] < hotRanks[flip.Problem][probLangs[j]]
		})
		for _, lang := range probLangs {
			delta := coldRanks[flip.Problem][lang] - hotRanks[flip.Problem][lang]
			sign := ""
			if delta > 0 {
				sign = "+"
			}
			w("| %-10s | %9s | %10s | %8d | %9d | %s%d |\n",
				lang,
				fmtNS(hotTimes[flip.Problem][lang]),
				fmtNS(coldTimes[flip.Problem][lang]),
				hotRanks[flip.Problem][lang],
				coldRanks[flip.Problem][lang],
				sign, delta,
			)
		}
		w("\n")
	}
	w("---\n\n")

	// --- Data quality section ---
	w("## Data Quality Notes\n\n")
	w("| Language | hot=0 entries (cold used as proxy) | cold=0 entries (hot used as proxy) |\n")
	w("|----------|-------------------------------------|-------------------------------------|\n")
	for _, lang := range langs {
		w("| %-10s | %35d | %35d |\n", lang, hotProxyCount[lang], coldMissingCount[lang])
	}
	w("\n")

	// Output
	outputPath := filepath.Join(repoBase(), "ProjectEuler.Benchmarks", "THREE_MODE_REPORT.md")
	if err := os.WriteFile(outputPath, []byte(sb.String()), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "error writing report: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("Report written to %s\n", outputPath)
	fmt.Printf("Common problems: %d\n", len(commonProblems))
	fmt.Printf("Languages: %s\n", strings.Join(langs, ", "))
}

// --- Helpers ---

func sortedKeys(m map[string]BenchmarkFile) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

func rankMap(langs []string, times map[string]int64) map[string]int {
	sorted := make([]string, len(langs))
	copy(sorted, langs)
	sort.Slice(sorted, func(i, j int) bool { return times[sorted[i]] < times[sorted[j]] })
	ranks := map[string]int{}
	for i, l := range sorted {
		ranks[l] = i + 1
	}
	return ranks
}

func rankTotals(langs []string, totals map[string]LangTotals, get func(LangTotals) int64) map[string]int {
	sorted := make([]string, len(langs))
	copy(sorted, langs)
	sort.Slice(sorted, func(i, j int) bool { return get(totals[sorted[i]]) < get(totals[sorted[j]]) })
	ranks := map[string]int{}
	for i, l := range sorted {
		ranks[l] = i + 1
	}
	return ranks
}

func median(vals []float64) float64 {
	if len(vals) == 0 {
		return 0
	}
	sorted := make([]float64, len(vals))
	copy(sorted, vals)
	sort.Float64s(sorted)
	n := len(sorted)
	if n%2 == 1 {
		return sorted[n/2]
	}
	return (sorted[n/2-1] + sorted[n/2]) / 2.0
}

func quadrant(hr, cr, mid float64) string {
	// Use <= mid to include the median boundary in the "fast" half
	hotFast := hr <= mid
	coldFast := cr <= mid
	switch {
	case hotFast && coldFast:
		return "Fast-fast (AOT compiled)"
	case hotFast && !coldFast:
		return "JIT tax (fast hot, slow cold)"
	case !hotFast && coldFast:
		return "Slow-hot / fast-cold"
	default:
		return "Slow-slow (interpreter)"
	}
}

func buildASCIIChart(langs []string, hotRank, coldRank map[string]float64, n int) string {
	// n x n grid, each cell is 1 rank unit wide/tall
	// hot rank on X (col), cold rank on Y (row); both 1-indexed
	// Use 2-char initials per language to avoid overlap
	initials := map[string]string{
		"ARM64":      "AS", // ARM64 Assembly
		"C":          "C ",
		"C++":        "C+",
		"C#":         "C#",
		"Go":         "Go",
		"Java":       "Ja",
		"JavaScript": "JS",
		"Python":     "Py",
		"Rust":       "Rs",
		"Zig":        "Zg",
	}

	grid := make([][]string, n)
	for i := range grid {
		grid[i] = make([]string, n)
		for j := range grid[i] {
			grid[i][j] = ".."
		}
	}

	for _, lang := range langs {
		col := int(math.Round(hotRank[lang])) - 1
		row := int(math.Round(coldRank[lang])) - 1
		if col < 0 {
			col = 0
		}
		if col >= n {
			col = n - 1
		}
		if row < 0 {
			row = 0
		}
		if row >= n {
			row = n - 1
		}
		init, ok := initials[lang]
		if !ok {
			init = lang[:2]
		}
		grid[row][col] = init
	}

	var sb strings.Builder
	header := "     hot rank -->"
	sb.WriteString(header + "\n")
	sb.WriteString("     ")
	for col := 1; col <= n; col++ {
		sb.WriteString(fmt.Sprintf("%-2d", col))
	}
	sb.WriteString("\n")
	sb.WriteString("     " + strings.Repeat("--", n) + "\n")
	for row := 0; row < n; row++ {
		if row == 0 {
			sb.WriteString(fmt.Sprintf("c %2d|", row+1))
		} else if row == n/2 {
			sb.WriteString(fmt.Sprintf("o %2d|", row+1))
		} else if row == n-1 {
			sb.WriteString(fmt.Sprintf("v %2d|", row+1))
		} else {
			sb.WriteString(fmt.Sprintf("  %2d|", row+1))
		}
		for col := 0; col < n; col++ {
			sb.WriteString(grid[row][col])
		}
		sb.WriteString("\n")
	}
	return sb.String()
}

func repoBase() string {
	// Walk up from executable location to find the parent of ProjectEuler.Benchmarks
	exe, err := os.Executable()
	if err != nil {
		return os.Getenv("HOME") + "/ccdev"
	}
	dir := filepath.Dir(exe)
	// Try up to 6 levels
	for i := 0; i < 6; i++ {
		if _, err := os.Stat(filepath.Join(dir, "ProjectEuler.Benchmarks")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	// Fallback: use known path
	home := os.Getenv("HOME")
	if home == "" {
		home = "/Users/augusthill"
	}
	return filepath.Join(home, "ccdev")
}

func findRepo(name string) string {
	base := repoBase()
	path := filepath.Join(base, name, "benchmark_results.json")
	if _, err := os.Stat(path); err == nil {
		return path
	}
	return ""
}
