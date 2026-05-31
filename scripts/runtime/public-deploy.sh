#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

"$SCRIPT_DIR/public-build.sh"
"$SCRIPT_DIR/public-migrate.sh"
"$SCRIPT_DIR/public-start.sh"
"$SCRIPT_DIR/public-smoke.sh"
