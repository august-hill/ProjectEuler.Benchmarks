// dud_audit — scan all 10 PE language repos for "dud" patterns.
//
// Categories:
//   E1  empty_dir            problem dir exists but no source file (or file empty)
//   S1  stub_solve           solve body is just `return <literal>` with no algorithm
//   S2  missing_answer       source present but no `Answer:` comment at top
//   S3  comment_mismatch     `// Answer:` differs from SQLite SSOT (runs.answer)
//   D1  bench_fail           SQLite SSOT runs.status=fail (algo broken)
//   D2  bench_missing_entry  source/dir exists but no row in SQLite SSOT (runs table)
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
	"database/sql"
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

	_ "modernc.org/sqlite"
)

// ---------- per-language config ----------

type LangConfig struct {
	Name    string // canonical short name; matches `runs.lang` column in the SQLite SSOT
	RepoDir string // repo root, absolute (still used by relPath for display)
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

// dbPath returns the absolute path to the SQLite SSOT.
// Migration history:
//
//	2026-05-24: read each lang repo's `benchmark_results.json` (deleted with `benchmark.sh`)
//	2026-05-25 (rebase): switched to `pe/benchmarks/data/private/<lang>.json`
//	2026-05-25 (SQLite migration): consolidated to single `pe/benchmarks/data/bench-private.db`
func dbPath() string {
	return peDir + "/benchmarks/data/bench-private.db"
}

const ccdev = "/Users/augusthill/ccdev"
const peDir = ccdev + "/pe"

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
		Name: "cpp", RepoDir: peDir + "/cpp",
		SourcePath:   func(n int) string { return peDir + "/cpp/problem_" + zeroPad(n) + "/main.cpp" },
		ProblemGlob:  peDir + "/cpp/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubBraceRe,
	},
	{
		Name: "python", RepoDir: peDir + "/python",
		SourcePath:   func(n int) string { return peDir + "/python/problem_" + zeroPad(n) + ".py" },
		ProblemGlob:  peDir + "/python/problem_*.py",
		ParseProblem: numFromPyFile, AnswerRe: answerHashRe, StubRe: stubPyRe,
	},
	{
		Name: "rust", RepoDir: peDir + "/rust",
		SourcePath:   func(n int) string { return peDir + "/rust/problem_" + zeroPad(n) + "/src/main.rs" },
		ProblemGlob:  peDir + "/rust/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubBraceRe,
	},
	{
		Name: "go", RepoDir: peDir + "/go",
		SourcePath:   func(n int) string { return peDir + "/go/problem_" + zeroPad(n) + "/main.go" },
		ProblemGlob:  peDir + "/go/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubBraceRe,
	},
	{
		Name: "java", RepoDir: peDir + "/java",
		SourcePath:   func(n int) string { return peDir + "/java/problem_" + zeroPad(n) + "/Main.java" },
		ProblemGlob:  peDir + "/java/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubBraceRe,
	},
	{
		Name: "javascript", RepoDir: peDir + "/javascript",
		SourcePath:   func(n int) string { return peDir + "/javaScript/problem_" + zeroPad(n) + "/main.js" },
		ProblemGlob:  peDir + "/javaScript/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubBraceRe,
	},
	{
		Name: "csharp", RepoDir: peDir + "/csharp",
		SourcePath:   func(n int) string { return peDir + "/csharp/problem_" + zeroPad(n) + "/Program.cs" },
		ProblemGlob:  peDir + "/csharp/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubBraceRe,
	},
	{
		Name: "zig", RepoDir: peDir + "/zig",
		SourcePath:   func(n int) string { return peDir + "/zig/problem_" + zeroPad(n) + "/main.zig" },
		ProblemGlob:  peDir + "/zig/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubBraceRe,
	},
	{
		Name: "c", RepoDir: peDir + "/c",
		SourcePath:   func(n int) string { return peDir + "/c/problem_" + zeroPad(n) + "/main.c" },
		ProblemGlob:  peDir + "/c/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubBraceRe,
	},
	{
		Name: "arm64", RepoDir: peDir + "/arm64",
		SourcePath:   func(n int) string { return peDir + "/arm64/problem_" + zeroPad(n) + "/solve.s" },
		ProblemGlob:  peDir + "/arm64/problem_*",
		ParseProblem: numFromDir, AnswerRe: answerSlashRe, StubRe: stubAsmRe,
	},
}

// ---------- bench data (data/bench-private.db, SQLite SSOT) ----------

type BenchEntry struct {
	Status string
	Answer string // bare value (no JSON wrapping); empty string = NULL in DB
	Error  string
	TimeNs int64
}

type BenchFile struct {
	Problems map[string]BenchEntry
}

// loadBench loads all rows for `lang` from the SQLite SSOT.
// Returns an empty BenchFile (not an error) if the DB file is absent — a
// pre-rebench state, valid for a clean clone before any bench has run.
//
// Migrated 2026-05-25 from per-lang JSON. Schema lives in
// `pe/benchmarks/cmd/euler-bench/db.go`; this reader maps the columns it
// cares about (status, answer, error, time_ns) into BenchEntry.
func loadBench(lang string) (*BenchFile, error) {
	path := dbPath()
	if _, err := os.Stat(path); err != nil {
		return &BenchFile{Problems: map[string]BenchEntry{}}, nil
	}
	// Read-only URI form prevents accidental writes from the audit tool.
	db, err := sql.Open("sqlite", "file:"+path+"?mode=ro")
	if err != nil {
		return nil, fmt.Errorf("open db: %w", err)
	}
	defer db.Close()

	rows, err := db.Query(
		`SELECT problem, status, COALESCE(answer,''), COALESCE(error,''), COALESCE(time_ns, 0)
		 FROM runs WHERE lang = ?`, lang)
	if err != nil {
		return nil, fmt.Errorf("query runs for %s: %w", lang, err)
	}
	defer rows.Close()

	bf := &BenchFile{Problems: map[string]BenchEntry{}}
	for rows.Next() {
		var p string
		var e BenchEntry
		if err := rows.Scan(&p, &e.Status, &e.Answer, &e.Error, &e.TimeNs); err != nil {
			return nil, fmt.Errorf("scan: %w", err)
		}
		bf.Problems[p] = e
	}
	return bf, rows.Err()
}

// answerToString returns the canonical comparison form of a bench answer.
// Post-SQLite migration this is a pass-through (the DB stores bare TEXT —
// no JSON wrapping to strip). Kept as a function so call sites don't have
// to change.
func answerToString(a string) string {
	return strings.TrimSpace(a)
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
	data, err := os.ReadFile(peDir + "/benchmarks/data/parked.json")
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

	bench, _ := loadBench(cfg.Name)
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
			Details: "SQLite SSOT has runs row but no matching source dir/file",
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
			Details: "source exists but no row in SQLite SSOT runs table",
		})
		return findings
	}

	// D1: status=fail
	if entry.Status == "fail" {
		findings = append(findings, Finding{
			Lang: cfg.Name, Problem: n, Category: "D1", Severity: sevError,
			Details: fmt.Sprintf("SQLite SSOT runs.status=fail (error: %q)", entry.Error),
		})
	}

	// C1 (cache_pattern) check retired 2026-05-25: the heuristic compared
	// warm time_ns vs cold_start_ns to spot solve() caching, but the
	// fresh-process bench model (every iteration is its own OS process)
	// eliminates the warm/cold distinction — every measurement is a cold
	// start. Cache-pattern detection is now a source-level concern, not
	// a bench-data signal. See project_pe_cache_pattern_campaign for the
	// source-grep approach.

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
		bench, _ := loadBench(cfg.Name)
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
