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

Milestone 9 changes the target meaning of `combined_score`: it must represent a
deterministic fused ranking signal, not a direct comparison between raw vector
similarity and PostgreSQL text-rank values. Raw vector and keyword scores remain
diagnostics because their numeric scales are not equivalent confidence values.

## Boundaries

Retrieval may:

- Read reviewed knowledge through the knowledge store.
- Use `EmbeddingProvider.embed()` to embed the visitor question.
- Use bounded question-intent profiles for deterministic lexical expansion.
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
- Runs keyword search with PostgreSQL full-text search using
  `websearch_to_tsquery('english', question)` and the matching English text
  vector.
- Runs intent-expanded lexical search for detected supported recruiter intents.
- Merges vector, keyword, and intent-expanded candidates by chunk id.
- Ranks deterministically with rank fusion over candidate ordering, then stable
  score and chunk-id tie-breakers.
- Returns only source-backed `RetrievedContext` records.

The Milestone 9 target is reciprocal rank fusion or an equivalent deterministic
rank-fusion strategy. Retrieval must not treat raw vector similarity and
`ts_rank_cd` as directly comparable confidence scores. Retrieval gathers
candidate evidence; `AnswerPolicy` decides whether that evidence is
intent-complete and answerable.

## Question Intent Expansion

Question-intent expansion is bounded to supported recruiter intents:

- workplaces and work history;
- current role;
- skills and technologies;
- education;
- publications and research outputs;
- projects and repositories;
- public contact links.

Each intent profile supplies trigger terms, accepted knowledge categories,
lexical expansion terms, and required evidence terms. Retrieval may use trigger
and expansion terms to improve recall. Policy must use the same profile
definitions to verify evidence completeness.

Sprint 9.2 introduces the shared profile definitions. Sprint 9.3 wires the
retriever to the profile expansion terms for intent-expanded lexical search and
rank fusion.

## Sprint 3.2 Scope

Sprint 3.2 adds PostgreSQL vector retrieval, keyword retrieval, deterministic
hybrid ranking, retrieval configuration, and mocked retrieval tests. It still
does not add answerability policy, grounded answer generation, chat APIs, or
visitor question collection.
