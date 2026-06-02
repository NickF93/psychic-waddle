# Milestone 9 Remediation Closure

Date: 2026-06-02

Branch: `feature/m9-remediation-plan`

## Status

Milestone 9 is validated after Sprint 9.11 through Sprint 9.15 remediation.

The earlier Sprint 9.10 conclusion that no runtime code remediation was needed
was wrong. The isolated project Docker stack reproduced a public smoke failure
for `Where did Niccolo work?`. The failure was in retrieval candidate
generation, not in `llama3.2`, policy, generation, tracked knowledge, or
embedding freshness.

Sprint 9.11 through Sprint 9.15 fixed the retrieval root causes and validated
the current branch against the project-only isolated Docker runtime.

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

Sprint 9.11 found two concrete retrieval defects:

- intent-expanded PostgreSQL search built one space-joined expansion string,
  which `websearch_to_tsquery('english', ...)` interpreted as an over-strict
  AND query;
- `PostgreSQLRetriever` applied `RETRIEVAL_MIN_SCORE` before answer policy saw
  candidates, contradicting the architecture contract that the threshold
  belongs to `AnswerPolicy`.

Sprint 9.12 through Sprint 9.14 remediated those defects:

- intent-expanded retrieval now uses controlled OR evidence queries from
  profile-owned lexical expansion terms;
- the raw visitor question is no longer appended to the intent-expanded query
  because vector and keyword retrieval already search the question;
- broad workplace retrieval expansion terms such as standalone `work` and
  `worked` were removed from retrieval expansion;
- `PostgreSQLRetriever` no longer accepts, stores, or applies `min_score`;
- retrieval returns ranked candidates and policy alone applies
  `RETRIEVAL_MIN_SCORE`;
- real PostgreSQL regression coverage now exercises the workplace failure
  shape when `TEST_DATABASE_URL` is available.

The final audited implementation keeps the M9 boundaries intact:

- retrieval gathers and ranks plausible public evidence but does not decide
  answerability or filter by policy threshold;
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

## Validation

Local validation after remediation:

```text
360 passed, 9 skipped
```

Isolated project Docker validation used `/tmp/psychic-waddle-debug.env` with
`COMPOSE_PROJECT_NAME=psychic-waddle-debug`.

```text
validated 1 sources, 113 facts, 113 chunks
indexed 113 chunk embeddings
runtime smoke passed: database ready, embeddings ready, providers reachable
workplace answerability smoke passed
public smoke passed: http://127.0.0.1:19080
```

Manual isolated runtime probes:

```text
Where did Niccolo work? -> answerable, with NAIS, Bonfiglioli, University of Ferrara, and CIAS.
What is Niccolo current role? -> answerable, Senior Machine Learning Engineer and Researcher at NAIS S.r.l. and Technical Lead of the AI team.
What are Niccolo main machine learning skills? -> answerable.
What publications does Niccolo have? -> answerable.
What is Niccolo favorite pizza topping? -> not_answerable with question_recorded.
```

Long-form manual probes were run sequentially because the configured local
`llama3.2` model is small; parallel long-form probes can return
`service_unavailable` under local debug load. The public workplace regression
path passes through public smoke.

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

Preserve PostgreSQL data, model volumes, certificate volumes, and ACME state:

```sh
cd ~/rag/psychic-waddle
git fetch --all --tags
git switch feature/m9-remediation-plan
git pull --ff-only

RUNTIME_WAIT_TIMEOUT_SECONDS=600 \
PUBLIC_SMOKE_BASE_URL=http://127.0.0.1:18080 \
scripts/runtime/public-upgrade.sh
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
