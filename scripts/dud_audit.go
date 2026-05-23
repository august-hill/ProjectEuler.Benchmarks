// dud_audit — scan all 10 PE language repos for "dud" patterns.
//
// Categories:
//   E1  empty_dir            problem dir exists but no source file (or file empty)
//   S1  stub_solve           solve body is just `return <literal>` with no algorithm
//   S2  missing_answer       source present but no `Answer:` comment at top
//   S3  comment_mismatch     `// Answer:` differs from benchmark_results.json answer
//   D1  bench_fail           benchmark_results.json status=fail (algo broken)
//   D2  bench_missing_entry  source/dir exists but no entry in benchmark_results.json
//   X1  cross_lang_disagree  multiple langs solve same problem with different answers
//   C1  cache_pattern        warm time_ns << cold_start_ns (solve() likely caches answer)
//                              — bench measures cache-return cost, not real algorithm.
//                              Heuristic: cold_ns > 1ms AND time_ns < 100µs AND
//                              (cold_ns/time_ns > 100 OR time_ns == 0).
//                              Added 2026-05-22 after session 477aafc3 surfaced 168
//                              suite-wide instances; see project_pe_cache_pattern_campaign
//                              in author's auto-memory for the fix campaign.
//
// Exit: 0 (no errors), 2 (≥1 error finding), 1 (tool error).
//
// Usage:
//   dud_audit                # human summary to stderr, JSON to stdout
//   dud_audit --lang cpp     # one language
//   dud_audit --severity error  # filter findings
//   dud_audit --quiet        # suppress human summary

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

// ---------- per-language config ----------

type LangConfig struct {
	Name      string // canonical short name matching benchmark_results.json schema
	RepoDir   string // repo root, absolute
	BenchFile string // relative to RepoDir
	// For each problem N (zero-padded 3-digit), where is the source-of-truth file?
	// Returns absolute path. nil means "not applicable" (problem not in this lang's scheme).
	SourcePath func(n int) string
	// Where to glob for the list of present problems. Returns absolute glob pattern.
	ProblemGlob string
	// Function to extract the problem number from a glob match.
	ParseProblem func(name string) (int, bool)
	// Regex to find the Answer comment. Capture group 1 = the answer string.
	AnswerRe *regexp.Regexp
	// Regex to detect a stub solve body. Matches if the function body is just a return literal.
	StubRe *regexp.Regexp
}

const ccdev = "/Users/augusthill/ccdev"

// "Answer: X" comment regex variants for // and # comment styles.
// Captures EITHER a parens-wrapped marker (e.g. "(not solved)") OR the first
// whitespace-delimited token (e.g. "233168" from "233168 (description)").
var (
	answerSlashRe = regexp.MustCompile(`(?m)^\s*//\s*Answer:\s*(\([^)]*\)|\S+)`)
	answerHashRe  = regexp.MustCompile(`(?m)^\s*#\s*Answer:\s*(\([^)]*\)|\S+)`)
)

// Stub detection: matches a solve function whose body is a single `return <literal>`.
// We accept various shapes (whitespace, semicolons, type qualifiers).
// Conservative — false negatives are fine; false positives are NOT (would be loud).
var (
	// `long long solve() { return 12345; }` and similar (cpp/c/zig/rust/go/java/csharp/js)
	stubBraceRe = regexp.MustCompile(`(?s)solve\s*\(\s*\)\s*[^{]*\{\s*return\s+([0-9-][^;\n]*)\s*;?\s*\}`)
	// Python `def solve(): return 12345` or block-form with just return
	stubPyRe = regexp.MustCompile(`(?m)def\s+solve\s*\(\s*\)\s*:\s*\n\s+return\s+([0-9-]\S*)\s*$`)
	// ARM64 _solve label with just movz/mov + ret + no other ops between
	stubAsmRe = regexp.MustCompile(`(?s)_solve:\s*(?:mov[a-z]?\s+x0\s*,\s*#?\d+\s*)+\s*ret`)
)

func zeroPad(n int) string { return fmt.Sprintf("%03d", n) }

func numFromDir(name string) (int, bool) {
	if !strings.HasPrefix(name, "problem_") || len(name) != 11 {
		return 0, false
	}
	n, err := strconv.Atoi(name[8:])
	return n, err == nil
}

func numFromPyFile(name string) (int, bool) {
	if !strings.HasPrefix(name, "problem_") || !strings.HasSuffix(name, ".py") {
		return 0, false
	}
	mid := name[8 : len(name)-3]
	if len(mid) != 3 {
		return 0, false
	}
	n, err := strconv.Atoi(mid)
	return n, err == nil
}

var langs = []LangConfig{
	{
		Name: "cpp", RepoDir: ccdev + "/ProjectEuler.CPlusPlus",
		BenchFile:    "benchmark_results.json",
		SourcePath:   func(n int) string { return ccdev + "/ProjectEuler.CPlusPlus/problem_" + zeroPad(n) + "/main.cpp" },
		ProblemGlob:  ccdev + "/ProjectEuler.CPlusPlus/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubBraceRe,
	},
	{
		Name: "python", RepoDir: ccdev + "/ProjectEuler.Python",
		BenchFile:    "benchmark_results.json",
		SourcePath:   func(n int) string { return ccdev + "/ProjectEuler.Python/problem_" + zeroPad(n) + ".py" },
		ProblemGlob:  ccdev + "/ProjectEuler.Python/problem_*.py",
		ParseProblem: numFromPyFile, AnswerRe: answerHashRe, StubRe: stubPyRe,
	},
	{
		Name: "rust", RepoDir: ccdev + "/ProjectEuler.Rust",
		BenchFile:    "benchmark_results.json",
		SourcePath:   func(n int) string { return ccdev + "/ProjectEuler.Rust/problem_" + zeroPad(n) + "/src/main.rs" },
		ProblemGlob:  ccdev + "/ProjectEuler.Rust/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubBraceRe,
	},
	{
		Name: "go", RepoDir: ccdev + "/ProjectEuler.Go",
		BenchFile:    "benchmark_results.json",
		SourcePath:   func(n int) string { return ccdev + "/ProjectEuler.Go/problem_" + zeroPad(n) + "/main.go" },
		ProblemGlob:  ccdev + "/ProjectEuler.Go/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubBraceRe,
	},
	{
		Name: "java", RepoDir: ccdev + "/ProjectEuler.Java",
		BenchFile:    "benchmark_results.json",
		SourcePath:   func(n int) string { return ccdev + "/ProjectEuler.Java/problem_" + zeroPad(n) + "/Main.java" },
		ProblemGlob:  ccdev + "/ProjectEuler.Java/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubBraceRe,
	},
	{
		Name: "javascript", RepoDir: ccdev + "/ProjectEuler.JavaScript",
		BenchFile:    "benchmark_results.json",
		SourcePath:   func(n int) string { return ccdev + "/ProjectEuler.JavaScript/problem_" + zeroPad(n) + "/main.js" },
		ProblemGlob:  ccdev + "/ProjectEuler.JavaScript/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubBraceRe,
	},
	{
		Name: "csharp", RepoDir: ccdev + "/ProjectEuler.CSharp",
		BenchFile:    "benchmark_results.json",
		SourcePath:   func(n int) string { return ccdev + "/ProjectEuler.CSharp/problem_" + zeroPad(n) + "/Program.cs" },
		ProblemGlob:  ccdev + "/ProjectEuler.CSharp/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubBraceRe,
	},
	{
		Name: "zig", RepoDir: ccdev + "/ProjectEuler.Zig",
		BenchFile:    "benchmark_results.json",
		SourcePath:   func(n int) string { return ccdev + "/ProjectEuler.Zig/problem_" + zeroPad(n) + "/main.zig" },
		ProblemGlob:  ccdev + "/ProjectEuler.Zig/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubBraceRe,
	},
	{
		Name: "c", RepoDir: ccdev + "/ProjectEuler.C",
		BenchFile:    "benchmark_results.json",
		SourcePath:   func(n int) string { return ccdev + "/ProjectEuler.C/problem_" + zeroPad(n) + "/main.c" },
		ProblemGlob:  ccdev + "/ProjectEuler.C/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubBraceRe,
	},
	{
		Name: "arm64", RepoDir: ccdev + "/ProjectEuler.ARM64",
		BenchFile:    "benchmark_results.json",
		SourcePath:   func(n int) string { return ccdev + "/ProjectEuler.ARM64/problem_" + zeroPad(n) + "/solve.s" },
		ProblemGlob:  ccdev + "/ProjectEuler.ARM64/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubAsmRe,
	},
}

// ---------- benchmark_results.json ----------

type BenchEntry struct {
	Status      string          `json:"status"`
	Answer      json.RawMessage `json:"answer"`
	Error       string          `json:"error,omitempty"`
	TimeNs      int64           `json:"time_ns,omitempty"`
	ColdStartNs int64           `json:"cold_start_ns,omitempty"`
}

type BenchFile struct {
	Problems map[string]BenchEntry `json:"problems"`
}

func loadBench(path string) (*BenchFile, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var bf BenchFile
	if err := json.Unmarshal(data, &bf); err != nil {
		return nil, err
	}
	return &bf, nil
}

// answerToString returns the canonical string form of a bench answer.
// Uses json.RawMessage to preserve full precision (avoids float64 truncation
// of large integers > 2^53). Strips JSON quotes if the answer is a string.
func answerToString(a json.RawMessage) string {
	if len(a) == 0 || string(a) == "null" {
		return ""
	}
	s := strings.TrimSpace(string(a))
	if len(s) >= 2 && s[0] == '"' && s[len(s)-1] == '"' {
		// String answer: strip JSON quotes (don't worry about embedded escapes — PE answers don't have them).
		return s[1 : len(s)-1]
	}
	return s
}

// markerCommentRe matches "Answer:" comments that are clearly placeholders, not real answers.
// These should not trigger S3 (mismatch); they signal the problem is openly unsolved/TBD.
var markerCommentRe = regexp.MustCompile(`^(?i)(UNSOLVED|TBD|TODO|N/?A|PENDING|WIP|UNKNOWN|\?+|\(.*\))$`)

// answersEquivalent returns true when comment and bench mean the same thing,
// modulo two known-noisy mismatches:
//   1. Decimal encoding: comment "0.464399" vs bench "464399" (project convention encodes
//      decimal answers as round(x * 10^N); the comment may show the unscaled form).
//   2. Trailing zeros after decimal: "1.0" vs "1".
// Returns false otherwise. Both inputs assumed already normalized (no surrounding whitespace).
func answersEquivalent(comment, bench string) bool {
	if comment == bench {
		return true
	}
	// Strip a leading sign for the comparison; reapply at the end if needed.
	if comment == "" || bench == "" {
		return false
	}
	// Comment with decimal point: try removing the decimal point and comparing.
	dotIdx := strings.Index(comment, ".")
	if dotIdx >= 0 {
		stripped := strings.ReplaceAll(comment, ".", "")
		// Trim leading zeros after sign (but keep at least one digit).
		stripped = trimLeadingZeros(stripped)
		if stripped == bench {
			return true
		}
	}
	// Symmetric case: bench has decimal point.
	dotIdx = strings.Index(bench, ".")
	if dotIdx >= 0 {
		stripped := trimLeadingZeros(strings.ReplaceAll(bench, ".", ""))
		if stripped == comment {
			return true
		}
	}
	return false
}

func trimLeadingZeros(s string) string {
	sign := ""
	if strings.HasPrefix(s, "-") {
		sign = "-"
		s = s[1:]
	}
	for len(s) > 1 && s[0] == '0' {
		s = s[1:]
	}
	return sign + s
}

// ---------- parked list ----------

func loadParkedSet() map[int]bool {
	data, err := os.ReadFile(ccdev + "/ProjectEuler.Benchmarks/data/parked.json")
	parked := make(map[int]bool)
	if err != nil {
		return parked
	}
	var raw []string
	if json.Unmarshal(data, &raw) != nil {
		return parked
	}
	for _, s := range raw {
		if n, err := strconv.Atoi(s); err == nil {
			parked[n] = true
		}
	}
	return parked
}

// ---------- finding ----------

type Finding struct {
	Lang     string `json:"language"`
	Problem  int    `json:"problem"`
	Category string `json:"category"`
	Severity string `json:"severity"` // error, warning, info
	Details  string `json:"details"`
}

const (
	sevError   = "error"
	sevWarning = "warning"
	sevInfo    = "info"
)

// ---------- scanning ----------

func scanLang(cfg LangConfig, parked map[int]bool) []Finding {
	var findings []Finding

	bench, _ := loadBench(filepath.Join(cfg.RepoDir, cfg.BenchFile))
	if bench == nil {
		bench = &BenchFile{Problems: map[string]BenchEntry{}}
	}

	matches, _ := filepath.Glob(cfg.ProblemGlob)
	seen := map[int]bool{}

	for _, m := range matches {
		base := filepath.Base(m)
		n, ok := cfg.ParseProblem(base)
		if !ok {
			continue
		}
		if parked[n] {
			continue
		}
		seen[n] = true

		srcPath := cfg.SourcePath(n)
		st, err := os.Stat(srcPath)

		// E1: dir/file exists but source file missing or empty
		if err != nil || st.Size() == 0 {
			// For Python, the glob match IS the source file; if size=0, it's E1.
			// For dir-based langs, the dir exists but inner main file is missing/empty.
			detail := "source file missing"
			if err == nil && st.Size() == 0 {
				detail = "source file empty (0 bytes)"
			}
			// Detect intent markers in the problem dir: SKIPPED, DEFERRED.md, etc.
			// If present, demote to info (not an error — visible "we're not solving this").
			sev := sevWarning
			if hasIntentMarker(filepath.Dir(srcPath)) {
				sev = sevInfo
				detail += " (has intent marker — SKIPPED/DEFERRED)"
			}
			findings = append(findings, Finding{
				Lang: cfg.Name, Problem: n, Category: "E1", Severity: sev,
				Details: detail + " at " + relPath(srcPath, cfg.RepoDir),
			})
			continue
		}

		content, _ := os.ReadFile(srcPath)
		findings = append(findings, scanContent(cfg, n, content, bench)...)
	}

	// D2: bench has entries for problems whose dir we didn't see (rare — should not happen for normal langs)
	for key, entry := range bench.Problems {
		n, err := strconv.Atoi(key)
		if err != nil || seen[n] || parked[n] {
			continue
		}
		_ = entry
		findings = append(findings, Finding{
			Lang: cfg.Name, Problem: n, Category: "D2", Severity: sevWarning,
			Details: "benchmark_results.json has entry but no matching source dir/file",
		})
	}

	return findings
}

func scanContent(cfg LangConfig, n int, content []byte, bench *BenchFile) []Finding {
	var findings []Finding
	key := zeroPad(n)
	keyAlt := strconv.Itoa(n)

	// S2: missing Answer comment
	answerMatch := cfg.AnswerRe.FindSubmatch(content)
	commentAnswer := ""
	if answerMatch != nil {
		commentAnswer = string(answerMatch[1])
	} else {
		findings = append(findings, Finding{
			Lang: cfg.Name, Problem: n, Category: "S2", Severity: sevWarning,
			Details: "no `Answer:` comment found at top of source",
		})
	}
	// M1: comment is a marker like "UNSOLVED" / "TBD" — different finding from S3 (numeric mismatch).
	if commentAnswer != "" && markerCommentRe.MatchString(commentAnswer) {
		findings = append(findings, Finding{
			Lang: cfg.Name, Problem: n, Category: "M1", Severity: sevInfo,
			Details: fmt.Sprintf("Answer comment is a marker (%q), not a real answer", commentAnswer),
		})
		// Don't trigger S3 below — clear the comment so the comparison is skipped.
		commentAnswer = ""
	}

	// S1: stub solve body
	if cfg.StubRe != nil && cfg.StubRe.Match(content) {
		findings = append(findings, Finding{
			Lang: cfg.Name, Problem: n, Category: "S1", Severity: sevError,
			Details: "solve body looks like just `return <literal>` (no algorithm)",
		})
	}

	// Bench cross-reference
	entry, ok := bench.Problems[key]
	if !ok {
		entry, ok = bench.Problems[keyAlt]
	}
	if !ok {
		findings = append(findings, Finding{
			Lang: cfg.Name, Problem: n, Category: "D2", Severity: sevInfo,
			Details: "source exists but no entry in benchmark_results.json",
		})
		return findings
	}

	// D1: status=fail
	if entry.Status == "fail" {
		findings = append(findings, Finding{
			Lang: cfg.Name, Problem: n, Category: "D1", Severity: sevError,
			Details: fmt.Sprintf("benchmark_results.json status=fail (error: %q)", entry.Error),
		})
	}

	// C1: cache pattern — warm time_ns is sub-µs while cold_start_ns is ms+.
	// Signals solve() is caching the answer (warm bench iterations measure cache-return).
	// Threshold: cold > 1ms AND time < 100µs AND (cold/time > 100 OR time == 0).
	// Only applies when status=pass (a failed bench's timings are meaningless).
	if entry.Status == "pass" && entry.ColdStartNs > 1_000_000 && entry.TimeNs < 100_000 {
		ratioMet := entry.TimeNs == 0 || (entry.ColdStartNs/entry.TimeNs) > 100
		if ratioMet {
			ratioStr := "∞ (time_ns=0)"
			if entry.TimeNs > 0 {
				ratioStr = fmt.Sprintf("%dx", entry.ColdStartNs/entry.TimeNs)
			}
			findings = append(findings, Finding{
				Lang: cfg.Name, Problem: n, Category: "C1", Severity: sevError,
				Details: fmt.Sprintf("cache pattern: time_ns=%d, cold_start_ns=%d (ratio %s) — solve() likely caches answer",
					entry.TimeNs, entry.ColdStartNs, ratioStr),
			})
		}
	}

	// S3: comment vs bench mismatch (only if comment present and bench has answer)
	if commentAnswer != "" && len(entry.Answer) > 0 {
		benchAns := answerToString(entry.Answer)
		if benchAns != "" && !answersEquivalent(commentAnswer, benchAns) {
			findings = append(findings, Finding{
				Lang: cfg.Name, Problem: n, Category: "S3", Severity: sevError,
				Details: fmt.Sprintf("comment Answer=%q != bench answer=%q", commentAnswer, benchAns),
			})
		}
	}

	return findings
}

// ---------- cross-language consistency ----------

func scanCrossLang(parked map[int]bool) []Finding {
	// Map: problem_number -> map[lang]answer
	answers := map[int]map[string]string{}

	for _, cfg := range langs {
		bench, _ := loadBench(filepath.Join(cfg.RepoDir, cfg.BenchFile))
		if bench == nil {
			continue
		}
		for key, entry := range bench.Problems {
			n, err := strconv.Atoi(key)
			if err != nil || parked[n] {
				continue
			}
			if entry.Status != "pass" || len(entry.Answer) == 0 {
				continue
			}
			ans := answerToString(entry.Answer)
			if ans == "" {
				continue
			}
			if answers[n] == nil {
				answers[n] = map[string]string{}
			}
			answers[n][cfg.Name] = ans
		}
	}

	var findings []Finding
	for n, m := range answers {
		if len(m) < 2 {
			continue
		}
		// Group by answer; merge groups whose answers are equivalent (decimal-encoding-aware).
		// Order is unstable; use representative answer-string for the group.
		groups := map[string][]string{}
		for lang, ans := range m {
			merged := false
			for rep := range groups {
				if answersEquivalent(ans, rep) {
					groups[rep] = append(groups[rep], lang)
					merged = true
					break
				}
			}
			if !merged {
				groups[ans] = []string{lang}
			}
		}
		if len(groups) > 1 {
			parts := []string{}
			for ans, langs_ := range groups {
				sort.Strings(langs_)
				parts = append(parts, fmt.Sprintf("%q:[%s]", ans, strings.Join(langs_, ",")))
			}
			sort.Strings(parts)
			findings = append(findings, Finding{
				Lang: "*", Problem: n, Category: "X1", Severity: sevError,
				Details: "cross-language answer disagreement: " + strings.Join(parts, " "),
			})
		}
	}

	return findings
}

// ---------- output ----------

type Report struct {
	ScanTime time.Time      `json:"scan_time"`
	Summary  ReportSummary  `json:"summary"`
	Findings []Finding      `json:"findings"`
}

type ReportSummary struct {
	LanguagesScanned int            `json:"languages_scanned"`
	Findings         int            `json:"findings"`
	BySeverity       map[string]int `json:"by_severity"`
	ByCategory       map[string]int `json:"by_category"`
	ByLanguage       map[string]int `json:"by_language"`
}

func summarize(findings []Finding) ReportSummary {
	s := ReportSummary{
		LanguagesScanned: len(langs),
		Findings:         len(findings),
		BySeverity:       map[string]int{},
		ByCategory:       map[string]int{},
		ByLanguage:       map[string]int{},
	}
	for _, f := range findings {
		s.BySeverity[f.Severity]++
		s.ByCategory[f.Category]++
		s.ByLanguage[f.Lang]++
	}
	return s
}

func writeHumanSummary(w *os.File, r Report) {
	fmt.Fprintf(w, "PE Trust Audit — %s\n", r.ScanTime.UTC().Format(time.RFC3339))
	fmt.Fprintf(w, "Languages scanned: %d   Findings: %d  (errors: %d, warnings: %d, info: %d)\n\n",
		r.Summary.LanguagesScanned, r.Summary.Findings,
		r.Summary.BySeverity[sevError], r.Summary.BySeverity[sevWarning], r.Summary.BySeverity[sevInfo])

	// Sort categories
	cats := []string{}
	for c := range r.Summary.ByCategory {
		cats = append(cats, c)
	}
	sort.Strings(cats)
	fmt.Fprintf(w, "By category:\n")
	for _, c := range cats {
		fmt.Fprintf(w, "  %-3s  %4d   (%s)\n", c, r.Summary.ByCategory[c], categoryName(c))
	}

	// Sort languages
	langKeys := []string{}
	for l := range r.Summary.ByLanguage {
		langKeys = append(langKeys, l)
	}
	sort.Strings(langKeys)
	fmt.Fprintf(w, "\nBy language:\n")
	for _, l := range langKeys {
		fmt.Fprintf(w, "  %-12s  %4d\n", l, r.Summary.ByLanguage[l])
	}

	// Top errors
	errs := []Finding{}
	for _, f := range r.Findings {
		if f.Severity == sevError {
			errs = append(errs, f)
		}
	}
	sort.Slice(errs, func(i, j int) bool {
		if errs[i].Lang != errs[j].Lang {
			return errs[i].Lang < errs[j].Lang
		}
		return errs[i].Problem < errs[j].Problem
	})
	if len(errs) > 0 {
		fmt.Fprintf(w, "\nTop errors (showing up to 30):\n")
		for i, f := range errs {
			if i >= 30 {
				fmt.Fprintf(w, "  ... %d more\n", len(errs)-30)
				break
			}
			fmt.Fprintf(w, "  %-10s p%03d  %s  %s\n", f.Lang, f.Problem, f.Category, f.Details)
		}
	}
}

func categoryName(c string) string {
	return map[string]string{
		"E1": "empty_dir / empty_file",
		"S1": "stub_solve",
		"S2": "missing_answer_comment",
		"S3": "comment_vs_bench_mismatch",
		"M1": "marker_comment (UNSOLVED/TBD/etc.)",
		"D1": "bench_status_fail",
		"D2": "bench_missing_entry",
		"X1": "cross_lang_answer_disagreement",
		"C1": "cache_pattern (warm << cold; solve() caches)",
	}[c]
}

// ---------- helpers ----------

func relPath(p, base string) string {
	if r, err := filepath.Rel(base, p); err == nil {
		return r
	}
	return p
}

// hasIntentMarker returns true if the dir contains evidence of documented
// in-progress work or intentional skip — any file, since a *truly* empty
// placeholder dir contains zero entries. The earlier marker-name allowlist
// missed dirs with `solve.cpp` / `test*.cpp` (in-progress C++ work) and other
// non-standard work-in-progress names.
func hasIntentMarker(dir string) bool {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return false
	}
	return len(entries) > 0
}

// ---------- main ----------

func main() {
	langFilter := flag.String("lang", "", "scan only this language (default: all)")
	sevFilter := flag.String("severity", "", "filter findings by severity (error|warning|info)")
	jsonOnly := flag.Bool("quiet", false, "suppress human summary on stderr")
	flag.Parse()

	parked := loadParkedSet()

	var findings []Finding
	for _, cfg := range langs {
		if *langFilter != "" && cfg.Name != *langFilter {
			continue
		}
		findings = append(findings, scanLang(cfg, parked)...)
	}
	// Cross-lang findings: if --lang FOO is set, only include cross-lang findings
	// that involve FOO (otherwise the per-lang error count is inflated by
	// disagreements between other languages — irrelevant for the FOO commit gate).
	crossFindings := scanCrossLang(parked)
	for _, f := range crossFindings {
		if *langFilter == "" || strings.Contains(f.Details, "["+*langFilter+",") || strings.Contains(f.Details, ","+*langFilter+",") || strings.Contains(f.Details, ","+*langFilter+"]") || strings.Contains(f.Details, "["+*langFilter+"]") {
			findings = append(findings, f)
		}
	}

	if *sevFilter != "" {
		filtered := findings[:0]
		for _, f := range findings {
			if f.Severity == *sevFilter {
				filtered = append(filtered, f)
			}
		}
		findings = filtered
	}

	sort.Slice(findings, func(i, j int) bool {
		if findings[i].Lang != findings[j].Lang {
			return findings[i].Lang < findings[j].Lang
		}
		if findings[i].Problem != findings[j].Problem {
			return findings[i].Problem < findings[j].Problem
		}
		return findings[i].Category < findings[j].Category
	})

	report := Report{
		ScanTime: time.Now(),
		Summary:  summarize(findings),
		Findings: findings,
	}

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(report); err != nil {
		fmt.Fprintln(os.Stderr, "encode error:", err)
		os.Exit(1)
	}
	if !*jsonOnly {
		writeHumanSummary(os.Stderr, report)
	}

	if report.Summary.BySeverity[sevError] > 0 {
		os.Exit(2)
	}
}
