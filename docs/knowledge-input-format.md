# Knowledge Input Format

## Purpose

The curated knowledge input format is the reviewed, human-controlled source for
portfolio facts before they are inserted into PostgreSQL.

This sprint defines facts only. It does not define ingestion persistence,
chunking, embedding generation, retrieval, answer policy, API behavior, or
visitor question collection.

## Authority Boundary

The input document is truth-oriented, not search-oriented.

- Facts are atomic verified claims.
- Chunks are later deterministic retrieval text derived from facts.
- Embeddings are later vector representations of chunks.
- Vector search must never become the source of truth.

The intended flow is:

```text
curated JSON facts -> deterministic chunks -> chunk embeddings -> retrieval
```

## Curated Sources

A curated source is a reviewed public-profile artifact admitted by the project
owner as evidence for facts.

Allowed source origins for v1:

- CV.
- Portfolio page.
- Thesis summary or thesis-derived reviewed note.
- Publication or research note.
- Project description.
- Manually reviewed public profile note.

A listed source is evidence only. Public answerability is controlled by
`facts.public_visible` and later `chunks.public_visible`; sources do not have a
separate public visibility flag.

## Forbidden Inputs

The knowledge input must never contain:

- private notes;
- unverified claims;
- visitor questions;
- recruiter or visitor identity;
- raw transcripts;
- IP addresses;
- user agents;
- cookies or session identifiers;
- email addresses, phone numbers, photos, or private contact details;
- model-generated facts not manually reviewed by the project owner.

Visitor questions are improvement signals only. They must be reviewed manually
before they influence curated facts, aliases, or evaluation cases.

## JSON Contract

The input file is a JSON object with exactly these top-level fields:

- `schema_version`: currently `1`.
- `sources`: non-empty array of reviewed source records.
- `facts`: non-empty array of fact records.

Example:

```json
{
  "schema_version": 1,
  "sources": [
    {
      "source_uri": "cv://niccolo/main",
      "title": "Niccolo Ferrari CV",
      "reviewed_at": "2026-05-28T00:00:00+00:00"
    }
  ],
  "facts": [
    {
      "source_uri": "cv://niccolo/main",
      "category": "experience",
      "fact_text": "Niccolo worked at NAIS s.r.l.",
      "source_locator": "Experience section",
      "public_visible": true
    }
  ]
}
```

### Source Record

Required fields:

- `source_uri`: stable source identifier, unique inside the document.
- `title`: human-readable reviewed source title.
- `reviewed_at`: timezone-aware ISO 8601 timestamp.

### Fact Record

Required fields:

- `source_uri`: source identifier present in `sources`.
- `category`: one bounded knowledge category.
- `fact_text`: atomic verified claim.
- `public_visible`: explicit boolean.

Optional fields:

- `source_locator`: source-local evidence pointer such as a section name.

Allowed categories:

- `experience`
- `education`
- `projects`
- `research`
- `skills`
- `contact`

## Validation Rules

The parser rejects:

- unsupported `schema_version`;
- unknown top-level, source, or fact fields;
- missing required fields;
- duplicate `source_uri` values;
- facts that reference unknown sources;
- unsupported categories;
- blank text fields;
- missing or non-boolean `public_visible`;
- timezone-naive `reviewed_at` values;
- forbidden visitor-derived fields.

Validation does not prove that a fact is true. It proves only that a reviewed
fact document satisfies the project contract and can map cleanly to the
knowledge schema.

## Milestone 2 Scope

Milestone 2 uses fact-first JSON only. Markdown ingestion is intentionally out
of scope until a later milestone proves that longer reviewed prose is needed.

Embedding indexing is a separate later command. Ingestion writes sources, facts,
and deterministic chunks; embedding indexing reads chunks and writes vectors.
