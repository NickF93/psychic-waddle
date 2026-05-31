#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

PUBLIC_SERVER_NAME=$(configured_value PUBLIC_SERVER_NAME)
LETSENCRYPT_EMAIL=$(configured_value LETSENCRYPT_EMAIL)
PUBLIC_HTTP_BIND_ADDRESS=$(configured_value PUBLIC_HTTP_BIND_ADDRESS)
PUBLIC_HTTP_PORT=$(configured_value PUBLIC_HTTP_PORT)

[ "$PUBLIC_HTTP_BIND_ADDRESS" = "0.0.0.0" ] || fail "PUBLIC_HTTP_BIND_ADDRESS must be 0.0.0.0 before issuing Let's Encrypt certificates"
[ "$PUBLIC_HTTP_PORT" = "80" ] || fail "PUBLIC_HTTP_PORT must be 80 before issuing Let's Encrypt certificates"

compose_profile_up_wait public nginx
compose_profile public run --rm certbot certonly \
    --webroot \
    --webroot-path /var/www/certbot \
    --cert-name portfolio-rag-assistant \
    --email "$LETSENCRYPT_EMAIL" \
    --agree-tos \
    --no-eff-email \
    --non-interactive \
    -d "$PUBLIC_SERVER_NAME"
