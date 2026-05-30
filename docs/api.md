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

## Endpoints

### `GET /health`

Returns a lightweight process health response.

Response:

```json
{
  "status": "ok"
}
```

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

Runtime composition uses only existing explicit environment names:

- `DATABASE_URL`
- `LLM_BACKEND`
- `LLM_BASE_URL`
- `LLM_API_KEY`
- `CHAT_MODEL`
- `EMBEDDING_MODEL`
- `RETRIEVAL_TOP_K`
- `RETRIEVAL_MIN_SCORE`

No aliases, deprecated names, hidden fallbacks, wildcard CORS defaults, or
legacy compatibility paths are allowed.

## Milestone 5 Acceptance

Milestone 5 is accepted when:

- `GET /health` returns a stable health response;
- `POST /chat` returns public-safe answers through the existing authorities;
- API schemas reject invalid language, blank questions, and oversized input;
- answerable responses expose source title and optional locator only;
- internal scores, prompts, stack traces, provider details, and database details
  do not reach the frontend;
- visitor questions are not persisted.
