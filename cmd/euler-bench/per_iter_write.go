// per_iter_write — write per-iteration bench results to data/<lang>.json
// with sanitization, plus a private full-data file at data/private/<lang>.json.
//
// SANITIZATION POLICY (CRITICAL — this repo is public):
//   - Public data files NEVER contain the `answer` field, regardless of
//     problem number.  PE's publishing rule (projecteuler.net/about#publish)
//     permits public discussion of ≤100 answers, but the bench data file's
//     purpose is timings — answers add no value here and only enlarge the
//     leak surface.  Narrative discussion (JOURNEY.md, etc.) is unaffected.
//   - Full data including answers for ALL problems is written to
//     data/private/<lang>.json — a gitignored path, local-only, for
//     verification and debugging.
//   - The single point of decision is `writePublicEntry` below — it has
//     no code path that writes the answer field at all.  The post-write
//     readback assertion + scripts/sanitization_gate.py both verify the
//     invariant "no public data file has any answer key, ever" as
//     defense-in-depth.
//
// VERIFICATION (inline Gate 1):
//   - For each (lang, problem) measured, the tool reads the canonical
//     answer from the lang source's `// Answer:` / `# Answer:` header
//     comment.  If the measured answer disagrees with the canonical, the
//     entry is recorded with status=fail and the data write proceeds; the
//     mismatch is also surfaced loudly in the run summary.

package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"time"
)

// (SanitizationCutoff retired 2026-05-23: public data files now NEVER include
// the answer field. The previous ≤100 carve-out aligned with PE policy's
// upper bound but offered no functional value to the bench data — answers
// add no information to a timing-focused file. Simpler rule, smaller leak
// surface, no per-problem branching.)

// publicEntry is the JSON shape of a problem result in data/<lang>.json.
// Schema after the 2026-05-23 "Single-Call Harness" cleanup: ONE timing
// per problem (median over N fresh-process invocations of the harness's
// single solve() call).  The legacy warm-vs-cold dichotomy is gone —
// fields are named directly for what they measure.
type publicEntry struct {
	Answer           any    `json:"answer,omitempty"`              // PUBLIC: never present (sanitization)
	TimeNs           int64  `json:"time_ns"`                       // median time_ns from RESULT line across N samples
	TimeMinNs        int64  `json:"time_min_ns,omitempty"`         // min across samples
	TimeMaxNs        int64  `json:"time_max_ns,omitempty"`         // max across samples
	Samples          int    `json:"samples,omitempty"`             // N (fresh-process invocations)
	SubprocessWallNs int64  `json:"subprocess_wall_ns,omitempty"`  // median Go-perceived wall, sanity-check secondary
	CompileTimeNs    int64  `json:"compile_time_ns,omitempty"`
	Status           string `json:"status"`
	Error            string `json:"error,omitempty"`
	PeakRSSBytes     int64  `json:"peak_rss_bytes,omitempty"`
	SourceLines      int    `json:"source_lines,omitempty"`
	SourceBytes      int    `json:"source_bytes,omitempty"`
	SourceHash       string `json:"source_hash,omitempty"` // SHA-256 hex of algorithm sources, concatenated in sorted-by-filename order
}

type benchData struct {
	Language  string                 `json:"language"`
	Platform  string                 `json:"platform"`
	Compiler  string                 `json:"compiler"`
	Timestamp string                 `json:"timestamp"`
	Problems  map[string]publicEntry `json:"problems"`
}

// readCanonicalAnswer pulls the `// Answer: NNN` or `# Answer: NNN` header
// from the lang's source file.  Returns the trimmed answer string and an
// error if the file can't be opened or no Answer header is present.
//
// Source-file selection is per-lang and mirrors the build adapter's source
// expectations.  For ARM64, solve.s is preferred (algorithm-implementation
// file); falls back to main.c if absent.
// Matches the canonical `// Answer: <value>` or `# Answer: <value>` header.
// Capture group: EITHER a fully parens-wrapped marker (e.g. "(not solved)")
// OR the first whitespace-delimited token (e.g. "464399" from
// "464399 (represents 0.464399... * 1000000 rounded)"). This matches the
// dud_audit parser's behavior so the two tools agree on canonical values.
// Bug history: an earlier `(.+?)\s*$` pattern captured the trailing
// parenthetical description as part of the canonical, producing false-positive
// mismatches on every non-integer-encoded problem (caught 2026-05-24 during
// the ARM64 full rebench: 6 spurious fails, all of shape "464399 (text)").
var answerHeaderRe = regexp.MustCompile(`(?m)^(?://|#)\s*Answer:\s*(\([^)]*\)|\S+)`)

func canonicalAnswerSourcePath(lang *Lang, baseDir, problem string) string {
	repoDir := filepath.Join(baseDir, lang.Repo)
	probDir := filepath.Join(repoDir, "problem_"+problem)

	// Lang-specific source-file picks:
	switch lang.Key {
	case "python":
		return filepath.Join(repoDir, "problem_"+problem+".py")
	case "arm64":
		// Prefer solve.s (algorithm location); fall back to main.c
		s := filepath.Join(probDir, "solve.s")
		if _, err := os.Stat(s); err == nil {
			return s
		}
		return filepath.Join(probDir, "main.c")
	case "csharp":
		return filepath.Join(probDir, "Program.cs")
	case "java":
		return filepath.Join(probDir, "Main.java")
	case "rust":
		return filepath.Join(probDir, "src", "main.rs")
	default:
		// cpp/c/go/zig/javascript: main.<srcext> at problem dir
		return filepath.Join(probDir, lang.SrcFile)
	}
}

func readCanonicalAnswer(lang *Lang, baseDir, problem string) (string, error) {
	path := canonicalAnswerSourcePath(lang, baseDir, problem)
	data, err := os.ReadFile(path)
	if err != nil {
		return "", fmt.Errorf("can't read %s: %w", path, err)
	}
	m := answerHeaderRe.FindSubmatch(data)
	if m == nil {
		return "", fmt.Errorf("no `Answer:` header in %s", path)
	}
	return strings.TrimSpace(string(m[1])), nil
}

// algorithmSourcePaths returns the file(s) that constitute the algorithm
// solution for (lang, problem). Used by both source-metric counting and
// source-hash computation. For ARM64 returns both the asm and its thin C
// harness wrapper (both contribute to the solution surface). For Java we
// hash only Main.java — Bench.java is shared per-problem harness boilerplate
// that doesn't affect algorithm freshness. Other langs are single-file.
//
// Result is sorted by path to give a deterministic concat order for hashing.
func algorithmSourcePaths(lang *Lang, baseDir, problem string) []string {
	repoDir := filepath.Join(baseDir, lang.Repo)
	probDir := filepath.Join(repoDir, "problem_"+problem)

	var paths []string
	switch lang.Key {
	case "arm64":
		// Both the asm solve and the thin C harness count — a change to
		// either is a change to the solution surface.
		for _, name := range []string{"main.c", "solve.s"} {
			p := filepath.Join(probDir, name)
			if _, err := os.Stat(p); err == nil {
				paths = append(paths, p)
			}
		}
	default:
		// All others: a single canonical source file (the one with the
		// `// Answer:` header).
		paths = append(paths, canonicalAnswerSourcePath(lang, baseDir, problem))
	}
	sort.Strings(paths)
	return paths
}

// countSourceMetrics returns (lines, bytes) summed across every file in the
// algorithm source set. For single-file langs this is the obvious thing; for
// ARM64 it sums asm + C harness. Returns (0, 0) on read error rather than
// failing the bench — a missing source-line count is non-fatal.
func countSourceMetrics(lang *Lang, baseDir, problem string) (lines, bytes int) {
	for _, path := range algorithmSourcePaths(lang, baseDir, problem) {
		data, err := os.ReadFile(path)
		if err != nil {
			continue
		}
		bytes += len(data)
		for _, b := range data {
			if b == '\n' {
				lines++
			}
		}
		// Count the final unterminated line if the file doesn't end with \n
		if len(data) > 0 && data[len(data)-1] != '\n' {
			lines++
		}
	}
	return lines, bytes
}

// hashAlgorithmSources returns a SHA-256 hex string over the concatenated
// bytes of every algorithm source file (in sorted-by-path order, so the
// result is deterministic). Empty string on read error — non-fatal.
//
// This is the cryptographic-strength complement to (source_lines, source_bytes):
// LOC+bytes catches the common case of any byte-count-changing edit; the
// hash catches byte-preserving edits (single-char swaps, identifier renames
// of the same length, etc.) that would otherwise slip past freshness checks.
func hashAlgorithmSources(lang *Lang, baseDir, problem string) string {
	h := sha256.New()
	any := false
	for _, path := range algorithmSourcePaths(lang, baseDir, problem) {
		data, err := os.ReadFile(path)
		if err != nil {
			continue
		}
		h.Write(data)
		any = true
	}
	if !any {
		return ""
	}
	return hex.EncodeToString(h.Sum(nil))
}

// writePublicEntry constructs the entry that lands in the public data file.
// The entry NEVER contains the answer field — this function has no code path
// that would set entry.Answer.  Mismatch detection still runs (against the
// canonical from `// Answer:` source comment) but the error message never
// reveals the value.
func writePublicEntry(r *perIterResult, canonical string, problemNum int) publicEntry {
	entry := publicEntry{
		TimeNs:           r.timeMedianNs(),
		TimeMinNs:        r.timeMinNs(),
		TimeMaxNs:        r.timeMaxNs(),
		Samples:          len(r.TimeSamplesNs),
		SubprocessWallNs: r.wallMedianNs(),
		Status:           "pass",
	}
	if r.BuildErr != "" {
		entry.Status = "fail"
		entry.Error = r.BuildErr
		return entry
	}
	if len(r.TimeSamplesNs) == 0 {
		entry.Status = "fail"
		if r.RunErr != "" {
			entry.Error = r.RunErr
		} else {
			entry.Error = "no measurements"
		}
		return entry
	}
	// Mismatch handling: if canonical disagrees with measured, mark fail.
	// The error message NEVER reveals the answer value — only that a
	// mismatch occurred, with a reference to where the canonical lives.
	if canonical != "" && canonical != r.Answer {
		entry.Status = "fail"
		entry.Error = "answer mismatch vs canonical `// Answer:` source comment"
	}
	return entry
}

// writePrivateEntry: full data, always includes the measured answer regardless
// of problem number.  Lives in data/private/ (gitignored).
func writePrivateEntry(r *perIterResult, canonical string) publicEntry {
	entry := publicEntry{
		TimeNs:           r.timeMedianNs(),
		TimeMinNs:        r.timeMinNs(),
		TimeMaxNs:        r.timeMaxNs(),
		Samples:          len(r.TimeSamplesNs),
		SubprocessWallNs: r.wallMedianNs(),
		Status:           "pass",
	}
	if r.BuildErr != "" {
		entry.Status = "fail"
		entry.Error = r.BuildErr
		return entry
	}
	if len(r.TimeSamplesNs) == 0 {
		entry.Status = "fail"
		entry.Error = r.RunErr
		return entry
	}
	// Always include answer in private file
	if r.Answer != "" {
		if _, err := strconv.ParseFloat(r.Answer, 64); err == nil {
			entry.Answer = json.Number(r.Answer)
		} else {
			entry.Answer = r.Answer
		}
	}
	if canonical != "" && canonical != r.Answer {
		entry.Status = "fail"
		entry.Error = fmt.Sprintf("answer mismatch: measured=%s canonical=%s", r.Answer, canonical)
	}
	return entry
}

// loadExistingData reads data/<lang>.json (or private equivalent) if it
// exists, returning a baseline to merge new measurements into.  Returns an
// empty benchData if the file is absent.
func loadExistingData(path, lang, compiler string) *benchData {
	d := &benchData{
		Language:  lang,
		Platform:  detectPlatform(),
		Compiler:  compiler,
		Timestamp: time.Now().UTC().Format("2006-01-02T15:04:05Z"),
		Problems:  map[string]publicEntry{},
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return d
	}
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.UseNumber()
	_ = dec.Decode(d)
	if d.Problems == nil {
		d.Problems = map[string]publicEntry{}
	}
	return d
}

// atomicWriteJSON writes JSON to path via .tmp + rename so partial writes
// can't be observed by a concurrent reader (sanitization_gate, etc.).
func atomicWriteJSON(path string, data any) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return fmt.Errorf("mkdir %s: %w", filepath.Dir(path), err)
	}
	tmp := path + ".tmp"
	f, err := os.OpenFile(tmp, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0o644)
	if err != nil {
		return err
	}
	enc := json.NewEncoder(f)
	enc.SetIndent("", "  ")
	if err := enc.Encode(data); err != nil {
		f.Close()
		os.Remove(tmp)
		return err
	}
	if err := f.Close(); err != nil {
		os.Remove(tmp)
		return err
	}
	return os.Rename(tmp, path)
}

// writeBenchResults updates data/<lang>.json (sanitized) and
// data/private/<lang>.json (full).  Existing entries for unmeasured
// problems are preserved.  Returns the number of mismatch failures.
func writeBenchResults(lang *Lang, baseDir string, results []*perIterResult) (mismatches int, err error) {
	benchmarksDir := filepath.Join(baseDir, "benchmarks")
	publicPath := filepath.Join(benchmarksDir, "data", lang.Key+".json")
	privatePath := filepath.Join(benchmarksDir, "data", "private", lang.Key+".json")

	compiler := getCompilerVersionPI(lang.CompilerCmd)
	public := loadExistingData(publicPath, lang.Key, compiler)
	private := loadExistingData(privatePath, lang.Key, compiler)
	now := time.Now().UTC().Format("2006-01-02T15:04:05Z")
	public.Timestamp = now
	private.Timestamp = now
	public.Compiler = compiler
	private.Compiler = compiler

	for _, r := range results {
		canonical, _ := readCanonicalAnswer(lang, baseDir, r.Problem)
		problemNum, _ := strconv.Atoi(r.Problem)
		srcLines, srcBytes := countSourceMetrics(lang, baseDir, r.Problem)
		srcHash := hashAlgorithmSources(lang, baseDir, r.Problem)

		pubEntry := writePublicEntry(r, canonical, problemNum)
		pubEntry.SourceLines = srcLines
		pubEntry.SourceBytes = srcBytes
		pubEntry.SourceHash = srcHash
		pubEntry.CompileTimeNs = r.CompileTimeNs
		pubEntry.PeakRSSBytes = r.PeakRSSBytes

		privEntry := writePrivateEntry(r, canonical)
		privEntry.SourceLines = srcLines
		privEntry.SourceBytes = srcBytes
		privEntry.SourceHash = srcHash
		privEntry.CompileTimeNs = r.CompileTimeNs
		privEntry.PeakRSSBytes = r.PeakRSSBytes

		if pubEntry.Status == "fail" && strings.Contains(pubEntry.Error, "mismatch") {
			mismatches++
		}

		public.Problems[r.Problem] = pubEntry
		private.Problems[r.Problem] = privEntry
	}

	if err := atomicWriteJSON(publicPath, public); err != nil {
		return mismatches, fmt.Errorf("write public: %w", err)
	}
	if err := atomicWriteJSON(privatePath, private); err != nil {
		return mismatches, fmt.Errorf("write private: %w", err)
	}

	// Sanity assertion: re-read the public file and verify NO problem has an
	// `answer` field anywhere.  Paranoid belt-and-braces against a future
	// bug that bypasses writePublicEntry.
	verify, err := os.ReadFile(publicPath)
	if err != nil {
		return mismatches, err
	}
	var check struct {
		Problems map[string]map[string]any `json:"problems"`
	}
	if err := json.Unmarshal(verify, &check); err == nil {
		var leaked []string
		for k, v := range check.Problems {
			if _, has := v["answer"]; has {
				leaked = append(leaked, k)
			}
		}
		if len(leaked) > 0 {
			sort.Strings(leaked)
			return mismatches, fmt.Errorf(
				"SANITIZATION VIOLATION: %s contains answer field for: %v "+
					"(public data must never contain the answer key)",
				publicPath, leaked,
			)
		}
	}

	return mismatches, nil
}

// getCompilerVersionPI runs the lang's CompilerCmd and returns the first line,
// or "unknown" if the command fails.  Named ...PI to avoid collision with
// any helper in runner.go.
func getCompilerVersionPI(cmdParts []string) string {
	if len(cmdParts) == 0 {
		return "unknown"
	}
	out, err := exec.Command(cmdParts[0], cmdParts[1:]...).CombinedOutput()
	if err != nil {
		return "unknown"
	}
	first := strings.SplitN(string(out), "\n", 2)[0]
	return strings.TrimSpace(first)
}

func detectPlatform() string {
	return runtime.GOARCH
}
