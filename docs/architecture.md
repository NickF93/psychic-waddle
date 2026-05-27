# Architecture Contract

## Product Goal

Build a small recruiter-facing Portfolio RAG Assistant for questions about
Niccolò's verified public profile.

The assistant retrieves reviewed context first, applies deterministic
answerability rules, and uses the configured LLM only to phrase approved
answers in a professional style.

## Non-Goals

- No generic autonomous agent platform.
- No tool-call loop or unbounded model-driven execution.
- No model-owned truth, source selection, or answerability decision.
- No automatic learning of facts from visitor questions.
- No visitor identity tracking.
- No support for topics outside Niccolò's reviewed public profile.

## Supported Question Domains

The v1 assistant may answer only when reviewed knowledge supports the answer.

- Work experience: employers, roles, responsibilities, dates, and public work
  history.
- Education: degrees, academic work, thesis, and public academic context.
- Skills: technologies, methods, languages, frameworks, and domains present in
  reviewed sources.
- Projects: public portfolio projects and repositories selected for the
  knowledge base.
- Research: papers, thesis work, experiments, and public research summaries.
- Contact: public portfolio or professional contact links only when explicitly
  curated.

The assistant must refuse or ask for clarification when the question is
off-topic, ambiguous, unsupported, private, or asks for speculation.

## Candidate Reviewed Sources

These paths are approved candidates for future ingestion. They are not ingested
by Milestone 0.

- `../CV/AI4I/CVNiccoloFerrari.tex`
- `../MH-PatchCore_Paper`
- `../PhD_Thesis_NF`
- `../DeepGenIndustrialIntegration`
- `../AIgentEgo`
- `../AgentOrchestrator`
- `../DREAM-GAN_paper`
- `../GraphMemorytransformer`

Milestone 2 must decide which files or documents inside these locations become
reviewed knowledge. A path being listed here does not make every file inside it
public, answerable, or trusted.

## Architecture Flow

The normal request flow is fixed:

1. The API receives a visitor question.
2. The `Retriever` searches reviewed knowledge through `KnowledgeStore`.
3. The `AnswerPolicy` decides whether the retrieved context is answerable.
4. The `AnswerGenerator` asks `LLMProvider` to phrase only approved context.
5. The API returns the answer, refusal, or clarification response.
6. If enabled, `QuestionCollector` stores only an anonymous improvement signal.

The LLM must never bypass retrieval, write facts, choose truth, or decide that a
question is answerable.

## Authority Boundaries

### `LLMProvider`

Owns model I/O only.

- Provides chat completion and embedding calls through provider-neutral
  contracts.
- Contains provider-specific HTTP payloads, routes, authentication, and response
  parsing.
- Must not retrieve knowledge, decide answerability, collect questions, or write
  application data.

### `KnowledgeStore`

Owns verified facts, chunks, sources, and embeddings only.

- Stores reviewed sources, facts, chunks, metadata, and embedding vectors.
- Serves persistence operations requested by ingestion and retrieval.
- Must not rank results, generate answers, call chat models, or collect visitor
  signals.

### `Retriever`

Owns search, ranking, and retrieval diagnostics only.

- Performs vector search, keyword search, and hybrid ranking over reviewed
  knowledge.
- Returns ranked context with scores and minimal diagnostics needed by policy.
- Must not generate final wording, decide final answerability, call chat models,
  or mutate the knowledge base.

### `AnswerPolicy`

Owns answerability decisions only.

- Decides answer, refuse, or clarify from question domain, retrieval scores,
  source support, and ambiguity.
- Produces deterministic decision metadata for tests and diagnostics.
- Must not call LLMs, search stores, generate polished prose, or persist data.

### `AnswerGenerator`

Owns final wording only.

- Converts an approved policy decision and approved retrieved context into a
  concise recruiter-facing answer.
- Preserves the visitor's language when supported by the prompt contract.
- Must not add facts absent from approved context, override policy, retrieve
  additional data, or store question signals.

### `QuestionCollector`

Owns anonymous question improvement signals only.

- Stores redacted question text and non-identifying answer metadata when
  collection is enabled.
- Supports later review of gaps, aliases, and evaluation cases.
- Must not store visitor identity, raw transcripts, or promote questions into
  knowledge automatically.

## Forbidden Ownership Mixing

- Provider code must not contain retrieval, policy, or storage decisions.
- Retrieval code must not produce polished answers.
- Policy code must not call a model or database search directly.
- Generation code must not fetch more context or decide whether answering is
  allowed.
- Question collection must not write reviewed facts or chunks.
- Storage code must not contain ranking, policy, generation, or provider
  payload logic.
- API code must orchestrate authorities without absorbing their business logic.

## Configuration Contract

Configuration names are explicit. No aliases, deprecated names, compatibility
names, or hidden fallbacks are allowed.

- `LLM_BACKEND`: selected backend, one of `ollama`, `llama-cpp`, or
  `openai-compatible`.
- `LLM_BASE_URL`: base URL for the selected backend.
- `LLM_API_KEY`: API key for providers that require one.
- `CHAT_MODEL`: chat model name sent to the selected backend.
- `EMBEDDING_MODEL`: embedding model name sent to the selected backend.
- `DATABASE_URL`: PostgreSQL connection URL.
- `RETRIEVAL_TOP_K`: number of candidate chunks requested by retrieval.
- `RETRIEVAL_MIN_SCORE`: minimum score required by answer policy.
- `QUESTION_COLLECTION_ENABLED`: enables anonymous question signal storage.

Milestone 0 defines names and ownership only. Runtime validation, defaults, and
example environment files belong to later implementation milestones.

## Privacy Contract

Visitor questions are improvement signals only.

The system must not store IP addresses, user agents, cookies, session IDs,
emails, phone numbers, names, company names, photos, raw transcripts, or any
other visitor identity.

If anonymous question collection is enabled, stored data is limited to redacted
question text and non-identifying answer metadata such as language, answer
status, source kinds, and retrieval scores. Visitor questions must be reviewed
manually before they influence facts, aliases, or evaluation cases.

## Milestone 0 Acceptance Checklist

- The product goal and non-goals are explicit.
- Supported question domains are bounded to Niccolò's reviewed public profile.
- Candidate source paths are listed without implying automatic ingestion.
- Each authority has exactly one responsibility.
- Allowed request flow is fixed and deterministic.
- Forbidden ownership mixing is documented.
- Configuration names are exact and have no aliases.
- Privacy rules prohibit visitor identity storage.
- No runtime code, schema, ingestion, provider implementation, or API endpoint is
  introduced by Milestone 0.
