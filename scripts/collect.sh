#!/bin/bash
# collect.sh - Copy benchmark_results.json from each sibling repo into data/
set -euo pipefail

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
    [haskell]="ProjectEuler.Haskell"
    [apl]="ProjectEuler.APL"
)

for name in "${!REPOS[@]}"; do
    repo="${REPOS[$name]}"
    src="$PARENT/$repo/benchmark_results.json"
    dst="$DATA_DIR/$name.json"
    if [ -f "$src" ]; then
        cp "$src" "$dst"
        echo "  Collected $repo -> $name.json"
    else
        echo "  SKIP: $src not found"
    fi
done

echo "Done. Files in $DATA_DIR:"
ls -la "$DATA_DIR"/*.json 2>/dev/null || echo "  (none)"
