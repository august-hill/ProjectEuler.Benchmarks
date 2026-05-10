#!/usr/bin/env bash
# pe-publish - commit + push staged Benchmarks changes; auto-close matching Todoist tasks.
#
# Usage:
#   pe-publish "commit message"
#   pe-publish                  (interactive: shows diff, prompts for message)
#
# Sequence:
#   1. cd to ProjectEuler.Benchmarks
#   2. Show staged changes (git diff --cached --stat)
#   3. Commit with the supplied message (pre-commit sanitization gate runs)
#   4. Push origin/main
#   5. Close any open "Review Benchmarks" Todoist tasks (uses ~/.todoist_token if present)
#
# Exit non-zero if there's nothing staged or the commit is rejected by the gate.
set -euo pipefail

BENCHMARKS_REPO="/Users/augusthill/ccdev/ProjectEuler.Benchmarks"
cd "$BENCHMARKS_REPO"

DIRTY=$(git status --porcelain | wc -l | tr -d ' ')
STAGED=$(git diff --cached --name-only | wc -l | tr -d ' ')

if [ "$DIRTY" = "0" ]; then
    echo "Nothing to publish — Benchmarks repo is clean."
    exit 1
fi

echo "Staged changes (${STAGED} file(s)):"
git diff --cached --stat
echo ""

if [ "$STAGED" = "0" ]; then
    echo "Working-tree changes are NOT staged. Stage with:"
    echo "  git add -u data/ COVERAGE.md RESULTS.md THREE_MODE_REPORT.md charts/"
    exit 1
fi

# Get commit message
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

echo ""
echo "→ Pushing to origin/main"
git push origin main

# Close matching open Todoist tasks (best-effort)
TOKEN_FILE="$HOME/.todoist_token"
if [ -f "$TOKEN_FILE" ]; then
    TOKEN=$(head -1 "$TOKEN_FILE" | tr -d '[:space:]')
    if [ -n "$TOKEN" ]; then
        echo ""
        echo "→ Closing matching 'Review Benchmarks' Todoist tasks..."
        IDS=$(curl -sS "https://api.todoist.com/api/v1/tasks" \
            -H "Authorization: Bearer $TOKEN" \
            | python3 -c "
import json, sys
data = json.load(sys.stdin)
tasks = data.get('results', data) if isinstance(data, dict) else data
for t in tasks:
    if 'Review Benchmarks' in t.get('content', ''):
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
