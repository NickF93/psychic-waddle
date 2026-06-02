# Knowledge Model

## Purpose

The knowledge model is the persistence contract for reviewed portfolio facts,
retrievable chunks, source references, and chunk embeddings.

It belongs to the `KnowledgeStore` authority only. It does not define
ingestion, retrieval ranking, answerability policy, answer generation, provider
I/O, API behavior, or anonymous question collection.

## Migration Contract

Schema changes are raw SQL migrations in `migrations/`, applied in
lexicographic order.

The schema requires PostgreSQL with the `pgvector` and `pgcrypto` extensions
available. `pgcrypto` is used only to backfill deterministic embedding content
hashes during migration. Container setup and runtime migration execution are
handled by later sprints.

## Tables

### `sources`

Stores reviewed source records. A source is a curated document, repository,
portfolio page, or public profile artifact admitted into the knowledge base.

Required fields:

- `source_uri`: stable source identifier, unique and non-blank.
- `title`: human-readable reviewed source title.
- `reviewed_at`: explicit review timestamp.

Sources are not visitor data and must not be created from visitor questions.

### `facts`

Stores atomic verified claims that may support answerability decisions.

Required fields:

- `source_id`: required reference to `sources`.
- `category`: one bounded knowledge category.
- `fact_text`: non-blank verified claim.
- `public_visible`: explicit public visibility flag, defaulting to `false`.

Every answerable fact must reference a reviewed source through `source_id`.
Facts without a source are invalid by schema.

### `chunks`

Stores retrievable text blocks derived from reviewed sources.

Required fields:

- `source_id`: required reference to `sources`.
- `category`: one bounded knowledge category.
- `chunk_index`: source-local deterministic order.
- `chunk_text`: non-blank retrievable text.
- `public_visible`: explicit public visibility flag, defaulting to `false`.

Chunks are retrieval units only. They do not decide ranking, answerability, or
final wording.

### `chunk_embeddings`

Stores embedding vectors for chunks.

Required fields:

- `chunk_id`: required reference to `chunks`.
- `embedding_backend`: one of `ollama`, `llama-cpp`, or `openai-compatible`.
- `embedding_model`: exact embedding model name used for the vector.
- `chunk_text_hash`: SHA-256 hex digest of the exact chunk text embedded.
- `embedding_dimension`: vector dimension recorded for validation.
- `embedding`: `pgvector` value.

Embeddings are unique per chunk, backend, and model. This supports multiple
embedding backends without forcing one global vector dimension. Retrieval must
filter by the configured backend and model before comparing vectors.

An embedding is current only when `chunk_text_hash` matches the current
`chunks.chunk_text` value. Knowledge reloads may update chunk text in place;
`knowledge index-embeddings` must regenerate stale rows for the configured
backend/model pair instead of requiring database destruction.

Approximate nearest-neighbor indexes are intentionally absent from Sprint 2.1.
Retrieval-specific indexing belongs to Sprint 3.1.

## Categories

Facts and chunks must use one of these categories:

- `experience`
- `education`
- `projects`
- `research`
- `skills`
- `contact`

These categories match the supported public-profile question domains. New
categories require an explicit migration and documentation update.

## Visibility

`facts.public_visible` and `chunks.public_visible` default to `false`.

Only records explicitly marked public may be used for recruiter-facing answers.
Private or draft-reviewed material can exist in the database without becoming
answerable by default.

## Boundary

This sprint does not load documents, chunk files, generate embeddings, search
vectors, rank chunks, expose APIs, or collect visitor questions.

Future ingestion must write only reviewed knowledge into this schema. Visitor
questions remain anonymous improvement signals and must never be promoted into
facts automatically.
