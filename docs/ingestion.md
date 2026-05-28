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
DATABASE_URL=postgresql://user:password@localhost:5432/portfolio \
  portfolio-rag-assistant knowledge ingest knowledge/profile.json
```

Multiple files may be provided:

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/portfolio \
  portfolio-rag-assistant knowledge ingest knowledge/cv.json knowledge/projects.json
```

`DATABASE_URL` is the only database connection variable for ingestion.

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

## Boundary

Ingestion owns only:

- loading curated JSON files.
- validating the accepted input contract.
- deterministic chunk creation.
- PostgreSQL persistence.

Ingestion must not own:

- provider-specific payloads.
- embedding generation.
- retrieval or ranking.
- answerability policy.
- final answer wording.
- visitor question collection.
