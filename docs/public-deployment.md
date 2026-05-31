# Public Deployment Boundary

## Purpose

Milestone 7 makes the Portfolio RAG Assistant deployable on
`vps.madnick.ovh` as a public HTTPS API consumed by the separate
`pigreco.xyz` portfolio project.

This document is the authoritative M7 deployment plan. Sprint 7.1 creates only
documentation. Later M7 sprints may add Compose services, Nginx configuration,
Certbot automation, scripts, tests, and validation commands according to this
contract.

This repository does not implement the portfolio webpage, chat widget, frontend
styling, or deployment of the separate `pigreco.xyz` project.

## Production Topology

Public browser traffic:

```text
Browser on pigreco.xyz
  -> https://vps.madnick.ovh/api/assistant/chat
  -> Nginx container
  -> API container http://api:8000/chat
  -> PostgreSQL + provider backends on the private Compose network
```

Public API host:

```text
https://vps.madnick.ovh
```

VPS network addresses:

```text
IPv4: 195.88.87.3
IPv6: 2a02:c207:2259:619::1
```

Portfolio origins allowed by CORS:

```text
https://pigreco.xyz
https://www.pigreco.xyz
```

The portfolio server address `85.215.155.0` is infrastructure context. It is
not a browser origin and must not be used in CORS unless a later explicit
debug-only plan adds temporary IP-origin testing.

## Public Routes

Nginx owns the public route namespace:

| Public route | Internal route | Purpose |
| --- | --- | --- |
| `POST /api/assistant/chat` | `POST /chat` | recruiter-facing question |
| `GET /api/assistant/health` | `GET /health` | public liveness smoke |
| `GET /api/assistant/ready` | `GET /ready` | public readiness smoke |

The API container keeps its existing local routes. Nginx performs only edge
adaptation: TLS, routing, CORS, request limits, timeouts, rate limits, and
privacy-safe logging. Nginx must not modify question text, answer text,
retrieval behavior, provider payloads, or database state.

PostgreSQL, Ollama, llama.cpp, and the Python API port are not public services.
Only Nginx publishes browser-facing ports. Sprint 7.2 provides the HTTP edge
runtime only; HTTPS port `443` is added in Sprint 7.3 after Let's Encrypt
certificate automation exists.

The Sprint 7.2 local default is intentionally bound to loopback:

```env
PUBLIC_HTTP_BIND_ADDRESS=127.0.0.1
PUBLIC_HTTP_PORT=8080
```

On `vps.madnick.ovh`, after operator validation and before certificate setup,
the HTTP edge may be bound publicly for ACME and smoke preparation:

```env
PUBLIC_HTTP_BIND_ADDRESS=0.0.0.0
PUBLIC_HTTP_PORT=80
```

## Edge Policy

CORS is enforced at Nginx, not duplicated in FastAPI. Allowed origins are
exactly:

```text
https://pigreco.xyz
https://www.pigreco.xyz
```

Unexpected browser origins must not receive permissive CORS headers. Wildcard
origins are forbidden.

Default chat rate limit:

```text
20 requests per minute, burst 40
```

The rate limit protects local model and provider resources. Future docs must
show how to tighten this value for stricter protection and how to remove it for
temporary controlled testing. Rate limiting may use the remote address in
Nginx memory for enforcement, but assistant access logs must not persist IP
addresses.

Assistant logs must use a redacted format. The format may include method, path
without query string, status, response size, request time, and allowed origin.
It must not include IP address, user agent, cookies, request body, query string,
raw question text, or API keys.

If an edge error log path can include visitor identity, it must not be persisted
for assistant traffic. Deployment documentation must make log retention explicit
instead of relying on host defaults.

Request body size limits must stay aligned with the API contract. The edge may
reject oversized requests before FastAPI reads them.

Proxy timeouts must account for local LLM latency while still bounding stuck
requests. Timeout values belong to the public edge configuration, not to the
answer generation authority.

## TLS

TLS uses free Let's Encrypt certificates. No paid certificate is required.

The deployment uses Nginx and Certbot containers. Certificate setup requires:

```env
PUBLIC_SERVER_NAME=vps.madnick.ovh
LETSENCRYPT_EMAIL=your-email@example.com
```

`LETSENCRYPT_EMAIL` is operator contact information for Let's Encrypt renewal
and account notices. It belongs only in the untracked server `.env`; do not
commit a real personal email address.

The deployment has two explicit Nginx modes:

| Mode | Compose profile | Service | Purpose |
| --- | --- | --- | --- |
| HTTP/bootstrap | `public` | `nginx` | serve ACME HTTP challenges and local edge checks before certificates exist |
| HTTPS runtime | `public-tls` | `nginx-tls` | terminate TLS after certificates exist |

The HTTP/bootstrap service must not load TLS certificate paths. The HTTPS
runtime service must not start until the certificate exists in the shared
certificate volume.

The certificate flow is:

1. DNS points `vps.madnick.ovh` to `195.88.87.3` and
   `2a02:c207:2259:619::1`.
2. Ports `80` and `443` are reachable on the VPS.
3. `.env` configures the public HTTP edge on port `80`:

   ```env
   PUBLIC_HTTP_BIND_ADDRESS=0.0.0.0
   PUBLIC_HTTP_PORT=80
   ```

4. Validate public Compose profiles and both Nginx configs:

   ```sh
   scripts/runtime/nginx-validate.sh
   ```

5. Run first public setup and issue the certificate explicitly:

   ```sh
   scripts/runtime/public-setup.sh --issue-certificate
   ```

   The setup command builds the API image, starts PostgreSQL, runs the single
   migration wrapper, prepares the configured local providers, starts the
   HTTP/bootstrap edge for ACME, calls `letsencrypt-setup.sh`, then stops the
   bootstrap edge so port `80` is free for the HTTPS runtime edge.

6. Start the HTTPS runtime edge:

   ```sh
   scripts/runtime/public-start.sh
   ```

7. Run public smoke validation:

   ```sh
   PUBLIC_SMOKE_BASE_URL=https://vps.madnick.ovh scripts/runtime/public-smoke.sh
   ```

8. Later update deploys use the non-certificate deployment path:

   ```sh
   PUBLIC_SMOKE_BASE_URL=https://vps.madnick.ovh scripts/runtime/public-deploy.sh
   ```

9. Renewal reuses the same certificate volume and reloads Nginx after success:

   ```sh
   scripts/runtime/letsencrypt-renew.sh
   ```

Certbot stores the service certificate under the fixed certificate name
`portfolio-rag-assistant`, so Nginx can use stable certificate paths while the
requested public DNS name remains explicit in `PUBLIC_SERVER_NAME`.

Certificate cleanup must require an explicit destructive flag. Normal public
`down` or `stop` operations must not delete certificates.

## Public Operation Scripts

The high-level public scripts are operator wrappers around the existing
component scripts. They do not duplicate migration SQL, certificate issuance,
provider setup, or API build behavior.

| Script | Purpose |
| --- | --- |
| `public-build.sh` | validate public Nginx/Compose config and build the API image |
| `public-setup.sh` | setup API, PostgreSQL, migration, configured local providers, and Nginx validation |
| `public-setup.sh --issue-certificate` | run setup plus the explicit first Let's Encrypt issuance path |
| `public-start.sh` | start configured local providers, PostgreSQL, API, stop bootstrap Nginx if present, and start `nginx-tls` |
| `public-stop.sh` | stop public edge, API, configured local providers, and PostgreSQL without deleting data |
| `public-down.sh` | remove runtime containers without deleting volumes |
| `public-cleanup.sh` | remove runtime containers and the local API image only |
| `public-deploy.sh` | build, start PostgreSQL, migrate, start HTTPS runtime, and smoke-test |
| `public-migrate.sh` | delegate to `postgres-migrate.sh` |
| `public-smoke.sh` | call public health, ready, CORS preflight, and chat routes through the edge |
| `nginx-validate.sh` | validate public and public-tls Compose rendering plus required Nginx directives |

Provider setup and start behavior is selected from `.env`:

- `CHAT_BACKEND=ollama` starts the Ollama chat path.
- `CHAT_BACKEND=llama-cpp` starts the llama.cpp chat path.
- `CHAT_BACKEND=openai-compatible` starts no local chat service.
- `EMBEDDING_BACKEND=ollama` starts the Ollama embedding path.
- `EMBEDDING_BACKEND=llama-cpp` starts the llama.cpp embedding path.
- `EMBEDDING_BACKEND=openai-compatible` starts no local embedding service.

`public-smoke.sh` defaults to the local HTTP edge:

```sh
scripts/runtime/public-smoke.sh
```

Production smoke must make the public target explicit:

```sh
PUBLIC_SMOKE_BASE_URL=https://vps.madnick.ovh scripts/runtime/public-smoke.sh
```

`public-deploy.sh` intentionally does not issue or renew certificates. Use
`public-setup.sh --issue-certificate` for first certificate issuance and
`letsencrypt-renew.sh` for renewal.

`public-cleanup.sh` must not delete PostgreSQL data, model volumes, certificate
volumes, ACME challenge data, or Let's Encrypt work data.

## M7 Sprint Breakdown

### Sprint 7.1: Public Deployment Plan

Deliver documentation only:

- update `PLAN.md`;
- update `docs/api.md`;
- add this document;
- link local runtime docs to this public deployment boundary.

No code, scripts, Compose services, Nginx configuration, Certbot configuration,
or runtime behavior changes belong in Sprint 7.1.

### Sprint 7.2: Public Edge Runtime Configuration

Add the Nginx public edge container and configuration:

- profile-gated service: `nginx` under the `public` Compose profile;
- HTTP edge only in this sprint;
- local default binding: `127.0.0.1:8080`;
- production HTTP binding: `0.0.0.0:80`;
- HTTPS port `443` deferred to Sprint 7.3;
- internal upstream: `http://api:8000`;
- public route namespace: `/api/assistant`;
- strict CORS allowlist;
- redacted assistant logs;
- request body limit;
- proxy timeouts;
- default rate limit `20/minute` with burst `40`;
- tests that render Compose and validate the Nginx config structure.

Manual local validation before the public script suite exists:

```sh
docker compose --env-file .env --profile public config
docker compose --env-file .env --profile public up --wait nginx
curl -s http://127.0.0.1:8080/api/assistant/health
curl -s http://127.0.0.1:8080/api/assistant/ready
```

Chat calls through the edge use:

```sh
curl -s -X POST http://127.0.0.1:8080/api/assistant/chat \
  -H 'content-type: application/json' \
  -H 'origin: https://pigreco.xyz' \
  -d '{"question":"Where did Niccolo work?","language":"en"}'
```

Direct public exposure of the Python API port remains out of scope. The API may
still publish on `127.0.0.1` for local operator tests.

### Sprint 7.3: Free TLS Automation

Add Certbot-based Let's Encrypt automation:

- profile-gated Certbot service;
- bounded certificate, Certbot work, and ACME challenge volumes;
- HTTP/bootstrap Nginx ACME challenge routing;
- HTTPS runtime Nginx config;
- certificate setup command: `scripts/runtime/letsencrypt-setup.sh`;
- certificate renewal command: `scripts/runtime/letsencrypt-renew.sh`;
- Nginx reload after renewal;
- required `PUBLIC_SERVER_NAME` and `LETSENCRYPT_EMAIL` validation;
- tests for required environment, public `443` ownership, ACME routing, and
  destructive cleanup guards.

### Sprint 7.4: Public Deployment Script Suite

Add the supported public operation scripts under `scripts/runtime`:

```text
public-build.sh
public-setup.sh
public-start.sh
public-stop.sh
public-down.sh
public-cleanup.sh
public-deploy.sh
public-migrate.sh
public-smoke.sh
nginx-validate.sh
```

`public-migrate.sh` must delegate to the single PostgreSQL migration authority
instead of duplicating migration logic.

The Let's Encrypt setup and renewal scripts are already delivered by Sprint 7.3.
Sprint 7.4 may call `letsencrypt-setup.sh` only through the explicit
`public-setup.sh --issue-certificate` path. It must not duplicate certificate
issuance or renewal logic, and `public-deploy.sh` must not issue or renew
certificates.

Cleanup scripts must not delete PostgreSQL data, model data, or certificates
without explicit destructive flags.

### Sprint 7.5: Public Smoke Validation

Harden public HTTPS smoke validation beyond the Sprint 7.4 smoke script:

- `GET https://vps.madnick.ovh/api/assistant/health`;
- `GET https://vps.madnick.ovh/api/assistant/ready`;
- `POST https://vps.madnick.ovh/api/assistant/chat`;
- CORS preflight from `https://pigreco.xyz`;
- CORS preflight from `https://www.pigreco.xyz`;
- rejection of an unexpected origin;
- confirmation that direct public access to the API container port is not part
  of the deployment path.

## Completion Criteria

M7 is complete only when:

- public HTTPS traffic reaches the service through Nginx;
- the public chat route is
  `https://vps.madnick.ovh/api/assistant/chat`;
- only `https://pigreco.xyz` and `https://www.pigreco.xyz` are accepted browser
  origins;
- PostgreSQL, local model services, and the Python API port are not public;
- Let's Encrypt certificate setup and renewal are scripted;
- first deploy, update deploy, stop, down, cleanup, migration, and smoke
  commands are documented and scripted;
- public smoke checks pass before the portfolio project consumes the API.
