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
- a compact source note may be included in the answer text;
- source references must correspond to approved context.

For `not_answerable` and `needs_clarification` responses:

- source references must be empty;
- generation must not imply hidden or partial evidence.

The LLM must not invent, rename, select, validate, or override source identity.

## Boundaries

Answer generation may:

- call `LLMProvider.chat()` for `answerable` decisions;
- format approved context into a prompt;
- produce deterministic fallback or clarification text;
- attach deterministic source references.

Answer generation must not:

- call `LLMProvider.embed()`;
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

Grounded prompt construction, provider calls, deterministic fallback wording,
and Milestone 4 acceptance coverage belong to later Sprint 4 commits.
