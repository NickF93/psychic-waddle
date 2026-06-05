#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

require_integer() {
    VALUE_KEY=$1
    VALUE=$(configured_value "$VALUE_KEY")
    case "$VALUE" in
        ""|*[!0-9]*) fail "$VALUE_KEY must be a positive integer" ;;
    esac
    [ "$VALUE" -gt 0 ] || fail "$VALUE_KEY must be a positive integer"
}

require_score() {
    VALUE_KEY=$1
    VALUE=$(configured_value "$VALUE_KEY")
    awk -v value="$VALUE" 'BEGIN {
        if (value !~ /^[0-9]+([.][0-9]+)?$/) exit 1
        numeric = value + 0
        if (numeric < 0 || numeric > 1) exit 1
    }' || fail "$VALUE_KEY must be a number between 0 and 1"
}

require_boolean() {
    VALUE_KEY=$1
    VALUE=$(configured_value "$VALUE_KEY")
    case "$VALUE" in
        true|false) ;;
        *) fail "$VALUE_KEY must be true or false" ;;
    esac
}

require_config_file() {
    VALUE_KEY=$1
    VALUE=$(configured_value "$VALUE_KEY")
    case "$VALUE" in
        config/*) ;;
        *) fail "$VALUE_KEY must point inside config/" ;;
    esac
    [ -f "$ROOT_DIR/$VALUE" ] || fail "missing config file: $ROOT_DIR/$VALUE"
}

require_backend_value() {
    VALUE_KEY=$1
    VALUE=$(configured_value "$VALUE_KEY")
    case "$VALUE" in
        ollama|llama-cpp|openai-compatible) ;;
        *) fail "$VALUE_KEY must be one of: llama-cpp, ollama, openai-compatible" ;;
    esac
}

require_local_api_bind() {
    API_BIND_ADDRESS_VALUE=$(configured_value API_BIND_ADDRESS)
    [ "$API_BIND_ADDRESS_VALUE" = "127.0.0.1" ] || fail "API_BIND_ADDRESS must be 127.0.0.1 for public deployment"
}

require_provider_keys() {
    CHAT_BACKEND_VALUE=$(configured_value CHAT_BACKEND)
    EMBEDDING_BACKEND_VALUE=$(configured_value EMBEDDING_BACKEND)

    env_value CHAT_API_KEY >/dev/null
    env_value EMBEDDING_API_KEY >/dev/null

    if [ "$CHAT_BACKEND_VALUE" = "openai-compatible" ]; then
        configured_value CHAT_API_KEY >/dev/null
    fi
    if [ "$EMBEDDING_BACKEND_VALUE" = "openai-compatible" ]; then
        configured_value EMBEDDING_API_KEY >/dev/null
    fi
}

require_llama_cpp_when_selected() {
    CHAT_BACKEND_VALUE=$(configured_value CHAT_BACKEND)
    EMBEDDING_BACKEND_VALUE=$(configured_value EMBEDDING_BACKEND)

    env_value LLAMA_CPP_MODEL_DIR >/dev/null
    env_value LLAMA_CPP_CHAT_MODEL_PATH >/dev/null
    env_value LLAMA_CPP_EMBEDDING_MODEL_PATH >/dev/null
    env_value LLAMA_CPP_EMBEDDING_POOLING >/dev/null

    if [ "$CHAT_BACKEND_VALUE" = "llama-cpp" ]; then
        require_llama_model_file LLAMA_CPP_CHAT_MODEL_PATH
    fi
    if [ "$EMBEDDING_BACKEND_VALUE" = "llama-cpp" ]; then
        require_llama_model_file LLAMA_CPP_EMBEDDING_MODEL_PATH
        configured_value LLAMA_CPP_EMBEDDING_POOLING >/dev/null
    fi
}

require_local_api_bind
require_integer API_PORT
require_integer PUBLIC_HTTP_PORT
require_integer PUBLIC_HTTPS_PORT
configured_value PUBLIC_HTTP_BIND_ADDRESS >/dev/null
configured_value PUBLIC_HTTPS_BIND_ADDRESS >/dev/null
configured_value PUBLIC_SERVER_NAME >/dev/null
configured_value LETSENCRYPT_EMAIL >/dev/null

configured_value POSTGRES_DB >/dev/null
configured_value POSTGRES_USER >/dev/null
configured_value POSTGRES_PASSWORD >/dev/null

require_backend_value CHAT_BACKEND
configured_value CHAT_BASE_URL >/dev/null
configured_value CHAT_MODEL >/dev/null
require_backend_value EMBEDDING_BACKEND
configured_value EMBEDDING_BASE_URL >/dev/null
configured_value EMBEDDING_MODEL >/dev/null
require_provider_keys
require_llama_cpp_when_selected

require_integer RETRIEVAL_TOP_K
require_score RETRIEVAL_MIN_SCORE
require_config_file INTENT_PROFILES_PATH
require_boolean QUESTION_COLLECTION_ENABLED

compose config >/dev/null
compose_profile public config >/dev/null
compose_profile public-tls config >/dev/null

info "public runtime environment validated"
