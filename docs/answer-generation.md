# Answer Generation

## Purpose

`AnswerGenerator` owns final recruiter-facing wording only.

It receives an answerability decision that has already been made by
`AnswerPolicy`. It must not retrieve more context, rank chunks, query
PostgreSQL, decide answerability, create facts, collect questions, or inspect
provider-specific payloads.

## Contract

The `AnswerGenerator` protocol exposes one async operation:

- `generate(request: AnswerGenerationRequest) -> AnswerGenerationResponse`

`AnswerGenerationRequest` contains:

- `question`: non-empty visitor question text.
- `decision`: an `AnswerPolicyDecision`.
- `language`: explicit output language, either `en` or `it`.

`AnswerGenerationResponse` contains:

- `answer_text`: final text for the recruiter-facing response.
- `status`: the original answerability status.
- `sources`: deterministic source references.

`AnswerSourceReference` contains:

- `source_title`
- `source_uri`
- optional `source_locator`

## Source Evidence

Source identity is deterministic and code-owned. It is derived only from
`AnswerPolicyDecision.approved_context`.

For answerable responses:

- structured source references must be returned;
- a compact source note must be included in the answer text;
- source references must correspond to approved context.

For `not_answerable` and `needs_clarification` responses:

- source references must be empty;
- generation must not imply hidden or partial evidence.

The LLM must not invent, rename, select, validate, or override source identity.

The answer text includes a deterministic source note after the generated prose:

- English: `Sources: <source title> (<source locator>).`
- Italian: `Fonti: <source title> (<source locator>).`

If a source has no locator, the note uses the source title only. Structured
source references remain the source of truth for later API and widget rendering.

## Grounded Synthesis

`GroundedAnswerGenerator` implements the contract for answerable decisions.

For `answerable` decisions, it:

- formats only approved context into the user prompt;
- excludes retrieval scores, thresholds, rankings, and internal diagnostics;
- calls `ChatProvider.chat()` with the configured chat model;
- appends the deterministic source note;
- returns structured source references deduplicated from approved context.

The system prompt requires the model to:

- answer concisely and professionally for a recruiter;
- use only approved context;
- avoid outside knowledge;
- avoid unsupported facts, dates, employers, degrees, skills, private
  information, and source evidence;
- return the exact internal sentinel `INSUFFICIENT_APPROVED_CONTEXT` if it cannot
  answer directly from approved context;
- omit citations and source labels because the application attaches sources.

If an answerable provider response returns the sentinel or clear insufficiency
wording, the generator deterministically demotes the response to
`not_answerable`, returns the standard fallback text, and attaches no sources.
This keeps public status, answer text, and source evidence consistent.

The generator uses explicit request language only:

- `en`: English.
- `it`: Italian.

The generator does not infer or store language from visitor traffic.

## Fallbacks

For `not_answerable`, `GroundedAnswerGenerator` does not call the provider. It
returns deterministic fallback text and no sources.

For `needs_clarification`, `GroundedAnswerGenerator` does not call the provider.
It returns deterministic clarification text and no sources.

Fallbacks are intentionally simple. The `AnswerPolicy` owns the decision; the
generator only phrases the already-decided outcome.

## Boundaries

Answer generation may:

- call `ChatProvider.chat()` for `answerable` decisions;
- format approved context into a prompt;
- produce deterministic fallback or clarification text;
- attach deterministic source references.

Answer generation must not:

- call `EmbeddingProvider.embed()`;
- call `Retriever`;
- query PostgreSQL;
- run answer policy;
- persist visitor questions or metadata;
- use unapproved retrieved context;
- expose retrieval scores or internal diagnostics to the answer text.

## Sprint 4.1 Scope

Sprint 4.1 adds the answer-generation contract, request and response models,
source reference model, explicit errors, fake-generator contract tests, and this
documentation.

## Sprint 4.2 Scope

Sprint 4.2 adds grounded synthesis through `GroundedAnswerGenerator`, mocked
provider tests, deterministic fallback and clarification wording, deterministic
source notes, and prompt checks that prevent unapproved context and score
metadata from reaching the model.

## Milestone 4 Acceptance

Milestone 4 is accepted when:

- an answerable policy decision can produce recruiter-facing text through
  `ChatProvider.chat()`;
- fallback and clarification decisions return deterministic text without model
  calls;
- `EmbeddingProvider.embed()` is never called by answer generation;
- approved context is the only context sent to the chat provider;
- retrieval scores and internal diagnostics are excluded from prompts and
  answer text;
- answerable responses include deterministic structured sources;
- answerable response text includes a deterministic English or Italian source
  note;
- no visitor-derived data is persisted.

## Milestone 5 Handoff

Milestone 5 may use `AnswerGenerator` as the final authority in the API request
flow:

1. API receives the visitor question.
2. API asks `Retriever` for context.
3. API asks `AnswerPolicy` for a decision.
4. API asks `AnswerGenerator` for final wording.
5. API maps `AnswerGenerationResponse` to the public `POST /chat` response.

The API layer must not copy answer-generation prompt logic, fallback wording, or
source formatting. It should only orchestrate authorities and adapt the response
for HTTP.

Sprint 4.3 adds acceptance coverage and these handoff notes. Public HTTP
schemas and endpoints remain Milestone 5 work.
