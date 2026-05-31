#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

require_command curl
require_command python3

PUBLIC_SMOKE_BASE_URL=${PUBLIC_SMOKE_BASE_URL:-http://127.0.0.1:8080}
PUBLIC_SMOKE_ORIGIN=${PUBLIC_SMOKE_ORIGIN:-https://pigreco.xyz}
CHAT_BODY='{"question":"Where did Niccolo work?","language":"en"}'

json_status_is() {
    EXPECTED_STATUS=$1
    python3 -c 'import json, sys; data = json.load(sys.stdin); assert data.get("status") == sys.argv[1], data' "$EXPECTED_STATUS"
}

json_chat_status_is_public() {
    python3 -c 'import json, sys; data = json.load(sys.stdin); assert data.get("status") in {"answerable", "not_answerable", "needs_clarification"}, data; assert isinstance(data.get("answer"), str), data'
}

curl -fsS -X OPTIONS "$PUBLIC_SMOKE_BASE_URL/api/assistant/chat" \
    -H "origin: $PUBLIC_SMOKE_ORIGIN" \
    -H "access-control-request-method: POST" \
    -H "access-control-request-headers: content-type" \
    -o /dev/null

HEALTH_RESPONSE=$(curl -fsS "$PUBLIC_SMOKE_BASE_URL/api/assistant/health" \
    -H "origin: $PUBLIC_SMOKE_ORIGIN")
printf '%s\n' "$HEALTH_RESPONSE" | json_status_is ok

READY_RESPONSE=$(curl -fsS "$PUBLIC_SMOKE_BASE_URL/api/assistant/ready" \
    -H "origin: $PUBLIC_SMOKE_ORIGIN")
printf '%s\n' "$READY_RESPONSE" | json_status_is ready

CHAT_RESPONSE=$(curl -fsS -X POST "$PUBLIC_SMOKE_BASE_URL/api/assistant/chat" \
    -H "content-type: application/json" \
    -H "origin: $PUBLIC_SMOKE_ORIGIN" \
    -d "$CHAT_BODY")
printf '%s\n' "$CHAT_RESPONSE" | json_chat_status_is_public

info "public smoke passed: $PUBLIC_SMOKE_BASE_URL"
