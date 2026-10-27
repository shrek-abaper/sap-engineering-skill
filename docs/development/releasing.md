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

## Local publishing credentials (maintainers)

Publishing tokens are stored in the tools' standard user-level config files —
outside the repository, mode 600, never committed and never passed on a
command line:

| Tool | File | Content |
|---|---|---|
| npm | `~/.npmrc` | `//registry.npmjs.org/:_authToken=<granular publish token>` |
| PyPI | `~/.pypirc` | `[pypi]` / `username = __token__` / `password = pypi-...` |

Set them once with hidden input:

```bash
# npm — replace any existing auth line first
umask 077
grep -v '^//registry.npmjs.org/:_authToken=' ~/.npmrc > ~/.npmrc.tmp
mv ~/.npmrc.tmp ~/.npmrc && chmod 600 ~/.npmrc
read -rs -p "npm token: " T
printf '//registry.npmjs.org/:_authToken=%s\n' "$T" >> ~/.npmrc
unset T

# PyPI
read -rs -p "PyPI token: " T
umask 077
printf '[pypi]\nusername = __token__\npassword = %s\n' "$T" > ~/.pypirc
chmod 600 ~/.pypirc
unset T
```

Guidance:

- npm: use a **granular access token** with *Read and write → Publish* only
  (plus *Bypass 2FA* for unattended publishing), set an expiry, and scope it
  to `sap-adt-cli` once the package exists.
- PyPI: the first upload of a new project needs an account-scoped token;
  replace it with a **project-scoped** token (`sap-adt`) afterwards.
- Rotate the tokens on a schedule and immediately after any exposure
  (chat, logs, screenshots). Files must stay 600 and outside the repo.
- The OS keyring is not usable in this WSL2 setup (`keyring.backends.fail`),
  and twine's keyring integration therefore falls back to prompting.
- After setup, `npm publish` (from `dist/npm/`) and
  `.venv/bin/twine upload dist/release/sap_adt-<ver>*` work non-interactively.

## Versioning

- CLI: `1.4.1` (single source: `pyproject.toml`; runtime/npm/installers
  inherit it).
- Plugin/docs: `1.1.9` (`.claude-plugin/plugin.json`; must equal
  `compatibility.json.plugin_version`).
- The compatibility shims were removed in the 1.4.0 source tree; no released
  artifact ever contained them, so no CLI version bump was required.

## Rollback

- The previous CLI release remains installable by pinning its version.
- The plugin marketplace can be reverted by restoring the previous
  `marketplace.json` entry (previous tag/commit).
- The runtime installer keeps the previous runtime if an upgrade fails.
- User config and keystore entries are never touched by install/uninstall.
