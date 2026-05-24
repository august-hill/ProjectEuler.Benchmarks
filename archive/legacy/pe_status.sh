#!/usr/bin/env bash
# pe-status - snapshot of pending PE work across all repos.
#
# Default state in the new auto-publish world: clean. The Benchmarks repo
# auto-commits + auto-pushes after every successful refresh. The user is
# only invoked when an automated gate trips — surfaced via:
#   $BENCHMARKS_REPO/.pe-exception.json
#
# Pure read-only; safe to run anytime.
set -uo pipefail

PARENT="/Users/augusthill/ccdev"
BENCHMARKS_REPO="${PE_BENCH_BENCHMARKS_REPO:-$PARENT/ProjectEuler.Benchmarks}"
EXCEPTION_FILE="$BENCHMARKS_REPO/.pe-exception.json"

# ANSI colors (disabled if not a TTY)
if [ -t 1 ]; then
    C_RED=$'\033[31m'; C_YEL=$'\033[33m'; C_GRN=$'\033[32m'
    C_DIM=$'\033[2m'; C_BLD=$'\033[1m'; C_RST=$'\033[0m'
else
    C_RED=""; C_YEL=""; C_GRN=""; C_DIM=""; C_BLD=""; C_RST=""
fi

echo "═══════════════════════════════════════════════"
echo "  pe-status — $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════"

# ---------------------------------------------------------------------------
# Lang repos
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Benchmarks repo: exception-first reporting
# ---------------------------------------------------------------------------
echo ""
echo "Benchmarks repo:"

B_STAGED=$(git -C "$BENCHMARKS_REPO" diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
LAST_COMMIT=$(git -C "$BENCHMARKS_REPO" log -1 --format="%ar — %s" 2>/dev/null)

if [ -f "$EXCEPTION_FILE" ]; then
    EXC=$(python3 -c "
import json
try:
    d = json.load(open('$EXCEPTION_FILE'))
    print(d.get('gate','?') + '|' + d.get('timestamp','?') + '|' + d.get('lang','?') + '|' + d.get('lang_commit_sha','?') + '|' + ','.join(d.get('problems',[])))
except Exception as e:
    print('PARSE_ERROR|' + str(e))
" 2>/dev/null || echo "PARSE_ERROR|read failed")
    GATE=$(echo "$EXC" | cut -d'|' -f1)
    TS=$(echo "$EXC" | cut -d'|' -f2)
    XLANG=$(echo "$EXC" | cut -d'|' -f3)
    XSHA=$(echo "$EXC" | cut -d'|' -f4)
    XPROBLEMS=$(echo "$EXC" | cut -d'|' -f5)

    # Pre-staging gates (answer_validation, bench_failed) leave nothing staged — that's expected, not stale.
    PRE_STAGE_GATES_REGEX="^(answer_validation|bench_failed)$"
    if [ "$B_STAGED" = "0" ] && ! [[ "$GATE" =~ $PRE_STAGE_GATES_REGEX ]]; then
        echo "  ${C_YEL}⚠  STALE EXCEPTION:${C_RST} ${GATE} for ${XLANG} p${XPROBLEMS}"
        echo "     (exception file present but no files staged — likely abandoned via git restore)"
        echo "     Clean up:  rm $EXCEPTION_FILE"
    else
        echo "  ${C_RED}${C_BLD}⚠  EXCEPTION:${C_RST} ${C_RED}${GATE}${C_RST}"
        echo "     ${C_DIM}tripped at:${C_RST} ${TS}"
        echo "     ${C_DIM}lang:${C_RST}       ${XLANG} @ ${XSHA}"
        echo "     ${C_DIM}problems:${C_RST}   ${XPROBLEMS}"
        echo "     ${C_DIM}staged:${C_RST}     ${B_STAGED} file(s)"
        echo ""
        echo "     ${C_DIM}details (first 8 lines):${C_RST}"
        python3 -c "
import json
try:
    d = json.load(open('$EXCEPTION_FILE'))
    details = (d.get('details') or '').splitlines()[:8]
    for line in details:
        print('       ' + line)
    if not details:
        print('       (no details captured)')
except Exception:
    print('       (could not read details)')
" 2>/dev/null
        echo ""
        echo "  Inspect: cd $BENCHMARKS_REPO && git diff --cached"
        echo "  Resolve: pe-publish \"refresh ${XLANG} p${XPROBLEMS}\"   ${C_DIM}# accept and publish${C_RST}"
        echo "     or:   cd $BENCHMARKS_REPO && git restore --staged .   ${C_DIM}# abandon${C_RST}"
    fi
else
    if [ "$B_STAGED" -gt "0" ]; then
        echo "  ${C_YEL}staged for manual publish: $B_STAGED file(s)${C_RST}"
        git -C "$BENCHMARKS_REPO" diff --cached --name-only | sed 's/^/    /'
        echo ""
        echo "  → run 'pe-publish \"your commit message\"' to publish"
    else
        echo "  ${C_GRN}✓ clean${C_RST} — last auto-publish: ${LAST_COMMIT}"
    fi
fi

# ---------------------------------------------------------------------------
# Todoist
# ---------------------------------------------------------------------------
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
def matches(t):
    c = t.get('content','')
    return ('Benchmarks gate tripped' in c or
            'Review Benchmarks' in c or
            'pe-bench' in c.lower() or
            'nightly bench' in c.lower())
ms = [t for t in tasks if matches(t)]
print(f'  {len(ms)} open pe-bench task(s)')
for t in ms:
    print(f'    [{t[\"id\"][-6:]}] {t[\"content\"]}')
"
    else
        echo "  (token file empty)"
    fi
else
    echo "  (no ~/.todoist_token — Todoist integration disabled)"
fi

# ---------------------------------------------------------------------------
# Nightly sweep
# ---------------------------------------------------------------------------
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
