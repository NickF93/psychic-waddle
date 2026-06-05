# Intent Catalog

`config/intent-profiles.json` is reviewed runtime configuration for deterministic
recruiter-question intent matching. It is not curated portfolio knowledge and
must not be ingested into PostgreSQL.

The catalog owns domain vocabulary only:

- supported recruiter intent identifiers;
- accepted reviewed-knowledge categories for each intent;
- trigger term groups used to recognize supported questions;
- lexical expansion terms used by retrieval;
- required evidence term groups used by answer policy.

The matcher algorithm, normalization rules, rank fusion, policy thresholds, and
knowledge category enum remain code authorities.

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

- `schema_version`: currently `2`;
- `profiles`: non-empty list of profile objects.

Each profile object must contain exactly:

- `intent`;
- `accepted_categories`;
- `trigger_groups`;
- `lexical_expansion_terms`;
- `required_evidence_groups`.

Each term group is a non-empty list of non-empty strings. Trigger groups and
required evidence groups use positive normalized lexical phrase/group semantics:
every group must be satisfied by at least one term in that group. A single-word
term matches a normalized word. A multi-word term matches the exact normalized
phrase.

## GitHub Ambiguity

GitHub routing is modeled only through positive reviewed trigger groups. GitHub
profile, account, link, or contact wording resolves to the contact intent.
GitHub repository, source-code, or project wording resolves to the projects
intent. Bare GitHub wording is intentionally ambiguous and remains unsupported
unless the catalog later defines a positive reviewed trigger group for it.
