#!/usr/bin/env bash
# lang_repo_pre_commit.sh — block commits that increase the dud-audit error
# count for a language. Compares working-tree error count against the baseline
# stored in scripts/dud_audit_baseline.json.
#
# Idea: as long as you don't INCREASE the dud count, commits proceed. To
# REMOVE duds (fix), commit normally — the hook will re-baseline next refresh.
# To re-baseline manually after intentional cleanup:
#   ./dud_audit --quiet > dud_audit_baseline.json
#
# Usage: lang_repo_pre_commit.sh --lang <name>
# Exit 0: no regression. Exit 1: regression — commit rejected.

LANG=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --lang) LANG="$2"; shift 2 ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$LANG" ]; then
    echo "ERROR: --lang required" >&2
    exit 1
fi

BENCHMARKS_REPO="${PE_BENCH_BENCHMARKS_REPO:-/Users/augusthill/ccdev/pe/benchmarks}"
DUD_AUDIT="$BENCHMARKS_REPO/scripts/dud_audit"
SRC="$BENCHMARKS_REPO/scripts/dud_audit.go"
BASELINE="$BENCHMARKS_REPO/scripts/dud_audit_baseline.json"

if [ ! -d "$BENCHMARKS_REPO" ]; then
    exit 0  # no benchmarks repo — skip silently
fi

# Build dud_audit if missing or older than source.
if [ ! -x "$DUD_AUDIT" ] || [ "$SRC" -nt "$DUD_AUDIT" ]; then
    if ! (cd "$BENCHMARKS_REPO/scripts" && go build -o dud_audit dud_audit.go) >&2; then
        echo "[pe-dud] WARN: failed to build dud_audit — pre-commit gate skipped" >&2
        exit 0
    fi
fi

# Run audit for this lang only.
CURRENT_JSON=$("$DUD_AUDIT" --lang "$LANG" --quiet 2>/dev/null)
if [ -z "$CURRENT_JSON" ]; then
    exit 0  # tool failed — don't block
fi

CURRENT_ERRORS=$(echo "$CURRENT_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["summary"]["by_severity"].get("error",0))' 2>/dev/null)
if [ -z "$CURRENT_ERRORS" ]; then
    exit 0  # parse failed — don't block
fi

# Generate baseline if missing (first run on a fresh clone). Baseline is
# intentionally NOT committed to the public Benchmarks repo because it
# contains comment-vs-bench detail strings that would leak answers for
# problems >100.
if [ ! -f "$BASELINE" ]; then
    "$DUD_AUDIT" --quiet > "$BASELINE" 2>/dev/null || true
fi

BASELINE_ERRORS=0
if [ -f "$BASELINE" ]; then
    BASELINE_ERRORS=$(python3 -c "
import json
d = json.load(open('$BASELINE'))
lang = '$LANG'
def involves(f):
    if f.get('language') == lang: return True
    if f.get('language') == '*':
        # cross-lang finding — include if lang appears in the details list
        det = f.get('details','')
        return f'[{lang},' in det or f',{lang},' in det or f',{lang}]' in det or f'[{lang}]' in det
    return False
print(sum(1 for f in d.get('findings',[]) if f.get('severity')=='error' and involves(f)))" 2>/dev/null || echo 0)
fi

if [ "$CURRENT_ERRORS" -gt "$BASELINE_ERRORS" ]; then
    NEW=$(( CURRENT_ERRORS - BASELINE_ERRORS ))
    echo ""
    echo "[pe-dud] dud-audit regression for $LANG: $CURRENT_ERRORS errors (baseline $BASELINE_ERRORS, +$NEW new)."
    echo "[pe-dud] Commit rejected. Run to investigate:"
    echo "[pe-dud]   $DUD_AUDIT --lang $LANG --severity error"
    echo "[pe-dud] After fixing OR if the new dud is intentional, re-baseline:"
    echo "[pe-dud]   $DUD_AUDIT --quiet > $BASELINE"
    echo "[pe-dud] To bypass for one commit (use sparingly): git commit --no-verify"
    exit 1
fi

exit 0
