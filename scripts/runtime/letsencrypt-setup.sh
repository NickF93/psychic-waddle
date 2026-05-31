#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

PUBLIC_SERVER_NAME=$(configured_value PUBLIC_SERVER_NAME)
LETSENCRYPT_EMAIL=$(configured_value LETSENCRYPT_EMAIL)

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
