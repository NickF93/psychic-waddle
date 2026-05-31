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
Only Nginx publishes public ports `80` and `443`.

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

The certificate flow for later implementation:

1. DNS points `vps.madnick.ovh` to `195.88.87.3` and
   `2a02:c207:2259:619::1`.
2. Ports `80` and `443` are reachable on the VPS.
3. Nginx starts with an HTTP challenge configuration.
4. Certbot requests the certificate through the shared ACME challenge volume.
5. Nginx starts or reloads the HTTPS configuration.
6. Renewal reuses the same certificate volume and reloads Nginx after success.

Certificate cleanup must require an explicit destructive flag. Normal public
`down` or `stop` operations must not delete certificates.

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

- public ports: `80:80` and `443:443`;
- internal upstream: `http://api:8000`;
- public route namespace: `/api/assistant`;
- strict CORS allowlist;
- redacted assistant logs;
- request body limit;
- proxy timeouts;
- default rate limit `20/minute` with burst `40`;
- tests that render Compose and validate the Nginx config structure.

### Sprint 7.3: Free TLS Automation

Add Certbot-based Let's Encrypt automation:

- certificate setup command;
- certificate renewal command;
- Nginx reload after renewal;
- required `LETSENCRYPT_EMAIL` validation;
- bounded certificate volumes;
- tests for required environment and destructive cleanup guards.

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
letsencrypt-setup.sh
letsencrypt-renew.sh
```

`public-migrate.sh` must delegate to the single PostgreSQL migration authority
instead of duplicating migration logic.

Cleanup scripts must not delete PostgreSQL data, model data, or certificates
without explicit destructive flags.

### Sprint 7.5: Public Smoke Validation

Add public HTTPS smoke validation:

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
