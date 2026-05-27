# Database Migrations

This directory contains raw SQL migrations for the PostgreSQL knowledge store.

Migrations are applied in lexicographic order. Each migration file name must use
an increasing numeric prefix and a short descriptive suffix:

```text
0001_knowledge_schema.sql
```

The migration layer owns schema definition only. It must not contain ingestion,
retrieval, ranking, answer policy, answer generation, provider I/O, API behavior,
or question collection logic.

The v1 database target is PostgreSQL with the `pgvector` extension available.
Container orchestration and runtime migration execution are handled in later
sprints.
