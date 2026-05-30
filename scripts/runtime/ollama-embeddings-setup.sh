#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

require_backend EMBEDDING_BACKEND ollama
EMBEDDING_MODEL_NAME=$(configured_value EMBEDDING_MODEL)
compose_profile ollama config >/dev/null
compose_profile ollama up -d ollama
compose_profile ollama exec ollama ollama pull "$EMBEDDING_MODEL_NAME"
