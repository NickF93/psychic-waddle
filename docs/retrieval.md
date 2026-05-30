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
- Use `LLMProvider.embed()` to embed the visitor question.
- Rank public chunks.
- Return source metadata needed by answer policy and later answer generation.

Retrieval must not:

- Call `LLMProvider.chat()`.
- Decide whether a question is answerable.
- Produce polished recruiter-facing prose.
- Persist, update, or delete knowledge.
- Store visitor questions or request metadata.
- Use private facts or chunks in recruiter-facing results.

## Sprint 3.1 Scope

Sprint 3.1 defines the provider-neutral retrieval contract only. PostgreSQL
queries, vector search, keyword search, hybrid ranking, and retrieval
configuration are implemented in Sprint 3.2.
