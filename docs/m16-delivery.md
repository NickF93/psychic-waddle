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

The deployment uses 15 seconds primary, 180 seconds fallback and 240
seconds overall including retrieval. Attempts use the remaining request budget.
For streaming, provider limits bound each upstream wait, allowing a healthy
answer to continue while text arrives. The overall deadline bounds the complete
request. JSON generation bounds the complete provider attempt. The configuration
default for the primary remains 30 seconds; the deployment explicitly selects 15.
`CHAT_MAX_TOKENS` and `CHAT_FALLBACK_MAX_TOKENS` independently bound generation
output, including any provider reasoning tokens. Both default to 384. The free
external deployment uses 2,048 to accommodate its hidden reasoning, while the
local fallback retains 384. Answers are instructed to stay under 120 words.
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

## Qualification and deployment

The accepted configuration uses anonymous OpenAI-compatible generation at
`https://ai-gateway.kilo.ai/api/v1` with the explicitly selected
`minimax/minimax-m3.1-flash:free`. Its catalog advertises zero input/output prices;
there is no credential and no substitution to paid models. Provider/model
selection lives in server configuration, not application branches. The earlier
Liquid candidate was rejected after live truncation and incomplete employer
coverage. Other free candidates returned capacity/rate failures.

Ollama `qwen2.5:3b-instruct` remains the explicit local fallback. Local embeddings,
approved knowledge and deterministic evidence policy remain local. The owner
authorized external generation using public portfolio facts. This authorization
does not imply a provider retention guarantee. The widget retains its original
waiting splash until actual answer text starts; no additional notice is shown.

## Follow-up configuration contract

Primary and fallback retain their existing identity, optional credential, timeout
and `MAX_TOKENS` environment settings. Each accepts `PARAMETER_PROFILE`,
`REASONING_MODE` (default/off/on), optional `REASONING_EFFORT`, `TEMPERATURE`,
`TOP_P`, `INPUT_MAX_BYTES`, `CONTEXT_TOKENS` and `INPUT_TOKENIZER`, under its
existing `CHAT_` or `CHAT_FALLBACK_` prefix. Blank sampling settings are omitted.
`GENERATION_PROFILES_PATH` selects the JSON capability/wire mapping file.
Invalid options or conflicting/unsafe mappings fail at startup. Default OpenAI
capabilities do not assume reasoning support; explicit effort/nested profiles
demonstrate the different protocols. No endpoint/model-specific branching exists
in the adapters or grounding layer.

The configured primary profile supports mandatory reasoning at low effort and
omits unsupported sampling controls. The example ceiling is 4,096 tokens; live
qualification must confirm it before deployment. The local profile keeps 384
output tokens, temperature 0 and its observed 4,096-token context.
Admission counts every message, reserves 256 framing tokens and the full output
ceiling, and independently checks the selected fallback. The external profile
uses conservative UTF-8 size accounting (not exact token usage). Local admission
uses Hugging Face tokenizers and a checksummed Qwen tokenizer pinned in the image;
it performs no request-time download and disables tokenizer truncation/padding.
Oversize input produces `context_limit_exceeded`, without dropping evidence.
JSON and streaming use the same parameter encoder. JSON completions require a
successful stop marker; HTTP errors retain status but exclude upstream bodies.

The API/proxy run from committed source `fe9f738414a96e7c0cd7506a80475677802fd3c3`
on nklella; persistent database/model/certificate volumes are unchanged. The
canonical server checkout remains clean on develop while the feature PR awaits
merge. Source snapshots and the private deployment override are under
`/opt/m16/`; runtime settings and rollback references are mode 0600.

Validation: 720 backend tests passed against disposable real PostgreSQL/pgvector,
with one existing skip. Four independent diff-review cycles completed; confirmed
findings were remediated. Tests exercise fallback exactly once before text,
no fallback after partial text, cancellation, global deadlines, provider stream
limits/finish markers, sentinel filtering, citations, safe retrieval failures
and independently configured primary/fallback budgets through actual API
dispatches. Deployed content checks verify actual employer coverage rather than
merely asserting the wording of the prompt.

The cross-repository live results, timings and exact canary cleanup are recorded
in vpn-hub's `docs/portfolio-assistant-m16-acceptance.md`. The fallback is slower
and has the existing small local model's quality limits; it is a continuity path,
not a quality or latency equivalent to the external primary.
