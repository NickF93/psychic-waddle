# Milestone 9 Follow-Up Review

Date: 2026-06-02

Branch: `feature/m9-remediation-plan`

## Current State

A read-only check confirmed the current branch is
`feature/m9-remediation-plan` and the worktree is clean.

The full test suite was not rerun during this review because the review request
was explicitly read-only and test execution may write local cache files. The
reported `360 passed` result is consistent with prior validation, but this
review did not independently re-execute it.

## Consolidated Point-By-Point Findings

### 1. Policy Category-Only Bypass

Severity: high.

Verdict: agree, real issue.

Confirmed in `src/portfolio_rag_assistant/policy/contract.py:203`. Intent
evidence is checked only under `if question_intents:`. If no intent is detected
but a broad category is inferred, policy can approve by category and source
count only.

Reproduction:

- Question: `What is Niccolo's experience?`
- Detected intents: `()`
- Context: `experience: Niccolo Ferrari has public profile information.`
- Result: `answerable / sufficient_source_backed_context`

This contradicts `docs/architecture.md:152`, especially the rule that
`AnswerPolicy` must not approve an answer solely because retrieved context has a
matching broad category.

Recommended remediation:

- remove the category-only answerability branch;
- make matched `QuestionIntentProfile` definitions the only path to
  `answerable`;
- add a bounded professional overview profile for recruiter experience,
  background, and career questions;
- add regression tests for category-keyword questions that do not trigger a
  supported profile;
- keep answerability deterministic inside policy, not retrieval or generation.

Remediation status:

- completed in follow-up commits on `feature/m9-remediation-plan`;
- `AnswerPolicy` now returns `answerable` only after a supported profile
  matches and context satisfies that profile's evidence terms;
- generic broad questions without a supported profile return
  `needs_clarification`;
- unsupported non-broad questions remain `not_answerable`.

### 2. Over-Broad Insufficiency Heuristic

Severity: medium.

Verdict: remediated.

Originally confirmed in `src/portfolio_rag_assistant/answer/grounded.py:41`.
The previous phrase list caught valid text such as:

```text
The CV does not mention a PhD, but lists a Master at University of Ferrara.
```

and demotes it to `not_answerable`.

Follow-up remediation:

- `GroundedAnswerGenerator` now delegates provider wording checks to the
  answer-package insufficiency classifier;
- deterministic demotion remains for the explicit
  `INSUFFICIENT_APPROVED_CONTEXT` sentinel;
- whole-answer English and Italian insufficiency refusals still demote to
  `not_answerable`;
- valid contrastive answers with embedded negative clauses remain `answerable`
  when they include substantive verified facts;
- tests cover sentinel output, prose refusals, English contrastive answers, and
  Italian contrastive answers.

Unit tests prove the deterministic guard behavior. They do not claim that the
deployed `llama3.2` model always emits the sentinel; real-model validation
remains a separate runtime check.

### 3. Hardcoded TLS Redirect

Severity: medium.

Verdict: agree, real issue.

Confirmed in `deploy/nginx/nginx-tls.conf:50`:

```nginx
return 308 https://vps.madnick.ovh$uri;
```

This contradicts the existence of `PUBLIC_SERVER_NAME` as operator-controlled
deployment configuration. It also drops query strings because it redirects with
`$uri` rather than `$request_uri`.

The current runtime configuration tests explicitly lock in this behavior in
`tests/test_runtime_configuration.py:383`, so a clean remediation must update
both the Nginx TLS configuration and the corresponding tests.

Recommended remediation:

- remove the hardcoded host from `deploy/nginx/nginx-tls.conf`;
- preserve the original request path and query string;
- keep the public-edge privacy logging constraints unchanged;
- update runtime configuration tests so the desired redirect behavior is the
  tested behavior.

Remediation status: implemented by redirecting HTTP requests with the Nginx
request host and full request URI:

```nginx
return 308 https://$host$request_uri;
```

### 4. Automated `docker compose exec` Without `-T`

Severity: medium.

Verdict: agree, real issue.

Confirmed automated lifecycle scripts use `docker compose exec` without
disabling pseudo-TTY allocation:

- `scripts/runtime/letsencrypt-renew.sh`;
- `scripts/runtime/ollama-chat-setup.sh`;
- `scripts/runtime/ollama-embeddings-setup.sh`.

`scripts/runtime/postgres-migrate.sh` already uses `exec -T`, so using `-T` in
the remaining automated scripts is consistent with the existing runtime script
style.

Impact:

- these scripts can fail in non-interactive execution contexts such as cron,
  systemd timers, or CI/CD runners with `the input device is not a TTY`;
- this is especially relevant for certificate renewal automation.

Recommended remediation:

- change the automated `exec` calls to `exec -T`;
- update runtime script tests to assert the headless-safe command shape.

Remediation status:

- completed in follow-up commits on `feature/m9-remediation-plan`;
- automated lifecycle scripts now disable pseudo-TTY allocation for
  `docker compose exec` calls;
- runtime script tests assert the headless-safe command shape.

### 5. Provider Code Duplication And HTTPX Connection Pooling

Severity: medium.

Verdict: agree, not urgent.

Confirmed repeated provider transport and helper code across:

- `src/portfolio_rag_assistant/provider/ollama.py:79`;
- `src/portfolio_rag_assistant/provider/openai_compatible.py:77`;
- `src/portfolio_rag_assistant/provider/llama_cpp.py:77`.

Provider implementations also instantiate and close a new `httpx.AsyncClient`
for each provider request. This prevents TCP connection reuse. For the current
small portfolio assistant, this is a maintainability and performance/lifecycle
improvement rather than current breakage.

Any refactor must extract provider-neutral transport only. It must not merge
provider-specific payload authority, introduce a global client, add hidden
fallbacks, or create compatibility shims.

### 6. No pgvector ANN Index

Severity: medium.

Verdict: agree.

Confirmed in `migrations/0001_knowledge_schema.sql:70`.
`chunk_embeddings.embedding` is declared as dimensionless `vector`, and the only
embedding index is `chunk_embeddings_chunk_id_idx`.

This is fine for the current 113 chunks, but it will not scale. A dimensionless
vector column cannot be indexed with an ivfflat or hnsw index targeted to the
configured embedding dimension.

Recommended remediation, if scale requires it:

- choose an explicit embedding dimension per supported backend/model strategy;
- add a non-destructive migration with the correct pgvector ANN index;
- keep backend/model isolation and chunk text hash freshness checks intact.

### 7. Chunked Request Body Size

Severity: low to medium.

Verdict: partly agree.

Confirmed the API request-size middleware checks the `content-length` header in
`src/portfolio_rag_assistant/api/app.py:63`. If a direct client sends a chunked
request without `content-length`, the application-level pre-check does not know
the total body size before passing control to the ASGI stack.

The normal public path is still protected by Nginx through
`client_max_body_size 4k`, so this is not an active public-edge bug in the
configured deployment. It is a defense-in-depth issue for direct or internal API
exposure.

Recommended remediation, if prioritized later:

- enforce the body byte limit while receiving the ASGI body stream;
- keep schema-level question validation;
- keep public Nginx body-size enforcement.

### 8. Shared psycopg Connection Lifecycle

Severity: low.

Verdict: partly agree.

Confirmed one PostgreSQL connection is created at composition time in
`src/portfolio_rag_assistant/api/composition.py:122`, shared by runtime services,
and no ASGI lifespan shutdown hook closes it.

The risk is better described as lifecycle, concurrency, and blocking behavior
risk rather than immediate data corruption. It is low priority for the current
deployment, but should be revisited if traffic grows or concurrent request load
becomes meaningful.

### 9. Question Review Sort-Order Index

Severity: low.

Verdict: agree.

Confirmed question review listing and export order events by:

```sql
ORDER BY created_at DESC, id DESC
```

while `migrations/0002_question_events.sql` declares separate indexes on
`review_state` and `created_at`.

A composite index on review state and descending sort columns would be more
efficient for a large event table. For this personal portfolio assistant and
manual operator review workload, the impact is negligible.

Recommended remediation, if this ever becomes necessary:

- add a non-destructive migration with a composite index matching the filtered
  newest-first query shape;
- keep question-event storage privacy constraints unchanged.

### 10. Duplicated `_format_vector`

Severity: low.

Verdict: agree.

Confirmed `_format_vector` exists in both retrieval and knowledge storage code.
This is low risk, but it creates drift potential for vector serialization.

If remediated, the shared helper must stay provider-neutral and must not merge
retrieval authority with knowledge-store authority.

### 11. Unbounded OR-Chain In `_delete_stale_facts`

Severity: low.

Verdict: agree.

Confirmed in `src/portfolio_rag_assistant/knowledge/store.py:257`.
The query is parameterized and safe, but the implementation is less clean than
the chunk sibling that uses `NOT IN`.

This is a maintainability issue, not a current correctness or security bug.

### 12. Verified Clean Areas

Verdict: mostly agree.

The reviewed boundaries match `AGENTS.md` and `docs/architecture.md` in the
following areas:

- retrieval gathers and ranks source-backed public candidates;
- retrieval uses RRF as the primary fused score and policy owns
  `RETRIEVAL_MIN_SCORE`;
- answer generation phrases approved context and demotes provider insufficiency
  output to `not_answerable` with no sources;
- question collection passes only `raw_question_text=request.question` in
  `src/portfolio_rag_assistant/api/service.py:125`;
- question collection inserts only `raw_question_text` in
  `src/portfolio_rag_assistant/questions/collector.py:62`;
- question collection stores no visitor identity, headers, browser metadata,
  answer text, answer status, source identifiers, retrieval scores, source
  kinds, per-question language, or request metadata;
- stale embedding detection uses the stored chunk text hash for the configured
  backend and model.

The main exception is the policy category-only bypass described above: the
policy boundary exists, but one branch still violates the architecture's
intent-complete evidence requirement.

## Recommended Priority

The next remediation work should be prioritized as follows:

1. close the high-severity policy category-only bypass and add regression tests;
2. narrow the answer-generation insufficiency demotion guard without allowing
   insufficiency text in `answerable` responses;
3. remove the hardcoded TLS redirect host and preserve the full request URI;
4. add `exec -T` to automated `docker compose exec` calls.

The remaining observations are valid but lower priority:

- provider transport cleanup and HTTP pooling are future maintainability and
  performance improvements;
- pgvector ANN indexing is only necessary when knowledge volume grows;
- app-level streamed request-size enforcement is defense-in-depth for direct API
  exposure;
- question review composite indexing is only useful if review-event volume grows
  enough to matter;
- vector formatting and stale-fact cleanup shape can be improved later as small
  maintainability refactors.
