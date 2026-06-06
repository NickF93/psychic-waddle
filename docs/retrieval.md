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

`RetrievalResponse` contains the original question, ranked `RetrievedContext`
records, and the intent authority's `IntentResolution`.

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

`combined_score` is a deterministic rank-quality signal used by answer policy.
It is not a direct comparison between raw vector similarity and PostgreSQL
text-rank values. Raw vector and keyword scores remain diagnostics because
their numeric scales are not equivalent confidence values.

## Boundaries

Retrieval may:

- Read reviewed knowledge through the knowledge store.
- Use `EmbeddingProvider.embed()` to embed the visitor question.
- Use bounded question-intent profiles for deterministic lexical expansion.
- Use semantic candidate intents resolved from reviewed catalog anchors.
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
| `RETRIEVAL_MIN_SCORE` | Yes | Minimum accepted combined score from `0` to `1`, applied by answer policy after retrieval. |

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
- Resolves lexical required intents plus semantic candidate intents after the
  single question embedding call.
- Runs intent-expanded lexical search for required and candidate recruiter
  intents.
- Merges vector, keyword, and intent-expanded candidates by chunk id.
- Ranks deterministically with raw reciprocal-rank-fusion sums over candidate
  ordering, then stable raw-score and chunk-id tie-breakers.
- Returns only source-backed `RetrievedContext` records.

RRF uses a fixed internal rank constant of `60`. The raw RRF sum is normalized
to the existing `0..1` `combined_score` contract by dividing by the maximum
possible RRF score for the channels where that chunk actually appeared. Missing
optional channels do not reduce policy threshold eligibility. The raw RRF sum
remains the ordering key so chunks found by multiple channels are still favored
in ranking.

Retrieval must not treat raw vector similarity and `ts_rank_cd` as directly
comparable confidence scores. Retrieval gathers candidate evidence;
`AnswerPolicy` applies `RETRIEVAL_MIN_SCORE` and decides whether that evidence
is intent-complete and answerable.

## Question Intent Expansion

Question-intent expansion is bounded to supported recruiter intents:

- professional overview;
- workplaces and work history;
- current role;
- skills and technologies;
- bounded ML, AI, deep-learning, LLM, and computer-vision role-fit wording
  through the skills intent;
- public license;
- public interests;
- education;
- publications and research outputs;
- projects and repositories;
- public contact links.

Each configured intent profile supplies positive trigger groups, accepted
knowledge categories, semantic example questions, semantic thresholds, lexical
expansion terms, and required evidence groups. Lexical matches become required
intents. Semantic matches start as candidate intents unless a reviewed required
threshold promotes them.

Retrieval may use catalog-owned required and candidate intents to improve
candidate gathering. Intent expansion is bounded to matching profiles'
controlled lexical expansion terms, joined as a PostgreSQL full-text OR query,
and searches only those profiles' accepted knowledge categories. The raw visitor
question is not appended to the intent-expanded query because vector and keyword
retrieval already search the question. Retrieval transports the same
`IntentResolution` to policy; it does not decide answerability.

Semantic anchor embeddings are in-memory runtime artifacts owned by the intent
resolver. They are not written to PostgreSQL and are not reviewed knowledge. If
the catalog is missing, invalid, or calibrated for a different embedding
backend/model, runtime startup fails instead of falling back to built-in
vocabulary or silently disabling semantic matching.

## Sprint 3.2 Scope

Sprint 3.2 adds PostgreSQL vector retrieval, keyword retrieval, deterministic
hybrid ranking, retrieval configuration, and mocked retrieval tests. It still
does not add answerability policy, grounded answer generation, chat APIs, or
visitor question collection.
