#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

DESTROY_DB=false
DESTROY_MODELS=false
DESTROY_CERTS=false
ISSUE_CERTIFICATE=false
TLS_RUNTIME=false

usage() {
    cat <<'USAGE'
usage: public-reset-and-setup.sh --destroy-db [--destroy-models] [--destroy-certs] [--issue-certificate|--tls-runtime]

Stop old runtime containers, remove selected persistent state with explicit
destructive flags, rebuild, migrate, load tracked knowledge, start the public
edge, and run smoke checks.

Destructive flags:
  --destroy-db       remove PostgreSQL data
  --destroy-models   remove Ollama model volume
  --destroy-certs    remove Let's Encrypt and ACME volumes

Startup mode:
  default            start HTTP/bootstrap edge
  --tls-runtime      start HTTPS runtime edge; certificates must already exist
  --issue-certificate issue Let's Encrypt certificate, then start HTTPS runtime
USAGE
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --destroy-db)
            DESTROY_DB=true
            ;;
        --destroy-models)
            DESTROY_MODELS=true
            ;;
        --destroy-certs)
            DESTROY_CERTS=true
            ;;
        --issue-certificate)
            ISSUE_CERTIFICATE=true
            TLS_RUNTIME=true
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

if [ "$DESTROY_DB" = false ] && [ "$DESTROY_MODELS" = false ] && [ "$DESTROY_CERTS" = false ]; then
    usage >&2
    fail "reset requires at least one explicit destructive flag"
fi

if [ "$ISSUE_CERTIFICATE" = true ] && [ "$DESTROY_CERTS" = true ]; then
    info "certificate state will be destroyed before fresh issuance"
fi

destroy_certificate_volumes() {
    remove_profile_service public-tls nginx-tls
    remove_profile_service public nginx
    remove_profile_service public certbot
    remove_compose_volume letsencrypt-certs
    remove_compose_volume letsencrypt-work
    remove_compose_volume acme-challenges
}

start_public_edge() {
    if [ "$TLS_RUNTIME" = true ]; then
        "$SCRIPT_DIR/public-start.sh"
    else
        "$SCRIPT_DIR/api-start.sh"
        compose_profile_up_wait public nginx
    fi
}

"$SCRIPT_DIR/public-cleanup.sh"

if [ "$DESTROY_DB" = true ]; then
    "$SCRIPT_DIR/postgres-cleanup.sh" --destroy-data
fi
if [ "$DESTROY_MODELS" = true ]; then
    "$SCRIPT_DIR/ollama-chat-cleanup.sh" --destroy-models
fi
if [ "$DESTROY_CERTS" = true ]; then
    destroy_certificate_volumes
fi

"$SCRIPT_DIR/public-validate-env.sh"

if [ "$ISSUE_CERTIFICATE" = true ]; then
    "$SCRIPT_DIR/public-setup.sh" --issue-certificate
else
    "$SCRIPT_DIR/public-setup.sh"
fi

"$SCRIPT_DIR/public-load-knowledge.sh"
start_public_edge
compose_provider_run api portfolio-rag-assistant runtime smoke
"$SCRIPT_DIR/public-smoke.sh"
