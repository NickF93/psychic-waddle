#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

require_backend CHAT_BACKEND ollama
CHAT_MODEL_NAME=$(configured_value CHAT_MODEL)
require_ollama_keep_alive
compose_profile_up_wait ollama ollama
preload_ollama_model "$CHAT_MODEL_NAME"
