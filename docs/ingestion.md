# Offline Ingestion

Offline ingestion loads reviewed public-profile knowledge into PostgreSQL.

It is deterministic and local. It does not call LLM providers, retrieve, rank,
answer questions, expose an API, or collect visitor questions.

## Input

Milestone 2 accepts curated JSON only.

Each file must follow `docs/knowledge-input-format.md`:

- `schema_version` is `1`.
- `sources` contains reviewed source records.
- `facts` contains atomic reviewed claims.
- every fact references a source in the same file.
- every fact has an explicit `public_visible` boolean.

Markdown ingestion is intentionally out of scope for Milestone 2.

## Command

```bash
DB_HOST=localhost \
DB_PORT=5432 \
DB_NAME=portfolio \
DB_USER=user \
DB_PASSWORD=password \
  portfolio-rag-assistant knowledge ingest knowledge/profile.json
```

Multiple files may be provided:

```bash
DB_HOST=localhost \
DB_PORT=5432 \
DB_NAME=portfolio \
DB_USER=user \
DB_PASSWORD=password \
  portfolio-rag-assistant knowledge ingest knowledge/cv.json knowledge/projects.json
```

Ingestion uses only the explicit database fields shown above.

## Persistence

The ingestion command validates the complete input batch before opening a write
transaction.

For each source in the batch, ingestion:

- upserts the source by `source_uri`.
- upserts facts by source, category, and fact text.
- removes stale facts for that source.
- creates one chunk for each public fact.
- upserts chunks by source and stable `chunk_index`.
- removes stale chunks for that source.

Sources not present in the current batch are not changed.

## Chunking

Chunks are generated deterministically from public facts:

```text
<category>: <fact_text>
```

Example:

```text
experience: Niccolo worked at NAIS s.r.l.
```

Non-public facts are stored as facts but do not produce chunks or embeddings.

## Embedding Indexing

Embedding indexing is a separate command:

```bash
DB_HOST=localhost \
DB_PORT=5432 \
DB_NAME=portfolio \
DB_USER=user \
DB_PASSWORD=password \
EMBEDDING_BACKEND=ollama \
EMBEDDING_BASE_URL=http://localhost:11434/api \
EMBEDDING_MODEL=nomic-embed-text \
  portfolio-rag-assistant knowledge index-embeddings
```

The command reads public chunks that do not already have a current embedding for
the selected backend and model. It calls only `EmbeddingProvider.embed()` and
stores:

- `chunk_id`.
- `embedding_backend`.
- `embedding_model`.
- `embedding_dimension`.
- a stable hash of the chunk text used to produce the embedding.
- `embedding`.

Rerunning the command for the same backend and model skips chunks whose stored
embedding hash still matches the current public chunk text. If the chunk text
changed after a knowledge update, the embedding is stale and must be regenerated
for that backend and model.

Running the command with a different backend or model creates separate
embedding rows for the same chunks. Refreshing stale embeddings for one
backend/model pair must not delete or rewrite embeddings for other pairs.

## Boundary

Ingestion owns only:

- loading curated JSON files.
- validating the accepted input contract.
- deterministic chunk creation.
- PostgreSQL persistence.

Ingestion must not own:

- provider-specific payloads.
- retrieval or ranking.
- answerability policy.
- final answer wording.
- visitor question collection.

Embedding indexing owns only provider-neutral embedding calls and vector
persistence. Provider-specific request and response payloads remain inside the
provider implementations.
