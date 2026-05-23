#!/usr/bin/env python3
"""Shared tier-model helper for the four PE Benchmarks report scripts.

Single source of truth lives in ``data/tiers.json``. Each tier defines:
- ``langs``: list of lowercase lang keys (matches compare_languages.py convention)
- ``problem_range``: [lo, hi] inclusive; hi may be ``None`` for unbounded
- ``label`` / ``description``: human-facing strings

Usage from a report script (regardless of where it's invoked from):

    from tiers import load_tiers, tier_for_problem, in_scope, TIER_ORDER

    tiers = load_tiers()
    if in_scope("go", 250, tiers):
        ...

See ``data/tiers.json`` for the live values and the
``project_pe_tier_model_2026-05-22`` auto-memory for rationale.
"""
from __future__ import annotations
import json
from pathlib import Path

# Display order matters for report sections — Foundation first, Frontier last.
TIER_ORDER = ["tier_1_foundation", "tier_2_deep_coverage", "tier_3_frontier"]

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "tiers.json"


def load_tiers(path: Path | str | None = None) -> dict:
    """Load and return the ``tiers`` sub-object from tiers.json.

    Returns a dict keyed by tier id (e.g. ``"tier_1_foundation"``). Callers
    should iterate via :data:`TIER_ORDER` to preserve Foundation→Frontier order.
    """
    p = Path(path) if path else _DEFAULT_PATH
    with open(p) as f:
        return json.load(f)["tiers"]


def tier_for_problem(problem_num: int, tiers: dict) -> str | None:
    """Return the tier id whose ``problem_range`` contains ``problem_num``.

    Tiers are checked in :data:`TIER_ORDER`; ranges are inclusive. Hi may be
    ``None`` (unbounded). Returns ``None`` if no tier matches (shouldn't happen
    for problem numbers ≥ 1 with the current schema).
    """
    for key in TIER_ORDER:
        if key not in tiers:
            continue
        lo, hi = tiers[key]["problem_range"]
        if problem_num >= lo and (hi is None or problem_num <= hi):
            return key
    return None


def langs_in_tier(tier_key: str, tiers: dict) -> list[str]:
    """Return the lowercase lang keys in scope for a given tier."""
    return list(tiers[tier_key]["langs"])


def in_scope(lang: str, problem_num: int, tiers: dict) -> bool:
    """True if ``lang`` is in scope for ``problem_num`` (i.e., listed in
    that problem's tier). Used to render ⬛ for out-of-scope cells.

    Note: a problem above a lang's max tier is OUT of scope for tier-comparison
    stats even if the lang has committed source for it (historical exception).
    """
    tier_key = tier_for_problem(problem_num, tiers)
    if tier_key is None:
        return False
    return lang in tiers[tier_key]["langs"]


def tier_label(tier_key: str, tiers: dict) -> str:
    """Human-facing label for a tier (e.g., 'Foundation')."""
    return tiers[tier_key]["label"]


def tier_problem_range(tier_key: str, tiers: dict) -> tuple[int, int | None]:
    """``(lo, hi)`` problem-number bounds; ``hi`` may be ``None`` (unbounded)."""
    lo, hi = tiers[tier_key]["problem_range"]
    return lo, hi


def tier_range_label(tier_key: str, tiers: dict) -> str:
    """Human-facing range string like '1-200' or '301+'."""
    lo, hi = tier_problem_range(tier_key, tiers)
    return f"{lo}-{hi}" if hi is not None else f"{lo}+"


if __name__ == "__main__":
    # Smoke test: print the loaded tier structure.
    t = load_tiers()
    for key in TIER_ORDER:
        if key not in t:
            continue
        lo, hi = t[key]["problem_range"]
        hi_s = "∞" if hi is None else str(hi)
        print(f"{t[key]['label']:15s}  problems {lo}-{hi_s}  "
              f"({len(t[key]['langs'])} langs: {', '.join(t[key]['langs'])})")
