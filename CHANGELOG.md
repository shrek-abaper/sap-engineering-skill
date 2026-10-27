# Changelog

## 1.4.1 — 2026-10-28

- Transport collection now uses the shared ADT HTTP client and handlers
  (`sap_adt.adt.client` / `sap_adt.adt.handlers`); the duplicated
  `sap_adt/transport/client.py` and the duplicated source-endpoint helpers
  were removed. One implementation owns Basic Auth, CSRF, retries, redaction
  and the `sap-client` query parameter.
- The shared client gained explicit connection injection (`set_config`) and
  sends `sap-client` on every request, including the CSRF pre-flight.
- No command, output-contract, credential or safety-gate changes. Request
  construction is unchanged apart from the added `sap-client` parameter.
- Plugin/docs payload unchanged (still 1.1.7); local candidate built, not yet
  published.

## Plugin/docs 1.1.7 — 2026-10-28

- Clarified npm vs npx in all install docs: the npm package is
  `sap-adt-cli`, its bin (and therefore the CLI command) is `sap-adt`.
  `npm install -g sap-adt-cli` provides that command on PATH; npx does not,
  so npx users must prefix every call (`npx sap-adt-cli@1.4.0 <command>`).
- Updated runtime-setup (single source), npm guide, npm package README,
  root READMEs and the skill READMEs; skill snapshots regenerated.
- Plugin payload regenerated; marketplace digest updated.

## Plugin/docs 1.1.6 — 2026-10-28

- README audit against the post-refactor code: root READMEs now describe the
  installable CLI (npm/PyPI/portable), the src/sap_adt + tools/ + packaging/
  layout, the real test baseline (320 tests, local-only) and the updated
  docs index. Skill READMEs drop the removed requirements.txt/.env-scanning
  steps, document `sap-adt configure` / `SAP_ADT_DOTENV` and the transport
  `collect|ping` commands, and list the generated setup/compatibility
  snapshots in their structure trees.
- Plugin payload regenerated; marketplace digest updated.

## Plugin/docs 1.1.5 — 2026-10-28

- Moved development assets out of the skill folder: the four refactor/history
  documents now live in `docs/development/archive/sap-adt-cli/`, and the ADT
  test fixtures (sanitized captures + golden + synthetic + sanitizer) moved
  to `tests/fixtures/sap_adt_cli/` (local `raw/` captures stay git-ignored).
- `skills/sap-adt-cli/` now contains only SKILL.md, READMEs, references and
  the dotenv example. No distribution payload changes beyond the SKILL.md
  reference to the archive location.
- Tests, contract checker, CLAUDE.md and ignore rules updated for the new
  paths. Plugin payload regenerated; marketplace digest updated.

## Plugin/docs 1.1.4 — 2026-10-28

- Removed the legacy skill-local script entry points
  (`skills/sap-adt-cli/scripts/sap_adt_cli.py`,
  `skills/sap-transport-gate/scripts/tr_collector.py`) and their
  `requirements.txt` files. Old-path invocations now fail — use `sap-adt`.
  No released artifact ever contained these shims, so no CLI version bump.
- `SKILL.md` now states the missing-CLI path explicitly: probe
  `sap-adt --version`; if absent, diagnose first, then guide the user —
  preferred `npx sap-adt-cli@1.4.0 install` when Node ≥ 18 exists, otherwise
  `pip install sap-adt==1.4.0` or the portable archive — and ask before
  running anything.
- Skill READMEs/references now document the `SAP_ADT_DOTENV` dotenv model
  (no skill-local `.env` scanning) and the `sap-adt transport collect`
  commands.
- Plugin payload regenerated; marketplace digest updated.

## Plugin/docs 1.1.3 — 2026-10-28

- All distribution channels are now live: npm `sap-adt-cli@1.4.0`, PyPI
  `sap-adt==1.4.0`, the GitHub Release `sap-adt-v1.4.0` (Linux portable
  runtime, plugin/skill zips, `SHA256SUMS`), and the marketplace `archive`
  source.
- Installation docs, README quick start and the releasing/agent guides now
  describe the published channels; the Windows installer and macOS runtime
  remain unbuilt and unverified.
- Plugin payload regenerated; marketplace digest updated.

## Plugin/docs 1.1.2 — 2026-10-28

- npm package is the unscoped **`sap-adt-cli`** (install:
  `npx sap-adt-cli@1.4.0 install`). No npm scope is needed, so any npm
  account can publish it. The CLI version is unchanged at 1.4.0.
- Supersedes the scoped name prepared in 1.1.1, which was never published
  to the registry.
- Skill snapshots and the plugin payload regenerated; marketplace archive
  points at the regenerated plugin zip.

## 1.4.0 — 2026-10-27

CLI distribution refactor (skill docs plugin version 1.1.0).

### Added
- `sap-adt` console entry point (`python -m sap_adt` equivalent); the Python
  implementation now lives in the installable `src/sap_adt` package.
- Self-contained runtime builds (PyInstaller onedir), portable archives and
  a Windows installer script (implemented, not yet verified on Windows).
- npm/npx channel `sap-adt-cli` with a custom
  `install` wizard (manifest-pinned SHA-256, atomic swap, self-test).
- `sap-adt transport collect|ping`; collection is read-only and uses the
  normal ADT profile/keystore resolution.
- Standalone skill snapshots (`dist/skills/`), docs-only plugin payload,
  per-skill `references/setup.md` + `runtime-compatibility.json` (generated)
  and conditional readiness guidance in SKILL.md.
- Release tooling: `build_manifest.py`, `check_release.py`, `SHA256SUMS`,
  candidate marketplace entry (never written to the live config).

### Changed
- Program name `sap-adt-cli` → `sap-adt` in help/version/messages.
- Skill-local `.env` requires an explicit `SAP_ADT_DOTENV` path; the legacy
  shims set it automatically.
- Tests import the `sap_adt` package; the cloud CI workflow was removed
  (verification is local — see CONTRIBUTING.md).

### Removed
- First-run `pip install` of dependencies from the CLI and collector.
- `tr_collector.py configure` forwarding (it wrote plaintext passwords);
  use `sap-adt configure`.

### Unchanged
- Commands/options, output contract `format_version=1`, 18 error codes and
  exit tiers, safety gates, config directory and keystore identifiers.

### Migration
See `docs/development/migration.md`. Roll back by checking out the previous
release; user configuration is untouched.

## Before 1.4.0

See git tags `v1.0.0`–`v1.1.1` and the skill revision history in
`docs/development/archive/sap-adt-cli/refactor-summary.md`.
