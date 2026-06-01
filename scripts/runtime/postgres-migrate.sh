#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

compose exec -T db sh <<'REMOTE_SCRIPT'
set -eu

psql_plain() {
    psql --set ON_ERROR_STOP=1 --tuples-only --no-align -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"
}

psql_exec() {
    psql --set ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"
}

ledger_exists=$(
    psql_plain --command "SELECT to_regclass('public.schema_migrations') IS NOT NULL"
)

if [ "$ledger_exists" = "f" ]; then
    existing_schema_tables=$(
        psql_plain --command "
        SELECT count(*)
        FROM unnest(ARRAY[
            'sources',
            'facts',
            'chunks',
            'chunk_embeddings',
            'question_events'
        ]) AS existing_table(table_name)
        WHERE to_regclass('public.' || table_name) IS NOT NULL
        "
    )
    if [ "$existing_schema_tables" != "0" ]; then
        echo "database has application tables but no schema_migrations ledger" >&2
        echo "refusing to guess applied migrations" >&2
        exit 1
    fi
fi

psql_exec --command "
CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_name text PRIMARY KEY,
    checksum_sha256 text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT schema_migrations_migration_name_not_blank CHECK (
        length(btrim(migration_name)) > 0
    ),
    CONSTRAINT schema_migrations_checksum_sha256_format CHECK (
        checksum_sha256 ~ '^[0-9a-f]{64}$'
    )
)
"

found_migration=false
for migration in /migrations/*.sql; do
    [ -f "$migration" ] || continue
    found_migration=true
    migration_name=$(basename "$migration")
    case "$migration_name" in
        [0-9][0-9][0-9][0-9]_*.sql) ;;
        *)
            echo "invalid migration file name: $migration_name" >&2
            exit 1
            ;;
    esac
    case "$migration_name" in
        *[!abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-]*)
            echo "invalid migration file name: $migration_name" >&2
            exit 1
            ;;
    esac

    set -- $(sha256sum "$migration")
    checksum=$1
    recorded_checksum=$(
        psql_plain --command "
        SELECT checksum_sha256
        FROM schema_migrations
        WHERE migration_name = '$migration_name'
        "
    )
    if [ -n "$recorded_checksum" ]; then
        if [ "$recorded_checksum" != "$checksum" ]; then
            echo "migration checksum mismatch: $migration_name" >&2
            exit 1
        fi
        echo "migration already applied: $migration_name"
        continue
    fi

    psql_exec <<SQL
BEGIN;
\i $migration
INSERT INTO schema_migrations (migration_name, checksum_sha256)
VALUES ('$migration_name', '$checksum');
COMMIT;
SQL
    echo "migration applied: $migration_name"
done

if [ "$found_migration" != "true" ]; then
    echo "no database migrations found" >&2
    exit 1
fi
REMOTE_SCRIPT
