# Public Chat API

## Purpose

The public API is the backend boundary for the portfolio chat widget. It accepts
one visitor question, orchestrates the existing authorities, and returns a
public-safe answer, refusal, or clarification.

The API must stay thin. It does not retrieve knowledge, decide answerability,
generate final wording, persist reviewed facts, create embeddings, or collect
visitor questions. Those responsibilities remain owned by the existing
authorities.

## Network Assumption

The application exposes local API routes inside the service container. The
public deployment boundary is owned by the reverse proxy runtime documented in
`docs/public-deployment.md`.

For production, browser JavaScript in the separate portfolio project calls the
public HTTPS API on `vps.madnick.ovh`:

```text
https://vps.madnick.ovh/api/assistant/chat
```

Nginx maps that public route to the local API route:

```text
http://api:8000/chat
```

Allowed browser origins are only:

```text
https://pigreco.xyz
https://www.pigreco.xyz
```

CORS is enforced at the Nginx edge for public deployment. The FastAPI
application does not add wildcard CORS defaults or duplicate edge CORS policy.

The HTTP/bootstrap Nginx edge keeps localhost-safe defaults for local
validation:

```text
http://127.0.0.1:18080/api/assistant/chat
```

The HTTPS runtime edge is enabled after Let's Encrypt certificate setup and
terminates public traffic on port `443`.

Use the public smoke script after deployment to verify the edge route, CORS
preflight, readiness, and the tracked workplace answerability path:

```sh
PUBLIC_SMOKE_BASE_URL=https://vps.madnick.ovh scripts/runtime/public-smoke.sh
```

The ASGI entrypoint is:

```text
portfolio_rag_assistant.api.main:app
```

## Endpoints

### `GET /health`

Returns a lightweight process health response.

Response:

```json
{
  "status": "ok"
}
```

### `GET /ready`

Returns readiness for recruiter-facing exposure. Readiness checks database
access, the expected knowledge schema, and embedding availability for the
configured embedding backend and model. When `QUESTION_COLLECTION_ENABLED=true`,
readiness also checks that the question collection schema exists.

Response:

```json
{
  "status": "ready"
}
```

`/ready` does not call chat or embedding providers. Provider reachability is
checked by the explicit runtime smoke command documented in
`docs/runtime.md`.

### `POST /chat`

Runs the recruiter-facing question flow:

1. `Retriever.retrieve()`
2. `AnswerPolicy.decide()`
3. `AnswerGenerator.generate()`
4. public response mapping

Request:

```json
{
  "question": "Where did Niccolo work?",
  "language": "en"
}
```

Request fields:

- `question`: non-empty visitor question, up to 1000 characters.
- `language`: explicit answer language, either `en` or `it`.

Example public call:

```sh
curl -X POST https://vps.madnick.ovh/api/assistant/chat \
  -H 'content-type: application/json' \
  -H 'origin: https://pigreco.xyz' \
  -d '{"question":"Where did Niccolo work?","language":"en"}'
```

Response:

```json
{
  "status": "answerable",
  "answer": "Niccolo worked at NAIS s.r.l.\n\nSources: Niccolo Ferrari CV.",
  "sources": [
    {
      "title": "Niccolo Ferrari CV",
      "locator": "Experience section"
    }
  ],
  "notices": []
}
```

Response fields:

- `status`: `answerable`, `not_answerable`, or `needs_clarification`.
- `answer`: final public text from the answer generator.
- `sources`: public source references, empty unless the status is
  `answerable`.

Public sources expose only:

- `title`
- optional `locator`

The API does not expose internal source URIs.

Refusal response:

```json
{
  "status": "not_answerable",
  "answer": "I do not have verified public context to answer that reliably.",
  "sources": []
}
```

Clarification response:

```json
{
  "status": "needs_clarification",
  "answer": "I can answer that, but I need a more specific question about experience, education, projects, research, skills, or contact details.",
  "sources": [],
  "notices": []
}
```

## Question Collection Notice

When `QUESTION_COLLECTION_ENABLED=true`, the backend may record the raw question
text only if the final chat status is `not_answerable`. This recording happens
after answer generation and must never change the answer text, answer status, or
source fields.

When recording succeeds, the response includes a machine-readable notice:

```json
{
  "notices": [
    {
      "code": "question_recorded"
    }
  ]
}
```

The separate `pigreco.xyz` frontend owns popup wording, timing, and graphics. It
may consume this notice code to show a non-blocking message. This backend must
not return visitor-facing prose about collection inside the answer text.

Question collection must not store IP addresses, user agents, cookies, session
IDs, frontend identifiers, per-question language, answer status, answer text,
source identifiers, source kinds, retrieval scores, request metadata, or any
browser/network metadata. Stored question records are operator review signals
only and must never automatically become facts, chunks, aliases, or evaluation
cases.

Operator review and deletion are documented in
[Question Review Workflow](question-review.md).

## Limits

Milestone 5 uses simple fixed limits:

- maximum request body size: 4096 bytes;
- maximum question length: 1000 characters.

These limits are abuse controls for the public widget boundary. They are not
analytics and must not create visitor-derived stored data.

## Error Behavior

The API returns stable public errors for invalid input and service failures.

The API must never expose:

- raw stack traces;
- provider-specific error text;
- database connection or query details;
- prompts;
- retrieval scores;
- ranking diagnostics;
- internal source URIs;
- request metadata;
- visitor identity.

## Configuration

Runtime composition uses only explicit environment names:

- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `CHAT_BACKEND`
- `CHAT_BASE_URL`
- `CHAT_API_KEY`
- `CHAT_MODEL`
- `EMBEDDING_BACKEND`
- `EMBEDDING_BASE_URL`
- `EMBEDDING_API_KEY`
- `EMBEDDING_MODEL`
- `RETRIEVAL_TOP_K`
- `RETRIEVAL_MIN_SCORE`
- `INTENT_PROFILES_PATH`
- `QUESTION_COLLECTION_ENABLED`

No aliases, deprecated names, hidden fallbacks, wildcard CORS defaults, or
legacy compatibility paths are allowed.

At runtime, composition builds:

1. the configured `ChatProvider`;
2. the configured `EmbeddingProvider`;
3. the configured intent catalog;
4. `PostgreSQLRetriever`;
5. `DeterministicAnswerPolicy`;
6. `GroundedAnswerGenerator`;
7. `PublicChatService`;
8. the database readiness service;
9. the FastAPI application.

The API layer only adapts HTTP input/output and orchestrates these authorities.
It must not copy prompt text, fallback wording, ranking logic, answerability
logic, provider payload logic, or database query logic.

## Milestone 5 Acceptance

Milestone 5 is accepted when:

- `GET /health` returns a stable health response;
- `GET /ready` returns readiness only when required schema and embeddings are ready;
- `POST /chat` returns public-safe answers through the existing authorities;
- API schemas reject invalid language, blank questions, and oversized input;
- answerable responses expose source title and optional locator only;
- internal scores, prompts, stack traces, provider details, and database details
  do not reach the frontend;
- Milestone 5 itself does not persist visitor questions. Milestone 8 adds only
  the bounded `not_answerable` question collection contract documented above.
