# Migration notes

## PyPI distribution rename — 1.4.x → 1.5.0

The PyPI project was renamed from `sap-adt` to **`sap-adt-cli`** (the npm
package was already `sap-adt-cli`). PyPI cannot rename a project, and the old
project was **removed from PyPI** after the rename — `pip install sap-adt`
now fails with "no matching distribution". Existing 1.4.x installations keep
working until you uninstall them.

**Do not run `pip install -U sap-adt`.** Both projects provide the same
import package (`sap_adt`); pip installs the new distribution before
uninstalling the old one, and the old RECORD then deletes the shared package
files and the `sap-adt` script.

Safe migration — the command is briefly unavailable between the two steps:

```bash
pip uninstall -y sap-adt
pip install "sap-adt-cli>=1.5.0,<2.0.0"
```

Fresh installs use `sap-adt-cli`. Nothing else changes: the command is still
`sap-adt`, the import package is `sap_adt`, and configuration stays in
`~/.sap-adt-cli`.

---

## CLI 1.3.x → 1.4.0

## What changed

| Before | After |
|---|---|
| `python3 skills/sap-adt-cli/scripts/sap_adt_cli.py <cmd>` | `sap-adt <cmd>` (the old script was removed; update the command) |
| First run pip-installed click/requests/urllib3 | No auto-install: install the CLI once (`pip install sap-adt`, npm, installer, portable) |
| Skill-local `.env` located by walking up from `config.py` | Declare the file explicitly with `SAP_ADT_DOTENV=/path/to/.env` |
| `tr_collector.py collect/configure/ping` (removed) | `sap-adt transport collect/ping`; `configure` → `sap-adt configure` |
| Collector stored a plaintext password in `~/.sap-transport-gate/config.json` | Profiles in `~/.sap-adt-cli/config.json` + OS keystore |
| Program name `sap-adt-cli` | `sap-adt` (help, `--version`, hint text) |

## Unchanged (by design)

- Command names/options, JSON envelope kinds, `format_version=1`, the 18
  error codes and exit tiers 0–4.
- Safety gates: read-only default, profile-scoped capability flags, prd hard
  refusal, per-operation `[y/N]`, non-interactive confirmation refusal
  (`--yes` only skips the prompt — it cannot bypass capability/prd gates),
  DML rejection.
- Config directory `~/.sap-adt-cli`, keystore service IDs, env precedence.
- Transport package layout (`manifest.json` + `sources/`).

## Migrating a collector setup

```bash
sap-adt configure                      # profile + keystore
sap-adt transport ping                 # verify connectivity
# then stop using --legacy-config (and consider deleting the old
# ~/.sap-transport-gate/config.json, which holds a plaintext password)
```

The old file is read only when `--legacy-config` is passed. It is never an
implicit fallback for a missing profile or a failed authentication.

## Rollback

Check out the previous release/commit; the old script entry points and
config schema still exist there. User configuration is untouched by the
upgrade either way.
