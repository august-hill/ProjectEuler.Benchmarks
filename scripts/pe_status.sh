#!/usr/bin/env bash
# pe-status - snapshot of pending PE work across all repos.
#
# Shows:
#   - Lang repos with uncommitted changes (and last commit timestamp)
#   - Benchmarks repo: dirty/staged file count + last hook timestamp
#   - Open "Review Benchmarks" Todoist tasks (if ~/.todoist_token present)
#   - Last nightly sweep timestamp (from ~/.pe-bench-nightly.log if present)
#
# Pure read-only; safe to run anytime.
set -uo pipefail

PARENT="/Users/augusthill/ccdev"
BENCHMARKS_REPO="$PARENT/ProjectEuler.Benchmarks"

echo "═══════════════════════════════════════════════"
echo "  pe-status — $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════"

# Lang repos
echo ""
echo "Language repos with uncommitted work:"
DIRTY_LANGS=0
for d in $PARENT/ProjectEuler.{C,CPlusPlus,CSharp,Go,Java,JavaScript,Python,Rust,Zig,ARM64}; do
    [ -d "$d/.git" ] || continue
    name=$(basename "$d")
    dirty=$(git -C "$d" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    if [ "$dirty" -gt "0" ]; then
        last=$(git -C "$d" log -1 --format="%ar" 2>/dev/null)
        printf "  %-30s %3s file(s) dirty  (last commit: %s)\n" "$name" "$dirty" "$last"
        DIRTY_LANGS=$((DIRTY_LANGS+1))
    fi
done
[ "$DIRTY_LANGS" = "0" ] && echo "  (all clean)"

# Benchmarks repo
echo ""
echo "Benchmarks repo:"
B_DIRTY=$(git -C "$BENCHMARKS_REPO" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
B_STAGED=$(git -C "$BENCHMARKS_REPO" diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
LAST_COMMIT=$(git -C "$BENCHMARKS_REPO" log -1 --format="%ar — %s" 2>/dev/null)
echo "  $B_DIRTY file(s) dirty, $B_STAGED staged"
echo "  last commit: $LAST_COMMIT"
if [ "$B_STAGED" -gt "0" ]; then
    echo "  staged for next publish:"
    git -C "$BENCHMARKS_REPO" diff --cached --name-only | sed 's/^/    /'
    echo ""
    echo "  → run 'pe-publish \"your commit message\"' to publish + close Todoist tasks"
fi

# Todoist
echo ""
echo "Todoist queue:"
TOKEN_FILE="$HOME/.todoist_token"
if [ -f "$TOKEN_FILE" ]; then
    TOKEN=$(head -1 "$TOKEN_FILE" | tr -d '[:space:]')
    if [ -n "$TOKEN" ]; then
        curl -sS "https://api.todoist.com/api/v1/tasks" \
            -H "Authorization: Bearer $TOKEN" \
            | python3 -c "
import json, sys
data = json.load(sys.stdin)
tasks = data.get('results', data) if isinstance(data, dict) else data
matches = [t for t in tasks if 'Review Benchmarks' in t.get('content', '') or 'pe-bench' in t.get('content', '').lower() or 'nightly bench' in t.get('content', '').lower()]
print(f'  {len(matches)} open pe-bench task(s)')
for t in matches:
    print(f'    [{t[\"id\"][-6:]}] {t[\"content\"]}')
"
    else
        echo "  (token file empty)"
    fi
else
    echo "  (no ~/.todoist_token — Todoist integration disabled)"
fi

# Nightly log
echo ""
echo "Nightly sweep:"
NIGHTLY_LOG="$HOME/.pe-bench-nightly.log"
if [ -f "$NIGHTLY_LOG" ]; then
    last_run=$(grep -E "^Nightly sweep:" "$NIGHTLY_LOG" 2>/dev/null | tail -1 | sed 's/^Nightly sweep: //')
    if [ -n "$last_run" ]; then
        echo "  last run: $last_run"
        echo "  log: $NIGHTLY_LOG"
    else
        echo "  log exists but no 'Nightly sweep:' line found yet"
    fi
else
    echo "  (no $NIGHTLY_LOG — launchd job not yet activated)"
fi

echo ""
