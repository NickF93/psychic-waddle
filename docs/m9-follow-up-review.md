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

## Point-By-Point Findings

### 1. Hardcoded TLS Redirect

Verdict: agree, real issue.

Confirmed in `deploy/nginx/nginx-tls.conf`:

```nginx
return 308 https://vps.madnick.ovh$uri;
```

This contradicts the existence of `PUBLIC_SERVER_NAME` as operator-controlled
deployment configuration. It also drops query strings because it redirects with
`$uri` rather than `$request_uri`.

The current runtime configuration tests explicitly lock in this behavior in
`tests/test_runtime_configuration.py`, so a clean remediation must update both
the Nginx TLS configuration and the corresponding tests.

Recommended remediation:

- remove the hardcoded host from `deploy/nginx/nginx-tls.conf`;
- preserve the original request path and query string;
- keep the public-edge privacy logging constraints unchanged;
- update runtime configuration tests so the desired redirect behavior is the
  tested behavior.

### 2. Automated `docker compose exec` Without `-T`

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

### 3. HTTPX Connection Pooling

Verdict: agree, but not urgent.

Confirmed provider implementations instantiate and close a new
`httpx.AsyncClient` for each provider request:

- `src/portfolio_rag_assistant/provider/ollama.py`;
- `src/portfolio_rag_assistant/provider/openai_compatible.py`;
- `src/portfolio_rag_assistant/provider/llama_cpp.py`.

This prevents TCP connection reuse. For the current small portfolio assistant,
this is a performance and lifecycle improvement rather than a correctness bug.

If remediated, it should be handled as a clean provider lifecycle design. It
should not be implemented with a global client, hidden fallback, compatibility
shim, or mixed provider/API authority.

### 4. Chunked Request Body Size

Verdict: partly agree.

Confirmed the API request-size middleware checks the `content-length` header.
If a direct client sends a chunked request without `content-length`, the
application-level pre-check does not know the total body size before passing
control to the ASGI stack.

The normal public path is still protected by Nginx through
`client_max_body_size 4k`, so this is not an active public-edge bug in the
configured deployment. It is a defense-in-depth issue for direct or internal API
exposure.

Recommended remediation, if prioritized later:

- enforce the body byte limit while receiving the ASGI body stream;
- keep schema-level question validation;
- keep public Nginx body-size enforcement.

### 5. Question Review Sort-Order Index

Verdict: agree, low priority.

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

### 6. Privacy, SOLID Boundaries, And Answerability

Verdict: agree.

The reviewed boundaries match `AGENTS.md` and `docs/architecture.md`:

- retrieval gathers and ranks source-backed public candidates;
- answer policy owns answerability, `RETRIEVAL_MIN_SCORE`, and
  intent-completeness checks;
- answer generation phrases approved context and demotes provider insufficiency
  output to `not_answerable` with no sources;
- question collection passes only `raw_question_text` for unanswered questions;
- question collection stores no visitor identity, headers, browser metadata,
  answer text, answer status, source identifiers, retrieval scores, source
  kinds, per-question language, or request metadata;
- stale embedding detection uses the stored chunk text hash for the configured
  backend and model.

No contradiction to `AGENTS.md` was found in these areas during this follow-up
review.

## Recommended Priority

The two concrete runtime fixes should be handled first:

1. remove the hardcoded TLS redirect host and preserve the full request URI;
2. add `exec -T` to automated `docker compose exec` calls.

The remaining observations are valid but lower priority:

- provider HTTP connection pooling is a future performance/lifecycle improvement;
- app-level streamed request-size enforcement is defense-in-depth for direct API
  exposure;
- question review composite indexing is only useful if review-event volume grows
  enough to matter.
