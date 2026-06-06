# Intent Catalog

`config/intent-profiles.json` is reviewed runtime configuration for deterministic
recruiter-question intent matching. It is not curated portfolio knowledge and
must not be ingested into PostgreSQL.

The catalog owns domain vocabulary only:

- supported recruiter intent identifiers;
- accepted reviewed-knowledge categories for each intent;
- trigger term groups used to recognize supported questions;
- semantic example questions used as embedding anchors for semantic intent
  routing;
- semantic calibration metadata and per-profile semantic thresholds;
- lexical expansion terms used by retrieval;
- required evidence term groups used by answer policy.

The matcher algorithm, normalization rules, rank fusion, semantic resolver,
policy thresholds, and knowledge category enum remain code authorities.

Observed typo variants may be listed as reviewed trigger terms when they are
accepted product vocabulary. For example, `prublications` is intentionally
listed as a publication-question variant.

Role-fit vocabulary must stay bounded to reviewed positive question wording.
For ML, AI, deep-learning, LLM, and computer-vision role-fit coverage, the
catalog lists complete suitability phrases such as `suitable for ml engineer
roles` or `good fit as an ai specialist`. Bare role labels or availability words
must not become triggers by themselves, because actual availability/open-to-work
claims require a reviewed availability fact.

## Runtime Contract

`INTENT_PROFILES_PATH` is the exact runtime configuration name for the catalog
path. In the public Docker runtime it must point to:

```text
config/intent-profiles.json
```

The loader fails fast when the file is missing, invalid JSON, has unknown fields,
has missing fields, defines duplicate intent IDs, uses invalid knowledge
categories, or contains empty term groups.

The application loads the catalog through the composition root and injects the
same catalog authority into retrieval and answer policy. The intent package must
not expose a default catalog, import-time catalog data, mutable registry, or
legacy wrapper functions.

Intent IDs are runtime values owned by the loaded catalog. Moving intent IDs out
of a Python `Literal` trades compile-time enumeration for load-time catalog
validation. Retrieval and policy must receive `QuestionIntent` values produced
by the configured catalog, not raw strings fabricated by consumers.

## JSON Shape

The top-level object must contain exactly:

- `schema_version`: currently `4`;
- `semantic_calibration`;
- `profiles`: non-empty list of profile objects.

`semantic_calibration` must contain exactly:

- `embedding_backend`;
- `embedding_model`;
- `precision_floor`;
- `minimum_required_support`.

Each profile object must contain exactly:

- `intent`;
- `accepted_categories`;
- `trigger_groups`;
- `semantic_example_questions`;
- `semantic_candidate_threshold`;
- `semantic_required_threshold`;
- `lexical_expansion_terms`;
- `required_evidence_groups`.

Each term group is a non-empty list of non-empty strings. Trigger groups and
required evidence groups use positive normalized lexical phrase/group semantics:
every group must be satisfied by at least one term in that group. A single-word
term matches a normalized word. A multi-word term matches the exact normalized
phrase.

`semantic_example_questions` is a non-empty list of reviewed example questions
used as embedding anchors by the semantic intent resolver. They are not visitor
facts and are not written to PostgreSQL.

`semantic_candidate_threshold` is the minimum cosine similarity for a semantic
match to become a candidate intent. `semantic_required_threshold` is either a
reviewed float threshold or `null`. A `null` required threshold means that
semantic matches for that profile remain candidate-only and cannot satisfy the
answerability gate.

## Semantic Resolution

Semantic intent resolution must remain generic:

- resolver code must not branch on concrete intent IDs;
- per-intent semantic thresholds must live in reviewed catalog data;
- semantic matches remain candidate intents unless calibrated evidence proves
  they are precise enough to become required intents.

The runtime embedding backend and model must match `semantic_calibration`.
Mismatch is a hard startup/configuration error. There is no fallback that
silently disables semantic matching or downgrades required thresholds.

The labeled evaluation fixture under `tests/fixtures/` is calibration data, not
runtime configuration. It must remain disjoint from catalog semantic anchors
after intent-text normalization so future threshold calibration does not measure
against the same questions used as embedding anchors. Near-duplicate review is a
manual governance concern.

Semantic threshold calibration is an offline proposal workflow. The
`intent calibrate-semantic` CLI command evaluates the reviewed anchors against a
labeled fixture, writes a near-duplicate review report under `/tmp`, and prints
proposed per-intent thresholds to stdout. It never writes
`config/intent-profiles.json`. A human must review the report and manually
commit any accepted `semantic_required_threshold` values into the catalog.

The labeled fixture is a calibration set, not a held-out test set. Meeting the
configured precision floor on that fixture is a necessary safety floor for
promotion to required intent status, not a generalization guarantee.

## GitHub Ambiguity

GitHub routing is modeled only through positive reviewed trigger groups. GitHub
profile, account, link, or contact wording resolves to the contact intent.
GitHub repository, source-code, or project wording resolves to the projects
intent. Bare GitHub wording is intentionally ambiguous and remains unsupported
unless the catalog later defines a positive reviewed trigger group for it.
