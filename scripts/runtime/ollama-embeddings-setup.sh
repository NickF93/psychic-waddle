#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

require_backend EMBEDDING_BACKEND ollama
EMBEDDING_MODEL_NAME=$(configured_value EMBEDDING_MODEL)
compose_profile ollama config >/dev/null
compose_profile_up_wait ollama ollama
compose_profile ollama exec -T ollama ollama pull "$EMBEDDING_MODEL_NAME"
