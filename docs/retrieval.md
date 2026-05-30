# Retrieval Contract

## Purpose

Retrieval finds reviewed public context that may support a recruiter-facing
answer. It owns search, ranking, and retrieval diagnostics only.

Retrieval does not decide answerability, generate final wording, write
knowledge, collect visitor questions, or expose provider-specific payloads.

## Contract

The `Retriever` protocol exposes one async operation:

- `retrieve(request: RetrievalRequest) -> RetrievalResponse`

`RetrievalRequest` contains:

- `question`: non-empty visitor question text.
- `top_k`: positive maximum number of ranked chunks to return.

`RetrievalResponse` contains the original question and ranked
`RetrievedContext` records.

Each `RetrievedContext` is a public source-backed chunk with:

- `chunk_id`
- `chunk_text`
- `category`
- `source_uri`
- `source_title`
- optional `source_locator`
- `RetrievalScore`

The result model rejects non-public chunks. Only `chunks.public_visible = true`
records may be returned by concrete retrieval implementations.

## Score Metadata

`RetrievalScore` contains inspectable scoring fields:

- `combined_score`: required final retrieval score.
- `vector_score`: optional vector score.
- `keyword_score`: optional keyword score.

Scores are diagnostics for ranking and answer policy. They are not visitor
analytics and must not be stored as visitor-derived data.

## Boundaries

Retrieval may:

- Read reviewed knowledge through the knowledge store.
- Use `EmbeddingProvider.embed()` to embed the visitor question.
- Rank public chunks.
- Return source metadata needed by answer policy and later answer generation.

Retrieval must not:

- Call `ChatProvider.chat()`.
- Decide whether a question is answerable.
- Produce polished recruiter-facing prose.
- Persist, update, or delete knowledge.
- Store visitor questions or request metadata.
- Use private facts or chunks in recruiter-facing results.

## Configuration

Retrieval uses explicit environment variable names. There are no aliases,
legacy names, or fallback defaults.

| Name | Required | Description |
| --- | --- | --- |
| `RETRIEVAL_TOP_K` | Yes | Positive maximum number of chunks requested by the application layer. |
| `RETRIEVAL_MIN_SCORE` | Yes | Minimum accepted combined score from `0` to `1`. |

The configured `EMBEDDING_MODEL` and `EMBEDDING_BACKEND` identify the
embeddings used by PostgreSQL retrieval. The retriever filters stored
embeddings by backend and model before comparing vectors.

## PostgreSQL Retrieval

`PostgreSQLRetriever` implements the retrieval contract against PostgreSQL and
`pgvector`.

The retriever:

- Embeds the question through `EmbeddingProvider.embed()` only.
- Searches only `chunks.public_visible = true`.
- Runs exact vector search over `chunk_embeddings`.
- Filters vector candidates by embedding backend and embedding model.
- Runs keyword search with PostgreSQL full-text search using the `simple`
  configuration.
- Merges vector and keyword candidates by chunk id.
- Ranks deterministically by combined score, vector score, keyword score, and
  chunk id.
- Returns only source-backed `RetrievedContext` records.

The combined score is the highest available score for the chunk across vector
and keyword search. This keeps scoring simple and inspectable for the later
answerability policy.

## Sprint 3.2 Scope

Sprint 3.2 adds PostgreSQL vector retrieval, keyword retrieval, deterministic
hybrid ranking, retrieval configuration, and mocked retrieval tests. It still
does not add answerability policy, grounded answer generation, chat APIs, or
visitor question collection.
