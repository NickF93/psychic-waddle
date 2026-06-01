#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

configured_value PUBLIC_SERVER_NAME >/dev/null
configured_value LETSENCRYPT_EMAIL >/dev/null

compose_profile public-tls run --rm certbot certificates \
    --cert-name portfolio-rag-assistant
