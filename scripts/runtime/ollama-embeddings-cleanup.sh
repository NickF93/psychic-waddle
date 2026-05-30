#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

require_cleanup_flag --destroy-models "$@"
remove_profile_service ollama ollama
remove_compose_volume ollama-models
