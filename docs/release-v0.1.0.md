# v0.1.0 MVP Release Report

Date: 2026-06-02

## Scope

`v0.1.0` is the first MVP release of the recruiter-facing Portfolio RAG
Assistant.

The release includes:

- reviewed profile knowledge ingestion;
- PostgreSQL and pgvector retrieval;
- deterministic answerability policy;
- grounded answer generation;
- public chat API;
- public HTTP/HTTPS runtime scripts;
- anonymous unanswered-question collection for manual review;
- Milestone 9 retrieval, policy, embedding freshness, and runtime smoke
  remediation.

The public MVP is English-first. Italian recruiter coverage is intentionally
tracked as post-MVP follow-up work.

## Version

The Python package version is `0.1.0`, so the release tag is `v0.1.0`.

## Validation

Local validation on the release candidate:

```text
timeout 45s python3 -m pytest -q tests
394 passed, 9 skipped
```

Runtime validation was also performed on the VPS deployment using:

```text
RUNTIME_WAIT_TIMEOUT_SECONDS=600 \
PUBLIC_SMOKE_BASE_URL=https://vps.madnick.ovh \
scripts/runtime/public-upgrade.sh --tls-runtime
```

The public smoke passed against `https://vps.madnick.ovh`, including:

- database, embeddings, and provider readiness;
- CORS checks for approved origins;
- unexpected origin rejection;
- workplace answerability smoke;
- public HTTPS smoke.

Manual public probes showed:

- core English recruiter questions return `answerable`;
- unsupported, private, and adversarial questions remain `not_answerable`;
- Italian coverage is partial and deferred.

## Deferred Follow-Up

Post-MVP follow-up is tracked in GitHub issues:

- <https://github.com/NickF93/psychic-waddle/issues/25>
- <https://github.com/NickF93/psychic-waddle/issues/26>

These issues are not release blockers for the English-first MVP.
