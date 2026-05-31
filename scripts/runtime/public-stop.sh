#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

stop_chat_backend() {
    CHAT_BACKEND_VALUE=$(env_value CHAT_BACKEND)
    case "$CHAT_BACKEND_VALUE" in
        openai-compatible) info "chat backend is external: openai-compatible" ;;
        ollama) "$SCRIPT_DIR/ollama-chat-stop.sh" ;;
        llama-cpp) "$SCRIPT_DIR/llama-cpp-chat-stop.sh" ;;
        *) fail "unsupported CHAT_BACKEND: $CHAT_BACKEND_VALUE" ;;
    esac
}

stop_embedding_backend() {
    EMBEDDING_BACKEND_VALUE=$(env_value EMBEDDING_BACKEND)
    case "$EMBEDDING_BACKEND_VALUE" in
        openai-compatible) info "embedding backend is external: openai-compatible" ;;
        ollama) "$SCRIPT_DIR/ollama-embeddings-stop.sh" ;;
        llama-cpp) "$SCRIPT_DIR/llama-cpp-embeddings-stop.sh" ;;
        *) fail "unsupported EMBEDDING_BACKEND: $EMBEDDING_BACKEND_VALUE" ;;
    esac
}

compose_profile public-tls stop nginx-tls
compose_profile public stop nginx
"$SCRIPT_DIR/api-stop.sh"
stop_chat_backend
stop_embedding_backend
"$SCRIPT_DIR/postgres-stop.sh"
