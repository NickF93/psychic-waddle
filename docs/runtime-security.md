# Runtime security maintenance

The security baseline uses Python 3.12.16, certifi 2026.10.23, pip 26.2.2,
Psycopg/binary 3.3.6, Ollama 0.40.11 and PostgreSQL 17.11 with pgvector 0.8.7.
Image and dependency pins are owned by the Dockerfile, installer/application
constraints and Compose configuration, respectively. Inspect actual runtime
contents before accepting an image: tags and build dates are insufficient.

The published Certbot 5.8.0 image retains affected trust material. The small
`deploy/certbot.Dockerfile` refreshes its Python patch level and trust, retaining
the vendor's application, Alpine ABI, entrypoint and paths. Its existing
cryptography dependency is patched to 50.0.2 for bundled OpenSSL 4.0.3; the
remaining vendor dependencies are preserved.
Its dependency constraints are owned by `deploy/certbot.lock`, independently of
the API dependency lock. Normal `public-build.sh`/upgrade builds both images;
for renewal-only maintenance, build it before renewal or first certificate setup:

```sh
docker compose --profile public-tls build certbot
```

This is a locally built refresh, not an unmodified vendor image. Its OS bundle,
certifi and pip bundle must pass the same fingerprint acceptance checks.

Repeat the fingerprint check on each accepted Python image (select `api` or
`certbot` as the service). These are the two affected root identities verified
for this maintenance, not a general certificate-brand filter:

```sh
docker compose --profile public-tls run --rm --no-deps -T --entrypoint python certbot - <<'PY'
import hashlib
import ssl
import certifi
import pip._vendor.certifi as pip_certifi

blocked = {
    "86A1ECBA089C4A8D3BBE2734C612BA341D813E043CF9E8A862CD5C57A36BBE6B",
    "D7A7A0FB5D7E2731D771E9484EBCDEF71D5F0C3E0A2948782BC83EE0EA699EF4",
}
for name, path in [("OS", None), ("certifi", certifi.where()), ("pip", pip_certifi.where())]:
    context = ssl.create_default_context(cafile=path)
    roots = {hashlib.sha256(c).hexdigest().upper() for c in context.get_ca_certs(binary_form=True)}
    assert roots and not blocked.intersection(roots), name
    print(name, len(roots), "verified")
PY
```

The incident guidance is maintained by the
[Python project](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576/).

## Preserving an existing deployment

1. Record running image IDs, service configuration, selected providers, model
   manifests, database ownership/encoding/collation, migration checksums and
   data/embedding counts and hashes. Compare the old/new libc and the database's
   recorded/actual collation versions: a logical restore rebuilds indexes and
   cannot establish that reusing the physical volume is safe. Keep private
   configuration outside Git.
2. Pull/build candidates first. Inspect OS, OpenSSL, certifi, pip-vendored and
   selected client trust sources. Reject affected certificates by verified
   fingerprint, preserving unrelated and operator-owned trust anchors. Confirm
   patched bundled libpq independently of the server's major version.
3. Restore a logical export into a disposable candidate database with its roles
   and ownership. Verify existing schema and retrieval; rehearse the extension
   update with `psql -X -v ON_ERROR_STOP=1`:

   ```sql
   BEGIN;
   SET LOCAL lock_timeout = '10s';
   SET LOCAL statement_timeout = '60s';
   ALTER EXTENSION vector UPDATE TO '0.8.7';
   COMMIT;
   ```

4. Before modifying production data, pause RAG writers and take one verified
   recovery set containing the stopped database, model storage and protected
   configuration. Preserve original images and verify archive checksums and
   readability. No PostgreSQL major-version conversion is involved.
5. Replace the database, Ollama and API incrementally, retaining existing named
   volumes, project/network identities, private access and provider settings.
   Apply the rehearsed extension update once; confirm its resulting version.
   Check PostgreSQL release-note prerequisites, collation and index health.
   Rebuild indexes only where applicable; do not reingest knowledge or regenerate
   embeddings for an image refresh.
6. Run the acceptance checks below before reopening RAG. On failure, restore the
   matching original images/configuration and recovery data. An extension update
   must not be rolled back by assuming an in-place extension downgrade exists.

Use a single protected effective Compose file and the existing standard
`COMPOSE_FILE` mechanism for operator commands and the renewal unit. Reconcile
it against actual running services: historical files may retain older image or
proxy settings. Persist the selected file in the operator environment and
renewal service environment. Historical files are recovery evidence, not active
deployment alternatives.

When installing the existing renewal timer, export the selected `COMPOSE_FILE`
and `COMPOSE_PROFILES`; `public-certbot-install-timer.sh` persists them in the
service. Reconcile an existing timer using its standard systemd environment
drop-in and reload systemd, preserving its schedule and existing `ENV_FILE`.

Use targeted Compose operations with explicit service names and `--no-deps`
where dependencies are already accepted. The broad `public-upgrade.sh` wrapper
also refreshes knowledge by default and is not the runtime-only maintenance
procedure. Preserve the current proxy, certificate/ACME volumes, renewal timer,
optional public sites and ThingsBoard network integration.

## Acceptance

- Run full Ruff and pytest checks. Set `TEST_DATABASE_URL` only to a disposable
  PostgreSQL/pgvector database for native schema/ingestion/retrieval tests.
- Run `RUN_TLS_INTEGRATION=1 python -m pytest -q tests/test_provider_tls.py` with
  socket access and OpenSSL. The fixture exercises the actual provider transport
  with valid TLS and rejects untrusted certificates and wrong hostnames.
- With Docker/OpenSSL, run isolated route, privacy, streaming and WebSocket
  regressions:

  ```sh
  RUN_PROXY_INTEGRATION=1 python -m unittest discover -s tests -p test_thingsboard_proxy.py -v
  ```
- Verify the built API as its actual runtime user, including packaged parameter
  profiles, tokenizer, migrations, dependency consistency and effective trust.
- Verify model identities, embedding shape and retrieval against the preserved
  vectors; test JSON and negotiated SSE through the public portfolio. Qualify
  existing fallback in isolation without changing production provider policy.
- Confirm database readiness, data/embedding hashes, service restart recovery,
  proxy routing/CORS/privacy, certificate renewal and related-site availability.
  Keep negative cases in disposable fixtures and avoid synthetic visitor records.

Record exact deployed revisions/image identities, results and unavailable
checks outside Git. Keep credentials, database exports and operational archives
out of source and public PR text. A healthy process alone does not establish
trust remediation, database preservation or successful generation.
