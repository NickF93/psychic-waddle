#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

require_backend CHAT_BACKEND llama-cpp
require_llama_model_file LLAMA_CPP_CHAT_MODEL_PATH
compose_profile llama-cpp config >/dev/null
compose_profile_up_wait llama-cpp llama-cpp-chat
