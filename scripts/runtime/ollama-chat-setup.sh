#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

require_backend CHAT_BACKEND ollama
CHAT_MODEL_NAME=$(configured_value CHAT_MODEL)
compose_profile ollama config >/dev/null
compose_profile_up_wait ollama ollama
compose_profile ollama exec -T ollama ollama pull "$CHAT_MODEL_NAME"
