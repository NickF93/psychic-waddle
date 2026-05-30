# Runtime Infrastructure

## Purpose

Milestone 6 defines a reproducible local runtime for the public API, PostgreSQL
with `pgvector`, and optional local LLM services.

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

The image contains application code and migrations. It does not bake `.env`
files, local model files, curated knowledge files, or database data into the
image.

## Compose Stack

The default Compose stack contains:

- `api`: FastAPI public chat API.
- `db`: PostgreSQL 17 with `pgvector`, using `pgvector/pgvector:0.8.2-pg17`.
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

Check health:

```sh
curl http://127.0.0.1:8000/health
```

## Knowledge Commands

Curated knowledge files are not baked into the image. Mount them explicitly for
maintenance commands.

Validate curated knowledge:

```sh
docker compose --env-file .env run --rm --volume "$PWD/knowledge:/knowledge:ro" api portfolio-rag-assistant knowledge validate /knowledge/profile.json
```

Ingest curated knowledge:

```sh
docker compose --env-file .env run --rm --volume "$PWD/knowledge:/knowledge:ro" api portfolio-rag-assistant knowledge ingest /knowledge/profile.json
```

Index embeddings after ingestion:

```sh
docker compose --env-file .env run --rm api portfolio-rag-assistant knowledge index-embeddings
```

Embedding indexing uses only the configured `LLMProvider.embed()` path. It does
not call chat models or create facts.

## Provider Configuration

The application still uses only the explicit configuration names defined in
`docs/backend-configuration.md` and `docs/api.md`:

- `DATABASE_URL`
- `LLM_BACKEND`
- `LLM_BASE_URL`
- `LLM_API_KEY`
- `CHAT_MODEL`
- `EMBEDDING_MODEL`
- `RETRIEVAL_TOP_K`
- `RETRIEVAL_MIN_SCORE`

Compose builds `DATABASE_URL` from the PostgreSQL service values:

```env
POSTGRES_DB=portfolio_rag_assistant
POSTGRES_USER=portfolio_rag_assistant
POSTGRES_PASSWORD=replace-with-local-password
```

## Optional Local LLM Profiles

The default Compose stack does not start local LLM services.

### Ollama

Enable the optional Ollama service:

```sh
docker compose --env-file .env --profile ollama up -d ollama
```

Configure the API:

```env
LLM_BACKEND=ollama
LLM_BASE_URL=http://ollama:11434/api
CHAT_MODEL=llama3.2
EMBEDDING_MODEL=nomic-embed-text
```

Model download is manual and explicit:

```sh
docker compose --env-file .env --profile ollama exec ollama ollama pull llama3.2
docker compose --env-file .env --profile ollama exec ollama ollama pull nomic-embed-text
```

Ollama model data is stored in the `ollama-models` named volume.

### llama.cpp

Place a GGUF model in the local model directory and set:

```env
LLM_BACKEND=llama-cpp
LLM_BASE_URL=http://llama-cpp:8080/v1
LLAMA_CPP_MODEL_DIR=./models
LLAMA_CPP_MODEL_PATH=/models/replace-with-model.gguf
CHAT_MODEL=replace-with-chat-model
EMBEDDING_MODEL=replace-with-embedding-model
```

Enable the optional llama.cpp server:

```sh
docker compose --env-file .env --profile llama-cpp up -d llama-cpp
```

The model directory is mounted read-only. M6 does not add GPU-specific Compose
configuration.
