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

Milestones 5 through 9 are intentionally deferred until the core proves it can
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
  - `ChatProvider`: chat model I/O only.
  - `EmbeddingProvider`: embedding model I/O only.
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

- Implementation: define `ChatProvider` and `EmbeddingProvider` protocols.
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
- Config: support separate chat and embedding backend, base URL, model, and API
  key settings.
- Test: add mocked HTTP tests for each provider.
- Validation: verify app code switches provider only through configuration.
- Checkpoint: the same provider contract tests pass for all providers.
- Final track/doc: backend configuration examples.

---

## Milestone 2: Verified Knowledge Base

**Feature:** curated source of truth for Niccolò's public profile.

### Sprint 2.1: Data Model

Items:

- Implementation: add PostgreSQL + `pgvector` migration foundation.
- Implementation: add tables for `sources`, `facts`, `chunks`, and
  `chunk_embeddings`.
- Implementation: add metadata categories: `experience`, `education`,
  `projects`, `research`, `skills`, and `contact`.
- Implementation: add public visibility controls for facts and chunks.
- Test: add migration and schema tests.
- Validation: every answerable fact points to a source.
- Checkpoint: schema supports work-history questions cleanly.
- Final track/doc: `docs/knowledge-model.md`.

### Sprint 2.2: Curated Fact Input Format

Items:

- Documentation: define curated sources, accepted public source origins,
  forbidden inputs, and the JSON contract.
- Implementation: add typed input models for source records, fact records, and
  full knowledge documents.
- Implementation: validate `schema_version`, unique source identifiers,
  reviewed timestamps, non-empty text fields, bounded categories, explicit
  public visibility, and fact source references.
- Implementation: reject visitor questions, unsupported categories, missing
  sources, blank facts, and malformed documents.
- Test: add curated input validation tests.
- Validation: the JSON model maps directly to existing `sources` and `facts`.
- Checkpoint: the format can express "Niccolò worked at NAIS s.r.l." as a
  reviewed public fact.
- Final track/doc: `docs/knowledge-input-format.md`.

### Sprint 2.3: Offline Ingestion Pipeline

Items:

- Implementation: add a minimal PostgreSQL client dependency and raw SQL
  persistence only.
- Implementation: add a bounded `KnowledgeStore` persistence module for
  sources, facts, and chunks.
- Implementation: add an `ingest` command for curated JSON files.
- Implementation: validate the full JSON document before any database write.
- Implementation: upsert sources by `source_uri`.
- Implementation: persist facts exactly from curated input.
- Implementation: generate one deterministic chunk per fact.
- Implementation: make repeated ingestion idempotent.
- Test: cover source, fact, and chunk persistence.
- Test: cover repeated ingestion and invalid input rollback.
- Validation: ingestion does not call LLMs, retrieve, rank, answer, or collect
  questions.
- Checkpoint: sample curated data can populate work-history facts.
- Final track/doc: `docs/ingestion.md`.

### Sprint 2.4: Embedding Indexing

Items:

- Implementation: add an `index-embeddings` command.
- Implementation: read chunks from PostgreSQL and call only
  `EmbeddingProvider.embed()`.
- Implementation: store vectors in `chunk_embeddings` with backend, model, and
  dimension.
- Implementation: overwrite embeddings for the selected backend and model when
  rerun without deleting embeddings for other backend/model pairs.
- Test: use a fake provider for deterministic embedding tests.
- Test: verify stored backend, model, dimension, and idempotent reruns.
- Validation: embedding logic contains no provider-specific payloads.
- Validation: tests perform no real network calls.
- Checkpoint: the knowledge base has vector-ready chunks for Milestone 3.
- Final track/doc: update `docs/ingestion.md`.

### Sprint 2.5: Knowledge QA and Maintenance

Items:

- Implementation: add a `validate` command using the same validation logic as
  ingestion.
- Implementation: add QA checks for duplicate facts, orphan source references,
  empty public facts, sources with no facts, and invalid public chunk
  derivation.
- Test: cover valid minimal knowledge and each QA failure.
- Validation: QA checks are deterministic, local, LLM-free, and non-mutating.
- Checkpoint: curated knowledge can be checked before deployment or indexing.
- Final track/doc: `docs/knowledge-maintenance.md`.

---

## Milestone 3: Retrieval and Answerability

**Feature:** retrieve source-backed public context and deterministically decide
whether answering is allowed.

This milestone builds the read side only. It does not add chat API endpoints,
final LLM wording, visitor question collection, model-generated facts, or
schema changes for direct chunk-to-fact references.

### Sprint 3.0: Plan Alignment

Items:

- Documentation: refine Milestone 3 into retrieval contract, PostgreSQL
  retrieval, and answerability policy sprints.
- Documentation: keep grounded answer generation in Milestone 4.
- Validation: confirm `PLAN.md`, `AGENTS.md`, and `docs/architecture.md` do not
  contradict the refined scope.
- Checkpoint: Milestone 3 can be implemented without crossing authority
  boundaries.

### Sprint 3.1: Retrieval Contract

Items:

- Implementation: add a `Retriever` protocol with async `retrieve()`.
- Implementation: define retrieval request, result, score, and response models.
- Implementation: include chunk text, category, source URI, source title,
  optional source locator, and score metadata in results.
- Implementation: define explicit retrieval error types.
- Test: add fake retriever contract tests.
- Validation: retrieval contract does not generate answers, decide
  answerability, mutate storage, or expose provider payloads.
- Checkpoint: retrieval outputs are source-backed and inspectable.
- Final track/doc: `docs/retrieval.md`.

### Sprint 3.2: PostgreSQL Retrieval

Items:

- Config: support `RETRIEVAL_TOP_K` and `RETRIEVAL_MIN_SCORE`.
- Implementation: add PostgreSQL retrieval against public chunks only.
- Implementation: embed visitor questions through `EmbeddingProvider.embed()`
  only.
- Implementation: filter chunk embeddings by configured backend and embedding
  model.
- Implementation: add exact vector search with `pgvector`.
- Implementation: add keyword search with PostgreSQL full-text search using the
  `simple` configuration.
- Implementation: merge vector and keyword candidates deterministically.
- Implementation: return ranked source-backed chunks only.
- Test: add fake-provider and fake-store tests with no network.
- Test: add optional PostgreSQL retrieval tests gated by `TEST_DATABASE_URL`.
- Validation: retrieval owns search, ranking, and retrieval diagnostics only.
- Checkpoint: exact names such as `NAIS` and semantic queries are retrievable.
- Final track/doc: update `docs/retrieval.md`.

### Sprint 3.3: Answerability Policy

Items:

- Implementation: add an `AnswerPolicy` protocol.
- Implementation: define deterministic policy request and decision models.
- Implementation: support `answerable`, `not_answerable`, and
  `needs_clarification` decisions.
- Implementation: apply `RETRIEVAL_MIN_SCORE`, retrieved categories, and source
  support without calling an LLM.
- Implementation: return approved context references for later answer
  generation.
- Test: cover relevant, irrelevant, low-confidence, unsupported, and ambiguous
  questions.
- Validation: policy does not call an LLM, search the database, phrase final
  answers, or persist data.
- Checkpoint: unsupported questions do not produce invented answers.
- Final track/doc: `docs/answer-policy.md`.

---

## Milestone 4: Answer Generation

**Feature:** polished recruiter-facing replies from verified context.

This milestone adds the `AnswerGenerator` authority only. It does not add public
HTTP endpoints, request orchestration, retrieval, answerability decisions,
database access, ingestion, or question collection.

Milestone 4 uses one canonical implementation branch:
`feature/answer-generation`. Sprint boundaries are preserved through separate
semantic commits.

Source evidence is represented in two ways:

- structured source references are returned deterministically from approved
  retrieved context;
- a compact source note is appended deterministically to the final answer text.

The LLM must not invent, rename, select, or validate sources. Source identity is
owned by code using `AnswerPolicyDecision.approved_context`.

### Sprint 4.0: Answer Generation Plan Alignment

Items:

- Documentation: expand Milestone 4 into concrete sprints.
- Documentation: define M4 boundaries against retrieval, policy, storage, API,
  and question collection.
- Documentation: define deterministic source payload plus deterministic source
  note behavior.
- Validation: confirm `PLAN.md`, `AGENTS.md`, and `docs/architecture.md` remain
  coherent.
- Checkpoint: M4 can start without architectural ambiguity.

### Sprint 4.1: Answer Generator Contract

Items:

- Implementation: add an `AnswerGenerator` protocol with async `generate()`.
- Implementation: define request model containing the visitor question, an
  `AnswerPolicyDecision`, and explicit language: `en` or `it`.
- Implementation: define response model containing answer text, answer status,
  and deterministic source references.
- Implementation: define source reference model from approved context with
  source title, source URI, and optional source locator.
- Implementation: define explicit answer generation error types.
- Test: validate accepted answerable requests.
- Test: reject blank questions and unsupported languages.
- Test: verify non-answerable decisions cannot carry sources.
- Test: add fake generator contract tests.
- Validation: contract does not retrieve, rank, decide answerability, call
  embeddings, access the database, or store questions.
- Final track/doc: `docs/answer-generation.md`.

### Sprint 4.2: Grounded Synthesis Implementation

Items:

- Implementation: add `GroundedAnswerGenerator`.
- Implementation: build a system prompt that forbids unsupported claims,
  speculation, private data, and external knowledge.
- Implementation: include only `AnswerPolicyDecision.approved_context` in the
  prompt.
- Implementation: exclude retrieval scores and internal diagnostics from the
  prompt.
- Implementation: call `ChatProvider.chat()` only for `answerable` decisions.
- Implementation: never call `EmbeddingProvider.embed()`.
- Implementation: return deterministic fallback text for `not_answerable`.
- Implementation: return deterministic clarification text for
  `needs_clarification`.
- Implementation: append deterministic English or Italian source notes for
  answerable responses.
- Implementation: return structured source references deduplicated from
  approved context.
- Test: fake provider receives exactly one chat request for answerable
  decisions.
- Test: fake provider is not called for refusal or clarification responses.
- Test: prompt contains approved context and excludes unapproved context.
- Test: prompt excludes score metadata.
- Test: answer text includes deterministic English and Italian source notes.
- Test: structured sources match approved context.
- Validation: generated answer body is model-produced, but evidence identity is
  code-produced.
- Final track/doc: update `docs/answer-generation.md` with prompt and fallback
  contract.

### Sprint 4.3: Milestone 4 Acceptance and Handoff

Items:

- Test: add an integration-style unit test using fake approved context for
  "Where did Niccolò work?".
- Test: verify answer generation works without retrieval, database, API, or
  question collection.
- Validation: answer generator output is suitable for later `POST /chat`
  response composition.
- Validation: no visitor-derived data is stored.
- Documentation: add M4 acceptance checklist and M5 handoff notes to
  `docs/answer-generation.md`.
- Checkpoint: M4 can produce recruiter-facing wording from an already approved
  policy decision.

---

## Milestone 5: Public Chat API

**Feature:** minimal backend API for the portfolio widget.

Milestone 5 adds the HTTP application boundary only. The API receives a visitor
question, orchestrates existing authorities, and returns a public-safe response.
It does not retrieve, decide answerability, generate wording, persist knowledge,
or collect visitor questions itself.

Milestone 5 does not add CORS middleware or a public edge. Public browser
exposure, route namespacing, TLS, and origin controls belong to Milestone 7.

### Sprint 5.1: API Plan And Contract

Items:

- Documentation: expand Milestone 5 into concrete sprints.
- Documentation: define API boundaries against retrieval, policy, answer
  generation, storage, and question collection.
- Documentation: define `GET /health`.
- Documentation: define `POST /chat`.
- Documentation: define public request fields:
  - `question`
  - `language`
- Documentation: define public response fields:
  - `status`
  - `answer`
  - `sources`
- Documentation: define public source fields:
  - `title`
  - optional `locator`
- Documentation: define that source URIs, retrieval scores, prompts, stack
  traces, provider errors, and database details never reach the frontend.
- Validation: confirm M5 does not introduce visitor question persistence.
- Final track/doc: `docs/api.md`.

### Sprint 5.2: API Schemas And Application Boundary

Items:

- Chore: add FastAPI dependency.
- Implementation: add API package.
- Implementation: define typed request and response schemas.
- Implementation: require explicit language: `en` or `it`.
- Implementation: reject blank questions.
- Implementation: reject oversized questions.
- Implementation: reject oversized request bodies.
- Implementation: add app factory with injected chat service.
- Test: validate accepted English and Italian requests.
- Test: reject blank questions, unsupported language, and oversized input.
- Test: verify source URI is not part of the public response model.

### Sprint 5.3: Chat Orchestration Service

Items:

- Implementation: add a chat service that orchestrates only:
  - `Retriever.retrieve()`
  - `AnswerPolicy.decide()`
  - `AnswerGenerator.generate()`
  - public response mapping
- Implementation: pass configured retrieval limits to retrieval and policy.
- Implementation: map answer sources to public title and locator only.
- Implementation: keep retrieval scores and diagnostics internal.
- Implementation: sanitize authority failures into public-safe API errors.
- Test: answerable flow calls retriever, policy, and generator.
- Test: not-answerable flow returns the generator fallback.
- Test: clarification flow returns the generator clarification response.
- Test: internal errors do not leak raw messages.

### Sprint 5.4: HTTP Endpoints

Items:

- Implementation: add `POST /chat`.
- Implementation: add `GET /health`.
- Implementation: wire endpoint to the injected chat service.
- Implementation: return stable JSON errors for validation and service failures.
- Implementation: do not add CORS in M5.
- Test: `GET /health` returns healthy status.
- Test: `POST /chat` returns answerable response.
- Test: `POST /chat` returns not-answerable response.
- Test: invalid input returns stable validation errors.
- Test: internal exceptions return sanitized errors only.

### Sprint 5.5: Real Runtime Composition

Items:

- Implementation: compose configured provider, PostgreSQL retriever,
  deterministic policy, and grounded answer generator.
- Config: use only exact existing environment names.
- Implementation: expose an ASGI `app` object.
- Validation: no config aliases or hidden fallbacks.
- Test: composition can be tested with fakes without real database or network.
- Documentation: document API examples and proxy deployment assumption.
- Checkpoint: frontend can call one proxied endpoint.
- Final track/doc: `docs/api.md`.

---

## Milestone 6: Runtime Infrastructure

**Feature:** reproducible container runtime for local development and a
single-server deployment base.

**Branch:** `feature/runtime-infrastructure`.

This milestone starts after the public API exists, so the backend service,
health endpoint, database, and optional local LLM services can be validated as a
real runtime stack. It must not introduce Kubernetes, Swarm, reverse proxy,
TLS, automatic model downloads, committed secrets, or a second database unless a
later milestone proves a real need.

Runtime defaults:

- PostgreSQL runtime uses `pgvector/pgvector:0.8.2-pg17`.
- Runtime container images are pinned by digest.
- Python runtime dependencies are constrained by `requirements.lock`.
- API port binding defaults to `127.0.0.1` for server-local operation. Public
  exposure belongs to a later reverse proxy boundary.
- Database migrations run explicitly through the PostgreSQL container with
  `psql`; the API container does not run migrations on startup.
- Optional local LLM services are CPU-only profiles in this milestone.

### Sprint 6.1: Backend Container

Items:

- Implementation: add minimal ASGI runtime dependency.
- Implementation: add backend `Dockerfile`.
- Implementation: add `.dockerignore`.
- Config: use only explicit existing environment names without aliases.
- Validation: backend image builds from a clean checkout.
- Validation: no secrets or local model files are baked into the image.
- Checkpoint: backend container can start and expose `GET /health`.
- Final track/doc: container notes in `docs/runtime.md`.

### Sprint 6.2: Compose Core Stack

Items:

- Implementation: add Compose config for `api` and PostgreSQL with `pgvector`.
- Implementation: add a named volume for PostgreSQL data.
- Implementation: add private Compose network and service health checks.
- Implementation: make the API service depend on database health.
- Config: add Compose environment example with placeholder values only.
- Validation: default API port binding is localhost-only.
- Validation: `docker compose config` passes.
- Validation: default stack starts from clean volumes.
- Validation: migration, ingestion, and `GET /health` can run through Compose.
- Checkpoint: a developer can run the service locally with one documented
  Compose command.
- Final track/doc: `docs/runtime.md`.

### Sprint 6.3: Optional Local LLM Profiles

Items:

- Implementation: add optional `ollama` profile using the official
  `ollama/ollama` image and a named model volume.
- Implementation: add optional `llama-cpp` profile using the official
  `ghcr.io/ggml-org/llama.cpp:server` image and a mounted model directory.
- Config: document internal service URLs for chat and embedding base URLs.
- Config: document that model download and placement are manual and explicit.
- Validation: enabling one local LLM profile does not require application code
  changes.
- Validation: default Compose stack does not start heavyweight LLM services.
- Checkpoint: API can be configured against either local profile or an external
  OpenAI-compatible endpoint.
- Final track/doc: LLM runtime examples in `docs/runtime.md`.

### Sprint 6.4: Runtime Documentation And Guards

Items:

- Test: add static runtime configuration guards.
- Documentation: document image build and Compose operation.
- Documentation: document explicit DB migration, ingestion, indexing, and
  health-check commands.
- Documentation: document optional LLM profiles and manual model setup.
- Validation: full test suite passes.
- Final track/doc: `docs/runtime.md`.

### Sprint 6.5: Runtime Remediation

Items:

- Refactor: split chat and embedding provider authorities in runtime
  composition.
- Config: replace ambiguous single-provider settings with capability-specific
  chat and embedding settings.
- Config: replace interpolated database connection URLs with discrete
  PostgreSQL connection fields.
- Implementation: add separate llama.cpp chat and embedding services.
- Implementation: add `/ready` for database, schema, and configured embedding
  readiness.
- Implementation: add an explicit `runtime smoke` command for database, chat
  provider, and embedding provider reachability before public exposure.
- Implementation: pin runtime images by digest.
- Implementation: add a runtime dependency lock consumed by the Docker build.
- Test: parse Compose structurally and verify local model profiles.
- Test: cover readiness and smoke command behavior with fakes.
- Documentation: update runtime, provider, API, retrieval, ingestion, and
  architecture docs.
- Validation: `docker compose config`, profile rendering, Docker build, and the
  full test suite pass.

### Sprint 6.6: Runtime Script Contract, API, and Database

Items:

- Implementation: add shared runtime script helpers under `scripts/runtime`.
- Implementation: add API scripts for build, setup, start, stop, down, and
  cleanup.
- Implementation: add PostgreSQL scripts for setup, start, stop, down, cleanup,
  and migration.
- Implementation: keep `postgres-migrate.sh` as the only migration script.
- Implementation: make service `down` stop and remove only the targeted service.
- Implementation: require `--destroy-data` before deleting the PostgreSQL data
  volume.
- Validation: API setup does not run migrations implicitly.
- Validation: scripts use `.env` by default and allow `ENV_FILE` override.

### Sprint 6.7: Local Model Runtime Scripts

Items:

- Implementation: add Ollama chat scripts for setup, start, stop, down, and
  cleanup.
- Implementation: add Ollama embedding scripts for setup, start, stop, down,
  and cleanup.
- Implementation: pull the configured Ollama model explicitly during setup when
  the matching backend is `ollama`.
- Implementation: require `--destroy-models` before deleting the Ollama model
  volume.
- Implementation: add llama.cpp chat scripts for setup, start, stop, down, and
  cleanup.
- Implementation: add llama.cpp embedding scripts for setup, start, stop, down,
  and cleanup.
- Implementation: validate configured llama.cpp model files before startup.
- Validation: llama.cpp cleanup never deletes bind-mounted model files.

### Sprint 6.8: Runtime Script Guards and Documentation

Items:

- Test: verify every runtime script exists, is executable, and passes shell
  syntax validation.
- Test: verify scripts use expected Compose services and profiles.
- Test: verify no script uses deprecated configuration names.
- Test: verify cleanup scripts avoid broad Compose volume removal and recursive
  filesystem deletion.
- Test: verify only `postgres-migrate.sh` runs migrations.
- Documentation: document the full runtime script matrix.
- Documentation: document setup order for external, Ollama, llama.cpp, and
  mixed provider deployments.
- Validation: full test suite passes.

### Sprint 6.9: Runtime Script Readiness Remediation

Items:

- Implementation: add health checks for Ollama and separate llama.cpp chat and
  embedding services.
- Implementation: make setup and start scripts wait for targeted service
  readiness.
- Implementation: make PostgreSQL migration fail on SQL errors.
- Test: guard readiness waits, strict migration failure, and local model health
  checks.
- Documentation: make runtime scripts the primary documented setup path and
  document shared Ollama service behavior.
- Validation: Compose renders supported profiles and the full test suite passes.

---

## Milestone 7: Public Deployment Boundary

**Feature:** make the RAG service deployable on `vps.madnick.ovh` as a public
HTTPS API consumed by the separate `pigreco.xyz` portfolio project.

Boundary:

- This repository owns the RAG service, public API contract, reverse proxy
  runtime, TLS automation, deployment scripts, and production smoke validation
  for `vps.madnick.ovh`.
- This repository does not implement the portfolio webpage, chat widget,
  frontend styling, or deployment of the separate `pigreco.xyz` project.
- Public browser calls originate only from `https://pigreco.xyz` and
  `https://www.pigreco.xyz`.
- Public traffic enters through an Nginx container on `vps.madnick.ovh`.
- PostgreSQL, Ollama, llama.cpp, and the Python API port are not directly
  exposed to the public internet.
- CORS is enforced at the Nginx edge.
- Public assistant logs are redacted and must not persist IP addresses, user
  agents, cookies, request bodies, or raw questions.
- TLS uses free Let's Encrypt certificates managed by Certbot containers.

### Sprint 7.1: Public Deployment Plan

Items:

- Documentation: replace the old Milestone 7 question-collection slot with the
  public deployment boundary.
- Documentation: move anonymous question collection to a later milestone.
- Documentation: remove in-repository portfolio widget implementation from the
  roadmap and define the portfolio as an external API consumer.
- Documentation: define the public API host `https://vps.madnick.ovh`.
- Documentation: define public routes under `/api/assistant`.
- Documentation: define the allowed portfolio origins.
- Documentation: define Nginx, Certbot, TLS, logging, rate-limit, and deployment
  responsibilities.
- Validation: documentation does not instruct operators to expose PostgreSQL,
  model services, or the Python API port directly.
- Validation: documentation is authoritative and does not add code, scripts, or
  runtime configuration in this sprint.
- Final track/doc: `docs/public-deployment.md`.

### Sprint 7.2: Public Edge Runtime Configuration

Items:

- Config: add an Nginx public edge container.
- Config: expose HTTP through the Nginx edge with localhost-safe defaults for
  local validation.
- Config: document that production may bind the HTTP edge to port `80`, while
  HTTPS port `443` is deferred to Sprint 7.3 when certificates exist.
- Config: route `POST /api/assistant/chat` to API container `POST /chat`.
- Config: route `GET /api/assistant/health` to API container `GET /health`.
- Config: route `GET /api/assistant/ready` to API container `GET /ready`.
- Config: allow CORS only for `https://pigreco.xyz` and
  `https://www.pigreco.xyz`.
- Config: add redacted assistant logs that omit IP address, user agent, cookies,
  request body, and raw question text.
- Config: add request body size limit and explicit proxy timeout settings.
- Config: add default edge rate limit of 20 requests per minute with burst 40,
  and document how to tighten or remove it.
- Test: structurally validate Compose and Nginx configuration.
- Test: verify public runtime exposes only intended ports.
- Documentation: document public edge runtime behavior.
- Final track/doc: `docs/public-deployment.md`.

### Sprint 7.3: Free TLS Automation

Items:

- Config: add Certbot container support for Let's Encrypt certificates.
- Config: mount certificate and ACME challenge volumes explicitly.
- Config: support initial HTTP certificate issue through `nginx` and HTTPS
  runtime through `nginx-tls` after the certificate exists.
- Config: require `PUBLIC_SERVER_NAME` and `LETSENCRYPT_EMAIL` from untracked
  `.env`.
- Script: add certificate setup command: `letsencrypt-setup.sh`.
- Script: add certificate renewal command: `letsencrypt-renew.sh`.
- Script: add Nginx reload flow after renewal.
- Documentation: define DNS prerequisites for `vps.madnick.ovh`.
- Documentation: document that Let's Encrypt certificates are free and no paid
  certificate is required.
- Test: guard required TLS environment variables, ACME challenge routing,
  public `443` ownership, and bounded certificate cleanup.
- Final track/doc: `docs/public-deployment.md`.

### Sprint 7.4: Public Deployment Script Suite

Items:

- Script: add public setup that prepares runtime by default and calls the
  existing Let's Encrypt setup command only with an explicit
  `--issue-certificate` flag.
- Script: add public build, start, stop, down, cleanup, deploy/update, and smoke
  commands.
- Script: add Nginx configuration validation.
- Script: add public migration wrapper that delegates to the single PostgreSQL
  migration authority.
- Script: support local HTTP and production HTTPS smoke targets through
  `PUBLIC_SMOKE_BASE_URL`.
- Script: ensure cleanup does not destroy DB data, model data, or certificates
  without explicit destructive flags.
- Documentation: document first deploy, update deploy, emergency stop, rollback,
  and cleanup procedures.
- Test: validate public deployment scripts and destructive-operation guards.
- Final track/doc: `docs/public-deployment.md`.

### Sprint 7.5: Public Smoke Validation

Items:

- Script: harden public HTTPS smoke validation beyond the Sprint 7.4 smoke
  script.
- Validation: check CORS preflight from `https://pigreco.xyz`.
- Validation: check CORS preflight from `https://www.pigreco.xyz`.
- Validation: reject unexpected browser origins.
- Validation: call public `/api/assistant/health`, `/api/assistant/ready`, and
  `/api/assistant/chat` through Nginx.
- Validation: confirm the API direct port is not part of public access when
  `PUBLIC_DIRECT_API_PROBE_URL` is explicitly provided.
- Test: validate public smoke behavior without real network calls.
- Documentation: document expected smoke output and troubleshooting.
- Final track/doc: `docs/public-deployment.md`.

---

## Milestone 8: Anonymous Question Collection

**Feature:** collect useful question signals without visitor tracking after the
public deployment boundary is stable.

### Sprint 8.1: Question Events

Items:

- Implementation: redact emails, phone numbers, names, and organizations before
  storage.
- Implementation: store only redacted question text as visitor-derived data.
- Implementation: do not store per-question language, answer status, source
  kinds, top scores, retrieval scores, or request metadata.
- Implementation: explicitly avoid IP address, user agent, cookies, session
  identity, email, phone, names, company names, photos, and raw transcripts.
- Test: add redaction and persistence tests.
- Validation: raw request metadata is not stored.
- Checkpoint: question review queue is useful without tracking visitors.
- Final track/doc: privacy note.

### Sprint 8.2: Review Loop

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

## Milestone 9: Release Validation

**Feature:** prove reliability before recruiters see it.

### Sprint 9.1: Evaluation Suite

Items:

- Documentation: define eval categories.
- Implementation: add eval runner.
- Test data: add employer, skills, projects, thesis, off-topic, and adversarial
  questions.
- Validation: no hallucinated employers, dates, degrees, or private claims.
- Checkpoint: minimum acceptance score is met before deploy.
- Final track/doc: release report.

### Sprint 9.2: Release Smoke

Items:

- Config: add production environment example.
- Validation: run health check, DB migration, ingestion, and chat smoke test
  using the runtime infrastructure from Milestone 6.
- Validation: confirm no debug traces, secrets, or private source material leak
  into recruiter-facing responses.
- Checkpoint: release candidate is reproducible from a clean state.
- Final track/doc: `docs/deployment.md`.
