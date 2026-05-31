# Runtime Infrastructure

## Purpose

Milestone 6 defines a reproducible local runtime for the public API, PostgreSQL
with `pgvector`, and optional local model services.

The runtime layer does not add CORS, TLS, a reverse proxy, Kubernetes, Swarm,
automatic model downloads, committed secrets, question collection, or API
behavior changes.

Public HTTPS exposure belongs to the Milestone 7 deployment boundary. That
boundary is documented in [Public Deployment Boundary](public-deployment.md) and
keeps the portfolio frontend in its separate project.

## Backend Image

Build the API image from the repository root:

```sh
docker build -t portfolio-rag-assistant:local .
```

The image starts:

```sh
uvicorn portfolio_rag_assistant.api.main:app --host 0.0.0.0 --port 8000
```

The image contains application code, migrations, and the dependency lock file.
It does not bake `.env` files, local model files, curated knowledge files, or
database data into the image.
Server-local deployment knowledge under `knowledge/` is ignored by Git and must
remain untracked unless a future explicit plan creates a reviewed committed
knowledge dataset.

Runtime build inputs are pinned:

- the Python base image is pinned by digest;
- the Python build backend is pinned exactly in `pyproject.toml`;
- PostgreSQL, Ollama, and llama.cpp images are pinned by digest;
- Python dependencies are constrained by `requirements.lock`;
- Docker builds do not upgrade `pip` at build time.

## Compose Stack

The default Compose stack contains:

- `api`: FastAPI public chat API.
- `db`: PostgreSQL 17 with `pgvector`.
- `postgres-data`: named PostgreSQL data volume.
- `runtime`: private bridge network.

The API host port is bound to localhost by default:

```env
API_BIND_ADDRESS=127.0.0.1
API_PORT=8000
```

Override `API_BIND_ADDRESS` explicitly only for a documented private-network
runtime. Public deployment keeps browser traffic behind the Nginx boundary
defined in Milestone 7.

Use `.env.example` only as a placeholder template. Real values belong in an
untracked local `.env` file.

## Runtime Scripts

The `scripts/runtime` directory provides the supported local operation layer
over Compose. Scripts resolve the repository root automatically, read `.env` by
default, and accept an explicit env file with:

```sh
ENV_FILE=/absolute/path/to/.env scripts/runtime/api-start.sh
```

For the full zero-to-running server procedure with PostgreSQL, Ollama, API
startup, knowledge ingestion, embedding indexing, smoke checks, and manual chat
tests, see [Server Setup Procedure](server-setup.md).

For the planned public `vps.madnick.ovh` deployment with Nginx, free Let's
Encrypt TLS, CORS, rate limits, and public smoke validation, see
[Public Deployment Boundary](public-deployment.md).

Setup and start scripts wait for the targeted service to become ready before
returning. The wait timeout defaults to 120 seconds and can be changed with:

```sh
RUNTIME_WAIT_TIMEOUT_SECONDS=300 scripts/runtime/llama-cpp-chat-start.sh
```

`down` scripts stop and remove only the targeted service container. They do not
remove unrelated services, networks, or volumes. Cleanup scripts are bounded to
their own component:

- API cleanup removes the API container and `portfolio-rag-assistant:local`
  image.
- PostgreSQL cleanup requires `--destroy-data` before deleting the
  `postgres-data` volume.
- Ollama cleanup requires `--destroy-models` before deleting the shared
  `ollama-models` volume.
- llama.cpp cleanup removes only service containers. It never deletes
  bind-mounted model files.
- Let's Encrypt setup and renewal scripts do not remove certificate, work, or
  ACME challenge volumes.

Script matrix:

| Component | Build | Setup | Start | Stop | Down | Cleanup | Extra |
| --- | --- | --- | --- | --- | --- | --- | --- |
| API/backend | `api-build.sh` | `api-setup.sh` | `api-start.sh` | `api-stop.sh` | `api-down.sh` | `api-cleanup.sh` | |
| PostgreSQL/pgvector | | `postgres-setup.sh` | `postgres-start.sh` | `postgres-stop.sh` | `postgres-down.sh` | `postgres-cleanup.sh --destroy-data` | `postgres-migrate.sh` |
| Ollama chat | | `ollama-chat-setup.sh` | `ollama-chat-start.sh` | `ollama-chat-stop.sh` | `ollama-chat-down.sh` | `ollama-chat-cleanup.sh --destroy-models` | |
| Ollama embeddings | | `ollama-embeddings-setup.sh` | `ollama-embeddings-start.sh` | `ollama-embeddings-stop.sh` | `ollama-embeddings-down.sh` | `ollama-embeddings-cleanup.sh --destroy-models` | |
| llama.cpp chat | | `llama-cpp-chat-setup.sh` | `llama-cpp-chat-start.sh` | `llama-cpp-chat-stop.sh` | `llama-cpp-chat-down.sh` | `llama-cpp-chat-cleanup.sh` | |
| llama.cpp embeddings | | `llama-cpp-embeddings-setup.sh` | `llama-cpp-embeddings-start.sh` | `llama-cpp-embeddings-stop.sh` | `llama-cpp-embeddings-down.sh` | `llama-cpp-embeddings-cleanup.sh` | |
| Let's Encrypt TLS | | `letsencrypt-setup.sh` | | | | | `letsencrypt-renew.sh` |
| Public deployment | `public-build.sh` | `public-setup.sh` | `public-start.sh` | `public-stop.sh` | `public-down.sh` | `public-cleanup.sh` | `public-migrate.sh`, `public-deploy.sh`, `public-smoke.sh`, `nginx-validate.sh` |

Public deployment scripts are high-level operator wrappers. They call the
existing API, PostgreSQL, provider, Nginx, and Let's Encrypt scripts instead of
duplicating those authorities.

`public-setup.sh` prepares API, database, migration, configured local
providers, and Nginx validation. It does not request a certificate unless the
operator passes the explicit flag:

```sh
scripts/runtime/public-setup.sh --issue-certificate
```

`public-deploy.sh` is the update path after setup. It builds the API image,
starts PostgreSQL, delegates migration to `postgres-migrate.sh`, starts the
public HTTPS runtime, and runs `public-smoke.sh`. It does not issue or renew
certificates.

`public-smoke.sh` defaults to the local HTTP edge:

```sh
scripts/runtime/public-smoke.sh
```

The local HTTP edge default is `http://127.0.0.1:18080`.

Production HTTPS smoke uses an explicit base URL:

```sh
PUBLIC_SMOKE_BASE_URL=https://vps.madnick.ovh scripts/runtime/public-smoke.sh
```

`public-cleanup.sh` removes runtime containers and the local API image only. It
does not delete PostgreSQL data, Ollama model data, llama.cpp model files,
Let's Encrypt certificates, ACME challenge data, or Let's Encrypt work data.

There is exactly one migration script:

```sh
scripts/runtime/postgres-migrate.sh
```

Provider scripts do not run database migrations. API scripts also do not run
database migrations.

Common setup orders:

```sh
# External chat and external embeddings.
scripts/runtime/postgres-setup.sh
scripts/runtime/postgres-migrate.sh
scripts/runtime/api-setup.sh
scripts/runtime/api-start.sh

# External chat with Ollama embeddings.
scripts/runtime/postgres-setup.sh
scripts/runtime/postgres-migrate.sh
scripts/runtime/ollama-embeddings-setup.sh
scripts/runtime/api-setup.sh
scripts/runtime/api-start.sh

# Ollama chat and Ollama embeddings.
scripts/runtime/postgres-setup.sh
scripts/runtime/postgres-migrate.sh
scripts/runtime/ollama-chat-setup.sh
scripts/runtime/ollama-embeddings-setup.sh
scripts/runtime/api-setup.sh
scripts/runtime/api-start.sh

# llama.cpp chat and llama.cpp embeddings.
scripts/runtime/postgres-setup.sh
scripts/runtime/postgres-migrate.sh
scripts/runtime/llama-cpp-chat-setup.sh
scripts/runtime/llama-cpp-embeddings-setup.sh
scripts/runtime/api-setup.sh
scripts/runtime/api-start.sh
```

For mixed local providers, run the setup script for the configured chat backend
and the setup script for the configured embedding backend. For example,
llama.cpp chat with Ollama embeddings uses `llama-cpp-chat-setup.sh` and
`ollama-embeddings-setup.sh`.

Validate the Compose file:

```sh
docker compose --env-file .env config
```

The runtime test suite also renders the default, Ollama, and llama.cpp Compose
profiles with `.env.example` so interpolation and profile errors fail locally.

Start PostgreSQL:

```sh
scripts/runtime/postgres-start.sh
```

Run the schema migration explicitly through the database container:

```sh
scripts/runtime/postgres-migrate.sh
```

Start the API:

```sh
scripts/runtime/api-start.sh
```

Check liveness:

```sh
curl http://127.0.0.1:8000/health
```

Check runtime readiness:

```sh
curl http://127.0.0.1:8000/ready
```

`/health` is liveness only. It confirms the API process answers HTTP requests.
`/ready` confirms database access, the expected knowledge schema, and at least
one public embedding for the configured embedding backend and model.

Before exposing the service to recruiters, run the explicit smoke check:

```sh
docker compose --env-file .env run --rm api portfolio-rag-assistant runtime smoke
```

The smoke check verifies readiness and calls both configured provider
capabilities once. This is intentionally not part of the periodic Docker
healthcheck because provider calls can be slow, metered, or model-loading.

## Knowledge Commands

Curated knowledge files are not baked into the image. Mount them explicitly for
maintenance commands.

Validate curated knowledge without starting dependencies:

```sh
docker compose --env-file .env run --rm --no-deps --volume "$PWD/knowledge:/knowledge:ro" api portfolio-rag-assistant knowledge validate /knowledge/profile.json
```

Ingest curated knowledge:

```sh
docker compose --env-file .env run --rm --volume "$PWD/knowledge:/knowledge:ro" api portfolio-rag-assistant knowledge ingest /knowledge/profile.json
```

Index embeddings after ingestion:

```sh
docker compose --env-file .env run --rm api portfolio-rag-assistant knowledge index-embeddings
```

Embedding indexing uses only the configured embedding provider. It does not call
chat models or create facts.

## Runtime Configuration

All names are explicit. There are no aliases, legacy names, or fallback
configuration paths.

Database configuration:

```env
POSTGRES_DB=portfolio_rag_assistant
POSTGRES_USER=portfolio_rag_assistant
POSTGRES_PASSWORD=replace-with-local-password
```

The API receives database settings as discrete environment variables inside
Compose: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD`.
Application code passes those fields directly to the PostgreSQL driver instead
of building a connection URL through string interpolation.

Model capability configuration:

```env
CHAT_BACKEND=openai-compatible
CHAT_BASE_URL=https://example.invalid/v1
CHAT_API_KEY=replace-with-chat-provider-token
CHAT_MODEL=replace-with-chat-model

EMBEDDING_BACKEND=openai-compatible
EMBEDDING_BASE_URL=https://example.invalid/v1
EMBEDDING_API_KEY=replace-with-embedding-provider-token
EMBEDDING_MODEL=replace-with-embedding-model
```

Set the chat and embedding base URLs to the same API root when one provider
serves both capabilities. Set them differently when chat and embeddings are
served by different systems.

Changing `EMBEDDING_BACKEND` or `EMBEDDING_MODEL` requires re-indexing the
knowledge base before `/ready` can pass for the new embedding pair.

## Optional Local Model Profiles

The default Compose stack does not start local model services.

### Ollama

Enable the optional Ollama service:

```sh
scripts/runtime/ollama-chat-start.sh
# or
scripts/runtime/ollama-embeddings-start.sh
```

Ollama is one shared service. The chat and embedding scripts target the same
service, model volume, and daemon; stopping or cleaning either side affects the
shared Ollama runtime.

Use Ollama for embeddings:

```env
EMBEDDING_BACKEND=ollama
EMBEDDING_BASE_URL=http://ollama:11434/api
EMBEDDING_MODEL=nomic-embed-text
```

Use Ollama for chat:

```env
CHAT_BACKEND=ollama
CHAT_BASE_URL=http://ollama:11434/api
CHAT_MODEL=llama3.2
```

Model download is explicit. Use the matching setup script for the configured
capability:

```sh
scripts/runtime/ollama-chat-setup.sh
scripts/runtime/ollama-embeddings-setup.sh
```

Equivalent manual commands are:

```sh
docker compose --env-file .env --profile ollama exec ollama ollama pull llama3.2
docker compose --env-file .env --profile ollama exec ollama ollama pull nomic-embed-text
```

Ollama model data is stored in the `ollama-models` named volume.

### llama.cpp

llama.cpp runs as two services because chat and embedding workloads require
separate server modes:

- `llama-cpp-chat`: chat completions.
- `llama-cpp-embeddings`: embeddings with `--embedding`.

Place GGUF models in the local model directory and set:

```env
LLAMA_CPP_MODEL_DIR=./models
LLAMA_CPP_CHAT_MODEL_PATH=/models/replace-with-chat-model.gguf
LLAMA_CPP_EMBEDDING_MODEL_PATH=/models/replace-with-embedding-model.gguf
LLAMA_CPP_EMBEDDING_POOLING=mean
```

Enable both llama.cpp services:

```sh
scripts/runtime/llama-cpp-chat-start.sh
scripts/runtime/llama-cpp-embeddings-start.sh
```

Use llama.cpp for chat:

```env
CHAT_BACKEND=llama-cpp
CHAT_BASE_URL=http://llama-cpp-chat:8080/v1
CHAT_MODEL=local-chat
```

Use llama.cpp for embeddings:

```env
EMBEDDING_BACKEND=llama-cpp
EMBEDDING_BASE_URL=http://llama-cpp-embeddings:8080/v1
EMBEDDING_MODEL=local-embedding
```

The model directory is mounted read-only. M6 does not add GPU-specific Compose
configuration.

### Mixed Mode

Use an external OpenAI-compatible API for chat and a local embedding backend
when the chat model is heavier than embedding generation:

```env
CHAT_BACKEND=openai-compatible
CHAT_BASE_URL=https://api.example.com/v1
CHAT_API_KEY=replace-with-chat-provider-token
CHAT_MODEL=external-chat-model

EMBEDDING_BACKEND=ollama
EMBEDDING_BASE_URL=http://ollama:11434/api
EMBEDDING_MODEL=nomic-embed-text
```
