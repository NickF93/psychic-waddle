#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

require_backend EMBEDDING_BACKEND ollama
require_ollama_keep_alive
compose_profile_up_wait ollama ollama
