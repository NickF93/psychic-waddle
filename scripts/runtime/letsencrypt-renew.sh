#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

DRY_RUN=false
if [ "$#" -gt 1 ]; then
    fail "usage: letsencrypt-renew.sh [--dry-run]"
fi
if [ "$#" -eq 1 ]; then
    [ "$1" = "--dry-run" ] || fail "usage: letsencrypt-renew.sh [--dry-run]"
    DRY_RUN=true
fi

configured_value PUBLIC_SERVER_NAME >/dev/null
configured_value LETSENCRYPT_EMAIL >/dev/null

if [ "$DRY_RUN" = true ]; then
    compose_profile public-tls run --rm certbot renew \
        --dry-run \
        --cert-name portfolio-rag-assistant \
        --webroot \
        --webroot-path /var/www/certbot
    info "certificate renewal dry run passed"
    exit 0
fi

MARKER_MOUNT=/var/lib/portfolio-rag-assistant-renewal
MARKER_FILE=renewed
MARKER_DIR=$(mktemp -d)
cleanup_marker() {
    rm -f "$MARKER_DIR/$MARKER_FILE"
    rmdir "$MARKER_DIR" 2>/dev/null || true
}
trap cleanup_marker EXIT

compose_profile public-tls run --rm \
    --volume "$MARKER_DIR:$MARKER_MOUNT" \
    certbot renew \
        --cert-name portfolio-rag-assistant \
        --webroot \
        --webroot-path /var/www/certbot \
        --deploy-hook "touch $MARKER_MOUNT/$MARKER_FILE"

if [ ! -f "$MARKER_DIR/$MARKER_FILE" ]; then
    info "no certificates renewed; nginx reload skipped"
    exit 0
fi

compose_profile public-tls exec nginx-tls nginx -t
compose_profile public-tls exec nginx-tls nginx -s reload
info "certificate renewed and nginx reloaded"
