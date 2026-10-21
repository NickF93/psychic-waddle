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
