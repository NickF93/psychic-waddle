# Optional public HTTPS sites

Only the opt-in `deploy/compose.thingsboard.yaml` override mounts this directory.
No site is enabled by default. Operator-rendered `.conf` files are ignored by
Git and excluded from application images. Templates live outside this directory.

See [ThingsBoard HTTPS](../../../docs/thingsboard-https.md) for configuration,
validation, certificate renewal and rollback. Preserve the separate
`private-services` source restrictions; never place a public site there.
