#!/usr/bin/env bash
# regen_all.sh - Run all report regenerators in order, after data/*.json refresh.
#
# All four reports are tier-aware as of 2026-05-22. Tier definitions live in
# `data/tiers.json` (single source of truth, consumed via `scripts/tiers.py`).
# To re-tier the suite, edit tiers.json then re-run this script.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

cd "$REPO_DIR"

echo "[1/4] coverage_report.py — heatmap matrix from filesystem"
python3 scripts/coverage_report.py

echo ""
echo "[2/4] three_metric_report.py — runtime/cold-start/compile leaderboards"
python3 scripts/three_metric_report.py --data-dir data --output THREE_MODE_REPORT.md

echo ""
echo "[3/4] compare_languages.py — language comparison table + per-problem winners"
python3 scripts/compare_languages.py

echo ""
echo "[4/4] final_analysis.py — RESULTS.md + 6 PNG charts"
python3 final_analysis.py

echo ""
echo "Done. Updated artifacts:"
ls -la COVERAGE.md RESULTS.md THREE_MODE_REPORT.md 2>/dev/null
ls -la charts/*.png 2>/dev/null | head -10 || true
