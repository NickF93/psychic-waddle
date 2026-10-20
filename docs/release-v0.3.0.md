# v0.3.0

Operational release of the portfolio RAG assistant following v0.2.2.

- Support configurable chat-provider timeouts without mixing provider capabilities.
- Recover persistent runtime services after Docker restarts and host reboots.
- Refresh the Nginx API upstream through embedded DNS after container address changes.
- Support opt-in private publication of the configured Ollama chat/embedding selections.
- Export secret-free native model metadata and immutable source provenance.
- Bound every Compose service's container logs and label the built API image.
- Allow retrieval plus bounded generation to finish before the public proxy deadline.
- Preserve deterministic answer policy, reviewed knowledge and privacy boundaries.

## Upgrade and recovery

Build the API from the exact release source. Preserve `.env`, provider selection,
private publication files, knowledge/index data and all persistent volumes.
Use the existing component/public startup scripts and verify `/ready` plus actual
grounded answers after recovery. Restore the prior image/configuration checkpoint
for rollback. See [runtime](runtime.md) and [private publication](private-provider.md).

## Validation status

The candidate passed all 634 tests with real disposable pgvector, public health
and readiness checks, actual grounded workplace answers and sequential host
reboot recovery. A final cold request through the portfolio returned HTTP 200
with verified NAIS/Bonfiglioli evidence in 143.93 seconds. The live CPU provider
uses its existing configurable 180-second deadline; the public RAG edge allows
270 seconds for both embedding phases, generation and handling margin.
Existing model, output bound, knowledge and deterministic answer policy are unchanged.
See the [integrated acceptance record](https://github.com/NickF93/vpn-hub/blob/release/0.1.0/docs/operational-release-acceptance-20261020.md)
for recovery, resources and limitations. Merge, tags, tagged deployment and
publication remain pending.

## Complete implementation history

The complete non-merge implementation history below is recorded through candidate
`25828c6146cebcb2a68e57c8ccb2aaa7dcc04505`. Release stabilization is included.
The [final release comparison](https://github.com/NickF93/psychic-waddle/compare/v0.2.2...v0.3.0) also includes the final acceptance metadata.

- [c748e727](https://github.com/NickF93/psychic-waddle/commit/c748e72716da50db83171e301746352efeff045a) fix(config): make chat provider timeout configurable
- [bba6d015](https://github.com/NickF93/psychic-waddle/commit/bba6d01596b1f1b578e11452ff3b40d2ce05c01d) fix(runtime): recover persistent services after Docker restarts
- [0fd2e226](https://github.com/NickF93/psychic-waddle/commit/0fd2e2264142488a0ab0f0e96ba7fc9cb3ac76f9) fix(nginx): refresh API upstream after container recovery
- [a4f0b300](https://github.com/NickF93/psychic-waddle/commit/a4f0b300562fe406e81866555ec07464d3427cd3) test(intent): make report path check independent of checkout
- [a58ac226](https://github.com/NickF93/psychic-waddle/commit/a58ac226523fa52b7425d848654c5799b7488c7e) docs(runtime): define optional private provider boundary
- [a0ea8276](https://github.com/NickF93/psychic-waddle/commit/a0ea82763c859d48c2c8f64b5dba6d6f62f10e13) feat(runtime): export selected models and support private provider publication
- [fc8042b6](https://github.com/NickF93/psychic-waddle/commit/fc8042b6a9f2bbd46d827eaf0eba34f1b75dff52) chore(release): prepare v0.3.0 operational runtime release
- [8119acbc](https://github.com/NickF93/psychic-waddle/commit/8119acbc62ff7425a33f7e14eb0c8eb2f0787962) test(retrieval): qualify native fusion with a wider candidate window
- [d68ae2bd](https://github.com/NickF93/psychic-waddle/commit/d68ae2bdf4a32353dffc042376c8cb1ccaaf2d16) fix(edge): preserve retrieval and generation response budgets
- [58c7f963](https://github.com/NickF93/psychic-waddle/commit/58c7f9633f1d52824e9efb0b3ba2bb1fb393c22c) fix(edge): include cold intent initialization in response window
- [25828c61](https://github.com/NickF93/psychic-waddle/commit/25828c6146cebcb2a68e57c8ccb2aaa7dcc04505) fix(edge): qualify the measured cold CPU response budget
