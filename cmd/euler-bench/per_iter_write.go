// per_iter_write — persist per-iteration bench results to the SQLite SSOT
// at data/bench-private.db. Single physical file; the public repo gets
// nothing — RESULTS.md + charts are the only thing committed.
//
// Migrated 2026-05-25: was JSON dual-write (data/<lang>.json public sanitized
// + data/private/<lang>.json full), now SQLite single-file. The sanitization
// invariant moves from "strip the answer field when serializing the public
// JSON" to "don't commit the .db file" — enforced by .gitignore +
// sanitization_gate.py rejection of any staged data/*.db or data/*.json.

package main

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"time"
)

// readCanonicalAnswer pulls the `// Answer: NNN` or `# Answer: NNN` header
// from the lang's source file.  Returns the trimmed answer string and an
// error if the file can't be opened or no Answer header is present.
//
// Matches the canonical `// Answer: <value>` or `# Answer: <value>` header.
// Capture group: EITHER a fully parens-wrapped marker (e.g. "(not solved)")
// OR the first whitespace-delimited token (e.g. "464399" from
// "464399 (represents 0.464399... * 1000000 rounded)"). Matches the
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
	sortStrings(paths)
	return paths
}

// sortStrings: trivial in-place sort to avoid pulling the sort package back
// in just for one call. n is always 1 or 2 in practice.
func sortStrings(s []string) {
	for i := 0; i < len(s); i++ {
		for j := i + 1; j < len(s); j++ {
			if s[j] < s[i] {
				s[i], s[j] = s[j], s[i]
			}
		}
	}
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

// buildRunRow converts a perIterResult into a runRow for SQLite write.
// Handles status (pass/fail/mismatch), nullable fields, and source metadata.
func buildRunRow(lang *Lang, r *perIterResult, canonical string,
	srcLines, srcBytes int, srcHash, compiler, platform string,
	measuredAt int64) *runRow {
	row := &runRow{
		Lang:        lang.Key,
		Problem:     r.Problem,
		SourceLines: srcLines,
		SourceBytes: srcBytes,
		SourceHash:  srcHash,
		MeasuredAt:  measuredAt,
		Compiler:    compiler,
		Platform:    platform,
	}
	if r.BuildErr != "" {
		row.Status = "fail"
		row.Error = r.BuildErr
		return row
	}
	if len(r.TimeSamplesNs) == 0 {
		row.Status = "fail"
		if r.RunErr != "" {
			row.Error = r.RunErr
		} else {
			row.Error = "no measurements"
		}
		return row
	}
	row.Status = "pass"
	row.Answer = r.Answer
	row.TimeNs = r.timeMedianNs()
	row.TimeMinNs = r.timeMinNs()
	row.TimeMaxNs = r.timeMaxNs()
	row.Samples = len(r.TimeSamplesNs)
	row.SubprocessWallNs = r.wallMedianNs()
	row.CompileTimeNs = r.CompileTimeNs
	row.PeakRSSBytes = r.PeakRSSBytes
	// Mismatch handling: if canonical disagrees with measured, mark fail.
	// The error message intentionally records both values for debugging —
	// safe to keep because the answer column is also stored on this row
	// (private DB only; never exported to the public repo).
	if canonical != "" && canonical != r.Answer {
		row.Status = "fail"
		row.Error = fmt.Sprintf("answer mismatch: measured=%s canonical=%s", r.Answer, canonical)
	}
	return row
}

// writeBenchResults upserts each result into the SSOT DB. Each row is written
// in a single transaction spanning `runs` (latest) + `run_history` (append).
// Returns the number of answer mismatches encountered.
func writeBenchResults(lang *Lang, baseDir string, results []*perIterResult) (mismatches int, err error) {
	db, err := openDB(baseDir)
	if err != nil {
		return 0, fmt.Errorf("open db: %w", err)
	}
	defer db.Close()

	compiler := getCompilerVersionPI(lang.CompilerCmd)
	platform := detectPlatform()
	measuredAt := time.Now().UTC().Unix()

	for _, r := range results {
		canonical, _ := readCanonicalAnswer(lang, baseDir, r.Problem)
		srcLines, srcBytes := countSourceMetrics(lang, baseDir, r.Problem)
		srcHash := hashAlgorithmSources(lang, baseDir, r.Problem)

		row := buildRunRow(lang, r, canonical, srcLines, srcBytes, srcHash,
			compiler, platform, measuredAt)
		if row.Status == "fail" && strings.Contains(row.Error, "mismatch") {
			mismatches++
		}
		if err := writeRun(db, row); err != nil {
			return mismatches, fmt.Errorf("writeRun %s/%s: %w", lang.Key, r.Problem, err)
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
