#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

start_chat_backend() {
    CHAT_BACKEND_VALUE=$(env_value CHAT_BACKEND)
    case "$CHAT_BACKEND_VALUE" in
        openai-compatible) info "chat backend is external: openai-compatible" ;;
        ollama) "$SCRIPT_DIR/ollama-chat-start.sh" ;;
        llama-cpp) "$SCRIPT_DIR/llama-cpp-chat-start.sh" ;;
        *) fail "unsupported CHAT_BACKEND: $CHAT_BACKEND_VALUE" ;;
    esac
}

start_embedding_backend() {
    EMBEDDING_BACKEND_VALUE=$(env_value EMBEDDING_BACKEND)
    case "$EMBEDDING_BACKEND_VALUE" in
        openai-compatible) info "embedding backend is external: openai-compatible" ;;
        ollama) "$SCRIPT_DIR/ollama-embeddings-start.sh" ;;
        llama-cpp) "$SCRIPT_DIR/llama-cpp-embeddings-start.sh" ;;
        *) fail "unsupported EMBEDDING_BACKEND: $EMBEDDING_BACKEND_VALUE" ;;
    esac
}

start_chat_backend
start_embedding_backend
"$SCRIPT_DIR/postgres-start.sh"
"$SCRIPT_DIR/api-start.sh"
compose_profile public stop nginx
compose_profile_up_wait public-tls nginx-tls
