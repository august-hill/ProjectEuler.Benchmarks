// db.go — SQLite SSOT for bench data. Single local file `data/bench-private.db`
// holds every measurement; the public repo gets only RESULTS.md + charts
// (no raw bench data is committed). Companion / dud_audit / report.py all read
// from this DB.
//
// Schema (version 1, established 2026-05-25):
//   runs         latest measurement per (lang, problem)   PK = (lang, problem)
//   run_history  every measurement appended; enables drift audit + sample accumulation
//   schema_version  single-row metadata
//
// Why SQLite (not JSON):
//   - Schema-validated writes catch field-name drifts at insert time (the
//     2026-05-23 cold_start_ns→time_ns rename was silent across all consumers).
//   - Transactional multi-table writes (`runs` + `run_history`) are atomic; the
//     prior `atomicWriteJSON` only handled single-file atomicity.
//   - Cross-lang / cross-problem queries are one SQL statement instead of
//     N json.load calls + nested dict access.
//   - Library: modernc.org/sqlite (pure-Go, no CGo). Same choice as aria-server
//     for workspace consistency.

package main

import (
	"database/sql"
	"fmt"
	"path/filepath"

	_ "modernc.org/sqlite"
)

// dbPath returns the absolute path to the SQLite SSOT.
func dbPath(baseDir string) string {
	return filepath.Join(baseDir, "benchmarks", "data", "bench-private.db")
}

// openDB opens the SSOT DB and applies the canonical pragmas + schema.
// Caller is responsible for closing.
func openDB(baseDir string) (*sql.DB, error) {
	path := dbPath(baseDir)
	db, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, fmt.Errorf("open sqlite %s: %w", path, err)
	}
	// WAL gives concurrent readers; NORMAL sync trades a tiny risk of
	// last-transaction loss on power failure for ~10x write throughput.
	// foreign_keys=OFF: we don't use FKs (run_history is not joined to runs).
	for _, pragma := range []string{
		"PRAGMA journal_mode=WAL",
		"PRAGMA synchronous=NORMAL",
		"PRAGMA foreign_keys=OFF",
		"PRAGMA busy_timeout=5000",
	} {
		if _, err := db.Exec(pragma); err != nil {
			db.Close()
			return nil, fmt.Errorf("%s: %w", pragma, err)
		}
	}
	if err := ensureSchema(db); err != nil {
		db.Close()
		return nil, err
	}
	return db, nil
}

// ensureSchema creates the tables if missing and verifies the schema version.
// Idempotent — safe to call on every open.
func ensureSchema(db *sql.DB) error {
	stmts := []string{
		`CREATE TABLE IF NOT EXISTS schema_version (
			version INTEGER NOT NULL PRIMARY KEY
		)`,
		`CREATE TABLE IF NOT EXISTS runs (
			lang               TEXT    NOT NULL,
			problem            TEXT    NOT NULL,
			status             TEXT    NOT NULL CHECK (status IN ('pass','fail')),
			answer             TEXT,
			time_ns            INTEGER,
			time_min_ns        INTEGER,
			time_max_ns        INTEGER,
			samples            INTEGER,
			subprocess_wall_ns INTEGER,
			compile_time_ns    INTEGER,
			peak_rss_bytes     INTEGER,
			source_lines       INTEGER,
			source_bytes       INTEGER,
			source_hash        TEXT,
			error              TEXT,
			measured_at        INTEGER NOT NULL,
			compiler           TEXT,
			platform           TEXT,
			cpu_ns             INTEGER,
			loadavg            REAL,
			flags              TEXT,
			PRIMARY KEY (lang, problem)
		)`,
		`CREATE TABLE IF NOT EXISTS run_history (
			id                 INTEGER PRIMARY KEY AUTOINCREMENT,
			lang               TEXT    NOT NULL,
			problem            TEXT    NOT NULL,
			status             TEXT    NOT NULL,
			answer             TEXT,
			time_ns            INTEGER,
			time_min_ns        INTEGER,
			time_max_ns        INTEGER,
			samples            INTEGER,
			subprocess_wall_ns INTEGER,
			compile_time_ns    INTEGER,
			peak_rss_bytes     INTEGER,
			source_lines       INTEGER,
			source_bytes       INTEGER,
			source_hash        TEXT,
			error              TEXT,
			measured_at        INTEGER NOT NULL,
			compiler           TEXT,
			platform           TEXT,
			cpu_ns             INTEGER,
			loadavg            REAL,
			flags              TEXT
		)`,
		`CREATE INDEX IF NOT EXISTS ix_history_by_problem
			ON run_history(lang, problem, measured_at DESC)`,
	}
	for _, s := range stmts {
		if _, err := db.Exec(s); err != nil {
			return fmt.Errorf("schema stmt failed: %w\nstmt: %s", err, s)
		}
	}

	// Initialize schema_version row if not yet set; migrate v1 -> v2 in place.
	// v2 (2026-07-03): adds cpu_ns (rusage user+sys, process-contract gate),
	// loadavg (1-min system load at measurement, environment audit trail),
	// flags (comma-separated warnings, e.g. no-corroboration / near-zero-time).
	var v int
	err := db.QueryRow("SELECT version FROM schema_version LIMIT 1").Scan(&v)
	if err == sql.ErrNoRows {
		if _, err := db.Exec("INSERT INTO schema_version (version) VALUES (2)"); err != nil {
			return fmt.Errorf("init schema_version: %w", err)
		}
	} else if err != nil {
		return fmt.Errorf("read schema_version: %w", err)
	} else if v == 1 {
		for _, mig := range []string{
			"ALTER TABLE runs ADD COLUMN cpu_ns INTEGER",
			"ALTER TABLE runs ADD COLUMN loadavg REAL",
			"ALTER TABLE runs ADD COLUMN flags TEXT",
			"ALTER TABLE run_history ADD COLUMN cpu_ns INTEGER",
			"ALTER TABLE run_history ADD COLUMN loadavg REAL",
			"ALTER TABLE run_history ADD COLUMN flags TEXT",
		} {
			if _, err := db.Exec(mig); err != nil {
				return fmt.Errorf("v1->v2 migration failed: %w\nstmt: %s", err, mig)
			}
		}
		if _, err := db.Exec("UPDATE schema_version SET version = 2"); err != nil {
			return fmt.Errorf("bump schema_version: %w", err)
		}
	} else if v != 2 {
		return fmt.Errorf("unsupported schema_version=%d (this tool expects 2)", v)
	}
	return nil
}

// runRow is the wire-format struct passed to writeRun. Mirrors the table
// columns 1:1 — keeps the writer/reader contract obvious.
type runRow struct {
	Lang             string
	Problem          string
	Status           string // "pass" or "fail"
	Answer           string // empty string → NULL
	TimeNs           int64
	TimeMinNs        int64
	TimeMaxNs        int64
	Samples          int
	SubprocessWallNs int64
	CompileTimeNs    int64
	PeakRSSBytes     int64
	SourceLines      int
	SourceBytes      int
	SourceHash       string
	Error            string // empty string → NULL
	MeasuredAt       int64  // unix epoch seconds
	Compiler         string
	Platform         string
	CPUNs            int64   // median rusage user+sys across samples
	LoadAvg          float64 // max 1-min loadavg observed across samples
	Flags            string  // comma-separated warnings; empty -> NULL
}

// writeRun upserts the given row into `runs` AND appends it to `run_history`,
// in a single transaction. Either both writes land or neither does.
func writeRun(db *sql.DB, r *runRow) error {
	tx, err := db.Begin()
	if err != nil {
		return fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback() // no-op if Commit succeeds

	const upsertRuns = `
		INSERT INTO runs (
			lang, problem, status, answer,
			time_ns, time_min_ns, time_max_ns, samples,
			subprocess_wall_ns, compile_time_ns, peak_rss_bytes,
			source_lines, source_bytes, source_hash,
			error, measured_at, compiler, platform,
			cpu_ns, loadavg, flags
		) VALUES (?,?,?,?, ?,?,?,?, ?,?,?, ?,?,?, ?,?,?,?, ?,?,?)
		ON CONFLICT(lang, problem) DO UPDATE SET
			status=excluded.status, answer=excluded.answer,
			time_ns=excluded.time_ns, time_min_ns=excluded.time_min_ns,
			time_max_ns=excluded.time_max_ns, samples=excluded.samples,
			subprocess_wall_ns=excluded.subprocess_wall_ns,
			compile_time_ns=excluded.compile_time_ns,
			peak_rss_bytes=excluded.peak_rss_bytes,
			source_lines=excluded.source_lines, source_bytes=excluded.source_bytes,
			source_hash=excluded.source_hash,
			error=excluded.error, measured_at=excluded.measured_at,
			compiler=excluded.compiler, platform=excluded.platform,
			cpu_ns=excluded.cpu_ns, loadavg=excluded.loadavg, flags=excluded.flags`

	const insertHistory = `
		INSERT INTO run_history (
			lang, problem, status, answer,
			time_ns, time_min_ns, time_max_ns, samples,
			subprocess_wall_ns, compile_time_ns, peak_rss_bytes,
			source_lines, source_bytes, source_hash,
			error, measured_at, compiler, platform,
			cpu_ns, loadavg, flags
		) VALUES (?,?,?,?, ?,?,?,?, ?,?,?, ?,?,?, ?,?,?,?, ?,?,?)`

	// INTEGER fields stored as-is — including legitimate 0 measurements
	// (closed-form algos can clock at sub-ns, faster than CLOCK_MONOTONIC's
	// resolution → time_ns=0). The `status` column is the authoritative
	// "is this data meaningful" gate; downstream consumers gate on
	// status='pass' before trusting time fields. Strings still null-out
	// on empty (less semantic loss there — "" vs NULL doesn't usually matter).
	args := []interface{}{
		r.Lang, r.Problem, r.Status, nullableString(r.Answer),
		r.TimeNs, r.TimeMinNs, r.TimeMaxNs, r.Samples,
		r.SubprocessWallNs, r.CompileTimeNs, r.PeakRSSBytes,
		r.SourceLines, r.SourceBytes, nullableString(r.SourceHash),
		nullableString(r.Error), r.MeasuredAt, nullableString(r.Compiler), nullableString(r.Platform),
		r.CPUNs, r.LoadAvg, nullableString(r.Flags),
	}
	if _, err := tx.Exec(upsertRuns, args...); err != nil {
		return fmt.Errorf("upsert runs: %w", err)
	}
	if _, err := tx.Exec(insertHistory, args...); err != nil {
		return fmt.Errorf("insert run_history: %w", err)
	}
	return tx.Commit()
}

// nullableString returns nil for empty strings so SQLite stores NULL, not ''.
func nullableString(s string) interface{} {
	if s == "" {
		return nil
	}
	return s
}

// (nullableInt64 retired 2026-05-25 — the zero-coercion semantically conflated
// "fail / not measured" with "measured 0" (legitimate for closed-form algos
// that clock at sub-ns). Status column is the authoritative gate; INTEGER
// fields now store as-is.)
