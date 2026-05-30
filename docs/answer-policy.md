# Answerability Policy

## Purpose

`AnswerPolicy` decides whether retrieved public context is sufficient for a
recruiter-facing answer.

The policy is deterministic. It does not call an LLM, query PostgreSQL, retrieve
additional context, generate final prose, or persist visitor data.

## Boundary

`AnswerPolicy` owns answerability decisions only.

It may use:

- the visitor question text passed by the caller;
- public `RetrievedContext` records returned by `Retriever`;
- retrieval scores;
- reviewed source references;
- bounded knowledge categories.

It must not:

- call `LLMProvider.chat()` or `LLMProvider.embed()`;
- search the database;
- alter retrieval ranking;
- create facts, chunks, or embeddings;
- phrase final recruiter-facing answers;
- collect, redact, or store visitor questions.

## Decision Contract

The policy returns one of three statuses:

- `answerable`: retrieved context is strong enough and source-backed.
- `not_answerable`: context is absent, weak, off-domain, or unsupported.
- `needs_clarification`: the question is broad and strong context spans multiple
  categories.

`answerable` decisions include approved context references for later answer
generation. Non-answerable and clarification decisions include no approved
context, so later components cannot accidentally generate an unsupported answer.

## Deterministic Signals

The default policy uses only local, inspectable signals:

- `RetrievedContext.score.combined_score` must be at least the configured
  `RETRIEVAL_MIN_SCORE` value passed into the policy request.
- At least one reviewed source must support the approved context.
- The question domain is inferred with a bounded keyword map for:
  - `experience`
  - `education`
  - `projects`
  - `research`
  - `skills`
  - `contact`
- If a domain is inferred, approved context is limited to that domain.
- If the question is broad and the usable context spans multiple domains, the
  policy asks for clarification.

The policy does not use model classification. If the deterministic signals are
not enough, the safe result is `not_answerable` or `needs_clarification`.

## Refusal And Clarification Behavior

The policy returns `not_answerable` when:

- retrieval returned no context;
- all context is below the required score threshold;
- the inferred question domain is not covered by usable context;
- approved context has no reviewed source support.

The policy returns `needs_clarification` when:

- the question is broad, such as a general profile or background request;
- retrieval found strong context across multiple categories.

Final wording for refusals or clarification prompts belongs to a later
generation/API layer, not to `AnswerPolicy`.
