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

Aggregate facts are allowed only when they summarize reviewed public source
material for a real recruiter intent. They must remain source-backed, broad, and
truth-oriented. Do not add a fact just to satisfy one question wording.

For the tracked CV profile, broad aggregates should cover only the supported M9
intent groups when the source supports them:

- workplaces and work history from `Professional Experience`;
- current role and current employer from `Professional Experience`;
- skills, tools, and specializations from the CV skills sections;
- education from `Degrees`;
- publications and research outputs from `Publications and Research Outputs`;
- public research software and repositories from `Research Software`;
- public professional links from `Public profile links`.

Before committing aggregate changes, perform a second pass that maps each broad
aggregate to its source locator and checks that it does not overstate employers,
roles, dates, degrees, papers, repositories, or contact channels. Private CV
fields remain excluded even when they appear in the reviewed source file.

When changing the tracked knowledge:

1. Update `knowledge/profile.json` from reviewed public source material.
2. Run `portfolio-rag-assistant knowledge validate knowledge/profile.json`.
3. Run the tracked knowledge tests.
4. Deploy with `scripts/runtime/public-upgrade.sh` so PostgreSQL and embeddings
   match the committed file.

Milestone 9 requires embedding freshness for changed knowledge. After a public
fact changes, the generated public chunk text changes too. Embedding indexing
must treat any embedding created from the old chunk text as stale for the
configured backend and model, regenerate it, and leave other backend/model
embedding pairs intact.

`scripts/runtime/public-load-knowledge.sh` and
`scripts/runtime/public-upgrade.sh` are the supported operator paths for this
refresh. Destroying PostgreSQL data must not be required just to pick up a
changed tracked profile.
