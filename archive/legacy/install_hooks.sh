#!/usr/bin/env bash
# install_hooks.sh - Install pre-commit gate (this repo) + post-commit hook (each lang repo).
# Idempotent: safe to re-run.
#
# What it installs:
#   - ProjectEuler.Benchmarks/.git/hooks/pre-commit  (sanitization gate)
#   - ProjectEuler.{Lang}/.git/hooks/pre-commit      (dud-audit regression gate)
#   - ProjectEuler.{Lang}/.git/hooks/post-commit     (auto-bench + sanitize-and-copy + stage)
#
# Hooks live in .git/hooks/ which is NOT version-controlled (per git design).
# Re-run this after fresh clone or after edits to the hook templates.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BENCHMARKS_REPO="$(dirname "$SCRIPT_DIR")"
PARENT="$(dirname "$BENCHMARKS_REPO")"

# Lang repo names (10 langs)
LANGS=(C CPlusPlus CSharp Go Java JavaScript Python Rust Zig ARM64)
LANG_KEYS=(c cpp csharp go java javascript python rust zig arm64)

echo "=== Installing pre-commit gate in $BENCHMARKS_REPO ==="
PRE="$BENCHMARKS_REPO/.git/hooks/pre-commit"
cat > "$PRE" <<'EOF'
#!/usr/bin/env bash
# Pre-commit sanitization gate for ProjectEuler.Benchmarks (PUBLIC repo).
# Calls scripts/sanitization_gate.py. See its docstring for details.
set -e
exec python3 "$(git rev-parse --show-toplevel)/scripts/sanitization_gate.py"
EOF
chmod +x "$PRE"
echo "  installed: $PRE"

echo ""
echo "=== Installing pre+post commit hooks in 10 lang repos ==="
for i in "${!LANGS[@]}"; do
    REPO_NAME="${LANGS[$i]}"
    LANG_KEY="${LANG_KEYS[$i]}"
    REPO="$PARENT/ProjectEuler.$REPO_NAME"
    if [ ! -d "$REPO/.git" ]; then
        echo "  SKIP: $REPO not a git repo"
        continue
    fi
    POST="$REPO/.git/hooks/post-commit"
    cat > "$POST" <<EOF
#!/usr/bin/env bash
# Auto-installed by ProjectEuler.Benchmarks/scripts/install_hooks.sh
# Re-run that script to update.
exec "$BENCHMARKS_REPO/scripts/lang_repo_post_commit.sh" --lang "$LANG_KEY"
EOF
    chmod +x "$POST"
    echo "  installed: $POST (--lang $LANG_KEY)"

    PRE_LANG="$REPO/.git/hooks/pre-commit"
    cat > "$PRE_LANG" <<EOF
#!/usr/bin/env bash
# Auto-installed by ProjectEuler.Benchmarks/scripts/install_hooks.sh
# Pre-commit dud-audit regression gate. Re-run install_hooks.sh to update.
exec "$BENCHMARKS_REPO/scripts/lang_repo_pre_commit.sh" --lang "$LANG_KEY"
EOF
    chmod +x "$PRE_LANG"
    echo "  installed: $PRE_LANG (--lang $LANG_KEY)"
done

echo ""
echo "Done. To verify:"
echo "  cd ProjectEuler.Python && touch problem_001.py && git commit -am 'test'"
echo "  Should see [pe-bench] output. Reset with: git reset --soft HEAD~1"
