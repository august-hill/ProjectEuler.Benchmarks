// check_timing_delta — flag PE benchmark timing regressions before auto-publish.
//
// Compares working-tree data/{lang}.json against `git show HEAD:data/{lang}.json`
// for the supplied problem list. A problem is a violation when:
//   - both sides have status=="pass" AND
//   - both sides have time_ns >= floor (default 2ms) AND
//   - max(new, old) / min(new, old) > threshold (default 3.0)
//
// First-time problems (not in HEAD) are recorded as "new" and don't fail.
// Threshold is overridable via PE_BENCH_REGRESSION_RATIO env var.
//
// stdout: a JSON report.
// exit 0: clean (no violations).
// exit 2: at least one violation.
// exit 1: tool error (bad args, malformed JSON, git failure).
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"strings"
)

type problemEntry struct {
	TimeNs int64  `json:"time_ns"`
	Status string `json:"status"`
}

type langData struct {
	Problems map[string]json.RawMessage `json:"problems"`
}

type violation struct {
	Problem string  `json:"problem"`
	OldNs   int64   `json:"old_ns"`
	NewNs   int64   `json:"new_ns"`
	Ratio   float64 `json:"ratio"`
}

type report struct {
	Lang        string      `json:"lang"`
	Threshold   float64     `json:"threshold"`
	FloorNs     int64       `json:"floor_ns"`
	Checked     []string    `json:"checked"`
	NewProblems []string    `json:"new_problems"`
	SkippedFloor []string   `json:"skipped_floor"`
	SkippedFail []string    `json:"skipped_fail"`
	Missing     []string    `json:"missing"`
	Violations  []violation `json:"violations"`
}

func loadFile(path string) (*langData, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var d langData
	if err := json.Unmarshal(b, &d); err != nil {
		return nil, fmt.Errorf("parse %s: %w", path, err)
	}
	return &d, nil
}

func loadFromHEAD(repo, lang string) (*langData, error) {
	cmd := exec.Command("git", "show", fmt.Sprintf("HEAD:data/%s.json", lang))
	cmd.Dir = repo
	out, err := cmd.Output()
	if err != nil {
		// File didn't exist in HEAD (new lang) — treat as empty
		return &langData{Problems: map[string]json.RawMessage{}}, nil
	}
	var d langData
	if err := json.Unmarshal(out, &d); err != nil {
		return nil, fmt.Errorf("parse HEAD:data/%s.json: %w", lang, err)
	}
	return &d, nil
}

// lookupProblem tries the literal key then a zero-padded 3-digit form.
// Data keys are stored zero-padded ("070") but callers might pass "70".
func lookupProblem(m map[string]json.RawMessage, key string) (problemEntry, bool) {
	candidates := []string{key}
	if n, err := strconv.Atoi(strings.TrimLeft(key, "0")); err == nil {
		candidates = append(candidates, fmt.Sprintf("%03d", n))
		candidates = append(candidates, strconv.Itoa(n))
	}
	for _, k := range candidates {
		if raw, ok := m[k]; ok {
			var pe problemEntry
			if err := json.Unmarshal(raw, &pe); err == nil {
				return pe, true
			}
		}
	}
	return problemEntry{}, false
}

func main() {
	var lang, problemsCSV, repo string
	flag.StringVar(&lang, "lang", "", "language key (e.g. arm64, python)")
	flag.StringVar(&problemsCSV, "problems", "", "comma-separated problem numbers")
	flag.StringVar(&repo, "repo", "/Users/augusthill/ccdev/ProjectEuler.Benchmarks", "Benchmarks repo path")
	flag.Parse()

	if lang == "" || problemsCSV == "" {
		fmt.Fprintln(os.Stderr, "usage: check_timing_delta --lang LANG --problems N1,N2,...")
		os.Exit(1)
	}

	threshold := 3.0
	if v := os.Getenv("PE_BENCH_REGRESSION_RATIO"); v != "" {
		if f, err := strconv.ParseFloat(v, 64); err == nil && f > 1.0 {
			threshold = f
		}
	}
	floorNs := int64(2_000_000)

	curPath := fmt.Sprintf("%s/data/%s.json", repo, lang)
	cur, err := loadFile(curPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "load current: %v\n", err)
		os.Exit(1)
	}
	head, err := loadFromHEAD(repo, lang)
	if err != nil {
		fmt.Fprintf(os.Stderr, "load HEAD: %v\n", err)
		os.Exit(1)
	}

	rep := report{
		Lang:      lang,
		Threshold: threshold,
		FloorNs:   floorNs,
	}

	for _, p := range strings.Split(problemsCSV, ",") {
		p = strings.TrimSpace(p)
		if p == "" {
			continue
		}
		curEntry, curOK := lookupProblem(cur.Problems, p)
		if !curOK {
			rep.Missing = append(rep.Missing, p)
			continue
		}
		headEntry, headOK := lookupProblem(head.Problems, p)
		if !headOK {
			rep.NewProblems = append(rep.NewProblems, p)
			continue
		}
		if curEntry.Status != "pass" || headEntry.Status != "pass" {
			rep.SkippedFail = append(rep.SkippedFail, p)
			continue
		}
		if curEntry.TimeNs < floorNs || headEntry.TimeNs < floorNs {
			rep.SkippedFloor = append(rep.SkippedFloor, p)
			continue
		}
		rep.Checked = append(rep.Checked, p)
		var ratio float64
		if curEntry.TimeNs >= headEntry.TimeNs {
			ratio = float64(curEntry.TimeNs) / float64(headEntry.TimeNs)
		} else {
			ratio = float64(headEntry.TimeNs) / float64(curEntry.TimeNs)
		}
		if ratio > threshold {
			rep.Violations = append(rep.Violations, violation{
				Problem: p,
				OldNs:   headEntry.TimeNs,
				NewNs:   curEntry.TimeNs,
				Ratio:   ratio,
			})
		}
	}

	out, err := json.MarshalIndent(rep, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "marshal report: %v\n", err)
		os.Exit(1)
	}
	fmt.Println(string(out))

	if len(rep.Violations) > 0 {
		os.Exit(2)
	}
}
