#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

ISSUE_CERTIFICATE=false
if [ "$#" -gt 1 ]; then
    fail "usage: public-setup.sh [--issue-certificate]"
fi
if [ "$#" -eq 1 ]; then
    [ "$1" = "--issue-certificate" ] || fail "usage: public-setup.sh [--issue-certificate]"
    ISSUE_CERTIFICATE=true
fi

setup_chat_backend() {
    CHAT_BACKEND_VALUE=$(env_value CHAT_BACKEND)
    case "$CHAT_BACKEND_VALUE" in
        openai-compatible) info "chat backend is external: openai-compatible" ;;
        ollama) "$SCRIPT_DIR/ollama-chat-setup.sh" ;;
        llama-cpp) "$SCRIPT_DIR/llama-cpp-chat-setup.sh" ;;
        *) fail "unsupported CHAT_BACKEND: $CHAT_BACKEND_VALUE" ;;
    esac
}

setup_embedding_backend() {
    EMBEDDING_BACKEND_VALUE=$(env_value EMBEDDING_BACKEND)
    case "$EMBEDDING_BACKEND_VALUE" in
        openai-compatible) info "embedding backend is external: openai-compatible" ;;
        ollama) "$SCRIPT_DIR/ollama-embeddings-setup.sh" ;;
        llama-cpp) "$SCRIPT_DIR/llama-cpp-embeddings-setup.sh" ;;
        *) fail "unsupported EMBEDDING_BACKEND: $EMBEDDING_BACKEND_VALUE" ;;
    esac
}

"$SCRIPT_DIR/nginx-validate.sh"
"$SCRIPT_DIR/api-setup.sh"
"$SCRIPT_DIR/postgres-setup.sh"
"$SCRIPT_DIR/public-migrate.sh"
setup_chat_backend
setup_embedding_backend

if [ "$ISSUE_CERTIFICATE" = true ]; then
    "$SCRIPT_DIR/letsencrypt-setup.sh"
    compose_profile public stop nginx
else
    info "certificate issuance skipped; run public-setup.sh --issue-certificate to call letsencrypt-setup.sh"
fi
