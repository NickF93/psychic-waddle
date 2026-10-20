# Changelog

## v0.3.0

Operational release of the portfolio RAG assistant following v0.2.2.

- Apply the qualified 60-second chat timeout without mixing provider capabilities.
- Recover persistent runtime services after Docker restarts and host reboots.
- Refresh the Nginx API upstream through embedded DNS after container address changes.
- Support opt-in private publication of the configured Ollama chat/embedding selections.
- Export secret-free native model metadata and immutable source provenance.
- Bound every Compose service's container logs and label the built API image.
- Preserve deterministic answer policy, reviewed knowledge and privacy boundaries.

See the [complete release history and recovery notes](docs/release-v0.3.0.md).

Previous releases: [GitHub Releases](https://github.com/NickF93/psychic-waddle/releases).
