#!/usr/bin/env bash
# pe-publish - manual override path for the auto-publish flow.
#
# In the auto-publish world, the post-commit hook commits + pushes itself
# whenever all gates pass. pe-publish is invoked when:
#   (a) a gate tripped, the user inspected/fixed/accepted, and wants to ship.
#   (b) auto-publish hit a push conflict the rebase retry couldn't resolve.
#
# Usage:
#   pe-publish "commit message"
#   pe-publish                  (interactive: shows diff, prompts for message)
#
# Sequence:
#   1. cd to BENCHMARKS_REPO
#   2. Detect state:
#        - staged changes:    commit + push (case a)
#        - local ahead of remote, nothing staged:  push only (case b)
#        - clean and aligned: nothing to do
#   3. Close any "Benchmarks gate tripped:" or legacy "Review Benchmarks:" Todoist tasks
#   4. Clear .pe-exception.json on success
#
# Exit non-zero if there's nothing to publish or the operation is rejected.
set -euo pipefail

BENCHMARKS_REPO="${PE_BENCH_BENCHMARKS_REPO:-/Users/augusthill/ccdev/ProjectEuler.Benchmarks}"
EXCEPTION_FILE="$BENCHMARKS_REPO/.pe-exception.json"
cd "$BENCHMARKS_REPO"

# How many local commits are ahead of origin/main?
AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo "0")
STAGED=$(git diff --cached --name-only | wc -l | tr -d ' ')
DIRTY=$(git status --porcelain | wc -l | tr -d ' ')

if [ "$STAGED" = "0" ] && [ "$AHEAD" = "0" ]; then
    if [ "$DIRTY" -gt "0" ]; then
        echo "Working-tree changes are NOT staged. Stage with:"
        echo "  git add -u data/ COVERAGE.md RESULTS.md THREE_MODE_REPORT.md charts/"
        exit 1
    fi
    echo "Nothing to publish — Benchmarks repo is clean and in sync with origin/main."
    exit 1
fi

if [ "$STAGED" -gt "0" ]; then
    echo "Staged changes (${STAGED} file(s)):"
    git diff --cached --stat
    echo ""

    MSG="${1:-}"
    if [ -z "$MSG" ]; then
        echo -n "Commit message: "
        read -r MSG
        if [ -z "$MSG" ]; then
            echo "Aborted (empty message)."
            exit 1
        fi
    fi

    echo ""
    echo "→ Committing: $MSG"
    git commit -m "$MSG"
fi

if [ "$AHEAD" != "0" ] && [ "$STAGED" = "0" ]; then
    echo "Local main is ${AHEAD} commit(s) ahead of origin/main; pushing without new commit."
fi

echo ""
echo "→ Pushing to origin/main"
if ! git push origin main; then
    echo ""
    echo "→ Push rejected; attempting rebase pull + retry ..."
    git pull --rebase origin main
    git push origin main
fi

# Clear exception state on success
if [ -f "$EXCEPTION_FILE" ]; then
    echo ""
    echo "→ Clearing exception state ($EXCEPTION_FILE)"
    rm -f "$EXCEPTION_FILE"
fi

# Close matching open Todoist tasks (both new-style "gate tripped" and legacy "Review Benchmarks")
TOKEN_FILE="$HOME/.todoist_token"
if [ -f "$TOKEN_FILE" ]; then
    TOKEN=$(head -1 "$TOKEN_FILE" | tr -d '[:space:]')
    if [ -n "$TOKEN" ]; then
        echo ""
        echo "→ Closing matching Todoist tasks..."
        IDS=$(curl -sS "https://api.todoist.com/api/v1/tasks" \
            -H "Authorization: Bearer $TOKEN" \
            | python3 -c "
import json, sys
data = json.load(sys.stdin)
tasks = data.get('results', data) if isinstance(data, dict) else data
for t in tasks:
    c = t.get('content', '')
    if 'Benchmarks gate tripped' in c or 'Review Benchmarks' in c:
        print(t['id'])
")
        COUNT=0
        for id in $IDS; do
            curl -sS -o /dev/null -X POST "https://api.todoist.com/api/v1/tasks/$id/close" \
                -H "Authorization: Bearer $TOKEN"
            COUNT=$((COUNT+1))
        done
        echo "   closed $COUNT task(s)"
    fi
fi

echo ""
echo "✓ Published."
