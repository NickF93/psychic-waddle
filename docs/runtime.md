# Runtime Infrastructure

## Purpose

Milestone 6 defines a reproducible local runtime for the public API, PostgreSQL
with `pgvector`, and optional local model services.

The runtime layer does not add CORS, TLS, a reverse proxy, Kubernetes, Swarm,
automatic model downloads, committed secrets, question collection, or API
behavior changes.

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

Override `API_BIND_ADDRESS` explicitly only when the service must listen on a
VPN/tun0 address.

Use `.env.example` only as a placeholder template. Real values belong in an
untracked local `.env` file.

Validate the Compose file:

```sh
docker compose --env-file .env config
```

The runtime test suite also renders the default, Ollama, and llama.cpp Compose
profiles with `.env.example` so interpolation and profile errors fail locally.

Start PostgreSQL:

```sh
docker compose --env-file .env up -d db
```

Run the schema migration explicitly through the database container:

```sh
docker compose --env-file .env exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /migrations/0001_knowledge_schema.sql'
```

Start the API:

```sh
docker compose --env-file .env up -d api
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
docker compose --env-file .env --profile ollama up -d ollama
```

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

Model download is manual and explicit:

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
docker compose --env-file .env --profile llama-cpp up -d llama-cpp-chat llama-cpp-embeddings
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
