#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

SKIP_KNOWLEDGE_REFRESH=false
TLS_RUNTIME=false

usage() {
    cat <<'USAGE'
usage: public-upgrade.sh [--skip-knowledge-refresh] [--tls-runtime]

Rebuild and restart the public runtime while preserving PostgreSQL data,
model volumes, certificate volumes, and ACME state.

By default the script refreshes committed knowledge/profile.json and starts
the HTTP/bootstrap edge. Use --tls-runtime when certificates already exist and
the HTTPS runtime edge should be started.
USAGE
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --skip-knowledge-refresh)
            SKIP_KNOWLEDGE_REFRESH=true
            ;;
        --tls-runtime)
            TLS_RUNTIME=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage >&2
            fail "unknown argument: $1"
            ;;
    esac
    shift
done

start_public_edge() {
    if [ "$TLS_RUNTIME" = true ]; then
        "$SCRIPT_DIR/public-start.sh"
    else
        "$SCRIPT_DIR/api-start.sh"
        compose_profile_up_wait public nginx
    fi
}

"$SCRIPT_DIR/public-validate-env.sh"
"$SCRIPT_DIR/public-setup.sh"

if [ "$SKIP_KNOWLEDGE_REFRESH" = false ]; then
    "$SCRIPT_DIR/public-load-knowledge.sh"
else
    info "knowledge refresh skipped"
fi

start_public_edge
compose_provider_run api portfolio-rag-assistant runtime smoke
"$SCRIPT_DIR/public-smoke.sh"
