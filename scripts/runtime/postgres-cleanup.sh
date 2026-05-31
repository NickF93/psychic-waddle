#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

require_cleanup_flag --destroy-data "$@"
remove_service db
remove_compose_volume postgres-data
