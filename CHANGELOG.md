# Changelog

## 1.4.0 — 2026-10-27

CLI distribution refactor (skill docs plugin version 1.1.0).

### Added
- `sap-adt` console entry point (`python -m sap_adt` equivalent); the Python
  implementation now lives in the installable `src/sap_adt` package.
- Self-contained runtime builds (PyInstaller onedir), portable archives and
  a Windows installer script (implemented, not yet verified on Windows).
- npm/npx channel `@shrek-abaper/sap-engineering-cli` with a custom
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
`skills/sap-adt-cli/docs/refactor-summary.md`.
