# Platform M11 — Reviewed profile refresh

21 October 2026. This is the platform roadmap's portfolio/research refresh,
not a renumbering of this repository's earlier implementation milestones.

## Knowledge and provenance

The reviewed corpus contains six sources and 123 public facts/chunks. The
canonical no-photo CV supplies the corrected Applied Soft Computing submission
status, precise NAIS contribution responsibility, English fluency, DBGA dates,
research supervision and public project facts. Source papers supply the reviewed
MH-PatchCore and GMT descriptions. The anomalib PR/release records independently
support the software contribution claims: MH-PatchCore is included in v2.7.0;
GRD-Net remains open, unmerged PR #3812. The final primary-source check found
that it had left draft status; both the fact and source title were refreshed.
Submission is not journal acceptance, and a reviewed manuscript update is not a
new uploaded arXiv version.

Public professional facts are selected explicitly. Personal contact details,
birthdate, home address, private editorial correspondence and visitor questions
were not imported. No runtime ingestion of a whole CV or private manuscript was
introduced. The source file remains `knowledge/profile.json`.

New paper/software facts must satisfy both the existing intent-evidence rules
and their lexical expansion vocabulary. A regression reproduced a contribution
fact that passed policy evidence but could not enter intent-expanded retrieval;
the fact now describes its software/source-code context explicitly. The existing
skills intent also recognizes spoken-language questions, using its existing
evidence boundary. The generic grounding prompt preserves each compared item's
individual review/release status in separate bullets. No scoring rule, evidence
threshold, provider or API contract changed.

## Deployment and qualification

Initial nklella API acceptance used an image built from
`399d6abf131635055130a0f9c517df622504a3cf`. The existing explicit loader validates,
ingests and indexes the committed file through the existing Compose services.
Native readback checks every persisted fact against Git, all 123 embeddings and
zero stale content hashes. PostgreSQL data, genuine question records and the
existing model/provider remain intact.

A semantic live check rejected an answer that described GMT as a graph neural
network while citing only CV citation records. Its reviewed technical facts now
include the public author/title/arXiv identifier as self-contained context;
native retrieval and the generated explanation are checked independently.
The corrected architecture fact ranks first in the original four-chunk window.
The final generated explanation preserves causal self-attention, graph-memory
navigation and gated displacement, with the paper summary cited.

The deployed `RETRIEVAL_TOP_K` remains 4. Early curation omitted the journal
fact from that window. Trials at 12 and 8 were rejected after broader software
answers exceeded the existing 180-second CPU provider limit. The final fix
identifies the paper submission and software/source-code contributions explicitly
within the existing intent vocabulary. Native readback now ranks the journal
fact first and includes both contribution statuses within four chunks. Portable
defaults, retrieval algorithm, model and timeouts are unchanged. This is not a
guarantee that every possible question completes within that limit; failures
stay bounded.

Rollback retains the previous M10 images, source and private runtime environment,
plus an operator checkpoint of only sources, facts, chunks and embeddings. A
data rollback must restore those knowledge tables together; re-ingesting an old
file alone does not remove sources absent from that batch. Preserve the separate
question-events table and genuine application data. No database reset, new
backup service or recovery framework was introduced.

## Checks and review

- Full locked suite: 641 tests pass, including real disposable PostgreSQL/pgvector;
  the exact test container/storage is removed in a finally block.
- Ruff and whitespace checks pass. Knowledge validation confirms source-backed,
  public-only, non-empty chunks. Tests cover current CV facts, primary
  contribution provenance, accurate limitations and existing intent eligibility.
- Two paired read-only diff-review cycles completed. The website's confirmed
  comparator ambiguity was corrected. Later curation, intent-vocabulary and
  grounding-prompt follow-ups from live acceptance were checked locally and
  natively; a third independent
  review was not run because the owner capped the loop at two cycles.

Final native API checks pass the distinct software statuses (139.79 seconds),
Italian/English fluency (101.17 seconds) and corrected GMT explanation (133.73
seconds). These are observed CPU timings, not latency guarantees.

The final mobile browser question explicitly asks for the journal and acceptance
status: ASOC and no announced acceptance are returned with sources in 88.311
seconds. Pending/disabled-send/close interaction passes. An earlier status-only
question returned the correct acceptance status but omitted the venue; its
failed venue assertion is retained, and no production code or assertion was
changed to hide that result. Unsupported questions are refused without sources;
empty input receives a readable 422 error.

All three exact canary question records were removed. The 119 genuine question
IDs/count were preserved, and no canary question remains. Integrated platform
fixtures were also removed: two users, one account/key, one conversation and
three sessions; synthetic usage was subtracted exactly and removed access is
denied. Disposable database/build/render/download artifacts and unused M11
images/sources were removed. Active deployment and M10 rollback identities remain.
All running services were healthy after cleanup; the existing indexer reported
zero remaining embeddings. Implementation and deployed acceptance passed.
[PR #58](https://github.com/NickF93/psychic-waddle/pull/58) records integration;
its GitHub merge record is authoritative for the resulting commit.

## Merged-source deployment

The owner separately approved merging this PR into `develop`, synchronizing the
local and nklella checkouts, and rebuilding the API from that merged commit.
The operator deployment receipt records the exact source commit, immutable image
identity, revision label and effective Compose configuration. Runtime configuration
comes from the merged source while existing secrets, certificates, provider
settings, databases and unrelated services are preserved.

Use the existing explicit loader and confirm all reviewed facts match Git, no
embedding is stale and repeat indexing is idle. Repeat real public assistant
acceptance, including supported factual answers, refusal and validation errors;
clean only exact canaries. The prior observations above remain historical evidence,
not a claim that the earlier feature image is the final integration deployment.

Final integration review reproduced a spoken-language alias collision: the bare
word `language` made supported GMT language-model research require unrelated
skills evidence. The two broad aliases were narrowed to personal-language
question phrases. Regression checks preserve spoken-language answers and confirm
that language-model research remains answerable from publication evidence alone;
no policy evidence threshold or semantic resolution rule changed.
