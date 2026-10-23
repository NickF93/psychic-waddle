# v0.4.0

Coordinated release of the integrated platform changes since v0.3.0.

## Delivered changes

- Refresh reviewed portfolio facts and keep deterministic evidence approval and retrieval local.
- Support Ollama-only, OpenAI-compatible-only and explicit external-to-local fallback generation through separate strategy, protocol and transport responsibilities.
- Normalize per-target reasoning, effort, output limits, temperature and top-p with capability validation and shared JSON/stream mapping.
- Enforce input budgets and complete-response semantics, retain structured provider errors and expose sanitized timing/fallback diagnostics.
- Stream approved answers, buffer non-rendering Markdown prefixes and allow one fallback only before visible answer text.
- Serve ThingsBoard HTTPS through the existing proxy with renewal and WebSockets while retaining the exact RAG routes and existing port 8080 access.

## Upgrade and recovery

Deploy the exact tag with the existing public runtime commands, preserving private environment, reviewed knowledge/index, database, local Ollama volumes and selected provider settings. Keep the existing ThingsBoard/Kafka images and state. External credentials remain server-side; no model/provider substitution is part of this release. Retain prior API/proxy images and private checkpoints.

## Validation and publication

Release-candidate checks were completed under Issue #63:

- Backend suite: 872 passed against disposable pgvector, including the seven opt-in native Docker/proxy cases.
- Cross-repository headless Chromium assistant/backend tests: 38 passed.
- Ruff reports 99 inherited findings. The same Ruff version/settings report exactly the same findings against the unchanged integrated base: zero added or removed. No Python source/tests changed in this release candidate.
- Live provider streaming, insufficient-evidence behavior and ThingsBoard HTTPS checks remain pending tagged deployment.

See the [coordinated acceptance record](https://github.com/NickF93/vpn-hub/blob/release/0.2.0/docs/coordinated-release-acceptance-20261024.md) for scope, exclusions and
publication gates. This candidate does not claim a published tag or final tagged
deployment. Exact released commit/image identities and live acceptance belong in
the final GitHub release manifest after the release PR is approved and merged.

Native validation is limited to a quick loading/switching smoke on .2 and .7,
restoring their previous residency. Existing matching model qualification remains
authoritative; no context policy, reasoning policy, placement tuning or model
campaign is introduced. Printer acceptance does not actuate or update a printer.

## Complete implementation history

The following non-merge history covers v0.3.0 through integrated candidate
`76903abb43b078a2941d35a02c3e3fb6a455247b`. The [full release comparison](https://github.com/NickF93/psychic-waddle/compare/v0.3.0...v0.4.0) also includes release stabilization.

- [69df57e4](https://github.com/NickF93/psychic-waddle/commit/69df57e4bc64fde452f738d711704bb866e9dad5) feat(knowledge): refresh verified CV and research facts
- [9e4f8aef](https://github.com/NickF93/psychic-waddle/commit/9e4f8aef152407df0c58d1175e83eb10cbcfca27) fix(knowledge): make reviewed facts intent-complete
- [87ef5d22](https://github.com/NickF93/psychic-waddle/commit/87ef5d2286a6f4d116144134cf20215c93a0b267) fix(knowledge): reconcile current CV dates and projects
- [c60b7aed](https://github.com/NickF93/psychic-waddle/commit/c60b7aed9ac4c1ceb7b9228cf3c65d6497cb69d0) fix(knowledge): keep contribution facts retrievable
- [608079ca](https://github.com/NickF93/psychic-waddle/commit/608079ca44454ac4ddad0802d7af94286fc09201) fix(knowledge): identify the journal submission as a paper
- [742f0fcd](https://github.com/NickF93/psychic-waddle/commit/742f0fcd55fe34685f064cb16860793399bafe72) fix(answers): preserve item statuses and spoken-language routing
- [00727220](https://github.com/NickF93/psychic-waddle/commit/007272202e3fbf9002d8f77b05af1bac4db27c42) fix(knowledge): reflect current open GRD-Net contribution; Refs: #57
- [399d6abf](https://github.com/NickF93/psychic-waddle/commit/399d6abf131635055130a0f9c517df622504a3cf) fix(knowledge): make GMT paper evidence self-contained; Refs: #57
- [9bc7f67e](https://github.com/NickF93/psychic-waddle/commit/9bc7f67ec7d048518c966ae78c4ee56a7f7b171e) docs(profile): record M11 native acceptance and cleanup; Refs: #57
- [00c44856](https://github.com/NickF93/psychic-waddle/commit/00c44856ab4ddbfd868c156985369319bf11bbeb) docs(profile): distinguish final M11 integration from initial acceptance; Refs: #57
- [cafbe194](https://github.com/NickF93/psychic-waddle/commit/cafbe1945efb575e31cf92f5b1ef8e0ad230a378) fix(intent): separate spoken languages from language-model research; Refs: #57
- [cdb07160](https://github.com/NickF93/psychic-waddle/commit/cdb07160de860574294982df1abf5a13e31b0155) docs(architecture): define bounded streaming and fallback
- [f3dcb2a0](https://github.com/NickF93/psychic-waddle/commit/f3dcb2a04a80e363b311878cfd7fedb6aa2ebb6b) feat(provider): support bounded native and compatible streams
- [e1d45627](https://github.com/NickF93/psychic-waddle/commit/e1d45627305457201b4ec317185b0ff1e7563c54) feat(answer): add explicit bounded fallback and provisional delivery
- [d1583162](https://github.com/NickF93/psychic-waddle/commit/d1583162c36152ce9c8f2a372d5f66bb284413a7) feat(api): negotiate grounded streams with bounded request lifetime
- [b2631b18](https://github.com/NickF93/psychic-waddle/commit/b2631b18f370d8e2f8d702d4ec896b189ff69f77) feat(runtime): provision local fallback and streaming delivery
- [41683c82](https://github.com/NickF93/psychic-waddle/commit/41683c82306e3ed5f85a843aa4cad61bcf8e81c3) fix(streaming): bound upstream waits and terminate retrieval failures safely
- [9322519d](https://github.com/NickF93/psychic-waddle/commit/9322519da270a5eb628bc2a26cab63202c8f8d38) fix(generation): configure independent model response budgets
- [0a3ec98e](https://github.com/NickF93/psychic-waddle/commit/0a3ec98eca77d512c0035badff78781ade2bede4) test(generation): verify configured budgets reach inference dispatch
- [fe9f7384](https://github.com/NickF93/psychic-waddle/commit/fe9f738414a96e7c0cd7506a80475677802fd3c3) fix(grounding): preserve employer and role coverage in concise answers
- [793ee83d](https://github.com/NickF93/psychic-waddle/commit/793ee83d87eb8b5c26a7b895c6530e7618e090f7) docs(acceptance): record qualified free generation and deployed gates
- [c1c90549](https://github.com/NickF93/psychic-waddle/commit/c1c90549846f8489fd0109291f965ce7d199b4ab) feat(generation): isolate delivery and validate target controls
- [f94b13db](https://github.com/NickF93/psychic-waddle/commit/f94b13dbaa4a3466bff72eb90453f965cc11aff4) fix(packaging): ship profiles and decouple embedding setup
- [357b6e10](https://github.com/NickF93/psychic-waddle/commit/357b6e106491f7e2307861c1bbf19761f1b88a1d) fix(container): expose pinned tokenizer to the app user
- [dbf061af](https://github.com/NickF93/psychic-waddle/commit/dbf061afa38682906758b47b8f902c888da26e45) fix(container): verify installed resources as runtime user
- [92505c08](https://github.com/NickF93/psychic-waddle/commit/92505c08c3949bfe896d800ba20bcbb3d305bbb5) fix(runtime): reuse target controls in provider smoke checks
- [1a6917de](https://github.com/NickF93/psychic-waddle/commit/1a6917de059f68a5df8f1da9f62e73b614474bf7) fix(config): identify input limits and remove obsolete state
- [06efdbdb](https://github.com/NickF93/psychic-waddle/commit/06efdbdb0a4e85c1f43e3066692c3ff99655f1b0) docs(acceptance): record reviewed M16 follow-up deployment
- [b05bc492](https://github.com/NickF93/psychic-waddle/commit/b05bc492c8d9677d3c9f5aa73bf1b627648eb430) fix(delivery): align pre-visible fallback with rendered Markdown
- [fab4cd0d](https://github.com/NickF93/psychic-waddle/commit/fab4cd0dc54017b013108a34fac8cc95d8067285) docs(acceptance): record rendered-text fallback deployment
- [3c7a9547](https://github.com/NickF93/psychic-waddle/commit/3c7a9547ede68487258832b28dcfffc2fb521258) feat(proxy): add opt-in shared-host ThingsBoard HTTPS routing
- [e876eb07](https://github.com/NickF93/psychic-waddle/commit/e876eb0763f80116746081aaa70522def849be92) fix(edge): redact redirect paths and renew all managed certificates
- [fa7c53b4](https://github.com/NickF93/psychic-waddle/commit/fa7c53b485a99caf53118254d76bca25754e74c7) fix(tls): reload successful renewals after partial failure
- [8da61951](https://github.com/NickF93/psychic-waddle/commit/8da61951d1ccb2fefe5dfeeb3e89fd659d8487f6) style(proxy): remove trailing blank line from shared snippet
