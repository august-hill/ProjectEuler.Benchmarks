#!/usr/bin/env bash
# Shared post-commit logic for the 10 PE language repos.
# Called by each repo's .git/hooks/post-commit (a thin wrapper that passes --lang).
#
# Behavior:
#   1. Detect problem numbers touched by HEAD.
#   2. If any, run partial bench in the lang repo (./benchmark.sh --problems N1,N2,...).
#      The lang's benchmark.sh has native merge logic that preserves existing entries.
#   3. Run Benchmarks/scripts/collect.sh (sanitize-then-copy).
#   4. Run Benchmarks/scripts/regen_all.sh (refresh reports).
#   5. STAGE the resulting changes in Benchmarks repo (do NOT commit/push — user controls).
#   6. Print a summary so the user knows to commit.
#
# Usage:
#   lang_repo_post_commit.sh --lang python
#
# Important: silent on no-op (no problems touched). Verbose on bench triggered.
# NOTE: deliberately NOT using `set -e` — we want the hook to be non-fatal even
# if a step fails; we report and exit 0 so the user's commit succeeds regardless.

LANG_NAME=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --lang) LANG_NAME="$2"; shift 2 ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$LANG_NAME" ]; then
    echo "ERROR: --lang required" >&2
    exit 1
fi

BENCHMARKS_REPO="/Users/augusthill/ccdev/ProjectEuler.Benchmarks"
LANG_REPO="$(git rev-parse --show-toplevel 2>/dev/null)"

if [ ! -d "$BENCHMARKS_REPO" ]; then
    # Benchmarks repo not present locally — silent skip
    exit 0
fi

# Extract problem numbers from files touched in HEAD commit.
# Keep zero-padding as it appears in filenames (e.g., 001 not 1) — the per-lang
# benchmark.sh expects `problem_NNN.{ext}` lookup with the original padding.
PROBLEMS=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null \
    | grep -oE 'problem_[0-9]+' \
    | sed 's/problem_//' \
    | sort -u \
    | paste -sd, -)

if [ -z "$PROBLEMS" ]; then
    # No problem files touched — nothing to bench
    exit 0
fi

echo ""
echo "[pe-bench] Post-commit hook for ProjectEuler.${LANG_NAME}: detected problems $PROBLEMS"
echo "[pe-bench] Running partial bench in $LANG_REPO ..."

# Partial bench (the per-lang benchmark.sh natively merges into benchmark_results.json)
LOG=$(mktemp)
(cd "$LANG_REPO" && ./benchmark.sh --problems "$PROBLEMS" >"$LOG" 2>&1)
BENCH_RC=$?
if [ "$BENCH_RC" -ne 0 ]; then
    echo "[pe-bench] benchmark.sh exited $BENCH_RC — last 10 lines:" >&2
    tail -10 "$LOG" >&2
    rm -f "$LOG"
    exit 0
fi
tail -3 "$LOG"
rm -f "$LOG"

echo "[pe-bench] Sanitize-and-copy ..."
LOG=$(mktemp)
(cd "$BENCHMARKS_REPO" && bash scripts/collect.sh >"$LOG" 2>&1)
COLLECT_RC=$?
if [ "$COLLECT_RC" -ne 0 ]; then
    echo "[pe-bench] collect.sh exited $COLLECT_RC — last 10 lines:" >&2
    tail -10 "$LOG" >&2
    rm -f "$LOG"
    exit 0
fi
rm -f "$LOG"

echo "[pe-bench] Regen reports ..."
LOG=$(mktemp)
(cd "$BENCHMARKS_REPO" && bash scripts/regen_all.sh >"$LOG" 2>&1)
REGEN_RC=$?
if [ "$REGEN_RC" -ne 0 ]; then
    echo "[pe-bench] regen_all.sh exited $REGEN_RC (warnings non-fatal; reports may still be partial) — last 5 lines:" >&2
    tail -5 "$LOG" >&2
fi
rm -f "$LOG"

# Stage changes in Benchmarks repo (don't commit — user controls)
(cd "$BENCHMARKS_REPO" && git add -u data/ COVERAGE.md RESULTS.md THREE_MODE_REPORT.md charts/ 2>/dev/null) || true

# Report
DIRTY=$(cd "$BENCHMARKS_REPO" && git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
echo "[pe-bench] Staged $DIRTY change(s) in $BENCHMARKS_REPO."
echo "[pe-bench] Run 'cd $BENCHMARKS_REPO && git commit -m \"refresh ${LANG_NAME} p${PROBLEMS}\"' to publish."
