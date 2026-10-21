# ThingsBoard HTTPS through the existing edge

M17 adds an opt-in native Nginx site. The existing ThingsBoard Compose project
owns its application, database, Kafka, network and telemetry listeners. This
repository owns only its existing proxy and certificate lifecycle. It does not
install, upgrade or restart ThingsBoard. No service is enabled by default.

## Configure

The public hostname must resolve to the edge and be covered by the selected
certificate. Configure these deployment values; none belongs in application code:

| Variable | Meaning | nklella deployment |
|---|---|---|
| `THINGSBOARD_SERVER_NAME` | Public DNS hostname | `vps.madnick.ovh` |
| `THINGSBOARD_CERTIFICATE_NAME` | Existing Certbot certificate directory name | `portfolio-rag-assistant` |
| `THINGSBOARD_UPSTREAM` | Docker DNS name and backend HTTP port | `MyTB2:9090` |
| `THINGSBOARD_NETWORK` | Backend-owned existing Docker network | `tb_default` |

Render `deploy/nginx/thingsboard.conf.template` using native `envsubst`, replacing
only `THINGSBOARD_SERVER_NAME`, `THINGSBOARD_CERTIFICATE_NAME` and
`THINGSBOARD_UPSTREAM`. Keep all Nginx `$variables` literal. Write the result to
`deploy/nginx/public-services/thingsboard.conf`, inspect it, and retain the prior
configuration privately. Use trusted hostname, certificate-name and host:port
values; validate the result with `nginx -t` before activation.

For example, after exporting the three template variables:

```sh
envsubst '${THINGSBOARD_SERVER_NAME} ${THINGSBOARD_CERTIFICATE_NAME} ${THINGSBOARD_UPSTREAM}' \
  < deploy/nginx/thingsboard.conf.template \
  > deploy/nginx/public-services/thingsboard.conf
```

Use `compose.yaml` plus `deploy/compose.thingsboard.yaml` and the deployment's
existing image/environment overrides. Keep that exact Compose file list in the
operator's deployment environment (`COMPOSE_FILE`, using absolute paths) so
future proxy recreation and certificate renewal use the same mounts and networks.
Only `nginx-tls` joins the external network; its original runtime network remains.
Never use a transient `docker network connect` as the installation mechanism.

Stage and syntax-check the complete configuration in a disposable Nginx container
with the same mounts and networks before replacing the live proxy. Then target
only `nginx-tls` with `up -d --no-deps`; do not run whole-stack deployment or
certificate bootstrap scripts against an already running TLS edge.

Inspect the effective `docker compose config` mount targets and candidate
`nginx -T` output as well as syntax. An older deployment override can pin
`/etc/nginx/nginx.conf` to an earlier snapshot and silently hide the new site.
Reconcile that target in the final operator override, preserving other mounts.
Before activation, verify the loaded configuration contains the chosen server
name, ThingsBoard upstream and shared assistant include. Do not publish full
configuration dumps or operator environment contents as acceptance artifacts.

## Routing and privacy

HTTPS `/` serves ThingsBoard, including its REST and WebSocket APIs. The three
exact `/api/assistant/chat`, `/api/assistant/health` and `/api/assistant/ready`
locations retain their single shared RAG definition, CORS, methods, limits,
redacted logs and streaming. Other hostnames retain the default RAG-only site.
Public HTTP continues serving ACME challenges and redirecting to HTTPS.

ThingsBoard receives correct HTTPS host/scheme/port and native WebSocket upgrade
headers. Untrusted forwarded-address headers are cleared. Its root route permits
10 MiB request bodies; RAG retains its existing 4 KiB bound. Backend DNS is
refreshed by Nginx's existing Docker resolver, without hardcoded container IPs.

The site logs fixed route categories, status, upstream status, byte count and
durations. Device tokens occur in paths and WebSocket credentials can occur in
queries: never log raw URLs, query strings, credentials, bodies or telemetry.
Do not enable verbose proxy error logs or browser traces containing credentials.

Existing HTTP `:8080`, MQTT and other telemetry listeners remain unchanged.
Firmware using those endpoints needs no update. Do not redirect `:8080`.

## Certificate maintenance and rollback

Reuse a currently valid matching certificate; do not issue a duplicate just to
enable this site. The selected nklella certificate covers `vps.madnick.ovh`.
Reuse the existing webroot Certbot renewal scripts and certificate volumes.
Renewal and status cover all certificates managed in that volume, including a
separately named ThingsBoard certificate. Certbot retains authority over each
certificate's renewal schedule; Nginx reloads only after a successful renewal.
Install `public-certbot-install-timer.sh` from the persistent deployed source,
with the effective Compose file list recorded in its environment file. Test
`public-certbot-test-renewal.sh`, timer activation and Nginx reload behavior.
Keep credentials and private keys outside Git and logs.

Rollback restores the prior proxy mount/configuration and Compose invocation,
then recreates only `nginx-tls`. Preserve the prior private Ollama include,
certificate volumes, application images, network identities and telemetry ports.
Do not delete certificates, volumes, existing dashboards or real device records.

Acceptance requires actual login/dashboard interactions, authenticated WebSocket
updates and a disposable telemetry device through HTTPS and unchanged `:8080`.
Clean up exact fixture IDs through supported APIs, and check portfolio streaming,
RAG access controls, certificate trust and renewal before marking the PR ready.
