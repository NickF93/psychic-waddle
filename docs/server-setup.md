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
PUBLIC_HTTP_BIND_ADDRESS=127.0.0.1
PUBLIC_HTTP_PORT=18080
PUBLIC_HTTPS_BIND_ADDRESS=127.0.0.1
PUBLIC_HTTPS_PORT=18443
PUBLIC_SERVER_NAME=vps.madnick.ovh
LETSENCRYPT_EMAIL=replace-with-letsencrypt-email

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
RETRIEVAL_CANDIDATE_FAN_OUT=50
RETRIEVAL_MIN_SCORE=0.3
INTENT_PROFILES_PATH=config/intent-profiles.json
QUESTION_COLLECTION_ENABLED=false

LLAMA_CPP_MODEL_DIR=./models
LLAMA_CPP_CHAT_MODEL_PATH=/models/replace-with-chat-model.gguf
LLAMA_CPP_EMBEDDING_MODEL_PATH=/models/replace-with-embedding-model.gguf
LLAMA_CPP_EMBEDDING_POOLING=mean
EOF
```

If this server already had an older `.env`, verify that the complete public
deployment block above is present. Compose intentionally fails when public edge
variables are missing instead of silently defaulting to an occupied port.

Validate the Compose configuration:

```sh
docker compose --env-file .env config
docker compose --env-file .env --profile ollama config
docker compose --env-file .env --profile public config
docker compose --env-file .env --profile public-tls config
```

All Compose configuration commands must render successfully before continuing.

## 3. Build The Backend Image

Build the local API image:

```sh
scripts/runtime/api-setup.sh
```

Expected result: Docker builds `portfolio-rag-assistant:local`.

For a fresh public test server where old containers or test data may exist, the
high-level destructive setup path is:

```sh
RUNTIME_WAIT_TIMEOUT_SECONDS=600 \
scripts/runtime/public-reset-and-setup.sh --destroy-db --destroy-models
```

This stops/removes runtime containers, removes only the explicitly selected
PostgreSQL and Ollama volumes, rebuilds, migrates, loads the committed
knowledge file, starts the local HTTP public edge, and runs smoke checks. Add
`--destroy-certs` only when the Let's Encrypt and ACME volumes must also be
discarded.

For later code updates that must preserve database, models, and certificates,
use the preserving upgrade path instead:

```sh
RUNTIME_WAIT_TIMEOUT_SECONDS=600 scripts/runtime/public-upgrade.sh
```

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

Expected result: the migration creates the migration ledger, `vector` extension,
knowledge tables, embedding table, question review table, and indexes.

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

## 6. Use The Reviewed Knowledge File

The reviewed public profile knowledge is committed at:

```text
knowledge/profile.json
```

Do not create a server-local replacement for this file unless a reviewed source
change requires it. The committed file is the canonical public facts dataset
used by the deployment scripts.

## 7. Validate, Ingest, And Index Knowledge

The high-level loader validates, ingests, and indexes the committed knowledge
file:

```sh
scripts/runtime/public-load-knowledge.sh
```

It delegates to the existing CLI commands. Manual equivalent commands are below
for debugging.

Validate the knowledge file without starting dependencies:

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

Expected result: the command indexes missing or stale embeddings for the
ingested chunks. A later run may report `indexed 0 chunk embeddings` only when
the configured backend/model already has current embeddings for every public
chunk. The current reviewed profile file validates as one source with more than
one hundred public facts and matching chunks.

Changing `EMBEDDING_BACKEND` or `EMBEDDING_MODEL` requires re-indexing before
readiness can pass for the new embedding pair. Changing `knowledge/profile.json`
requires `scripts/runtime/public-load-knowledge.sh` or
`scripts/runtime/public-upgrade.sh`; PostgreSQL data destruction is not part of
normal knowledge refresh.

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

The API is still local-only at this point. Public exposure belongs to the
Milestone 7 public deployment boundary with reverse proxy, free Let's Encrypt
TLS, CORS/origin controls, rate limits, and production knowledge data.

## 12. Public TLS Startup On `vps.madnick.ovh`

Run this section only after the local setup, readiness, smoke, and chat checks
above pass with the production knowledge base.

DNS must point `vps.madnick.ovh` to the service VPS:

```text
IPv4: 195.88.87.3
IPv6: 2a02:c207:2259:619::1
```

The VPS firewall and provider firewall must allow inbound TCP `80` and `443`.
The Python API port stays private; do not expose `8000` publicly.

Edit `.env` for public certificate issuance and HTTPS runtime:

```env
PUBLIC_HTTP_BIND_ADDRESS=0.0.0.0
PUBLIC_HTTP_PORT=80
PUBLIC_HTTPS_BIND_ADDRESS=0.0.0.0
PUBLIC_HTTPS_PORT=443
PUBLIC_SERVER_NAME=vps.madnick.ovh
LETSENCRYPT_EMAIL=your-real-letsencrypt-contact-email
```

`LETSENCRYPT_EMAIL` is used only by Let's Encrypt for account and renewal
notices. Do not commit a real email address.

Validate the public profiles and Nginx configs:

```sh
scripts/runtime/nginx-validate.sh
```

Run first public setup and request the free certificate explicitly:

```sh
scripts/runtime/public-setup.sh --issue-certificate
```

This setup path builds the API image, starts PostgreSQL, runs the migration
wrapper, prepares configured local providers, starts the HTTP/bootstrap edge for
ACME, calls `letsencrypt-setup.sh`, and then stops the bootstrap edge.
Certificate issuance intentionally refuses loopback/local HTTP settings:
`PUBLIC_HTTP_BIND_ADDRESS` must be `0.0.0.0` and `PUBLIC_HTTP_PORT` must be
`80`.

Start the HTTPS runtime edge:

```sh
scripts/runtime/public-start.sh
```

Check the public HTTPS routes through the high-level smoke script:

```sh
PUBLIC_SMOKE_BASE_URL=https://vps.madnick.ovh scripts/runtime/public-smoke.sh
```

Expected output without the optional direct API-port probe:

```text
cors preflight passed: https://pigreco.xyz
cors preflight passed: https://www.pigreco.xyz
unexpected origin rejected: https://example.invalid
workplace answerability smoke passed
direct API probe skipped: set PUBLIC_DIRECT_API_PROBE_URL to check public port 8000
public smoke passed: https://vps.madnick.ovh
```

To validate M8 question collection through the public edge, run the opt-in
notice check:

```sh
PUBLIC_SMOKE_BASE_URL=https://vps.madnick.ovh \
PUBLIC_SMOKE_CHECK_QUESTION_COLLECTION=true \
scripts/runtime/public-smoke.sh
```

This records one unsupported question for manual review.

On the public server, also probe the public IP for accidental FastAPI exposure:

```sh
PUBLIC_SMOKE_BASE_URL=https://vps.madnick.ovh \
PUBLIC_DIRECT_API_PROBE_URL=http://195.88.87.3:8000/health \
scripts/runtime/public-smoke.sh
```

This direct probe must not return `2xx`. If it fails, remove public exposure of
port `8000`; the public deployment path must be Nginx on `443`.

For later code/config updates after the certificate exists, use:

```sh
PUBLIC_SMOKE_BASE_URL=https://vps.madnick.ovh scripts/runtime/public-upgrade.sh --tls-runtime
```

The public smoke script checks both portfolio CORS origins, rejection of an
unexpected origin, health, readiness, the chat route, and optional question
collection notices. A direct manual chat request is still useful when checking
answer text:

```sh
curl -s -X POST https://vps.madnick.ovh/api/assistant/chat \
  -H 'content-type: application/json' \
  -H 'origin: https://pigreco.xyz' \
  -d '{"question":"Where did Niccolo work?","language":"en"}'
```

Renew certificates with:

```sh
scripts/runtime/letsencrypt-renew.sh
```

Check certificate status:

```sh
scripts/runtime/public-certbot-status.sh
```

Test renewal without changing certificates:

```sh
scripts/runtime/public-certbot-test-renewal.sh
```

Install the host systemd renewal timer after first certificate issuance:

```sh
scripts/runtime/public-certbot-install-timer.sh --dry-run
scripts/runtime/public-certbot-install-timer.sh
```

Renewal expects `nginx-tls` to be running because the ACME HTTP challenge is
served by the HTTPS runtime profile on port `80`. The renewal script reloads
`nginx-tls` only when Certbot reports that a certificate was actually renewed.

For the complete public deployment boundary, see
[Public Deployment Boundary](public-deployment.md).
