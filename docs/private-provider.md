# Optional private provider publication

Issue #51 adds an opt-in extension to the existing Nginx runtime and a
secret-free export of configured Ollama model selections and native metadata.
The platform supplies source-address policy and public aliases; this application
continues using its configured direct providers. Empty configuration enables no
provider publication. Do not publish model administration or visitor data.

The `deploy/nginx/private-services` directory is mounted read-only into each
public Nginx profile. Generated `.conf` files are ignored by Git. Validate with
`nginx -t` before reload; retain the prior private file until acceptance succeeds.
Use native exact-source `allow`/`deny` and fixed methods/endpoints. Forward neither
client authorization nor forwarded-address headers to the provider. Preserve the
existing redacted operational logs.

Export inside the existing API container, without inference:

```sh
docker compose --env-file .env exec -T api portfolio-rag-assistant runtime export-ollama-catalog \
  --source-commit FULL_COMMIT --chat-context 4096 --chat-output 1024 --embedding-context 2048
```

The explicit gateway limits do not change the RAG's own generation settings.
Exported model digests and native capabilities must match the installed selections;
architectural maximums are distinct from configured context. No credentials,
prompts, templates or unselected models are exported.
