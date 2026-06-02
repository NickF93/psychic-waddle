# Database Migrations

This directory contains raw SQL migrations for the PostgreSQL knowledge store.

Migrations are applied in lexicographic order. Each migration file name must use
an increasing numeric prefix and a short descriptive suffix:

```text
0001_knowledge_schema.sql
```

The runtime migration command records applied files in `schema_migrations` with
the migration name, SHA-256 checksum, and application timestamp. Already applied
migrations are skipped only when the stored checksum matches the file checksum.
Checksum mismatches fail the migration command.

If application tables already exist but `schema_migrations` does not, the
runtime migration command fails instead of guessing a baseline. Operators must
start from a clean database or restore a database that was migrated with the
ledger.

The migration layer owns schema definition only. It must not contain ingestion,
retrieval, ranking, answer policy, answer generation, provider I/O, API behavior,
or question collection logic.

The v1 database target is PostgreSQL with the `pgvector` and `pgcrypto`
extensions available. `pgcrypto` is used by migrations for deterministic
content-hash backfills. Container orchestration and runtime migration execution
are handled in later sprints.
