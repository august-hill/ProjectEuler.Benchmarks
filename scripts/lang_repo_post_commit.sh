#!/usr/bin/env bash
# Shared post-commit logic for the 10 PE language repos.
# Called by each repo's .git/hooks/post-commit (a thin wrapper that passes --lang).
#
# Behavior:
#   1. Detect problem numbers touched by HEAD.
#   2. If any, run partial bench in the lang repo.
#   3. Gate 1 — validate_answers.py --strict   (BEFORE staging in Benchmarks)
#   4. collect.sh + regen_all.sh + git add     (refresh + stage)
#   5. Gate 2 — sanitization_gate.py            (against staged content)
#   6. Gate 3 — check_timing_delta              (regression vs HEAD)
#   7. Auto-commit + auto-push origin/main      (one rebase retry on conflict)
#
# On any gate trip: write .pe-exception.json + create one Todoist task; do NOT commit.
# On success: clear any prior .pe-exception.json + close stale Todoist tasks.
#
# Override: BENCHMARKS_REPO env var points elsewhere (used by sandbox tests).
#
# Usage: lang_repo_post_commit.sh --lang python
#
# Note: deliberately NOT using `set -e` — the hook must be non-fatal; we report and
# exit 0 so the user's lang-repo commit succeeds regardless of bench/publish state.

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

LANG_NAME_LOWER=$(echo "$LANG_NAME" | tr '[:upper:]' '[:lower:]')
BENCHMARKS_REPO="${PE_BENCH_BENCHMARKS_REPO:-/Users/augusthill/ccdev/ProjectEuler.Benchmarks}"
LANG_REPO="$(git rev-parse --show-toplevel 2>/dev/null)"
EXCEPTION_FILE="$BENCHMARKS_REPO/.pe-exception.json"

if [ ! -d "$BENCHMARKS_REPO" ]; then
    exit 0
fi

# Extract problem numbers from files touched in HEAD (preserve zero-padding).
PROBLEMS=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null \
    | grep -oE 'problem_[0-9]+' \
    | sed 's/problem_//' \
    | sort -u \
    | paste -sd, -)

if [ -z "$PROBLEMS" ]; then
    exit 0
fi

LANG_COMMIT_SHA=$(cd "$LANG_REPO" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")

echo ""
echo "[pe-bench] Post-commit for ProjectEuler.${LANG_NAME}: detected problems $PROBLEMS"

# ---------------------------------------------------------------------------
# Helper: trip an exception. Writes .pe-exception.json + creates Todoist task.
# Caller is responsible for `exit 0` after invoking.
# ---------------------------------------------------------------------------
trip_exception() {
    local gate="$1"
    local details_file="$2"

    python3 "$BENCHMARKS_REPO/scripts/write_exception.py" \
        --gate "$gate" \
        --lang "$LANG_NAME_LOWER" \
        --problems "$PROBLEMS" \
        --lang-sha "$LANG_COMMIT_SHA" \
        --details-file "$details_file" \
        --output "$EXCEPTION_FILE" || true

    echo "[pe-bench] EXCEPTION: $gate — wrote $EXCEPTION_FILE" >&2

    "$BENCHMARKS_REPO/scripts/notify_todoist.sh" \
        --content "Benchmarks gate tripped: ${LANG_NAME} p${PROBLEMS} (${gate})" \
        --description "Auto-publish blocked by gate \"${gate}\".

LANG:     ${LANG_NAME} @ ${LANG_COMMIT_SHA}
PROBLEMS: ${PROBLEMS}
DETAILS:  cat ${EXCEPTION_FILE}

Inspect:  cd ${BENCHMARKS_REPO} && git diff --cached
Resolve:  pe-publish \"refresh ${LANG_NAME} p${PROBLEMS}\"   (accept and publish)
   or:    cd ${BENCHMARKS_REPO} && git restore --staged .   (abandon)
Status:   pe-status" \
        --priority 3 \
        --dedupe-key "${LANG_NAME} @ ${LANG_COMMIT_SHA}" \
        >/dev/null 2>&1 || true
}

# ---------------------------------------------------------------------------
# Step 1: partial bench in lang repo
# ---------------------------------------------------------------------------
echo "[pe-bench] Running partial bench in $LANG_REPO ..."
LOG=$(mktemp)
(cd "$LANG_REPO" && ./benchmark.sh --problems "$PROBLEMS" >"$LOG" 2>&1)
BENCH_RC=$?
if [ "$BENCH_RC" -ne 0 ]; then
    echo "[pe-bench] benchmark.sh exited $BENCH_RC — last 10 lines:" >&2
    tail -10 "$LOG" >&2
    trip_exception "bench_failed" "$LOG"
    rm -f "$LOG"
    exit 0
fi
tail -3 "$LOG"
rm -f "$LOG"

# ---------------------------------------------------------------------------
# Gate 1: answer validation against C++ canonical (BEFORE staging)
# Reads sibling private repos' benchmark_results.json — independent of staged state.
# ---------------------------------------------------------------------------
echo "[pe-bench] Gate 1: validate answers ..."
LOG=$(mktemp)
(cd "$BENCHMARKS_REPO" && python3 scripts/validate_answers.py --strict --lang "$LANG_NAME_LOWER" --problems "$PROBLEMS" >"$LOG" 2>&1)
VAL_RC=$?
if [ "$VAL_RC" -ne 0 ]; then
    echo "[pe-bench] gate-1 (answer_validation) tripped:"
    cat "$LOG"
    trip_exception "answer_validation" "$LOG"
    rm -f "$LOG"
    exit 0
fi
rm -f "$LOG"

# ---------------------------------------------------------------------------
# Sanitize-and-copy + regen reports (existing behavior)
# ---------------------------------------------------------------------------
echo "[pe-bench] Sanitize-and-copy ..."
LOG=$(mktemp)
(cd "$BENCHMARKS_REPO" && bash scripts/collect.sh >"$LOG" 2>&1)
COLLECT_RC=$?
if [ "$COLLECT_RC" -ne 0 ]; then
    echo "[pe-bench] collect.sh exited $COLLECT_RC — last 10 lines:" >&2
    tail -10 "$LOG" >&2
    trip_exception "collect_failed" "$LOG"
    rm -f "$LOG"
    exit 0
fi
rm -f "$LOG"

echo "[pe-bench] Regen reports ..."
LOG=$(mktemp)
(cd "$BENCHMARKS_REPO" && bash scripts/regen_all.sh >"$LOG" 2>&1)
REGEN_RC=$?
if [ "$REGEN_RC" -ne 0 ]; then
    echo "[pe-bench] regen_all.sh exited $REGEN_RC (non-fatal) — last 5 lines:" >&2
    tail -5 "$LOG" >&2
fi
rm -f "$LOG"

# Stage everything
(cd "$BENCHMARKS_REPO" && git add -u data/ COVERAGE.md RESULTS.md THREE_MODE_REPORT.md charts/ 2>/dev/null) || true

# Bail early if nothing actually changed (idempotent re-runs)
STAGED_COUNT=$(cd "$BENCHMARKS_REPO" && git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
if [ "$STAGED_COUNT" = "0" ]; then
    echo "[pe-bench] No changes to publish (working tree matches HEAD)."
    rm -f "$EXCEPTION_FILE"
    exit 0
fi

# ---------------------------------------------------------------------------
# Gate 2: sanitization on staged content
# ---------------------------------------------------------------------------
echo "[pe-bench] Gate 2: sanitization ..."
LOG=$(mktemp)
(cd "$BENCHMARKS_REPO" && python3 scripts/sanitization_gate.py >"$LOG" 2>&1)
SAN_RC=$?
if [ "$SAN_RC" -ne 0 ]; then
    echo "[pe-bench] gate-2 (sanitization) tripped:"
    cat "$LOG"
    trip_exception "sanitization" "$LOG"
    rm -f "$LOG"
    exit 0
fi
rm -f "$LOG"

# ---------------------------------------------------------------------------
# Gate 3: timing regression vs HEAD
# ---------------------------------------------------------------------------
echo "[pe-bench] Gate 3: timing regression ..."
SRC="$BENCHMARKS_REPO/scripts/check_timing_delta.go"
BIN="$BENCHMARKS_REPO/scripts/check_timing_delta"
if [ ! -x "$BIN" ] || [ "$SRC" -nt "$BIN" ]; then
    echo "[pe-bench]   (re)building $BIN ..."
    if ! (cd "$BENCHMARKS_REPO/scripts" && go build -o check_timing_delta check_timing_delta.go) 2>&1; then
        echo "[pe-bench] WARN: failed to build check_timing_delta — skipping gate-3" >&2
        BIN=""
    fi
fi

if [ -n "$BIN" ] && [ -x "$BIN" ]; then
    LOG=$(mktemp)
    "$BIN" --lang "$LANG_NAME_LOWER" --problems "$PROBLEMS" --repo "$BENCHMARKS_REPO" >"$LOG" 2>&1
    DELTA_RC=$?
    if [ "$DELTA_RC" = "2" ]; then
        echo "[pe-bench] gate-3 (timing_regression) tripped:"
        cat "$LOG"
        trip_exception "timing_regression" "$LOG"
        rm -f "$LOG"
        exit 0
    fi
    if [ "$DELTA_RC" -ne 0 ]; then
        echo "[pe-bench] gate-3 returned $DELTA_RC unexpectedly:"
        cat "$LOG"
        trip_exception "timing_regression_tool_error" "$LOG"
        rm -f "$LOG"
        exit 0
    fi
    rm -f "$LOG"
fi

# ---------------------------------------------------------------------------
# All gates passed — auto-commit + auto-push (one rebase retry on conflict)
# ---------------------------------------------------------------------------
echo "[pe-bench] All gates passed. Auto-publishing ..."
COMMIT_MSG="refresh ${LANG_NAME} p${PROBLEMS}"

COMMIT_LOG=$(mktemp)
(cd "$BENCHMARKS_REPO" && git commit -m "$COMMIT_MSG" >"$COMMIT_LOG" 2>&1)
COMMIT_RC=$?
if [ "$COMMIT_RC" -ne 0 ]; then
    echo "[pe-bench] git commit failed:"
    cat "$COMMIT_LOG"
    trip_exception "commit_failed" "$COMMIT_LOG"
    rm -f "$COMMIT_LOG"
    exit 0
fi
rm -f "$COMMIT_LOG"

PUSH_LOG=$(mktemp)
(cd "$BENCHMARKS_REPO" && git push origin main >"$PUSH_LOG" 2>&1)
PUSH_RC=$?
if [ "$PUSH_RC" -ne 0 ]; then
    echo "[pe-bench] push failed, attempting rebase + retry ..."
    (cd "$BENCHMARKS_REPO" && git pull --rebase origin main >>"$PUSH_LOG" 2>&1 && git push origin main >>"$PUSH_LOG" 2>&1)
    PUSH_RC=$?
fi
if [ "$PUSH_RC" -ne 0 ]; then
    echo "[pe-bench] push failed even after rebase:"
    cat "$PUSH_LOG"
    trip_exception "push_conflict" "$PUSH_LOG"
    rm -f "$PUSH_LOG"
    exit 0
fi
rm -f "$PUSH_LOG"

# Success — clear any prior exception state
rm -f "$EXCEPTION_FILE"

# Best-effort: close any stale "Benchmarks gate tripped: $LANG_NAME ..." Todoist tasks
TOKEN_FILE="$HOME/.todoist_token"
if [ -f "$TOKEN_FILE" ]; then
    TOKEN=$(head -1 "$TOKEN_FILE" | tr -d '[:space:]')
    if [ -n "$TOKEN" ]; then
        IDS=$(curl -sS "https://api.todoist.com/api/v1/tasks" \
            -H "Authorization: Bearer $TOKEN" 2>/dev/null \
            | LANG_NEEDLE="$LANG_NAME" python3 -c "
import json, os, sys
needle_prefix = f\"Benchmarks gate tripped: {os.environ['LANG_NEEDLE']}\"
try:
    data = json.load(sys.stdin)
    tasks = data.get('results', data) if isinstance(data, dict) else data
    for t in tasks:
        if t.get('content', '').startswith(needle_prefix):
            print(t['id'])
except Exception:
    pass
" 2>/dev/null)
        for id in $IDS; do
            curl -sS -o /dev/null -X POST "https://api.todoist.com/api/v1/tasks/$id/close" \
                -H "Authorization: Bearer $TOKEN" 2>/dev/null
        done
    fi
fi

echo "[pe-bench] ✓ Auto-published: $COMMIT_MSG"
exit 0
