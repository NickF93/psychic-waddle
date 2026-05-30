#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd "$SCRIPT_DIR/../.." && pwd)
ENV_FILE=${ENV_FILE:-"$ROOT_DIR/.env"}
COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-portfolio-rag-assistant}
RUNTIME_WAIT_TIMEOUT_SECONDS=${RUNTIME_WAIT_TIMEOUT_SECONDS:-120}

fail() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

info() {
    printf '%s\n' "$*"
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

require_env_file() {
    [ -f "$ENV_FILE" ] || fail "missing env file: $ENV_FILE"
}

compose() {
    require_command docker
    require_env_file
    (cd "$ROOT_DIR" && docker compose --env-file "$ENV_FILE" "$@")
}

compose_profile() {
    PROFILE_NAME=$1
    shift
    compose --profile "$PROFILE_NAME" "$@"
}

compose_config() {
    compose config >/dev/null
}

wait_timeout() {
    case "$RUNTIME_WAIT_TIMEOUT_SECONDS" in
        ""|*[!0-9]*) fail "RUNTIME_WAIT_TIMEOUT_SECONDS must be a positive integer" ;;
    esac
    [ "$RUNTIME_WAIT_TIMEOUT_SECONDS" -gt 0 ] || fail "RUNTIME_WAIT_TIMEOUT_SECONDS must be a positive integer"
    printf '%s\n' "$RUNTIME_WAIT_TIMEOUT_SECONDS"
}

compose_up_wait() {
    compose up --wait --wait-timeout "$(wait_timeout)" "$@"
}

compose_profile_up_wait() {
    PROFILE_NAME=$1
    shift
    compose_profile "$PROFILE_NAME" up --wait --wait-timeout "$(wait_timeout)" "$@"
}

env_value() {
    ENV_KEY=$1
    require_env_file
    ENV_RAW=$(
        awk -v key="$ENV_KEY" '
            /^[[:space:]]*($|#)/ { next }
            {
                line = $0
                sub(/^[[:space:]]*/, "", line)
                if (index(line, key "=") == 1) {
                    print substr(line, length(key) + 2)
                    found = 1
                    exit
                }
            }
            END { if (!found) exit 1 }
        ' "$ENV_FILE"
    ) || fail "missing required env value: $ENV_KEY"

    case "$ENV_RAW" in
        \"*\") ENV_RAW=${ENV_RAW#\"}; ENV_RAW=${ENV_RAW%\"} ;;
    esac

    printf '%s\n' "$ENV_RAW"
}

require_backend() {
    BACKEND_KEY=$1
    EXPECTED_BACKEND=$2
    ACTUAL_BACKEND=$(env_value "$BACKEND_KEY")
    [ "$ACTUAL_BACKEND" = "$EXPECTED_BACKEND" ] || fail "$BACKEND_KEY must be $EXPECTED_BACKEND in $ENV_FILE"
}

configured_value() {
    VALUE_KEY=$1
    VALUE=$(env_value "$VALUE_KEY")
    case "$VALUE" in
        ""|replace-with*) fail "$VALUE_KEY must be configured in $ENV_FILE" ;;
    esac
    printf '%s\n' "$VALUE"
}

remove_service() {
    SERVICE_NAME=$1
    compose rm --stop --force "$SERVICE_NAME"
}

remove_profile_service() {
    PROFILE_NAME=$1
    SERVICE_NAME=$2
    compose_profile "$PROFILE_NAME" rm --stop --force "$SERVICE_NAME"
}

compose_volume_name() {
    printf '%s_%s\n' "$COMPOSE_PROJECT_NAME" "$1"
}

remove_compose_volume() {
    VOLUME_NAME=$(compose_volume_name "$1")
    require_command docker
    if docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1; then
        docker volume rm "$VOLUME_NAME"
    else
        info "volume not present: $VOLUME_NAME"
    fi
}

remove_docker_image() {
    IMAGE_NAME=$1
    require_command docker
    if docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
        docker image rm "$IMAGE_NAME"
    else
        info "image not present: $IMAGE_NAME"
    fi
}

require_cleanup_flag() {
    EXPECTED_FLAG=$1
    shift
    if [ "$#" -ne 1 ] || [ "$1" != "$EXPECTED_FLAG" ]; then
        fail "cleanup requires explicit $EXPECTED_FLAG"
    fi
}

require_llama_model_file() {
    MODEL_ENV_KEY=$1
    MODEL_PATH=$(configured_value "$MODEL_ENV_KEY")
    MODEL_DIR=$(configured_value LLAMA_CPP_MODEL_DIR)

    case "$MODEL_PATH" in
        /models/*) MODEL_RELATIVE_PATH=${MODEL_PATH#/models/} ;;
        *) fail "$MODEL_ENV_KEY must point inside /models because Compose mounts LLAMA_CPP_MODEL_DIR there" ;;
    esac

    case "$MODEL_DIR" in
        /*) HOST_MODEL_PATH="$MODEL_DIR/$MODEL_RELATIVE_PATH" ;;
        *) HOST_MODEL_PATH="$ROOT_DIR/$MODEL_DIR/$MODEL_RELATIVE_PATH" ;;
    esac

    [ -f "$HOST_MODEL_PATH" ] || fail "missing llama.cpp model file: $HOST_MODEL_PATH"
}
