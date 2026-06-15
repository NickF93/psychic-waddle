# v0.2.2 Release Report

Date: 2026-06-15

## Scope

`v0.2.2` is a hotfix for Ollama-backed public deployments. It supersedes
`v0.2.1` for Ollama deployments because the `v0.2.1` chat warmup command could
block during setup after the model pull completed.

The release keeps the explicit model-residency contract from `v0.2.1`:

```env
OLLAMA_KEEP_ALIVE=-1
OLLAMA_CHAT_WARMUP_PROMPT="Reply with OK."
```

The chat setup and start scripts now warm the configured Ollama chat model with
the configured warmup prompt through a timeout-bounded Docker Compose exec call.
They then verify the loaded-model list through the same bounded execution path.
A warmup failure now fails the script instead of leaving the public upgrade
command blocked indefinitely.

The fix is limited to runtime scripts, tests, version metadata, and
documentation. It does not change retrieval, answer policy, answer generation,
provider-neutral contracts, or the reviewed knowledge base.

## Version

The Python package version is `0.2.2`, so the release tag is `v0.2.2`.

## Validation

Required local validation on the hotfix branch:

```text
sh -n scripts/runtime/*.sh

python3 -m pytest -q \
  tests/test_runtime_scripts.py \
  tests/test_runtime_configuration.py

timeout 45s python3 -m pytest -q tests

python3 -m ruff check .
git diff --check
```

Required Ollama runtime validation before release:

```text
RUNTIME_WAIT_TIMEOUT_SECONDS=600 scripts/runtime/ollama-chat-setup.sh
RUNTIME_WAIT_TIMEOUT_SECONDS=600 scripts/runtime/ollama-chat-start.sh
docker compose --env-file .env --profile ollama exec -T ollama ollama ps
sleep 420
docker compose --env-file .env --profile ollama exec -T ollama ollama ps
```

Both `ollama ps` checks should list the configured resident chat model.

## Public Upgrade

Upgrade the public server from the release tag with:

```text
grep -Fx 'OLLAMA_KEEP_ALIVE=-1' .env
grep -Fx 'OLLAMA_CHAT_WARMUP_PROMPT="Reply with OK."' .env

timeout 900s env \
  RUNTIME_WAIT_TIMEOUT_SECONDS=600 \
  PUBLIC_SMOKE_BASE_URL=https://vps.madnick.ovh \
  scripts/runtime/public-upgrade.sh --tls-runtime
```

After upgrade, verify residency:

```text
docker compose --env-file .env --profile ollama exec -T ollama ollama ps
sleep 420
docker compose --env-file .env --profile ollama exec -T ollama ollama ps
```

## Operational Note

Keeping a model resident requires enough system memory for the selected local
model or models. If the VPS cannot hold them, the failure mode is capacity
pressure, not answerability, retrieval, or API routing.
