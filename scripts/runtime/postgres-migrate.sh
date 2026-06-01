#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

compose exec -T db sh -c '
set -eu
for migration in /migrations/*.sql; do
    [ -f "$migration" ] || {
        echo "no database migrations found" >&2
        exit 1
    }
    psql --set ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$migration"
done
'
