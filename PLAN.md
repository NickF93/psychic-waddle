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

Milestones 5 and later are intentionally deferred until the core proves it can
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

### Sprint 7.6: Public Env Upgrade Remediation

Items:

- Config: require public edge bind and port variables explicitly instead of
  using hidden Compose defaults.
- Config: move local public edge defaults to `127.0.0.1:18080` and
  `127.0.0.1:18443` to avoid common local port conflicts.
- Script: make Nginx validation fail clearly when public edge variables are
  missing from `.env`.
- Test: validate missing public edge variables fail before deployment.
- Documentation: document the required M7 public block for older server `.env`
  files.
- Final track/doc: `docs/public-deployment.md`.

---

## Milestone 8: Anonymous Question Collection

**Feature:** collect useful raw unanswered-question signals without visitor
tracking after the public deployment boundary is stable.

### Sprint 8.1: Contract And Schema

Items:

- Documentation: update `AGENTS.md`, `docs/architecture.md`, `docs/api.md`, and
  this plan for raw unanswered-question collection.
- Documentation: document that frontend graphics and popup text live in
  `pigreco.xyz`, while this backend returns machine-readable notice codes.
- Dependency: add `rich` and `textual` as main runtime dependencies for local
  operator CLI/TUI review tools.
- Implementation: add `question_events` schema.
- Implementation: store `id`, `raw_question_text`, `review_state`,
  `review_category`, `review_note`, `created_at`, and `updated_at`.
- Implementation: allow review states `pending`, `reviewed`, and `ignored`.
- Implementation: allow review categories `missing_fact`, `alias`, `eval_case`,
  `unclear`, `off_topic`, `private_data`, `spam`, and `other`.
- Test: prove the schema does not include visitor identity, answer text, answer
  status, per-question language, source IDs, source kinds, retrieval scores, or
  request metadata.
- Validation: raw question text is the only runtime visitor-derived field.
- Final track/doc: privacy and schema contract.

### Sprint 8.2: Collector Authority

Items:

- Config: add explicit `QUESTION_COLLECTION_ENABLED`.
- Implementation: define `QuestionCollector` authority.
- Implementation: persist only the raw question text received from the chat
  service.
- Implementation: disabled collection is explicit and writes nothing.
- Implementation: sanitize collector failures so the chat response still
  returns normally.
- Test: enabled collection stores a pending question event.
- Test: disabled collection stores nothing.
- Test: collector failures do not leak database details.
- Validation: collector never stores answer, retrieval, provider, request,
  browser, session, or network metadata.
- Final track/doc: collector contract.

### Sprint 8.3: API Integration

Items:

- Implementation: inject `QuestionCollector` into runtime API composition.
- Implementation: trigger collection only when the final chat status is
  `not_answerable`.
- Implementation: add public response notices.
- Implementation: return `question_recorded` notice only after successful
  collection.
- Test: answerable and clarification responses are not collected.
- Test: not-answerable responses are collected when enabled.
- Test: answer text, status, and sources remain unchanged by collection.
- Test: collection failure returns the normal chat response without a notice.
- Final track/doc: API notice contract.

### Sprint 8.4: Review Tools

Items:

- Implementation: add CLI commands to list, show, mark, delete, and export
  question records.
- Implementation: add a local Textual terminal review mode.
- Implementation: use Rich for readable terminal table output.
- Implementation: allow reviewed questions to be categorized and annotated with
  admin notes.
- Documentation: define how reviewed questions become new facts, aliases, or eval
  cases.
- Test: add CLI review command tests.
- Test: add terminal review behavior tests where practical without requiring an
  interactive terminal.
- Validation: visitor questions never auto-promote into the knowledge base.
- Checkpoint: improvement loop exists without contaminating reviewed truth.
- Final track/doc: review workflow.

### Sprint 8.5: Documentation And Validation

Items:

- Documentation: document backend/frontend notice integration.
- Documentation: document manual deletion as the retention policy.
- Documentation: document operator commands for review, export, and cleanup.
- Validation: run the full test suite.
- Validation: run migration validation.
- Checkpoint: raw unanswered-question collection is operational without
  changing the public answer flow.
- Final track/doc: `docs/question-review.md`.

---

## Milestone 9: Answerability Remediation

**Feature:** structurally remediate recruiter-question reliability before
release validation.

Milestone 9 fixes the known weakness where a source-backed question such as
"Where did Niccolo work?" can fail even though tracked knowledge contains the
answer. The remediation must improve retrieval recall, intent completeness,
embedding freshness, public smoke validation, and stale authoritative
documentation without making unsupported questions answerable.

The milestone must preserve the core architecture: retrieval gathers plausible
reviewed context, answer policy decides answerability deterministically, and
the LLM only phrases already-approved answers.

### Sprint 9.1: Authoritative Remediation Plan

This sprint is documentation-only. It must not change runtime code, database
schema, scripts, tests, or tracked knowledge.

Items:

- Documentation: update this plan so Milestone 9 owns answerability
  remediation and the former release-validation milestone moves to Milestone
  10.
- Documentation: reconcile `AGENTS.md`, `docs/architecture.md`, retrieval,
  ingestion, answer policy, answer generation, and public deployment docs with
  the M8 raw unanswered-question contract and the M9 remediation target.
- Documentation: state that answerability is decided before generation.
- Documentation: state that retrieval returns plausible candidate context while
  policy decides whether evidence is intent-complete.
- Documentation: state that changed chunk text must invalidate or refresh
  embeddings for the configured backend and model.
- Documentation: define the planned bounded `QuestionIntentProfile` authority.
- Documentation: define planned recruiter intent profiles for workplaces,
  current role, skills, education, publications, projects, and public contacts.
- Documentation: define future retrieval remediation with vector search,
  PostgreSQL full-text search, intent-expanded lexical retrieval, and rank
  fusion.
- Documentation: define future policy remediation that forbids category-only
  answerability approval.
- Documentation: define future public smoke assertions for answerable and
  unsupported questions.
- Validation: confirm the sprint changes only documentation.
- Checkpoint: the full M9 implementation plan is decision-complete before any
  software remediation starts.
- Final track/doc: this plan and affected authority docs.

### Sprint 9.2: Shared Question Intent Profiles

Items:

- Implementation: add a bounded question-intent authority that contains no
  provider, database, API, generation, or storage logic.
- Implementation: define profiles for workplace/work history, current role,
  skills, education, publications, projects/repositories, and public contact
  links.
- Implementation: each profile defines trigger terms, accepted knowledge
  categories, lexical expansion terms, and required evidence terms.
- Implementation: make retrieval and policy consume the same profile
  definitions instead of duplicating fragile keyword maps.
- Test: cover positive and negative profile detection for natural recruiter
  phrasings.
- Validation: unsupported personal, private, speculative, and off-topic
  questions do not match an answerable recruiter intent.
- Checkpoint: intent definitions are shared, bounded, deterministic, and
  inspectable.
- Final track/doc: update answer policy and retrieval docs.

### Sprint 9.3: Hybrid Retrieval Candidate Generation And Fusion

Items:

- Implementation: keep vector retrieval through the configured embedding
  backend and model.
- Implementation: keep PostgreSQL full-text retrieval with
  `websearch_to_tsquery('english', question)`.
- Implementation: add intent-expanded lexical retrieval for detected recruiter
  intents.
- Implementation: merge vector, keyword, and intent-expanded candidates by
  chunk identity.
- Implementation: replace direct raw-score comparison between vector scores and
  PostgreSQL text-rank scores with rank fusion, preferably reciprocal rank
  fusion.
- Implementation: keep raw vector and keyword scores as diagnostics only.
- Implementation: avoid treating fused rank as visitor analytics or persisted
  request metadata.
- Test: prove exact employer/workplace chunks can be retrieved for natural
  questions such as "Where did Niccolo work?".
- Test: prove vector-only, keyword-only, and overlap candidates are ordered
  deterministically.
- Validation: retrieval still does not decide answerability, generate wording,
  persist visitor data, or mutate knowledge.
- Checkpoint: candidate generation favors recall while policy remains the
  answerability gate.
- Final track/doc: update `docs/retrieval.md`.

### Sprint 9.4: Embedding Freshness

Items:

- Implementation: add a stable content hash for the chunk text associated with
  each stored embedding.
- Implementation: define an embedding as stale when the stored content hash
  differs from the current public chunk text for the same backend and model.
- Implementation: make `knowledge index-embeddings` index missing and stale
  embeddings.
- Implementation: preserve separate embeddings for different backend/model
  pairs.
- Implementation: make `public-load-knowledge.sh` and `public-upgrade.sh`
  refresh changed knowledge without database destruction.
- Test: changing a public fact changes the generated chunk and causes
  re-embedding for the configured backend and model.
- Test: unchanged chunks are not re-embedded.
- Test: embeddings for other backend/model pairs are not deleted or rewritten.
- Validation: `indexed 0 chunk embeddings` is correct only when no public chunk
  text changed for the configured backend and model.
- Checkpoint: tracked knowledge can be safely updated on the VPS without
  destroying PostgreSQL data.
- Final track/doc: update ingestion and knowledge maintenance docs.

### Sprint 9.5: Policy Intent Completeness

Items:

- Implementation: require intent-complete evidence before returning
  `answerable`.
- Implementation: reject category-only matches as insufficient.
- Implementation: workplace questions require employer, workplace, company,
  role, or work-history evidence.
- Implementation: current-role questions require current employer or current
  role evidence.
- Implementation: skills questions require skills, technologies, tooling,
  specialization, or domain evidence.
- Implementation: education, publication, project, and contact questions use
  their corresponding intent evidence terms.
- Test: "Where did Niccolo work?" is answerable only with workplace evidence.
- Test: "What is Niccolo's current role?" is answerable only with current-role
  evidence.
- Test: "What are Niccolo's main machine learning skills?" is answerable only
  with skills evidence.
- Test: "What is Niccolo's favorite pizza topping?" remains `not_answerable`.
- Validation: strong unrelated retrieval cannot make an unsupported question
  answerable.
- Checkpoint: answerability is deterministic and intent-complete.
- Final track/doc: update `docs/answer-policy.md`.

### Sprint 9.6: Answer Generation Consistency

Items:

- Implementation: keep the LLM as a phrasing-only authority.
- Implementation: require answerable decisions to provide sufficient approved
  context before generation.
- Implementation: keep a deterministic guard that demotes generated
  insufficiency output to `not_answerable` with no sources.
- Test: answerable public responses never contain "not enough context",
  "insufficient context", or equivalent insufficiency wording.
- Test: provider sentinel or clear insufficiency wording returns the standard
  not-answerable fallback and no sources.
- Validation: generation does not retrieve, search, decide answerability, or
  persist visitor data.
- Checkpoint: public status, answer text, and sources remain consistent.
- Final track/doc: update `docs/answer-generation.md` if needed.

### Sprint 9.7: Knowledge Refinement

Items:

- Documentation: keep `knowledge/profile.json` as the first complete tracked
  reviewed profile.
- Review: audit current tracked profile facts against
  `../CV/CV/CVNiccoloFerrari_short.tex` and the shared M9 intent profiles.
- Implementation: add or refine only source-backed aggregate facts that express
  real recruiter intents.
- Implementation: keep workplace/current-role/skills/education/publications/
  projects/contact aggregates when grounded in reviewed source material.
- Implementation: reject question-specific hacks that exist only to satisfy one
  phrasing.
- Test: tracked knowledge validates with all aggregate facts.
- Test: tracked knowledge privacy checks continue to reject private contact
  details, visitor questions, and unreviewed assumptions.
- Validation: visitor question records never auto-promote into tracked facts.
- Checkpoint: broad recruiter questions have source-backed broad chunks.
- Final track/doc: update knowledge maintenance docs.

### Sprint 9.8: Knowledge Content Double Audit

Items:

- Review: perform a second pass over the final tracked profile after Sprint 9.7
  changes.
- Review: map every broad aggregate group to a CV section or source locator that
  supports it.
- Review: confirm there are no hallucinated employers, titles, dates, degrees,
  papers, repositories, contact channels, private fields, visitor questions, or
  recruiter-derived raw text.
- Test: every required broad recruiter intent has at least one aggregate fact.
- Test: each aggregate fact uses the category accepted by the matching intent
  profile and satisfies its required evidence terms.
- Validation: run tracked knowledge validation and focused tracked-knowledge
  tests after the second pass.
- Checkpoint: the committed profile is source-backed, privacy-safe, and not
  tuned to one question wording.
- Final track/doc: document aggregate review rules if the maintenance workflow
  needs clarification.

### Sprint 9.9: Runtime Acceptance And Public Smoke

Items:

- Implementation: strengthen public smoke validation so it can assert a known
  answerable workplace question.
- Implementation: assert the workplace answer contains expected source-backed
  evidence such as NAIS and Bonfiglioli when using the tracked profile.
- Implementation: assert an unsupported personal question returns
  `not_answerable`.
- Implementation: keep question-collection notice validation explicitly opt-in
  because it intentionally records an unanswered question.
- Test: runtime script tests cover the new smoke behavior without requiring
  real provider calls where possible.
- Validation: `public-upgrade.sh` preserves data and still refreshes changed
  knowledge and embeddings.
- Validation: no public smoke response leaks source URIs, retrieval scores,
  prompts, stack traces, secrets, or private data.
- Checkpoint: the VPS upgrade path detects the original workplace regression.
- Final track/doc: update public deployment and runtime docs.

### Sprint 9.10: Full Remediation Audit And Closure

Items:

- Review: audit retrieval, policy, generation, ingestion, runtime scripts,
  tests, and docs for bugs, regressions, stale contracts, exposed secrets,
  weak abstractions, shortcuts, and architectural drift.
- Remediation: fix only root causes; do not add legacy shims, compatibility
  aliases, hidden fallbacks, or workaround behavior.
- Validation: run the full test suite.
- Validation: run tracked knowledge validation.
- Validation: run public runtime smoke where provider services are available.
- Validation: verify expected manual questions:
  - "Where did Niccolo work?" returns `answerable`.
  - "What is Niccolo's current role?" returns `answerable`.
  - "What are Niccolo's main machine learning skills?" returns `answerable`.
  - "What publications does Niccolo have?" returns `answerable`.
  - "What is Niccolo's favorite pizza topping?" returns `not_answerable`.
- Checkpoint: M9 is ready for explicit review and merge approval.
- Final track/doc: `docs/m9-remediation-closure.md`.

### Sprint 9.11: Runtime Retrieval Failure Reopen

Items:

- Documentation: mark the previous M9 closure report as superseded by the live
  isolated Docker failure.
- Documentation: record that the failure is retrieval candidate generation, not
  `llama3.2`, policy, answer generation, tracked knowledge, or embedding
  freshness.
- Documentation: record the direct root cause: intent-expanded PostgreSQL
  search currently builds a space-joined string that
  `websearch_to_tsquery('english', ...)` interprets as an over-strict AND
  query.
- Documentation: record the architectural root cause: retrieval currently
  applies `RETRIEVAL_MIN_SCORE` before policy sees candidates, contradicting
  the architecture contract that the threshold belongs to answer policy.
- Checkpoint: M9 is open until runtime proof passes in the isolated project
  stack.
- Final track/doc: update this plan and the M9 closure report.

### Sprint 9.12: Structured Intent Evidence Retrieval

Items:

- Implementation: replace concatenated intent-expanded query text with a
  controlled OR query built only from profile-owned evidence terms.
- Implementation: do not include raw visitor question text in intent-expanded
  retrieval; vector and keyword retrieval already search the question.
- Implementation: remove broad workplace retrieval expansion terms such as
  standalone `work` and `worked`; keep precise evidence terms such as
  `professional workplaces`, `work history`, employer, workplace, company, and
  employment.
- Test: assert intent search parameters use OR semantics and no longer contain
  the raw question.
- Test: assert unsupported questions do not run intent-expanded retrieval.
- Checkpoint: natural workplace questions can retrieve source-backed workplace
  aggregate chunks without increasing `RETRIEVAL_TOP_K`.
- Final track/doc: update `docs/retrieval.md`.

### Sprint 9.13: Policy-Owned Score Threshold

Items:

- Implementation: remove `RETRIEVAL_MIN_SCORE` from the retriever constructor,
  state, ranking function, and retrieval result filtering.
- Implementation: keep `RETRIEVAL_MIN_SCORE` in runtime configuration because
  `PublicChatService` passes it to `AnswerPolicyRequest`.
- Implementation: retrieval returns the top ranked candidate contexts; policy
  alone decides which candidates meet the score threshold.
- Test: prove retrieval does not discard candidates below policy threshold.
- Checkpoint: retrieval is candidate generation only, and answerability remains
  policy-owned.
- Final track/doc: update retrieval and API composition tests.

### Sprint 9.14: Real PostgreSQL Retrieval Regression Coverage

Items:

- Test: add real PostgreSQL coverage for the workplace failure shape when
  `TEST_DATABASE_URL` is available.
- Test: insert tracked-profile-style workplace aggregate chunks plus noisy
  experience chunks, then prove `Where did Niccolo work?` retrieves workplace
  evidence with `top_k=4`.
- Test: keep fake-cursor tests for query shape and RRF behavior, but do not use
  them as the only authority for PostgreSQL full-text semantics.
- Checkpoint: real SQL semantics cover the AND/OR regression.
- Final track/doc: update retrieval tests.

### Sprint 9.15: Isolated Runtime Proof And Server Commands

Items:

- Validation: clean only the project debug stack using
  `COMPOSE_PROJECT_NAME=psychic-waddle-debug`.
- Validation: rebuild, reset, migrate, load tracked knowledge, index
  embeddings, and run public smoke from `/tmp/psychic-waddle-debug.env`.
- Validation: manually prove workplace, current role, machine-learning skills,
  and publications questions are `answerable`.
- Validation: manually prove pizza topping remains `not_answerable`.
- Validation: clean the isolated project debug stack after proof.
- Documentation: update final server commands after the runtime proof.
- Checkpoint: M9 is ready for explicit PR review only after live project smoke
  passes.
- Final track/doc: update M9 closure documentation.

Acceptance:

- Answerability depends on intent-complete reviewed evidence, not category-only
  retrieval.
- Retrieval no longer compares vector and keyword raw scores as if they were the
  same confidence scale.
- Changed tracked knowledge refreshes stale embeddings without database
  destruction.
- Public smoke catches the original workplace failure mode.
- Unsupported personal or off-topic questions remain safely not answerable.
- Authoritative docs agree with implemented M8 privacy behavior and implemented M9
  remediation architecture.

---

## Milestone 10: Release Validation

**Feature:** prove reliability before recruiters see it.

### Sprint 10.1: Evaluation Suite

Items:

- Documentation: define eval categories.
- Implementation: add eval runner.
- Test data: add employer, skills, projects, thesis, off-topic, and adversarial
  questions.
- Validation: no hallucinated employers, dates, degrees, or private claims.
- Checkpoint: minimum acceptance score is met before deploy.
- Final track/doc: release report.

### Sprint 10.2: Release Smoke

Items:

- Config: add production environment example.
- Validation: run health check, DB migration, ingestion, and chat smoke test
  using the runtime infrastructure from Milestone 6.
- Validation: confirm no debug traces, secrets, or private source material leak
  into recruiter-facing responses.
- Checkpoint: release candidate is reproducible from a clean state.
- Final track/doc: `docs/deployment.md`.

---

## Milestone 11: Intent Authority Data-Driven Remediation

**Feature:** move reviewed recruiter intent vocabulary out of hardcoded Python
lists and prepare the intent authority for later semantic routing without
weakening deterministic answerability.

Milestone 11 is post-v0.1.0 remediation work. Milestone 10 remains the closed
release-validation milestone for the MVP release. M11 must preserve current
answerability behavior during the initial catalog migration, then deliberately
remove remaining intent-specific branches through reviewed positive catalog
semantics.

The target is not to make every Python literal configurable. Reviewed recruiter
domain vocabulary belongs in data; matching algorithms, rank-fusion behavior,
schema-bound category enums, and architectural invariants remain code
authorities.

### Preflight 11.0: Temporary Migration Oracle

Items:

- Validation: generate current intent behavior into `/tmp`.
- Validation: derive probes from current vocabulary where possible.
- Validation: do not commit the oracle or generated fixtures.
- Validation: use the oracle only to verify the first migration.
- Checkpoint: the catalog migration has a one-time behavior witness without
  fossilizing disliked implementation behavior in the public repository.

### Sprint 11.1: Data-Driven Lexical Catalog

Items:

- Implementation: add `load_intent_catalog(path) -> IntentCatalog`.
- Implementation: keep the loader as an explicit factory with no import-time
  file I/O.
- Implementation: do not introduce a JSON-loaded module global.
- Implementation: move current recruiter vocabulary to reviewed JSON while
  preserving behavior.
- Config: add explicit runtime config wiring for the catalog path.
- Documentation: define the exact lexical catalog contract.
- Documentation: explicitly state that the current GitHub/contact
  disambiguation branch is intentionally retained as frozen behavior and will
  be removed in Sprint 11.3.
- Test: cover the catalog loader, configured runtime wiring, and preserved
  lexical behavior.
- Checkpoint: domain vocabulary is reviewed data, while the frozen matcher
  behavior is still verifiably unchanged.

### Sprint 11.2: Intent Authority Refactor

Items:

- Implementation: move catalog loading into the composition root.
- Implementation: inject the intent authority into retrieval and policy.
- Implementation: remove module-level hardcoded profile constants.
- Implementation: avoid mutable global registries.
- Implementation: avoid compatibility shims, legacy exports, hidden fallbacks,
  or deprecated interfaces.
- Test: prove retrieval and policy use the injected intent authority.
- Checkpoint: intent detection is a single bounded authority threaded through
  the application instead of import-time global state.

### Sprint 11.3: Positive Phrase Trigger Semantics

Items:

- Implementation: deliberately changed trigger matching from simple word groups
  to positive phrase/group semantics where needed.
- Implementation: removed the GitHub/contact special-case branch.
- Implementation: modeled ambiguity only through reviewed positive catalog
  groups.
- Test: GitHub profile questions resolve to the contact intent.
- Test: GitHub repository and source-code questions resolve to the projects
  intent.
- Test: bare ambiguous GitHub wording is `not_answerable` unless explicitly
  defined in reviewed catalog data.
- Documentation: updated intent semantics to describe positive groups and the
  ambiguity decision.
- Checkpoint: intent routing contains no hardcoded contact/project exception.

### Sprint 11.4: Catalog Contract And Coverage

Items:

- Implementation: reject unknown catalog fields.
- Implementation: fail fast for missing or invalid catalog paths.
- Test: strict schema validation rejects malformed catalog data.
- Test: representative English and Italian recruiter phrases map to the
  expected supported intents.
- Test: unsupported, private, speculative, and off-topic questions remain
  `not_answerable`.
- Documentation: update architecture, retrieval, answer-policy, runtime, and
  API docs with the final lexical catalog contract.
- Checkpoint: the lexical catalog is explicit, validated, and covered without
  hidden fallback behavior.

### Sprint 11.5: Semantic Intent Preparation

Items:

- Data: add reviewed example questions per intent.
- Test data: add a labeled intent-evaluation fixture.
- Documentation: define the future semantic resolver invariant:
  - zero `if intent == ...` code branches;
  - per-intent thresholds live in reviewed data;
  - semantic matches start as candidate intents unless calibrated.
- Validation: do not add a runtime semantic matcher in this sprint.
- Checkpoint: semantic intent work has reviewed data and calibration fixtures
  before it can affect answerability.

### Sprint 11.6: Semantic Intent Matcher And Resolver

Items:

- Implementation: embed reviewed example questions, not bare trigger words.
- Implementation: reuse the already-computed question embedding where
  available.
- Implementation: resolve required and candidate intents without intent-specific
  code branches.
- Implementation: allow semantic intents into the hard policy evidence gate
  only after threshold calibration against the Sprint 11.5 eval set and a
  defined precision bar.
- Implementation: otherwise keep semantic intents candidate-only so they may
  help retrieval without forcing `not_answerable`.
- Test: calibrated semantic matches improve supported recruiter paraphrase
  coverage without reducing unsupported/private refusal behavior.
- Documentation: update the intent authority and policy docs with required vs
  candidate semantics.
- Checkpoint: semantic routing improves recall while preserving deterministic
  policy ownership of answerability.

Acceptance:

- Reviewed recruiter vocabulary is data/config-driven.
- Intent matching has no import-time catalog I/O, mutable global registry,
  compatibility shim, hidden fallback, or intent-specific exception branch.
- Retrieval and policy consume one injected intent authority.
- Positive lexical semantics cover the contact/project ambiguity without
  hardcoded suppression logic.
- Semantic intent matching, when implemented, cannot blindly turn fuzzy matches
  into hard policy requirements.
- Unsupported, private, speculative, and off-topic questions remain refused.
