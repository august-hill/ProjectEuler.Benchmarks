#!/usr/bin/env bash
# nightly_sweep.sh - Catch-all benchmark refresh, intended to run via launchd at 03:00 daily.
#
# Two passes:
#   1. PARTIAL — for each lang repo with commits in the last 24h, partial-bench
#      just the touched problems. Cheap; ~minutes per affected lang.
#   2. ROTATING FULL SWEEP — one lang per day of week (rotation based on $(date +%u)):
#        Mon=cpp, Tue=c, Wed=rust, Thu=go, Fri=zig, Sat=python, Sun=arm64
#      The non-rotation langs (csharp, java, javascript) get full sweeps less often
#      via manual runs. Adjust the rotation by editing the FULL_SWEEP_FOR_DAY array.
#      Full sweep = all 200 problems in that lang; takes 30-60 min.
#
# After both passes: collect.sh + regen_all.sh, stage in Benchmarks repo.
# This script does NOT commit/push — user reviews next morning and commits manually.
#
# Output goes to ~/.pe-bench-nightly.log (rotated; keeps last 7 days).
#
# Activate (one-time):
#   cp ~/Library/LaunchAgents/com.augusthill.pe-bench-nightly.plist.template \
#      ~/Library/LaunchAgents/com.augusthill.pe-bench-nightly.plist
#   launchctl load ~/Library/LaunchAgents/com.augusthill.pe-bench-nightly.plist
# Disable:
#   launchctl unload ~/Library/LaunchAgents/com.augusthill.pe-bench-nightly.plist
set -uo pipefail

BENCHMARKS_REPO="/Users/augusthill/ccdev/ProjectEuler.Benchmarks"
PARENT="$(dirname "$BENCHMARKS_REPO")"
LOG="$HOME/.pe-bench-nightly.log"

# Rotate log: keep last 7 days
if [ -f "$LOG" ]; then
    LOG_AGE=$(( ($(date +%s) - $(stat -f %m "$LOG" 2>/dev/null || echo 0)) / 86400 ))
    if [ "$LOG_AGE" -gt 7 ]; then
        mv "$LOG" "$LOG.old"
    fi
fi

exec >>"$LOG" 2>&1
echo ""
echo "=========================================="
echo "Nightly sweep: $(date)"
echo "=========================================="

# Lang repo mapping
declare -a LANG_KEYS=(c cpp csharp go java javascript python rust zig arm64)
declare -A LANG_REPO=(
    [c]="ProjectEuler.C"
    [cpp]="ProjectEuler.CPlusPlus"
    [csharp]="ProjectEuler.CSharp"
    [go]="ProjectEuler.Go"
    [java]="ProjectEuler.Java"
    [javascript]="ProjectEuler.JavaScript"
    [python]="ProjectEuler.Python"
    [rust]="ProjectEuler.Rust"
    [zig]="ProjectEuler.Zig"
    [arm64]="ProjectEuler.ARM64"
)

# Rotating full-sweep schedule (1=Mon, 2=Tue, ..., 7=Sun)
declare -A FULL_SWEEP_FOR_DAY=(
    [1]=cpp
    [2]=c
    [3]=rust
    [4]=go
    [5]=zig
    [6]=python
    [7]=arm64
)

DAY_OF_WEEK=$(date +%u)
FULL_SWEEP_LANG="${FULL_SWEEP_FOR_DAY[$DAY_OF_WEEK]:-}"
echo "Day-of-week=$DAY_OF_WEEK; full-sweep target: ${FULL_SWEEP_LANG:-none}"

# Pass 1: partial bench for any lang with commits in last 24h
echo ""
echo "=== Pass 1: partial bench for langs touched in last 24h ==="
for lang in "${LANG_KEYS[@]}"; do
    repo="$PARENT/${LANG_REPO[$lang]}"
    if [ ! -d "$repo/.git" ]; then continue; fi

    # Problems touched in the last 24h's commits
    PROBLEMS=$(cd "$repo" && git log --since="24 hours ago" --name-only --pretty=format: 2>/dev/null \
        | grep -oE 'problem_[0-9]+' | sed 's/problem_//' | sort -u | paste -sd, -)

    if [ -z "$PROBLEMS" ]; then
        echo "  $lang: no recent problem commits"
        continue
    fi
    echo "  $lang: bench problems $PROBLEMS"
    (cd "$repo" && ./benchmark.sh --problems "$PROBLEMS") || echo "    bench failed (non-fatal)"
done

# Pass 2: rotating full sweep (one lang per day)
if [ -n "$FULL_SWEEP_LANG" ]; then
    echo ""
    echo "=== Pass 2: full sweep for $FULL_SWEEP_LANG ==="
    repo="$PARENT/${LANG_REPO[$FULL_SWEEP_LANG]}"
    if [ -d "$repo/.git" ]; then
        echo "  $FULL_SWEEP_LANG: full sweep (30-60 min) ..."
        (cd "$repo" && ./benchmark.sh) || echo "    full sweep failed (non-fatal)"
    fi
fi

# Final: collect.sh (sanitize + copy) and regen_all.sh
echo ""
echo "=== Sanitize-and-copy + regen reports ==="
(cd "$BENCHMARKS_REPO" && bash scripts/collect.sh) || echo "  collect failed (non-fatal)"
(cd "$BENCHMARKS_REPO" && bash scripts/regen_all.sh) || echo "  regen failed (non-fatal)"

# Stage changes (do NOT commit/push — user reviews next morning)
(cd "$BENCHMARKS_REPO" && git add -u data/ COVERAGE.md RESULTS.md THREE_MODE_REPORT.md charts/ 2>/dev/null) || true
DIRTY=$(cd "$BENCHMARKS_REPO" && git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
echo ""
echo "Staged $DIRTY change(s) in $BENCHMARKS_REPO"
echo "Review tomorrow with: cd $BENCHMARKS_REPO && git diff --cached"
echo ""

# Queue a Todoist task for morning review (silent no-op if no token at ~/.todoist_token)
"$BENCHMARKS_REPO/scripts/notify_todoist.sh" \
    --content "Review nightly bench sweep ($(date +%Y-%m-%d))" \
    --description "Full sweep target: ${FULL_SWEEP_LANG:-none}. Staged ${DIRTY} change(s) in Benchmarks.

REVIEW:   cd ${BENCHMARKS_REPO} && git diff --cached
PUBLISH:  pe-publish \"nightly refresh $(date +%Y-%m-%d)\"
   (auto-closes this task on success)
SNAPSHOT: pe-status
LOG:      ${LOG}" \
    --priority 2 \
    --due "today 9am" || true

echo "Done at $(date)."
