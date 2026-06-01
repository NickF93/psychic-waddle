# Knowledge Maintenance

Knowledge maintenance keeps curated profile facts trustworthy before ingestion
or re-indexing.

The checks are deterministic and local. They do not use an LLM, call providers,
connect to PostgreSQL, retrieve, answer questions, or collect visitor data.

## Command

The canonical reviewed public profile knowledge is tracked in Git:

```text
knowledge/profile.json
```

Validate it locally:

```bash
portfolio-rag-assistant knowledge validate knowledge/profile.json
```

Multiple files may be validated together:

```bash
portfolio-rag-assistant knowledge validate knowledge/cv.json knowledge/projects.json
```

The command requires no environment variables.

In the Docker runtime, validate, ingest, and index the tracked profile knowledge
with:

```bash
scripts/runtime/public-load-knowledge.sh
```

Preserving public upgrades run this loader by default through
`scripts/runtime/public-upgrade.sh`.

## Checks

Validation first applies the curated input contract from
`docs/knowledge-input-format.md`.

It rejects:

- malformed JSON.
- unsupported file types.
- unsupported categories.
- facts without source references.
- duplicate source identifiers.
- duplicate facts.
- forbidden visitor, recruiter, or user data fields.

It then applies maintenance QA:

- every source must be referenced by at least one fact.
- at least one fact must be public.
- every public fact must generate one deterministic chunk.
- generated chunks must be public and non-empty.

Source-level public visibility is intentionally not checked in Milestone 2
because public visibility belongs to facts and chunks.

## Boundary

Validation owns only local checks over curated files and deterministic chunk
derivation.

Validation must not decide truth. Human review decides whether a source and fact
are accepted into the curated knowledge base.

## Tracked Knowledge Rules

Committed knowledge must contain only reviewed public facts. It must not contain
private email addresses, phone numbers, WhatsApp links, home addresses,
birthdates, photos, visitor questions, raw transcripts, recruiter-derived raw
records, or unreviewed assumptions.

Visitor question records are improvement signals only. A reviewed operator may
use them to decide that a public source should be curated, but visitor text must
never be copied directly into `knowledge/profile.json` as a fact.

When changing the tracked knowledge:

1. Update `knowledge/profile.json` from reviewed public source material.
2. Run `portfolio-rag-assistant knowledge validate knowledge/profile.json`.
3. Run the tracked knowledge tests.
4. Deploy with `scripts/runtime/public-upgrade.sh` so PostgreSQL and embeddings
   match the committed file.
