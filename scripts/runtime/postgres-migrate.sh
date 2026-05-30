#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /migrations/0001_knowledge_schema.sql'
