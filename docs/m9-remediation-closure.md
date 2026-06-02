# Milestone 9 Remediation Closure

Date: 2026-06-02

Branch: `feature/m9-remediation-plan`

## Audit Scope

Sprint 9.10 audited the implemented Milestone 9 answerability remediation
against `AGENTS.md` and `docs/architecture.md`.

Reviewed areas:

- bounded question intent profiles;
- PostgreSQL vector, keyword, intent-expanded retrieval, and RRF ranking;
- embedding freshness through chunk text hashes;
- deterministic policy intent-completeness checks;
- answer-generation insufficiency demotion guard;
- tracked `knowledge/profile.json` aggregates against the CV source;
- public smoke and runtime deployment scripts;
- API, runtime, public deployment, retrieval, policy, generation, and knowledge
  maintenance docs;
- question collection privacy boundaries and public edge logging constraints.

## Findings

No runtime code remediation was required by the closure audit.

The audited implementation keeps the M9 boundaries intact:

- retrieval gathers and ranks plausible public evidence but does not decide
  answerability;
- policy requires intent-complete evidence and rejects category-only support;
- generation phrases approved context and demotes provider insufficiency output
  to `not_answerable` with no sources;
- embedding indexing refreshes missing or stale embeddings for the configured
  backend and model without database destruction;
- tracked knowledge aggregates are source-backed, broad recruiter-intent facts,
  not question-specific hacks;
- public smoke catches the original workplace regression and keeps unsupported
  question collection validation opt-in;
- question collection stores only raw unanswered-question text plus allowed
  operator review metadata;
- Nginx public logs remain redacted and do not include visitor identity,
  request bodies, raw questions, query strings, user agents, cookies, source
  IDs, retrieval scores, answer status, or answer text.

The only closure change was documentation: `PLAN.md` now points Sprint 9.10 to
this closure report and describes the M9 remediation architecture as
implemented rather than planned.

## Validation

Local validation performed during closure:

```text
validated 1 sources, 113 facts, 113 chunks
```

```text
124 passed, 1 skipped
```

Focused tests covered intent profiles, retrieval, embedding freshness, policy,
answer generation, tracked knowledge, and runtime smoke behavior.

```text
359 passed, 8 skipped
```

The full local test suite passed.

Live public smoke is an environment validation and must be run on the target
server after deployment because it depends on configured providers, PostgreSQL,
the public edge, and loaded embeddings.

## Server Validation Commands

Fresh destructive setup on a test server, preserving existing certificates:

```sh
cd ~/rag/psychic-waddle
git fetch --all --tags
git switch feature/m9-remediation-plan
git pull --ff-only

RUNTIME_WAIT_TIMEOUT_SECONDS=600 \
PUBLIC_SMOKE_BASE_URL=http://127.0.0.1:18080 \
scripts/runtime/public-reset-and-setup.sh --destroy-db --destroy-models
```

HTTPS production-style clean reset, preserving existing certificates:

```sh
cd ~/rag/psychic-waddle
git fetch --all --tags
git switch feature/m9-remediation-plan
git pull --ff-only

RUNTIME_WAIT_TIMEOUT_SECONDS=600 \
PUBLIC_SMOKE_BASE_URL=https://vps.madnick.ovh \
scripts/runtime/public-reset-and-setup.sh --destroy-db --destroy-models --tls-runtime
```

If certificates must also be destroyed and freshly issued:

```sh
cd ~/rag/psychic-waddle
git fetch --all --tags
git switch feature/m9-remediation-plan
git pull --ff-only

RUNTIME_WAIT_TIMEOUT_SECONDS=600 \
PUBLIC_SMOKE_BASE_URL=https://vps.madnick.ovh \
scripts/runtime/public-reset-and-setup.sh --destroy-db --destroy-models --destroy-certs --issue-certificate
```

Post-setup validation:

```sh
PUBLIC_SMOKE_BASE_URL=http://127.0.0.1:18080 scripts/runtime/public-smoke.sh

docker compose --env-file .env --profile ollama run --rm \
  api portfolio-rag-assistant runtime smoke

curl -s -X POST http://127.0.0.1:18080/api/assistant/chat \
  -H 'content-type: application/json' \
  -d '{"question":"Where did Niccolo work?","language":"en"}' | python3 -m json.tool

curl -s -X POST http://127.0.0.1:18080/api/assistant/chat \
  -H 'content-type: application/json' \
  -d '{"question":"What is Niccolo favorite pizza topping?","language":"en"}' | python3 -m json.tool
```

Optional question-collection validation, which intentionally records one
pending review event:

```sh
PUBLIC_SMOKE_BASE_URL=http://127.0.0.1:18080 \
PUBLIC_SMOKE_CHECK_QUESTION_COLLECTION=true \
scripts/runtime/public-smoke.sh
```

For HTTPS runtime, use `https://vps.madnick.ovh` in `PUBLIC_SMOKE_BASE_URL` and
the public chat URLs.
