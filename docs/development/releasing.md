# Releasing

**Nothing in this document is executed by an agent without explicit
authorization.** Remote publishing is a separate, human-approved step.

## Preconditions

1. `tools/check_release.py` passes on a locally built candidate.
2. The working tree is clean and the commit recorded in
   `dist/release/release-manifest.json` is the intended source.
3. Platform claims match `packaging/targets.json` (do not advertise
   unverified targets).

## Order (when authorized)

1. Commit/merge the release state; tag `sap-adt-v<cli_version>` (the CLI
   line) and optionally `plugin-v<plugin_version>`.
2. Publish GitHub Release with the runtime archives, wheel/sdist, npm
   tarball, plugin + skill zips, `SHA256SUMS`, `release-manifest.json`.
3. `npm publish` the staged package (`dist/npm/`), then verify
   `npx <pkg>@<version> install` on a clean machine (Node-only).
4. Upload `PyPI` wheel/sdist, then verify a clean-venv install.
5. Only after the artifacts exist and are verified: point the live
   `.claude-plugin/marketplace.json` at the new archive
   (`source: archive`, real URL + sha256 from
   `release-manifest.json.marketplace_candidate`), bump the plugin version
   when the payload changed, and commit. Never commit placeholder URLs or
   digests, and never point the marketplace at a file that is not yet
   uploaded.
6. Announce the minimum Claude Code version for archive sources
   (≥ 2.1.224, verified against the official marketplace reference).

## Versioning

- CLI: `1.4.0` (single source: `pyproject.toml`; runtime/npm/installers
  inherit it).
- Plugin/docs: `1.1.0` (`.claude-plugin/plugin.json`; must equal
  `compatibility.json.plugin_version`).
- Removing the compatibility shims later is a CLI 2.0.0 change (it breaks
  direct `scripts/sap_adt_cli.py` users).

## Rollback

- The previous CLI release remains installable by pinning its version.
- The plugin marketplace can be reverted by restoring the previous
  `marketplace.json` entry (previous tag/commit).
- The runtime installer keeps the previous runtime if an upgrade fails.
- User config and keystore entries are never touched by install/uninstall.
