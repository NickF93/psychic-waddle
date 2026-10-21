# M16 delivery contract

Extend the existing provider boundary for incremental OpenAI-compatible and
Ollama chat. Credentials are optional server-side configuration. Primary and
fallback endpoints/models are explicit; no provider names are embedded in code.
One fallback attempt is permitted only before visible text, after provider
failure. An insufficient-evidence answer never triggers fallback.

Local embeddings, retrieval and deterministic evidence approval remain unchanged.
External generation receives only application instructions, requested language,
question and approved public context. It receives no visitor identity, retrieval
scores, database identifiers or unapproved knowledge. Generation policy owns
sentinel suppression and final insufficiency classification. Sources remain
code-owned and appear only on completed answers.

POST /chat supports JSON and explicitly negotiated text/event-stream. SSE events
are status, delta, complete and error. Complete carries the authoritative existing
response body; early output is provisional. EOF without completion is failure.
Cancellation closes upstream resources and cannot trigger fallback.

Default delivery limits are 15 seconds primary, 180 seconds fallback and 240
seconds overall including retrieval. Attempts use the remaining request budget.
Human-readable logs report provider role, sanitized failure reason and durations,
never questions, context, answers, credentials or upstream error bodies.

Deployment must validate optional credentials, start and preload configured local
fallbacks, preserve persistent data, and keep both proxy deadlines above the
application deadline. Qualification and live acceptance precede PR readiness.

## Configuration and wire contract

`CHAT_*` selects the primary. `CHAT_API_KEY` may be absent or empty; no
Authorization header is sent in that case. Set `CHAT_TIMEOUT_SECONDS=15` for
the external primary. `CHAT_FALLBACK_BACKEND`, `CHAT_FALLBACK_BASE_URL` and
`CHAT_FALLBACK_MODEL` explicitly enable a fallback. Its API key is optional;
`CHAT_FALLBACK_TIMEOUT_SECONDS` defaults to 180. The bundled lifecycle supports
the requested local Ollama fallback. `CHAT_REQUEST_TIMEOUT_SECONDS` defaults to
240 and covers retrieval plus all generation attempts. Leave fallback identity
fields empty to disable fallback. Malformed partial settings fail validation.

SSE status data contains phase `retrieving` or `generating` and a code-owned
primary/fallback role during generation. Delta data contains `text`. Complete
data is the existing JSON response body; error data contains a public code and
readable retry instruction. Heartbeat comments contain no answer content.
Cancellation and partial failure never initiate another provider attempt.

The native catalog exporter continues to publish only local Ollama selections:
when the primary is external, its explicitly selected Ollama fallback supplies
the local chat declaration. External models are never silently added to the
private inference gateway.
