#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

down_chat_backend() {
    CHAT_BACKEND_VALUE=$(env_value CHAT_BACKEND)
    case "$CHAT_BACKEND_VALUE" in
        openai-compatible) info "chat backend is external: openai-compatible" ;;
        ollama) "$SCRIPT_DIR/ollama-chat-down.sh" ;;
        llama-cpp) "$SCRIPT_DIR/llama-cpp-chat-down.sh" ;;
        *) fail "unsupported CHAT_BACKEND: $CHAT_BACKEND_VALUE" ;;
    esac
}

down_embedding_backend() {
    EMBEDDING_BACKEND_VALUE=$(env_value EMBEDDING_BACKEND)
    case "$EMBEDDING_BACKEND_VALUE" in
        openai-compatible) info "embedding backend is external: openai-compatible" ;;
        ollama) "$SCRIPT_DIR/ollama-embeddings-down.sh" ;;
        llama-cpp) "$SCRIPT_DIR/llama-cpp-embeddings-down.sh" ;;
        *) fail "unsupported EMBEDDING_BACKEND: $EMBEDDING_BACKEND_VALUE" ;;
    esac
}

remove_profile_service public-tls nginx-tls
remove_profile_service public nginx
remove_profile_service public certbot
"$SCRIPT_DIR/api-down.sh"
down_chat_backend
down_embedding_backend
"$SCRIPT_DIR/postgres-down.sh"
