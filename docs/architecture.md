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
3. The `AnswerPolicy` decides whether the retrieved context is answerable and
   intent-complete.
4. The `AnswerGenerator` asks a `ChatProvider` to phrase only approved context.
5. The API returns the answer, refusal, or clarification response.
6. If enabled, `QuestionCollector` stores only an anonymous improvement signal.

The LLM must never bypass retrieval, write facts, choose truth, or decide that a
question is answerable.

## Milestone 9 Remediation Target

Milestone 9 makes answerability reliable for natural recruiter questions without
expanding the assistant beyond Niccolo's reviewed public profile.

The target architecture separates candidate generation from answerability:

- Retrieval gathers plausible public context with vector search, full-text
  search, and deterministic recruiter-intent expansion.
- Policy decides whether the gathered context actually answers the question.
- Generation receives only approved context and must not decide that missing
  context is sufficient.
- Embedding indexing treats changed chunk text as stale and refreshes embeddings
  for the configured backend and model.

Natural questions such as "Where did Niccolo work?" must be answerable when
tracked reviewed knowledge contains workplace evidence. Unsupported personal or
off-topic questions must remain not answerable even if retrieval finds strong
but unrelated context.

## Authority Boundaries

### `ChatProvider`

Owns chat model I/O only.

- Provides chat completion calls through a provider-neutral contract.
- Contains provider-specific HTTP payloads, routes, authentication, and response
  parsing.
- Must not retrieve knowledge, decide answerability, collect questions, or write
  application data.

### `EmbeddingProvider`

Owns embedding model I/O only.

- Provides embedding calls through a provider-neutral contract.
- Contains provider-specific HTTP payloads, routes, authentication, and response
  parsing.
- Must not retrieve knowledge, rank chunks, decide answerability, collect
  questions, or write application data.

### `KnowledgeStore`

Owns verified facts, chunks, sources, and embeddings only.

- Stores reviewed sources, facts, chunks, metadata, and embedding vectors.
- Serves persistence operations requested by ingestion and retrieval.
- Stores a deterministic hash of the exact embedded chunk text so indexing and
  readiness can reject stale vectors after reviewed knowledge changes.
- Must not rank results, generate answers, call chat models, or collect visitor
  signals.

### `QuestionIntentProfile`

Owns bounded recruiter-intent definitions only.

- Defines deterministic positive trigger terms or exact normalized trigger
  phrases, accepted knowledge categories, lexical expansion terms, and required
  evidence terms for supported recruiter intents from the reviewed
  `config/intent-profiles.json` runtime catalog.
- Owns catalog-produced intent identifiers; retrieval and policy must not
  fabricate intent IDs from raw strings.
- Covered intents are professional overview, workplaces and work history,
  current role, skills, education, publications, projects and repositories, and
  public contact links.
- May be read by retrieval for deterministic query expansion.
- May be read by policy for deterministic evidence-completeness checks.
- Must not call providers, search PostgreSQL, rank chunks, generate answers,
  persist data, collect questions, or inspect request metadata.
- The catalog is matcher configuration, not portfolio knowledge, and must not be
  ingested into the knowledge store.
- The catalog loader must fail fast for missing files, invalid JSON, unknown or
  missing fields, invalid schema versions, duplicate intents, invalid knowledge
  categories, and empty term groups. There is no default catalog or hidden
  fallback.

### `Retriever`

Owns search, ranking, and retrieval diagnostics only.

- Performs vector search, keyword search, and hybrid ranking over reviewed
  knowledge.
- May use `QuestionIntentProfile` definitions to add deterministic lexical
  expansion for supported recruiter intents.
- Must treat vector scores and text-rank scores as different diagnostic scales
  unless a rank-fusion algorithm combines their result ordering.
- Returns ranked context with scores and minimal diagnostics needed by policy.
- Must not generate final wording, decide final answerability, call chat models,
  or mutate the knowledge base.

### `AnswerPolicy`

Owns answerability decisions only.

- Decides answer, refuse, or clarify from matched question profiles, retrieval
  scores, source support, and ambiguity.
- Uses `QuestionIntentProfile` definitions to require intent-complete evidence
  for common recruiter intents.
- Must return `answerable` only when a supported `QuestionIntentProfile` matches
  and approved context satisfies that profile's evidence requirements.
- Must not approve an answer solely because retrieved context has a matching
  broad category.
- Produces deterministic decision metadata for tests and diagnostics.
- Must not call LLMs, search stores, generate polished prose, or persist data.

### `AnswerGenerator`

Owns final wording only.

- Converts an approved policy decision and approved retrieved context into a
  concise recruiter-facing answer.
- Preserves the visitor's language when supported by the prompt contract.
- For fit or suitability questions, summarizes approved evidence only and must
  not provide a yes/no hiring verdict, hiring recommendation, or prediction.
- Must return a consistent not-answerable response if the provider indicates
  that approved context is insufficient.
- Must not add facts absent from approved context, override policy, retrieve
  additional data, or store question signals.

### `QuestionCollector`

Owns anonymous question improvement signals only.

- Stores raw text only for questions that are not answerable from verified
  context when collection is enabled.
- Supports later review of gaps, aliases, and evaluation cases. Review state,
  category, note, and timestamps are admin-owned workflow data, not runtime
  visitor metadata.
- Must not store visitor identity outside the raw question text, answer text,
  answer status, source identifiers, source kinds, retrieval scores,
  per-question language, request metadata, or promote questions into knowledge
  automatically.

## Forbidden Ownership Mixing

- Provider code must not contain retrieval, policy, or storage decisions.
- Retrieval code must not produce polished answers.
- Policy code must not call a model or database search directly.
- Generation code must not fetch more context or decide whether answering is
  allowed.
- Intent-profile code must not call providers, search stores, rank chunks,
  generate answers, or persist data.
- Question collection must not write reviewed facts or chunks.
- Storage code must not contain ranking, policy, generation, or provider
  payload logic.
- API code must orchestrate authorities without absorbing their business logic.

## Configuration Contract

Configuration names are explicit. No aliases, deprecated names, compatibility
names, or hidden fallbacks are allowed.

- `CHAT_BACKEND`: chat backend, one of `ollama`, `llama-cpp`, or
  `openai-compatible`.
- `CHAT_BASE_URL`: base URL for chat requests.
- `CHAT_API_KEY`: optional API key for chat requests.
- `CHAT_MODEL`: chat model name.
- `EMBEDDING_BACKEND`: embedding backend, one of `ollama`, `llama-cpp`, or
  `openai-compatible`.
- `EMBEDDING_BASE_URL`: base URL for embedding requests.
- `EMBEDDING_API_KEY`: optional API key for embedding requests.
- `EMBEDDING_MODEL`: embedding model name.
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`: PostgreSQL
  connection fields.
- `RETRIEVAL_TOP_K`: number of candidate chunks requested by retrieval.
- `RETRIEVAL_MIN_SCORE`: minimum score required by answer policy.
- `INTENT_PROFILES_PATH`: explicit path to the reviewed intent catalog. The
  path is mandatory at runtime and must load before the public API is served.
- `QUESTION_COLLECTION_ENABLED`: enables anonymous question signal storage.

Milestone 0 defines names and ownership only. Runtime validation, defaults, and
example environment files belong to later implementation milestones.

## Privacy Contract

Visitor questions are improvement signals only.

The system must not store visitor identity or request metadata outside the raw
question text explicitly submitted by the visitor.

If anonymous question collection is enabled, stored visitor-derived data is
limited to raw text from questions that are not answerable from verified
context. The raw text may contain personal data typed by the visitor; the
operator must review and manually delete records that are not useful or should
not be retained.

Question review metadata is limited to admin-owned state, category, note, and
timestamps. The system must not store IP addresses, user agents, cookies,
session IDs, frontend identifiers, per-question language, answer status, answer
text, source identifiers, source kinds, retrieval scores, raw request metadata,
or any other answer/request metadata from visitor traffic. Visitor questions
must be reviewed manually before they influence facts, aliases, or evaluation
cases.

The public Nginx edge is allowed to persist only redacted operational access
logs needed to run the public service. Those logs may contain timestamp, HTTP
method, normalized route path without query string, status code, response byte
count, request duration, and allowed browser origin. They must not contain IP
addresses, user agents, cookies, request bodies, raw questions, query strings,
API keys, source identifiers, retrieval scores, answer status, answer text, or
any forwarded visitor identity headers.

The public Nginx edge may use an IP-derived rate-limit key only in volatile
Nginx memory. That key must not be logged, exported, persisted, forwarded to the
API, or stored in application data.

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
