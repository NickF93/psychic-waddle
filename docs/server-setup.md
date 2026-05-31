# Server Setup Procedure

This document describes the full zero-to-running setup for a single server using:

- PostgreSQL with `pgvector`;
- the backend/API container;
- Ollama as the chat backend;
- Ollama as the embedding backend;
- explicit migration, ingestion, embedding indexing, readiness, smoke, and chat checks.

Run every command from the repository root:

```sh
cd ~/rag/psychic-waddle
```

The API is bound to `127.0.0.1` in this procedure. Do not expose it publicly
until the setup, readiness, smoke, and chat checks all pass.

## 1. Install Docker If Missing

Check whether Docker and Compose are already installed:

```sh
docker --version
docker compose version
```

If either command fails, install Docker:

```sh
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
. /etc/os-release

curl -fsSL "https://download.docker.com/linux/${ID}/gpg" | sudo tee /etc/apt/keyrings/docker.asc >/dev/null
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker "$USER"
newgrp docker
```

Verify the installation:

```sh
docker --version
docker compose version
```

If Docker permissions still fail after `newgrp docker`, log out of the server
and log back in.

## 2. Create `.env` For Ollama Chat And Embeddings

Create a local `.env` file. This file is untracked and must not be committed.

```sh
POSTGRES_PASSWORD="$(openssl rand -hex 24)"

cat > .env <<EOF
API_BIND_ADDRESS=127.0.0.1
API_PORT=8000

POSTGRES_DB=portfolio_rag_assistant
POSTGRES_USER=portfolio_rag_assistant
POSTGRES_PASSWORD=$POSTGRES_PASSWORD

CHAT_BACKEND=ollama
CHAT_BASE_URL=http://ollama:11434/api
CHAT_API_KEY=
CHAT_MODEL=llama3.2

EMBEDDING_BACKEND=ollama
EMBEDDING_BASE_URL=http://ollama:11434/api
EMBEDDING_API_KEY=
EMBEDDING_MODEL=nomic-embed-text

RETRIEVAL_TOP_K=4
RETRIEVAL_MIN_SCORE=0.3

LLAMA_CPP_MODEL_DIR=./models
LLAMA_CPP_CHAT_MODEL_PATH=/models/replace-with-chat-model.gguf
LLAMA_CPP_EMBEDDING_MODEL_PATH=/models/replace-with-embedding-model.gguf
LLAMA_CPP_EMBEDDING_POOLING=mean
EOF
```

Validate the Compose configuration:

```sh
docker compose --env-file .env config
docker compose --env-file .env --profile ollama config
```

Both commands must render successfully before continuing.

## 3. Build The Backend Image

Build the local API image:

```sh
scripts/runtime/api-setup.sh
```

Expected result: Docker builds `portfolio-rag-assistant:local`.

## 4. Start PostgreSQL And Run Migrations

Start PostgreSQL with `pgvector`:

```sh
scripts/runtime/postgres-setup.sh
```

Check the database container:

```sh
docker compose --env-file .env ps
```

Run the schema migration:

```sh
scripts/runtime/postgres-migrate.sh
```

Expected result: the migration creates the `vector` extension, knowledge tables,
embedding table, and indexes.

## 5. Start Ollama And Pull Models

Start the shared Ollama service and pull the chat model:

```sh
RUNTIME_WAIT_TIMEOUT_SECONDS=600 scripts/runtime/ollama-chat-setup.sh
```

Pull the embedding model:

```sh
RUNTIME_WAIT_TIMEOUT_SECONDS=600 scripts/runtime/ollama-embeddings-setup.sh
```

Check Ollama and the installed models:

```sh
docker compose --env-file .env --profile ollama ps
docker compose --env-file .env --profile ollama exec ollama ollama list
```

Expected result: `llama3.2` and `nomic-embed-text` are listed.

## 6. Create A First Knowledge File

Create a minimal test knowledge file:

```sh
mkdir -p knowledge

cat > knowledge/profile.json <<'JSON'
{
  "schema_version": 1,
  "sources": [
    {
      "source_uri": "cv://niccolo/main",
      "title": "Niccolo Ferrari CV",
      "reviewed_at": "2026-05-31T00:00:00+00:00"
    }
  ],
  "facts": [
    {
      "source_uri": "cv://niccolo/main",
      "category": "experience",
      "fact_text": "Niccolo worked at NAIS s.r.l.",
      "source_locator": "Experience section",
      "public_visible": true
    },
    {
      "source_uri": "cv://niccolo/main",
      "category": "experience",
      "fact_text": "Niccolo worked at Bonfiglioli.",
      "source_locator": "Experience section",
      "public_visible": true
    }
  ]
}
JSON
```

This file is only a functional test. Replace it with real reviewed public facts
before using the service for recruiters.

## 7. Validate, Ingest, And Index Knowledge

Validate the local knowledge file without starting dependencies:

```sh
docker compose --env-file .env run --rm --no-deps \
  --volume "$PWD/knowledge:/knowledge:ro" \
  api portfolio-rag-assistant knowledge validate /knowledge/profile.json
```

Ingest the validated knowledge into PostgreSQL:

```sh
docker compose --env-file .env run --rm \
  --volume "$PWD/knowledge:/knowledge:ro" \
  api portfolio-rag-assistant knowledge ingest /knowledge/profile.json
```

Generate embeddings using the configured Ollama embedding backend:

```sh
docker compose --env-file .env --profile ollama run --rm \
  api portfolio-rag-assistant knowledge index-embeddings
```

Expected result: the command indexes embeddings for the ingested chunks.

Changing `EMBEDDING_BACKEND` or `EMBEDDING_MODEL` requires re-indexing before
readiness can pass for the new embedding pair.

## 8. Start The Backend/API Service

Start the API:

```sh
scripts/runtime/api-start.sh
```

Check all services:

```sh
docker compose --env-file .env --profile ollama ps
```

Expected result: API, database, and Ollama containers are running and healthy.

## 9. Manual Runtime Tests

Check API liveness:

```sh
curl -s http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

Check runtime readiness:

```sh
curl -s http://127.0.0.1:8000/ready
```

Expected response:

```json
{"status":"ready"}
```

Run the full smoke test:

```sh
docker compose --env-file .env --profile ollama run --rm \
  api portfolio-rag-assistant runtime smoke
```

Expected output:

```text
runtime smoke passed: database ready, embeddings ready, providers reachable
```

Run a chat test:

```sh
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'content-type: application/json' \
  -d '{"question":"Where did Niccolo work?","language":"en"}'
```

Expected result: the response status is `answerable`, the answer mentions the
ingested work facts, and the source list includes `Niccolo Ferrari CV`.

For easier JSON inspection:

```sh
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'content-type: application/json' \
  -d '{"question":"Where did Niccolo work?","language":"en"}' | python3 -m json.tool
```

## 10. Useful Debug Commands

Inspect service status:

```sh
docker compose --env-file .env --profile ollama ps
```

Inspect API logs:

```sh
docker compose --env-file .env logs api
```

Inspect database logs:

```sh
docker compose --env-file .env logs db
```

Inspect Ollama logs:

```sh
docker compose --env-file .env --profile ollama logs ollama
```

Inspect installed Ollama models:

```sh
docker compose --env-file .env --profile ollama exec ollama ollama list
```

## 11. Stop Or Clean Up

Stop API only:

```sh
scripts/runtime/api-stop.sh
```

Stop PostgreSQL only:

```sh
scripts/runtime/postgres-stop.sh
```

Stop the shared Ollama service:

```sh
scripts/runtime/ollama-chat-stop.sh
```

Remove service containers without deleting volumes:

```sh
scripts/runtime/api-down.sh
scripts/runtime/postgres-down.sh
scripts/runtime/ollama-chat-down.sh
```

Destroy database data only when intentionally resetting the local database:

```sh
scripts/runtime/postgres-cleanup.sh --destroy-data
```

Destroy Ollama model data only when intentionally deleting downloaded models:

```sh
scripts/runtime/ollama-chat-cleanup.sh --destroy-models
```

The API is still local-only in this setup. Public exposure belongs to the
Milestone 7 public deployment boundary with reverse proxy, free Let's Encrypt
TLS, CORS/origin controls, rate limits, and production knowledge data. See
[Public Deployment Boundary](public-deployment.md).
