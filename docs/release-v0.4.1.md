# v0.4.1 — Restore portfolio external generation

## Problem and change

The explicitly selected `minimax/minimax-m3.1-flash:free` disappeared from Kilo's
live model catalog after its launch promotion ended. Direct requests returned
HTTP 404 in about 0.17 seconds; the existing local fallback worked but took
roughly 46–134 seconds depending on residency and output.

Select anonymous `cohere/north-mini-code:free` explicitly in the server settings.
Use the existing generic `openai-reasoning` profile with reasoning off and blank
effort. Retain the 4,096-token output ceiling, 65,536-byte input bound, 15-second
primary timeout and the existing 180-second local fallback. Declare the current
model's 256,000-token context, reserving generation capacity as before.

The live catalog lists zero input/output pricing and no expiration for North;
this is not a guarantee of future availability. Dots3-Note Preview remains a
qualified alternative with a published 31 December 2026 expiry and is not an
automatic secondary target. No paid model or automatic model router is selected.

No application/provider/transport logic, dependency, local retrieval, reviewed
knowledge, evidence policy, widget or fallback configuration changes.

## Qualification and validation

Qualification used the real deployed retrieval/policy/generation boundaries with
process-local target overrides; production settings were unchanged at that point.
Question collection was disabled in these qualification processes.

| Target/check | First answer text | Total | Result |
| --- | --- | --- | --- |
| North English sourced streaming | 7.43 s | 11.09 s | Primary only, four sources |
| North complete JSON work history | n/a | 16.78 s | Approved complete answer, one source |
| North Italian sourced streaming | 0.80 s | 4.87 s | Primary only, four sources |
| Dots3 English sourced streaming | 10.88 s | 12.39 s | Primary only, four sources |

The focused configuration, parameter-mapping, grounding, generation and fallback
suite passed 280 tests. The example's reasoning-off settings are encoded in both
JSON and streaming payloads without effort values. No native GPU/model campaign
or unrelated service update is required.

Final immutable source/image identities, tagged deployment, live browser timings
and cleanup are recorded in the GitHub release assets after the hotfix PR merges.

## Deployment and recovery

Deploy the exact released API image and target settings on nklella only. Back up
the private environment and effective Compose configuration on the server before
applying the five changed primary fields. Retain the prior image/configuration
for rollback. Preserve API credentials, fallback fields, proxy, database, local
models, ThingsBoard, Kafka, volumes and unrelated services. A rollback to v0.4.0
restores the old target and therefore its known fallback-only behavior.

## Complete implementation history

See the [full comparison](https://github.com/NickF93/psychic-waddle/compare/v0.4.0...v0.4.1)
for the configuration hotfix, regression checks and patch release metadata.
