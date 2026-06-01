# Question Review Workflow

## Purpose

Milestone 8 adds a backend-only improvement loop for unanswered recruiter
questions.

Collection happens after the normal chat response has already been generated.
It never changes answer text, answer status, sources, or answerability.

The stored record is intentionally small:

- raw unanswered question text;
- operator-owned review state;
- operator-owned review category;
- operator-owned review note;
- timestamps.

The application must not store IP addresses, user agents, cookies, session
identifiers, frontend identifiers, per-question language, answer status, answer
text, source identifiers, source kinds, retrieval scores, browser metadata, or
request metadata.

## Runtime Enablement

Question collection is explicit:

```env
QUESTION_COLLECTION_ENABLED=false
```

Set it to `true` only when the operator wants to record raw text for
`not_answerable` responses:

```env
QUESTION_COLLECTION_ENABLED=true
```

Disabled collection writes nothing. If enabled collection fails, the user still
receives the normal chat response and no collection notice is returned.

## Frontend Notice Contract

The backend exposes a machine-readable notice only after successful collection:

```json
{
  "notices": [
    {
      "code": "question_recorded"
    }
  ]
}
```

The `pigreco.xyz` frontend owns popup text, graphics, timing, and dismissal.
The frontend should treat this notice as non-blocking. It must not expect the
answer body to contain visitor-facing collection prose.

No notice is returned when collection is disabled, when the response is
`answerable` or `needs_clarification`, or when storage fails.

## Review Commands

Run commands from the repository root through the API container when using the
Compose runtime.

List pending questions:

```sh
docker compose --env-file .env run --rm api \
  portfolio-rag-assistant questions list --state pending
```

Show one record:

```sh
docker compose --env-file .env run --rm api \
  portfolio-rag-assistant questions show 1
```

Mark a reviewed missing fact:

```sh
docker compose --env-file .env run --rm api \
  portfolio-rag-assistant questions mark 1 \
  --state reviewed \
  --category missing_fact \
  --note "Add this only after a reviewed public source is curated."
```

Ignore spam or off-topic questions:

```sh
docker compose --env-file .env run --rm api \
  portfolio-rag-assistant questions mark 1 \
  --state ignored \
  --category spam \
  --note "Not useful for the public portfolio assistant."
```

Export review records as JSON Lines:

```sh
docker compose --env-file .env run --rm api \
  portfolio-rag-assistant questions export --format jsonl
```

Delete one raw record:

```sh
docker compose --env-file .env run --rm api \
  portfolio-rag-assistant questions delete 1
```

Open the local terminal review mode:

```sh
docker compose --env-file .env run --rm api \
  portfolio-rag-assistant questions review
```

The terminal review mode shows recent records, accepts a question id, and can
mark records as reviewed, mark records as ignored, add category/note fields, or
delete the raw record.

## Categories

Allowed review categories are:

- `missing_fact`: useful answer gap that needs a reviewed public source.
- `alias`: useful alternate wording for an existing public concept.
- `eval_case`: useful future evaluation question.
- `unclear`: too ambiguous to act on directly.
- `off_topic`: outside the supported public-profile domains.
- `private_data`: contains private or inappropriate personal data.
- `spam`: abuse or meaningless input.
- `other`: useful but not covered by the categories above.

## Promotion Rules

Question records never become knowledge automatically.

For `missing_fact`, the operator must:

1. Find or create a reviewed public source.
2. Add the fact to the curated knowledge input file.
3. Validate the knowledge file.
4. Ingest it.
5. Re-index embeddings.
6. Delete or mark the original question record after review.

For `alias` or `eval_case`, use the exported question only as an operator
signal. A future explicit milestone may add alias or evaluation datasets. Until
then, question records must not be ingested as facts, chunks, or sources.

## Retention

Manual deletion is the retention policy.

Raw records remain until the operator deletes them. If a visitor writes personal
data inside the question text, it is stored as part of the raw text and must be
removed manually when reviewed.

Use delete for records that are not useful or should not be retained:

```sh
docker compose --env-file .env run --rm api \
  portfolio-rag-assistant questions delete 1
```
