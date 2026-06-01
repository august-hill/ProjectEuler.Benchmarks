// companion-export emits sanitized per-language JSON files for the pe-companion
// macOS app. It reads the canonical bench DB read-only and writes one JSON
// file per language to the output directory, matching the schema that
// pe-companion's LocalJSONLoader expects.
//
// Why this exists separately from euler-bench:
//   - Single-purpose sanitization choke point. The `answer` column is never
//     SELECTed here, so it cannot leak into the app bundle. Audit is
//     `grep -r '"answer"' <outdir>` returning zero hits.
//   - The companion is sideloaded; the DB itself (with the answer column) must
//     not be bundled. JSON export decouples the wire format from the SSOT.
//   - If the runs table ever grows a sensitive column, it won't leak unless
//     someone explicitly adds it to this file's SELECT list.
//
// Output JSON shape (per language):
//
//	{
//	  "language": "cpp",
//	  "platform": "arm64",
//	  "compiler": "Apple clang version ...",
//	  "timestamp": "2026-05-25T00:00:00Z",   // ISO-8601 of max measured_at
//	  "problems": {
//	    "001": {
//	      "time_ns": 1234, "time_min_ns": 1200, "time_max_ns": 1300,
//	      "samples": 10, "compile_time_ns": 480000000, "peak_rss_bytes": ...,
//	      "source_lines": 55, "source_bytes": 1354,
//	      "status": "pass", "measured_at": 1748131200
//	    },
//	    ...
//	  }
//	}
//
// Fields NEVER emitted: answer, subprocess_wall_ns, source_hash.
// Fields not yet in the new schema but still in the legacy Swift model
// (cold_start_ns, iterations): also never emitted; the Swift model is being
// updated to treat them as optional during the migration.
package main

import (
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sort"
	"time"

	_ "modernc.org/sqlite"
)

// languages is the canonical 10-language list. Order matters only for
// log messages; pe-companion's LocalJSONLoader reads any subset that exists.
var languages = []string{
	"arm64", "c", "cpp", "csharp", "go",
	"java", "javascript", "python", "rust", "zig",
}

// problemEntry is the per-problem JSON shape. Pointer fields use omitempty so
// nullable DB columns disappear from JSON rather than appearing as `null` —
// this matches the existing fixture shape that the Swift decoder expects.
type problemEntry struct {
	TimeNs        *int64  `json:"time_ns,omitempty"`
	TimeMinNs     *int64  `json:"time_min_ns,omitempty"`
	TimeMaxNs     *int64  `json:"time_max_ns,omitempty"`
	Samples       *int64  `json:"samples,omitempty"`
	CompileTimeNs *int64  `json:"compile_time_ns,omitempty"`
	PeakRSSBytes  *int64  `json:"peak_rss_bytes,omitempty"`
	SourceLines   *int64  `json:"source_lines,omitempty"`
	SourceBytes   *int64  `json:"source_bytes,omitempty"`
	Status        string  `json:"status"`
	Error         *string `json:"error,omitempty"`
	MeasuredAt    int64   `json:"measured_at"`
}

// langReport is the top-level JSON shape. Compiler/platform/timestamp are
// derived from the most-recently-measured row for the language (per-row in the
// DB, but a single language run typically uses one toolchain — picking one
// representative keeps the file shape stable with the legacy fixture format).
type langReport struct {
	Language  string                  `json:"language"`
	Platform  string                  `json:"platform"`
	Compiler  string                  `json:"compiler"`
	Timestamp string                  `json:"timestamp"`
	Problems  map[string]problemEntry `json:"problems"`
}

func main() {
	dbPath := flag.String("db", "", "path to bench-private.db (required)")
	outDir := flag.String("out", "", "output directory for per-language JSON (required)")
	flag.Parse()

	if *dbPath == "" || *outDir == "" {
		log.Fatalf("usage: companion-export -db <path> -out <dir>")
	}
	if _, err := os.Stat(*dbPath); err != nil {
		log.Fatalf("db not readable: %v", err)
	}
	if err := os.MkdirAll(*outDir, 0o755); err != nil {
		log.Fatalf("mkdir %s: %v", *outDir, err)
	}

	// Read-only URI — defensive even though we never write. NOTE: we
	// intentionally do NOT set immutable=1 here. The bench DB can be
	// actively written to by euler-bench while we're reading; immutable=1
	// asserts the file won't change and lets SQLite skip WAL consultation,
	// which would produce stale/torn reads in that case. Plain mode=ro
	// keeps WAL handling intact and we get a consistent snapshot even
	// mid-rebench. Matches the read pattern in report.py.
	db, err := sql.Open("sqlite", "file:"+*dbPath+"?mode=ro")
	if err != nil {
		log.Fatalf("open db: %v", err)
	}
	defer db.Close()

	totalRows := 0
	for _, lang := range languages {
		report, n, err := loadLanguage(db, lang)
		if err != nil {
			log.Fatalf("load %s: %v", lang, err)
		}
		if n == 0 {
			log.Printf("%-10s — no rows; skipping (no JSON written)", lang)
			continue
		}
		outPath := filepath.Join(*outDir, lang+".json")
		if err := writeJSON(outPath, report); err != nil {
			log.Fatalf("write %s: %v", outPath, err)
		}
		log.Printf("%-10s — %4d problems → %s", lang, n, filepath.Base(outPath))
		totalRows += n
	}
	log.Printf("done. %d total rows across %d languages → %s",
		totalRows, len(languages), *outDir)
}

// loadLanguage builds a langReport for one language. Returns (report, rowCount, err);
// rowCount == 0 means no rows exist for the language (call site skips writing).
//
// SECURITY-CRITICAL: this SELECT lists every column we emit. The `answer`
// column is intentionally absent — never add it without re-reading
// pe/benchmarks/CLAUDE.md sanitization rules. `subprocess_wall_ns` and
// `source_hash` are also omitted as not-relevant-to-the-app.
func loadLanguage(db *sql.DB, lang string) (langReport, int, error) {
	const query = `
		SELECT problem, status,
		       time_ns, time_min_ns, time_max_ns, samples,
		       compile_time_ns, peak_rss_bytes,
		       source_lines, source_bytes,
		       error, measured_at, compiler, platform
		FROM runs
		WHERE lang = ?
		ORDER BY problem`

	rows, err := db.Query(query, lang)
	if err != nil {
		return langReport{}, 0, fmt.Errorf("query: %w", err)
	}
	defer rows.Close()

	report := langReport{
		Language: lang,
		Problems: make(map[string]problemEntry),
	}
	var maxMeasuredAt int64

	for rows.Next() {
		var (
			problem                                                  string
			status                                                   string
			timeNs, timeMinNs, timeMaxNs, samples                    sql.NullInt64
			compileTimeNs, peakRSSBytes, sourceLines, sourceBytes    sql.NullInt64
			errStr, compiler, platform                               sql.NullString
			measuredAt                                               int64
		)
		if err := rows.Scan(
			&problem, &status,
			&timeNs, &timeMinNs, &timeMaxNs, &samples,
			&compileTimeNs, &peakRSSBytes, &sourceLines, &sourceBytes,
			&errStr, &measuredAt, &compiler, &platform,
		); err != nil {
			return langReport{}, 0, fmt.Errorf("scan: %w", err)
		}

		report.Problems[problem] = problemEntry{
			TimeNs:        nullInt(timeNs),
			TimeMinNs:     nullInt(timeMinNs),
			TimeMaxNs:     nullInt(timeMaxNs),
			Samples:       nullInt(samples),
			CompileTimeNs: nullInt(compileTimeNs),
			PeakRSSBytes:  nullInt(peakRSSBytes),
			SourceLines:   nullInt(sourceLines),
			SourceBytes:   nullInt(sourceBytes),
			Status:        status,
			Error:         nullStr(errStr),
			MeasuredAt:    measuredAt,
		}

		// Track newest row to derive top-level compiler/platform/timestamp.
		if measuredAt > maxMeasuredAt {
			maxMeasuredAt = measuredAt
			if compiler.Valid {
				report.Compiler = compiler.String
			}
			if platform.Valid {
				report.Platform = platform.String
			}
		}
	}
	if err := rows.Err(); err != nil {
		return langReport{}, 0, fmt.Errorf("rows: %w", err)
	}

	if maxMeasuredAt > 0 {
		report.Timestamp = time.Unix(maxMeasuredAt, 0).UTC().Format(time.RFC3339)
	}
	return report, len(report.Problems), nil
}

// nullInt converts a nullable INTEGER column into a *int64 for omitempty JSON.
func nullInt(n sql.NullInt64) *int64 {
	if !n.Valid {
		return nil
	}
	v := n.Int64
	return &v
}

// nullStr converts a nullable TEXT column into a *string for omitempty JSON.
func nullStr(s sql.NullString) *string {
	if !s.Valid || s.String == "" {
		return nil
	}
	v := s.String
	return &v
}

// writeJSON marshals the report and writes it atomically (write to .tmp, rename).
// Stable key ordering: map keys are sorted alphabetically by encoding/json, so
// problem keys ("001", "002", ...) come out in the right order naturally.
func writeJSON(path string, report langReport) error {
	// Sort the problem map's keys deterministically. encoding/json already
	// sorts map keys alphabetically, but spelling it out keeps the contract
	// explicit if the output struct ever changes.
	keys := make([]string, 0, len(report.Problems))
	for k := range report.Problems {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	data, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal: %w", err)
	}

	// Atomic write to avoid leaving a partial file if the process dies mid-write
	// while the SPM build plugin's prebuild command is executing.
	tmpPath := path + ".tmp"
	if err := os.WriteFile(tmpPath, data, 0o644); err != nil {
		return fmt.Errorf("write tmp: %w", err)
	}
	if err := os.Rename(tmpPath, path); err != nil {
		_ = os.Remove(tmpPath)
		return fmt.Errorf("rename: %w", err)
	}
	return nil
}
