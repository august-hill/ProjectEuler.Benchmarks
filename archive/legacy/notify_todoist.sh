#!/usr/bin/env bash
# notify_todoist.sh - Create a Todoist task. Silent no-op if no token configured.
#
# Usage:
#   notify_todoist.sh --content "Title" [--description "Body"] [--priority 1-4] [--due "today 9am"] [--dedupe-key "K"]
#
# Priority: 1=natural (lowest), 2=normal, 3=high, 4=urgent.
# Token sourced from ~/.todoist_token (single-line file, chmod 600 recommended).
# If the file doesn't exist or is empty, exits 0 silently — never fails the caller.
# If the API is unreachable, prints a warning but exits 0 (best-effort signal).
#
# Dedupe: if --dedupe-key is supplied, GET open tasks first; if any open task's
# content OR description contains the key as a substring, skip creation silently.
# This prevents the "hook fires twice for the same lang@sha" duplicate-task bug
# (project_pe_hook_dedupe_todo.md). Suggested key shape: "{lang} @ {commit_sha}".

TOKEN_FILE="$HOME/.todoist_token"
if [ ! -f "$TOKEN_FILE" ]; then
    exit 0
fi
TOKEN=$(head -1 "$TOKEN_FILE" | tr -d '[:space:]')
if [ -z "$TOKEN" ]; then
    exit 0
fi

CONTENT=""
DESCRIPTION=""
PRIORITY="2"
DUE=""
DEDUPE_KEY=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --content) CONTENT="$2"; shift 2;;
        --description) DESCRIPTION="$2"; shift 2;;
        --priority) PRIORITY="$2"; shift 2;;
        --due) DUE="$2"; shift 2;;
        --dedupe-key) DEDUPE_KEY="$2"; shift 2;;
        *) echo "[notify_todoist] Unknown arg: $1" >&2; exit 1;;
    esac
done

if [ -z "$CONTENT" ]; then
    echo "[notify_todoist] --content required" >&2
    exit 1
fi

# Dedupe: if a key is given, look for an open task that already mentions it.
if [ -n "$DEDUPE_KEY" ]; then
    EXISTING=$(curl -sS "https://api.todoist.com/api/v1/tasks" \
        -H "Authorization: Bearer $TOKEN" 2>/dev/null \
        | NTD_KEY="$DEDUPE_KEY" python3 -c "
import json, os, sys
key = os.environ.get('NTD_KEY','')
try:
    data = json.load(sys.stdin)
    tasks = data.get('results', data) if isinstance(data, dict) else data
    for t in tasks:
        c = t.get('content','') or ''
        d = t.get('description','') or ''
        if key and (key in c or key in d):
            print(t.get('id',''))
            break
except Exception:
    pass
" 2>/dev/null)
    if [ -n "$EXISTING" ]; then
        # Open task already exists for this dedupe key — silent skip.
        exit 0
    fi
fi

# Build JSON safely via Python (handles arbitrary content with quotes/newlines)
JSON=$(python3 -c '
import json, sys
content, description, priority, due = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
body = {"content": content, "priority": int(priority)}
if description:
    body["description"] = description
if due:
    body["due_string"] = due
print(json.dumps(body))
' "$CONTENT" "$DESCRIPTION" "$PRIORITY" "$DUE")

# Best-effort POST; warn but don't fail if API errors.
# Endpoint: /api/v1/tasks (the unified API; old /rest/v2 was deprecated, returns 410).
HTTP_STATUS=$(curl -sS -o /dev/null -w "%{http_code}" \
    -X POST 'https://api.todoist.com/api/v1/tasks' \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$JSON" 2>/dev/null) || HTTP_STATUS="000"

if [ "$HTTP_STATUS" = "200" ] || [ "$HTTP_STATUS" = "204" ]; then
    : # success, silent
else
    echo "[notify_todoist] API returned HTTP $HTTP_STATUS (non-fatal)" >&2
fi
exit 0
