#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

"$SCRIPT_DIR/nginx-validate.sh"
"$SCRIPT_DIR/api-build.sh"
