#!/usr/bin/env bash
# collect.sh - Sanitize-and-copy benchmark_results.json from each sibling repo into data/
#
# CRITICAL: per-lang benchmark_results.json contains `answer` field for ALL problems.
# data/*.json is PUBLIC (sanitized: no `answer` for problems >100 per
# projecteuler.net/about#publish). This script strips answers for >100 during copy.
# See feedback_pe_data_sanitization.md (auto-memory) for the 2026-05-09 incident.
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$SCRIPT_DIR/../data"
PARENT="$(dirname "$(dirname "$SCRIPT_DIR")")"

declare -A REPOS=(
    [c]="ProjectEuler.C"
    [cpp]="ProjectEuler.CPlusPlus"
    [csharp]="ProjectEuler.CSharp"
    [go]="ProjectEuler.Go"
    [rust]="ProjectEuler.Rust"
    [python]="ProjectEuler.Python"
    [java]="ProjectEuler.Java"
    [javascript]="ProjectEuler.JavaScript"
    [arm64]="ProjectEuler.ARM64"
    [zig]="ProjectEuler.Zig"
)

# Strip `answer` field for problems >100, then verify; bail if leak detected.
sanitize_and_copy() {
    local src="$1" dst="$2" name="$3"
    jq '.problems |= with_entries(if (.key | tonumber) > 100 then .value |= del(.answer) else . end)' \
        "$src" > "$dst"
    local leaked
    leaked=$(jq -r '[.problems | to_entries[] | select((.key | tonumber) > 100) | select(.value.answer != null)] | length' "$dst" 2>/dev/null)
    if [ "$leaked" != "0" ]; then
        echo "  ERROR: $leaked answers leaked for >100 in $dst — REFUSING TO PROCEED" >&2
        rm -f "$dst"
        return 1
    fi
    echo "  Collected $name (sanitized: stripped answers for >100)"
}

for name in "${!REPOS[@]}"; do
    repo="${REPOS[$name]}"
    src="$PARENT/$repo/benchmark_results.json"
    dst="$DATA_DIR/$name.json"
    if [ -f "$src" ]; then
        sanitize_and_copy "$src" "$dst" "$name"
    else
        echo "  SKIP: $src not found"
    fi
done

echo ""
echo "Done. Files in $DATA_DIR:"
ls -la "$DATA_DIR"/*.json 2>/dev/null || echo "  (none)"
