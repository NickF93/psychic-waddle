# Portfolio RAG Assistant Plan

## Purpose

Build a small, reliable portfolio assistant for recruiter-facing questions about
Niccolò's verified public profile.

This project is a **Portfolio RAG Assistant**, not a generic autonomous agent.
The system retrieves verified context first, applies deterministic answerability
rules, and uses the LLM only to produce a polished final answer.

## Planning Model

- **Milestone:** a user-visible feature or capability.
- **Sprint:** a coherent implementation tranche inside one milestone.
- **Item:** an atomic unit of documentation, implementation, test, validation,
  checkpoint, or final tracking documentation.
- **Commit:** required immediately after each completed item or sprint, using
  the `type(scope): summary` message format. Huge milestone-end commits are
  forbidden; commits must follow coherent semantic work groups.

## Non-Negotiable Principles

- Keep the system simple, bounded, and designed only for this task.
- Prefer explicit contracts over generic abstractions.
- Keep authorities isolated and decoupled.
- Do not mix retrieval, answer policy, generation, storage, and provider logic.
- Do not add legacy shims, deprecated paths, compatibility aliases, or shortcuts.
- SOLID practice is mandatory.
- SOLID is more important than DRY.
- The knowledge base is reviewed truth; visitor questions are improvement
  signals only.
- No tool loop, autonomous agent loop, or unbounded model-driven execution.
- No persistent visitor identity.

## Core Decisions

- Backend: Python + FastAPI.
- Primary data store: PostgreSQL.
- Vector search: `pgvector`.
- Keyword search: PostgreSQL full-text search.
- LLM backends:
  - Ollama.
  - llama.cpp.
  - Generic OpenAI-compatible API.
- MongoDB is out of scope for v1 unless a later milestone proves a real need.
- Provider-specific payloads must stay inside provider implementations.

## Initial Delivery Focus

Implement Milestones 0 through 4 first. These define the reliable core:
architecture, provider abstraction, verified knowledge, retrieval, answer policy,
and grounded answer generation.

Milestones 5 through 8 are intentionally deferred until the core proves it can
answer correctly and refuse safely.

---

## Milestone 0: Project Definition

**Feature:** locked scope, contracts, architecture boundaries.

This milestone is documentation-only. It must not introduce runtime code,
database schema, provider implementations, ingestion logic, or API endpoints.

### Sprint 0.1: Architecture Contract

Items:

- Documentation: define product goal, non-goals, and supported question domains.
- Documentation: list candidate reviewed source paths without treating them as
  automatically ingested knowledge.
- Documentation: define isolated authorities:
  - `LLMProvider`: model I/O only.
  - `KnowledgeStore`: verified facts, chunks, sources, and embeddings only.
  - `Retriever`: search, ranking, and retrieval diagnostics only.
  - `AnswerPolicy`: answerability decisions only.
  - `AnswerGenerator`: final wording only.
  - `QuestionCollector`: anonymous question improvement signals only.
- Config: define environment variables with no aliases or legacy names.
- Validation: confirm no component owns two unrelated responsibilities.
- Validation: confirm the request flow, forbidden ownership mixing, and privacy
  constraints are documented.
- Checkpoint: architecture accepted before application code starts.
- Final track/doc: `docs/architecture.md`.

Acceptance:

- `docs/architecture.md` is the authoritative contract for Milestone 0.
- Supported question domains are bounded to Niccolò's reviewed public profile.
- Candidate source paths are documented only as future ingestion inputs.
- Exact config names are documented without aliases or deprecated alternatives.
- Visitor question collection is defined as anonymous improvement signals only.
- `PLAN.md` and `AGENTS.md` do not contradict the architecture contract.

---

## Milestone 1: LLM Backend Abstraction

**Feature:** one clean interface supporting the three required backends.

### Sprint 1.1: Provider Contract

Items:

- Implementation: define `LLMProvider` protocol with `chat()` and `embed()`.
- Implementation: define provider-neutral request and response models.
- Implementation: define explicit provider error types.
- Test: add contract tests using a fake provider.
- Validation: ensure provider-specific payloads do not leak outside the provider
  package.
- Checkpoint: fake provider passes the complete contract test suite.
- Final track/doc: `docs/provider-contract.md`.

### Sprint 1.2: Provider Implementations

Items:

- Implementation: add `OllamaProvider`.
- Implementation: add `LlamaCppProvider`.
- Implementation: add `OpenAICompatibleProvider`.
- Config: support `LLM_BACKEND`, `LLM_BASE_URL`, `CHAT_MODEL`,
  `EMBEDDING_MODEL`, and `LLM_API_KEY`.
- Test: add mocked HTTP tests for each provider.
- Validation: verify app code switches provider only through configuration.
- Checkpoint: the same provider contract tests pass for all providers.
- Final track/doc: backend configuration examples.

---

## Milestone 2: Verified Knowledge Base

**Feature:** curated source of truth for Niccolò's public profile.

### Sprint 2.1: Data Model

Items:

- Implementation: add tables for `sources`, `facts`, `chunks`, and
  `chunk_embeddings`.
- Implementation: add metadata categories: `experience`, `education`,
  `projects`, `research`, `skills`, and `contact`.
- Implementation: add public visibility controls for facts and chunks.
- Test: add migration and schema tests.
- Validation: every answerable fact points to a source.
- Checkpoint: schema supports work-history questions cleanly.
- Final track/doc: `docs/knowledge-model.md`.

### Sprint 2.2: Offline Ingestion

Items:

- Implementation: add ingestion command for curated Markdown and JSON facts.
- Implementation: add deterministic chunking strategy.
- Implementation: generate embeddings through the configured provider.
- Implementation: make re-indexing idempotent.
- Test: add ingestion tests with sample profile data.
- Validation: repeated ingestion does not duplicate facts or chunks.
- Checkpoint: sample KB supports "where did Niccolò work?"
- Final track/doc: ingestion guide.

---

## Milestone 3: Retrieval and Answer Policy

**Feature:** retrieve relevant context and decide whether answering is allowed.

### Sprint 3.1: Retrieval

Items:

- Implementation: add vector search with `pgvector`.
- Implementation: add keyword search with PostgreSQL full-text search.
- Implementation: add a small hybrid ranker.
- Test: cover employer, skill, project, and thesis retrieval questions.
- Validation: exact names such as `NAIS` and semantic queries both work.
- Checkpoint: top results are inspectable and deterministic enough for testing.
- Final track/doc: retrieval scoring notes.

### Sprint 3.2: Answerability Gate

Items:

- Implementation: add score thresholds.
- Implementation: add category/domain allowlist.
- Implementation: add low-confidence fallback.
- Implementation: add clarification response for ambiguous questions.
- Test: cover answer, refuse, and clarify cases.
- Validation: the LLM never decides truth or answerability alone.
- Checkpoint: unsupported questions do not produce invented answers.
- Final track/doc: answer policy specification.

---

## Milestone 4: Answer Generation

**Feature:** polished recruiter-facing replies from verified context.

### Sprint 4.1: Grounded Synthesis

Items:

- Implementation: add system prompt for context-only answers.
- Implementation: generate answers only from approved retrieved context.
- Implementation: return source-aware answer payloads.
- Implementation: preserve user language for English and Italian.
- Test: verify generated answers use only supplied context.
- Validation: missing context returns a clear "not verified" response.
- Checkpoint: answers are concise, professional, and source-grounded.
- Final track/doc: prompt contract.

---

## Milestone 5: Public Chat API

**Feature:** minimal backend API for the portfolio widget.

### Sprint 5.1: API Surface

Items:

- Implementation: add `POST /chat`.
- Implementation: add `GET /health`.
- Implementation: add typed request and response schemas.
- Implementation: add request size limits and simple abuse controls.
- Test: add API tests.
- Validation: raw internal traces never leak to the frontend.
- Checkpoint: frontend can call one endpoint.
- Final track/doc: API reference.

---

## Milestone 6: Anonymous Question Collection

**Feature:** collect useful question signals without visitor tracking.

### Sprint 6.1: Question Events

Items:

- Implementation: redact emails, phone numbers, names, and organizations before
  storage.
- Implementation: store only redacted question text, language, answer status,
  source kinds, and top scores.
- Implementation: explicitly avoid IP address, user agent, cookies, session
  identity, email, phone, names, company names, photos, and raw transcripts.
- Test: add redaction and persistence tests.
- Validation: raw request metadata is not stored.
- Checkpoint: question analytics are useful without tracking visitors.
- Final track/doc: privacy note.

### Sprint 6.2: Review Loop

Items:

- Implementation: add admin/export command for unanswered and low-confidence
  questions.
- Implementation: allow reviewed questions to be marked as reviewed or ignored.
- Documentation: define how reviewed questions become new facts, aliases, or eval
  cases.
- Test: add review command tests.
- Validation: visitor questions never auto-promote into the knowledge base.
- Checkpoint: improvement loop exists without contaminating reviewed truth.
- Final track/doc: review workflow.

---

## Milestone 7: Portfolio Widget

**Feature:** small customer-service-style chat UI.

### Sprint 7.1: Widget Integration

Items:

- Implementation: add floating chat button.
- Implementation: add compact chat panel.
- Implementation: add loading, error, answer, fallback, and clarification states.
- Implementation: add source chips when they improve trust without clutter.
- Test: add basic UI interaction tests.
- Validation: widget works on mobile and desktop.
- Checkpoint: recruiter can ask a question in under five seconds.
- Final track/doc: frontend integration notes.

---

## Milestone 8: Release Validation

**Feature:** prove reliability before recruiters see it.

### Sprint 8.1: Evaluation Suite

Items:

- Documentation: define eval categories.
- Implementation: add eval runner.
- Test data: add employer, skills, projects, thesis, off-topic, and adversarial
  questions.
- Validation: no hallucinated employers, dates, degrees, or private claims.
- Checkpoint: minimum acceptance score is met before deploy.
- Final track/doc: release report.

### Sprint 8.2: Deployment

Items:

- Config: add production environment example.
- Implementation: add Dockerfile and compose/deploy config.
- Validation: run health check, DB migration, ingestion, and chat smoke test.
- Checkpoint: deploy is reproducible from a clean state.
- Final track/doc: `docs/deployment.md`.
