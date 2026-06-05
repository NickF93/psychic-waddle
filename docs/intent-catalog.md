# Intent Catalog

`config/intent-profiles.json` is reviewed runtime configuration for deterministic
recruiter-question intent matching. It is not curated portfolio knowledge and
must not be ingested into PostgreSQL.

The catalog owns domain vocabulary only:

- supported recruiter intent identifiers;
- accepted reviewed-knowledge categories for each intent;
- trigger term groups used to recognize supported questions;
- lexical expansion terms used by retrieval;
- required evidence term groups used by answer policy;
- the frozen GitHub/contact disambiguation word list retained for Sprint 11.1.

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

## JSON Shape

The top-level object must contain exactly:

- `schema_version`: currently `1`;
- `profiles`: non-empty list of profile objects;
- `frozen_disambiguation`: Sprint 11.1 frozen behavior data.

Each profile object must contain exactly:

- `intent`;
- `accepted_categories`;
- `trigger_groups`;
- `lexical_expansion_terms`;
- `required_evidence_groups`.

Each term group is a non-empty list of non-empty strings. Trigger groups and
required evidence groups use the existing normalized lexical matcher: every group
must be satisfied by at least one term in the group.

## Sprint 11.1 Frozen Branch

Sprint 11.1 intentionally retains the current GitHub/contact disambiguation
branch as frozen behavior: a contact profile match containing `github` is skipped
when project-context words are also present. The branch exists only to preserve
behavior during the catalog migration. Sprint 11.3 removes this branch and
models ambiguity through positive reviewed trigger groups.
