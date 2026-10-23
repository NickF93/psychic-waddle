# M16 delivery contract

Extend the existing provider boundary for incremental OpenAI-compatible and
Ollama chat. Credentials are optional server-side configuration. Primary and
fallback endpoints/models are explicit; no provider names are embedded in code.
One fallback attempt is permitted only before visible text, after provider
failure. An insufficient-evidence answer never triggers fallback.

For streaming, visibility means non-whitespace rendered answer text, using the
widget's safe Markdown syntax. Delivery buffers empty headings/lists/quotes,
fences without code, reference definitions and whitespace-only text. A failed
primary's buffered prefix is discarded before fallback. A successful completion
with no rendered text is an empty provider response and may use the same one
fallback attempt. Literal punctuation that renders as text counts as visible;
once such text is emitted, fallback remains disabled. Grounding still owns
sentinel suppression and insufficient-evidence classification. JSON delivery is
unchanged.

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
external deployment uses 4,096 with reasoning explicitly disabled; the
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

The current configuration uses anonymous OpenAI-compatible generation at
`https://ai-gateway.kilo.ai/api/v1` with the explicitly selected
`cohere/north-mini-code:free`. On 24 October its live catalog lists zero
input/output prices, a 256,000-token context and no published expiration date.
This is not an availability guarantee. No credential or automatic model router
is configured; paid models are never substituted.

The initial `minimax/minimax-m3.1-flash:free` selection was removed from the live
catalog after its launch promotion ended. Requests returned HTTP 404 and correctly
used the local fallback. Hotfix v0.4.1 explicitly replaces that target after real
RAG streaming qualification. North uses the existing `openai-reasoning` profile,
`CHAT_REASONING_MODE=off`, blank effort and a 4,096-token generation ceiling.
Its context declaration is 256,000 tokens; the 65,536-byte input limit remains.
Dots3-Note Preview also passed the same qualification but was not selected; its
catalog lists an expiration of 31 December 2026. Provider selection remains
operator configuration, not branching in the application or adapters.

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

The original MiniMax target used mandatory reasoning at low effort; the current
North target uses the existing generic mapping with reasoning disabled and no
effort value. Sampling controls remain unset. The 4,096-token output ceiling is
retained and was exercised in the replacement qualification. The local profile
keeps 384 output tokens, temperature 0 and its observed 4,096-token context.
Admission counts every message, reserves 256 framing tokens and the full output
ceiling, and independently checks the selected fallback. The external profile
uses conservative UTF-8 size accounting (not exact token usage). Local admission
uses Hugging Face tokenizers and a checksummed Qwen tokenizer pinned in the image;
it performs no request-time download and disables tokenizer truncation/padding.
Oversize input produces `context_limit_exceeded`, without dropping evidence.
JSON and streaming use the same parameter encoder. JSON completions require a
successful stop marker; HTTP errors retain status but exclude upstream bodies.

The API runs committed source `1a6917de059f68a5df8f1da9f62e73b614474bf7`, image
`portfolio-rag-assistant:m16-1a6917de059f`, on nklella. The existing proxy remains
on its initial M16 source and mounts; database/model/certificate volumes are unchanged. The
canonical server checkout remains clean on develop while the feature PR awaits
merge. Source snapshots and the private deployment override are under
`/opt/m16/`; runtime settings and rollback references are mode 0600.

Follow-up validation: 785 tests passed against disposable real PostgreSQL/pgvector,
with no skips. One paired independent review used GPT-6.1-Sol high and owner-
authorized OpenCode Go Kimi K3 high in place of quota-blocked Claude. Confirmed
packaging, Markdown-prefix, input-variable diagnostics and obsolete-state findings
were remediated and retested. Initial M16's four review cycles remain historical
evidence. Tests exercise fallback exactly once before text,
no fallback after partial text, cancellation, global deadlines, provider stream
limits/finish markers, sentinel filtering, citations, safe retrieval failures
and independently configured primary/fallback budgets through actual API
dispatches. Deployed content checks verify actual employer coverage rather than
merely asserting the wording of the prompt.

The actual installed wheel and final container resolve packaged profiles; embedding
I/O does not load chat configuration. Image builds exercise profile and tokenizer
access as the unprivileged runtime user. The tokenizer directory is traversable
and its checksummed file read-only. The operational smoke command reuses the
configured controls/input guard instead of fixed temperature/eight-token settings.
Startup errors identify the actual primary/fallback input-limit variable.

Isolated live API acceptance verified primary-only, Ollama-only and one real
connection-failure fallback (134.588s complete, 70.668s first text). Ollama-only
completed in 70.907s, first text 14.098s. The final image returned explicit JSON
503 and SSE `context_limit_exceeded` before inference; unsupported reasoning was
rejected with networking disabled. Public JSON/SSE answers, citations, paper
status and the deployed operational smoke passed. Context framing accounting is
conservative, not a claim of exact MiniMax token usage.

The cross-repository live results, timings and exact canary cleanup are recorded
in vpn-hub's `docs/portfolio-assistant-m16-acceptance.md`. The fallback is slower
and has the existing small local model's quality limits; it is a continuity path,
not a quality or latency equivalent to the external primary.

## Rendered-text fallback correction — 21 October 2026

The subsequent supplied review reproduced a backend/widget mismatch: Markdown
structure alone counted as visible backend output. The correction above covers
failed and renderer-empty successful streams, while retaining grounding-owned
insufficiency and the no-fallback-after-visible-output rule.

Source `b05bc492c8d9677d3c9f5aa73bf1b627648eb430` is deployed on nklella as
`portfolio-rag-assistant:m16-b05bc492c8d9` (image
`sha256:ff81441aa8a0e181fa5dea02d1314840bea2c509fa72dca01afa035dff6d44d5`).
The full real-PostgreSQL/pgvector suite passed: 858 tests, no skips. Installed
wheel, explicit dependency and unprivileged image checks passed. The frontend's
38 Chromium cases include ten new real-backend desktop/mobile integration cases;
eight Node tests passed. Actual public desktop/mobile answers streamed before
completion, returned both workplace facts with citations, and had no page errors.
The deployed runtime smoke and health/readiness passed. Only the API was replaced;
five other containers kept IDs/start times. Production question rows stayed
119 → 119. The task-labelled test database and remote scratch were removed;
active runtime source/image and protected rollback remain. No home host was used.
The existing PRs remain unmerged pending owner authorization.
