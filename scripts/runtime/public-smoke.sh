#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

require_command curl
require_command python3

PUBLIC_SMOKE_BASE_URL=${PUBLIC_SMOKE_BASE_URL:-http://127.0.0.1:18080}
PUBLIC_SMOKE_ALLOWED_ORIGIN=https://pigreco.xyz
PUBLIC_SMOKE_ALLOWED_WWW_ORIGIN=https://www.pigreco.xyz
PUBLIC_SMOKE_REJECTED_ORIGIN=https://example.invalid
CHAT_BODY='{"question":"Where did Niccolo work?","language":"en"}'

json_status_is() {
    EXPECTED_STATUS=$1
    python3 -c 'import json, sys; data = json.load(sys.stdin); assert data.get("status") == sys.argv[1], data' "$EXPECTED_STATUS"
}

json_chat_status_is_public() {
    python3 -c 'import json, sys; data = json.load(sys.stdin); assert data.get("status") in {"answerable", "not_answerable", "needs_clarification"}, data; assert isinstance(data.get("answer"), str), data'
}

curl_headers_status() {
    curl -sS -D - -o /dev/null -w 'status=%{http_code}\n' "$@"
}

assert_cors_preflight_allowed() {
    ORIGIN=$1
    PREFLIGHT_RESPONSE=$(curl_headers_status -X OPTIONS "$PUBLIC_SMOKE_BASE_URL/api/assistant/chat" \
        -H "origin: $ORIGIN" \
        -H "access-control-request-method: POST" \
        -H "access-control-request-headers: content-type")

    printf '%s\n' "$PREFLIGHT_RESPONSE" | python3 -c 'import sys
origin = sys.argv[1]
headers = {}
status = None
for line in sys.stdin.read().splitlines():
    if line.startswith("status="):
        status = line.split("=", 1)[1]
    elif ":" in line:
        key, value = line.split(":", 1)
        headers.setdefault(key.lower(), []).append(value.strip())
assert status == "204", {"status": status, "headers": headers}
assert origin in headers.get("access-control-allow-origin", []), headers' "$ORIGIN"
    info "cors preflight passed: $ORIGIN"
}

assert_cors_preflight_rejected() {
    ORIGIN=$1
    PREFLIGHT_RESPONSE=$(curl_headers_status -X OPTIONS "$PUBLIC_SMOKE_BASE_URL/api/assistant/chat" \
        -H "origin: $ORIGIN" \
        -H "access-control-request-method: POST" \
        -H "access-control-request-headers: content-type")

    printf '%s\n' "$PREFLIGHT_RESPONSE" | python3 -c 'import sys
status = None
for line in sys.stdin.read().splitlines():
    if line.startswith("status="):
        status = line.split("=", 1)[1]
assert status == "403", {"status": status}'
    info "unexpected origin rejected: $ORIGIN"
}

assert_direct_api_not_public() {
    if [ -z "${PUBLIC_DIRECT_API_PROBE_URL:-}" ]; then
        info "direct API probe skipped: set PUBLIC_DIRECT_API_PROBE_URL to check public port 8000"
        return
    fi

    DIRECT_STATUS=$(curl -sS --connect-timeout 3 --max-time 5 -o /dev/null -w '%{http_code}' "$PUBLIC_DIRECT_API_PROBE_URL" 2>/dev/null || true)
    case "$DIRECT_STATUS" in
        2??) fail "direct API port is publicly reachable: $PUBLIC_DIRECT_API_PROBE_URL returned $DIRECT_STATUS" ;;
        *) info "direct API probe passed: $PUBLIC_DIRECT_API_PROBE_URL returned ${DIRECT_STATUS:-000}" ;;
    esac
}

assert_cors_preflight_allowed "$PUBLIC_SMOKE_ALLOWED_ORIGIN"
assert_cors_preflight_allowed "$PUBLIC_SMOKE_ALLOWED_WWW_ORIGIN"
assert_cors_preflight_rejected "$PUBLIC_SMOKE_REJECTED_ORIGIN"

HEALTH_RESPONSE=$(curl -fsS "$PUBLIC_SMOKE_BASE_URL/api/assistant/health" \
    -H "origin: $PUBLIC_SMOKE_ALLOWED_ORIGIN")
printf '%s\n' "$HEALTH_RESPONSE" | json_status_is ok

READY_RESPONSE=$(curl -fsS "$PUBLIC_SMOKE_BASE_URL/api/assistant/ready" \
    -H "origin: $PUBLIC_SMOKE_ALLOWED_ORIGIN")
printf '%s\n' "$READY_RESPONSE" | json_status_is ready

CHAT_RESPONSE=$(curl -fsS -X POST "$PUBLIC_SMOKE_BASE_URL/api/assistant/chat" \
    -H "content-type: application/json" \
    -H "origin: $PUBLIC_SMOKE_ALLOWED_ORIGIN" \
    -d "$CHAT_BODY")
printf '%s\n' "$CHAT_RESPONSE" | json_chat_status_is_public

assert_direct_api_not_public

info "public smoke passed: $PUBLIC_SMOKE_BASE_URL"
