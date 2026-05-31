#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

require_command grep

BOOTSTRAP_CONFIG="$ROOT_DIR/deploy/nginx/nginx.conf"
TLS_CONFIG="$ROOT_DIR/deploy/nginx/nginx-tls.conf"

require_config_line() {
    CONFIG_FILE=$1
    EXPECTED_LINE=$2
    grep -F "$EXPECTED_LINE" "$CONFIG_FILE" >/dev/null 2>&1 || fail "missing Nginx directive in $CONFIG_FILE: $EXPECTED_LINE"
}

validate_public_routes() {
    CONFIG_FILE=$1
    require_config_line "$CONFIG_FILE" "location = /api/assistant/chat"
    require_config_line "$CONFIG_FILE" "proxy_pass http://api:8000/chat?;"
    require_config_line "$CONFIG_FILE" "location = /api/assistant/health"
    require_config_line "$CONFIG_FILE" "proxy_pass http://api:8000/health?;"
    require_config_line "$CONFIG_FILE" "location = /api/assistant/ready"
    require_config_line "$CONFIG_FILE" "proxy_pass http://api:8000/ready?;"
    require_config_line "$CONFIG_FILE" "\"https://pigreco.xyz\""
    require_config_line "$CONFIG_FILE" "\"https://www.pigreco.xyz\""
    require_config_line "$CONFIG_FILE" "limit_req zone=assistant_chat burst=40 nodelay;"
    require_config_line "$CONFIG_FILE" "location ^~ /.well-known/acme-challenge/"
}

compose_profile public config >/dev/null
compose_profile public-tls config >/dev/null

validate_public_routes "$BOOTSTRAP_CONFIG"
validate_public_routes "$TLS_CONFIG"
require_config_line "$TLS_CONFIG" "listen 443 ssl;"
require_config_line "$TLS_CONFIG" "ssl_certificate /etc/letsencrypt/live/portfolio-rag-assistant/fullchain.pem;"
require_config_line "$TLS_CONFIG" "ssl_certificate_key /etc/letsencrypt/live/portfolio-rag-assistant/privkey.pem;"

info "Nginx public and public-tls configuration validated"
