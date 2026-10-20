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

This is an M10 release candidate. Final tags, deployment identities, integrated
acceptance and reboot results are recorded by the release gate before publication.
Existing model qualifications remain authoritative; no full-context or all-model
loading campaign is implied by this operational release.

## Complete implementation history

Changes since [v0.2.2](https://github.com/NickF93/psychic-waddle/releases/tag/v0.2.2); [comparison](https://github.com/NickF93/psychic-waddle/compare/v0.2.2...f3697adc04a8f4477e380c64d156e2749f64289d).

- [c748e727](https://github.com/NickF93/psychic-waddle/commit/c748e72716da50db83171e301746352efeff045a) fix(config): make chat provider timeout configurable
- [bba6d015](https://github.com/NickF93/psychic-waddle/commit/bba6d01596b1f1b578e11452ff3b40d2ce05c01d) fix(runtime): recover persistent services after Docker restarts
- [0fd2e226](https://github.com/NickF93/psychic-waddle/commit/0fd2e2264142488a0ab0f0e96ba7fc9cb3ac76f9) fix(nginx): refresh API upstream after container recovery
- [a4f0b300](https://github.com/NickF93/psychic-waddle/commit/a4f0b300562fe406e81866555ec07464d3427cd3) test(intent): make report path check independent of checkout
- [a58ac226](https://github.com/NickF93/psychic-waddle/commit/a58ac226523fa52b7425d848654c5799b7488c7e) docs(runtime): define optional private provider boundary
- [a0ea8276](https://github.com/NickF93/psychic-waddle/commit/a0ea82763c859d48c2c8f64b5dba6d6f62f10e13) feat(runtime): export selected models and support private provider publication
