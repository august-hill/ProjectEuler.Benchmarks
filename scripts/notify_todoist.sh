#!/usr/bin/env bash
# notify_todoist.sh - Create a Todoist task. Silent no-op if no token configured.
#
# Usage:
#   notify_todoist.sh --content "Title" [--description "Body"] [--priority 1-4] [--due "today 9am"]
#
# Priority: 1=natural (lowest), 2=normal, 3=high, 4=urgent.
# Token sourced from ~/.todoist_token (single-line file, chmod 600 recommended).
# If the file doesn't exist or is empty, exits 0 silently — never fails the caller.
# If the API is unreachable, prints a warning but exits 0 (best-effort signal).

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
while [[ $# -gt 0 ]]; do
    case "$1" in
        --content) CONTENT="$2"; shift 2;;
        --description) DESCRIPTION="$2"; shift 2;;
        --priority) PRIORITY="$2"; shift 2;;
        --due) DUE="$2"; shift 2;;
        *) echo "[notify_todoist] Unknown arg: $1" >&2; exit 1;;
    esac
done

if [ -z "$CONTENT" ]; then
    echo "[notify_todoist] --content required" >&2
    exit 1
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
