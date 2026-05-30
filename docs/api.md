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

The portfolio website calls this service through a server-side proxy over the
private OpenVPN/tun0 network. Browser JavaScript should call the portfolio
origin, not this API directly.

Milestone 5 does not add CORS middleware. If a future deployment exposes the
API directly to browsers, that change must add explicit allowed-origin
configuration without wildcard defaults.

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
configured embedding backend and model.

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

Example proxied call:

```sh
curl -X POST https://pigreco.xyz/chat \
  -H 'content-type: application/json' \
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
  ]
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
  "sources": []
}
```

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

No aliases, deprecated names, hidden fallbacks, wildcard CORS defaults, or
legacy compatibility paths are allowed.

At runtime, composition builds:

1. the configured `ChatProvider`;
2. the configured `EmbeddingProvider`;
3. `PostgreSQLRetriever`;
4. `DeterministicAnswerPolicy`;
5. `GroundedAnswerGenerator`;
6. `PublicChatService`;
7. the database readiness service;
8. the FastAPI application.

The API layer only adapts HTTP input/output and orchestrates these authorities.
It must not copy prompt text, fallback wording, ranking logic, answerability
logic, provider payload logic, or database query logic.

## Milestone 5 Acceptance

Milestone 5 is accepted when:

- `GET /health` returns a stable health response;
- `GET /ready` returns readiness only when schema and embeddings are ready;
- `POST /chat` returns public-safe answers through the existing authorities;
- API schemas reject invalid language, blank questions, and oversized input;
- answerable responses expose source title and optional locator only;
- internal scores, prompts, stack traces, provider details, and database details
  do not reach the frontend;
- visitor questions are not persisted.
