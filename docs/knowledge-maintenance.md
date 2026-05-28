# Knowledge Maintenance

Knowledge maintenance keeps curated profile facts trustworthy before ingestion
or re-indexing.

The checks are deterministic and local. They do not use an LLM, call providers,
connect to PostgreSQL, retrieve, answer questions, or collect visitor data.

## Command

```bash
portfolio-rag-assistant knowledge validate knowledge/profile.json
```

Multiple files may be validated together:

```bash
portfolio-rag-assistant knowledge validate knowledge/cv.json knowledge/projects.json
```

The command requires no environment variables.

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
