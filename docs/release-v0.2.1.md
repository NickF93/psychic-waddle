# v0.2.1 Release Report

Date: 2026-06-15

## Scope

`v0.2.1` is a hotfix for Ollama-backed public deployments.

The release keeps local Ollama models resident between visitor requests by
passing the explicit `OLLAMA_KEEP_ALIVE` runtime setting to the Ollama service.
For the public CPU-only deployment, the intended value is:

```env
OLLAMA_KEEP_ALIVE=-1
```

The Ollama chat setup and start paths now preload the configured chat model and
verify that it appears in the loaded-model list. This removes the cold first
reply caused by Ollama unloading the model after an idle period.

The fix is limited to runtime configuration, scripts, and documentation. It does
not change retrieval, answer policy, generation, provider-neutral contracts, or
the reviewed knowledge base.

## Version

The Python package version is `0.2.1`, so the release tag is `v0.2.1`.

## Validation

Local validation on the hotfix branch:

```text
python3 -m pytest -q tests/test_runtime_scripts.py tests/test_runtime_configuration.py
63 passed

timeout 45s python3 -m pytest -q tests
581 passed, 9 skipped

python3 -m ruff check .
All checks passed!

git diff --check
passed
```

Runtime validation on the public deployment should use:

```text
RUNTIME_WAIT_TIMEOUT_SECONDS=600 \
PUBLIC_SMOKE_BASE_URL=https://vps.madnick.ovh \
scripts/runtime/public-upgrade.sh --tls-runtime

docker compose --env-file .env --profile ollama exec -T ollama ollama ps
```

The `ollama ps` output should list the resident chat model after the upgrade.

## Operational Note

Keeping a model resident requires enough system memory for the selected local
model or models. If the VPS cannot hold them, the failure mode is capacity
pressure, not answerability, retrieval, or API routing.
