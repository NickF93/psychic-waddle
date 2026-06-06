# v0.2.0 Release Report

Date: 2026-06-06

## Scope

`v0.2.0` is a post-MVP reliability and intent-routing release for the
Portfolio RAG Assistant.

The release includes:

- data-driven intent catalog loading from reviewed runtime configuration;
- catalog-owned intent identifiers and shared `IntentResolution`;
- positive trigger semantics for bounded question routing;
- strict catalog validation and fail-fast runtime composition;
- semantic intent preparation with reviewed example anchors;
- candidate-only semantic intent routing;
- offline semantic calibration proposals that never write the committed catalog;
- collected-question coverage for public-profile, skills, license, interests,
  publication, and role-fit phrasing;
- role-fit answerability grounded through reviewed skills evidence;
- retrieval candidate fan-out separated from final `top_k`;
- refreshed public narrative documentation through the root `README.md` and
  design-decision notes.

The release keeps unsupported, private, speculative, availability, and internal
diagnostic questions outside the answerability boundary unless reviewed public
knowledge supports them.

## Version

The Python package version is `0.2.0`, so the release tag is `v0.2.0`.

The package readme metadata now points to `README.md`, which is the repository's
public overview. `PLAN.md` remains the project planning history.

## Validation

Local validation on the release candidate:

```text
python3 -m ruff check .
All checks passed!

timeout 45s python3 -m pytest -q tests
581 passed, 9 skipped

git diff --check
passed
```

Runtime validation on the public deployment should be performed before the final
release merge to `main` using:

```text
RUNTIME_WAIT_TIMEOUT_SECONDS=600 \
PUBLIC_SMOKE_BASE_URL=https://vps.madnick.ovh \
scripts/runtime/public-upgrade.sh --tls-runtime
```

The release report must be updated if final runtime smoke finds a release
blocker.

## Deferred Follow-Up

Post-MVP cleanup and broader bilingual coverage remain tracked in GitHub
issues:

- <https://github.com/NickF93/psychic-waddle/issues/25>
- <https://github.com/NickF93/psychic-waddle/issues/26>

Both issues remain open for `v0.2.0`.

Italian coverage has improved through the shared catalog and runtime routing
work, but broader Italian suitability and role-fit phrasing still needs a
dedicated follow-up. That work should remain data-driven through the reviewed
intent catalog and concrete runtime evidence checks.
