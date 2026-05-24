#!/usr/bin/env python3
"""
Write .pe-exception.json — local diagnostic record when an automated gate
trips during the auto-publish flow.

Called by lang_repo_post_commit.sh:
  python3 scripts/write_exception.py \
      --gate timing_regression \
      --lang arm64 \
      --problems 070,092,189 \
      --lang-sha abc123 \
      --details-file /tmp/gate.log \
      --output .pe-exception.json

Schema:
  {
    "timestamp": "2026-05-10T12:34:56Z",
    "lang": "arm64",
    "problems": ["070", "092", "189"],
    "lang_commit_sha": "abc123",
    "gate": "timing_regression",
    "details": "<contents of details file, trimmed>"
  }

The details field is captured verbatim from the gate's stdout/stderr so the
user can read the gate's own diagnostic when running `pe-status`.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

MAX_DETAILS_BYTES = 16 * 1024  # cap to keep the file tractable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", required=True,
                    help="gate identifier: answer_validation | sanitization | timing_regression | push_conflict | bench_failed")
    ap.add_argument("--lang", required=True)
    ap.add_argument("--problems", required=True, help="comma-separated")
    ap.add_argument("--lang-sha", default="unknown")
    ap.add_argument("--details-file", help="path to file with gate's stdout/stderr")
    ap.add_argument("--output", required=True, help="output path (e.g. .pe-exception.json)")
    args = ap.parse_args()

    details = ""
    if args.details_file:
        p = Path(args.details_file)
        if p.exists():
            details = p.read_text(errors="replace")
            if len(details) > MAX_DETAILS_BYTES:
                details = details[:MAX_DETAILS_BYTES] + f"\n... [truncated, original {len(details)} bytes]"

    payload = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lang": args.lang,
        "problems": [p.strip() for p in args.problems.split(",") if p.strip()],
        "lang_commit_sha": args.lang_sha,
        "gate": args.gate,
        "details": details.strip(),
    }
    Path(args.output).write_text(json.dumps(payload, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
