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
- bounded knowledge categories;
- configured `QuestionIntentProfile` definitions shared with retrieval.

It must not:

- call `ChatProvider.chat()` or `EmbeddingProvider.embed()`;
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
- Retrieval computes `combined_score` as matched-channel rank quality. It is
  bounded from `0` to `1` and is not reduced because an optional retrieval
  channel did not return the same chunk.
- At least one reviewed source must support the approved context.
- Supported recruiter questions are detected with the configured
  `QuestionIntentProfile` catalog for professional overview, workplace, current
  role, skills, education, publications, projects, and contact/profile
  questions.
- Intent triggers may be normalized words or exact normalized phrases. This
  supports bounded recruiter phrasing such as `kind of work`, `ruolo attuale`,
  `datore di lavoro`, `pre-prints`, and `come posso contattare` without adding
  an unbounded synonym engine.
- Detected catalog-owned intents map to their accepted knowledge categories and
  required evidence terms.
- Policy receives the `IntentResolution` returned by retrieval. It uses only
  `required_intents` for category and evidence gating.
- Candidate semantic intents may help retrieval gather context, but candidate
  intents are invisible to the policy evidence gate and cannot make an answer
  answerable.
- Required evidence may be a normalized word or an exact normalized phrase,
  such as `worked at`, `work history`, `current role`, or `current employer`.
- Category labels and chunk prefixes alone are not evidence. A chunk such as
  `education: Niccolo has public profile information` does not satisfy an
  education question unless it also contains degree, university, Ph.D.,
  master's, bachelor's, study, completion, or equivalent profile evidence.
- When no configured profile matches, the policy cannot return `answerable`.
- If no configured profile matches and the question is a generic broad profile
  request, the policy returns `needs_clarification`.
- If no configured profile matches and the question is not generic broad, the
  policy returns `not_answerable`.
- Matching category alone is never sufficient. Shared profiles define accepted
  categories and required evidence; policy rejects category-only support.
- Professional overview questions require explicit professional evidence such
  as real experience, career, role, responsibility, research, deployment, or
  work-history terms.
- Workplace/work-history questions require explicit employment evidence such
  as employer, company, workplace, internship, `worked at`, or `work history`.
- Current-role questions require current/present role or employer evidence,
  not merely a previous role in the experience category.
- Fit or suitability phrasing maps to the existing professional-overview and
  skills profiles. It does not create a separate suitability intent. Because
  both profiles match, answerability requires both experience evidence and
  skills evidence. Reviewed role-fit variants cover bounded ML, AI, deep
  learning, LLM, and industrial-computer-vision role wording when the question
  asks about fit, suitability, or match.
- Availability or open-to-work questions are not answerable from role-fit
  evidence alone. They require an explicit reviewed availability fact; otherwise
  they remain unsupported.
- Public license questions use a bounded license intent over the existing
  skills knowledge category and require explicit license evidence.
- Public interests questions use a bounded interests intent over the existing
  skills knowledge category and require explicit interests evidence.
- If the question is broad and the usable context spans multiple domains, the
  policy asks for clarification.
- If no domain is inferred and the question is not a broad profile question,
  the policy returns `not_answerable`; strong unrelated retrieval is not enough
  to make an unsupported question answerable.

The policy does not use model classification. If the deterministic signals are
not enough, the safe result is `not_answerable` or `needs_clarification`.

## Vocabulary Coverage Limits

Question-intent vocabulary is bounded and reviewed. It covers explicit
recruiter phrasings, common English/Italian variants, and punctuation-normalized
forms that are represented in `QuestionIntentProfile`.

The policy receives catalog-owned required intent values through
`IntentResolution`. It must not fabricate intent IDs from raw strings, run its
own raw-question intent detection, read a default catalog, or use a hidden
fallback when `INTENT_PROFILES_PATH` is missing or invalid.

It is not a general semantic synonym system. New aliases, language variants, or
question patterns must be added deliberately with tests. Broad category labels,
generic verbs such as `uses`, `include`, or `includes`, and unsupported private
or off-topic phrasing must not make context answerable by themselves.

Observed typo variants such as `prublications` are deliberately listed only as
reviewed catalog vocabulary, not learned from visitor traffic at runtime.

Catalog semantic example questions are embedding anchors for the semantic
resolver. Semantic matches remain candidate intents unless the catalog contains
a reviewed required threshold calibrated for the configured embedding backend
and model. Candidate-only semantic matches do not reach policy answerability.

## Refusal And Clarification Behavior

The policy returns `not_answerable` when:

- retrieval returned no context;
- all context is below the required score threshold;
- no configured profile matches a non-broad question;
- the matched profile's accepted categories are not covered by usable context;
- category-matching context does not contain required profile evidence;
- approved context has no reviewed source support.

The policy returns `needs_clarification` when:

- the question is broad and generic, such as a general profile, summary, or
  tell-me-about request, and no supported profile matched.

Final wording for refusals or clarification prompts belongs to a later
generation/API layer, not to `AnswerPolicy`.
