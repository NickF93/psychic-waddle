# v0.2.2 Release Report

`v0.2.2` fixes Ollama startup warmup by replacing CLI-based warmup with bounded
non-interactive model residency validation.

The Ollama runtime path now preloads the configured chat model through Ollama's
HTTP API and verifies residency through `/api/ps`. `OLLAMA_KEEP_ALIVE` remains an
explicit configuration value; use `-1` on the portfolio VPS when the model should
remain resident between requests.

The Python package version is `0.2.2`, so the release tag is `v0.2.2`.
