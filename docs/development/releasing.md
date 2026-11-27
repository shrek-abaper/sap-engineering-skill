# Releasing

**Nothing in this document is executed by an agent without explicit
authorization.** Remote publishing is a separate, human-approved step.

CLI **1.6.7** / plugin/docs **1.3.8** adds the Watt brand and compatible
`sap-watt` Python/npm entry packages, not new SAP authorization. Core and
entry versions share `pyproject.toml`; build Python core with `python -m build`,
then the entry with `tools/build_watt.py`. `tools/build_npm.py` stages both npm
packages and `tools/build_manifest.py` lists both wheels, sdists and npm tarballs.
Use only current-version artifacts listed in that manifest.

Publishing order for this transition: first publish and verify the GitHub
native assets; then publish the Python `sap-adt-cli` core before its exact-version
`sap-watt` dependent entry. Publish each npm package from its own staging tree
(`dist/npm`, `dist/npm-watt`) after runtime URLs are live, and verify both public
installs. Do not publish an empty package merely to reserve a name. The new
package owns only `sap-watt`; no default bare `watt` executable is installed.
Keep native filenames, tag prefix, Windows AppId and existing configuration.
Only switch marketplace after its new archive is live and checksum-verified.

CLI **1.6.6** / plugin/docs **1.3.7** adds atomic-executor
target expectations, explicit JSON normalization, enhancement metadata and
bounded impact, Unit gates/evidence, diagnosis packages, transport analysis,
single-entity configuration comparisons, quality bridges, local Git/TR mappings
and verified requirement evidence assembly. It neither embeds LLM orchestration
nor invokes a SAP abapGit serializer. Native coverage is not claimed; supplied
coverage/lint execution is not attested. See the Skill's `references/executor.md`.
The release procedure below gates tagging, publication and marketplace switching.

CLI **1.6.5** / plugin/docs **1.3.6** adds Unit regression/JUnit, typed local
functions, Report selections/variants, expanded DDIC/RAP lifecycle and reviewed
multi-object development. Isolated DEV acceptance verified these workflows and
cleanup; the backend's dangerous-Unit risk ceiling remains in force. Physical
Table activation, service publication and non-local transport mutation are not
claimed live-certified. See the Skill's `references/core-workflows.md`.
CLI 1.6.4 / plugin/docs 1.3.5 added Class source parts, candidate-buffer
checks, controlled basic-object creation and read-only RAP/OData evidence.
Snippet execution now needs only `allow_execute`; its invocation-owned
temporary-Class lifecycle does not enable generic source writes.
CLI 1.6.3 / plugin/docs 1.3.4 added controlled Class, Report and
temporary-Class snippet execution, including local function/BAPI calls.
Independent execution permission and reviewed-plan confirmation apply;
unknown execution is never replayed. CLI 1.6.2 / plugin/docs 1.3.3 added
dynamic REST2RFC Gateway guidance to the integration wiki.
CLI 1.6.2 made `write-source` a verified, baseline-bound write with staged
results. CLI 1.6.1 combined Unit/Dump evidence diagnosis with opt-in
experimental debugging. Live debugger attachment and persistent SAP affinity
remain unverified and must not be described as certified.
Rebuild and verify every advertised native target from the release source;
previous-version builds do not validate a new candidate. Implementation and
local verification alone do not authorize tagging or publication.

## Preconditions

1. `tools/check_release.py --skip-marketplace` passes on a locally built
   candidate (an upgrade keeps the previous live marketplace archive).
2. The working tree is clean and the commit recorded in
   `dist/release/release-manifest.json` is the intended source.
3. Platform claims match `packaging/targets.json` (do not advertise
   unverified targets).

## Order (when authorized)

1. Commit/merge the release state; tag `sap-adt-v<cli_version>` (the CLI
   line) and optionally `plugin-v<plugin_version>`.
2. Publish GitHub Release with the runtime archives, wheel/sdist, npm
   tarball, Windows desktop installer (when rebuilt and verified for this
   version), plugin + skill zips, `SHA256SUMS`,
   `release-manifest.json`. Use the artifact list in the manifest, not a
   wildcard over `dist/release/` that could include older releases.
3. After the release exists, regenerate the manifest/npm staging with
   `tools/build_manifest.py --release-state published`, upload the updated
   npm tarball/checksums/manifest, and `npm publish` the staged package
   (`dist/npm/`). Then verify
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
7. Run `tools/check_release.py` without `--skip-marketplace` against the
   final published manifest and live marketplace.

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
  replace it with a **project-scoped** token (`sap-adt-cli`) afterwards.
- Rotate the tokens on a schedule and immediately after any exposure
  (chat, logs, screenshots). Files must stay 600 and outside the repo.
- The OS keyring is not usable in this WSL2 setup (`keyring.backends.fail`),
  and twine's keyring integration therefore falls back to prompting.
- After setup, `npm publish` (from `dist/npm/`) and
  `.venv/bin/twine upload dist/release/sap_adt_cli-<ver>*` work non-interactively.

## Versioning

- CLI: `1.6.7` (single source: `pyproject.toml`; runtime/npm/installers/entry
  inherit it).
- Plugin/docs: `1.3.8` (`.claude-plugin/plugin.json`; must equal
  `compatibility.json.plugin_version`).
- The compatibility shims were removed in the 1.4.0 source tree; no released
  artifact ever contained them, so no CLI version bump was required.

## Rollback

- The previous CLI release remains installable by pinning its version.
- The plugin marketplace can be reverted by restoring the previous
  `marketplace.json` entry (previous tag/commit).
- The runtime installer keeps the previous runtime if an upgrade fails.
- User config and keystore entries are never touched by install/uninstall.
