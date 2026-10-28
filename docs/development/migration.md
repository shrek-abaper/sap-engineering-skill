# Migration notes

## PyPI distribution rename — 1.4.x → 1.5.0

The PyPI project was renamed from `sap-adt` to **`sap-adt-cli`** (the npm
package was already `sap-adt-cli`). PyPI cannot rename a project, so:

- Install/upgrade with `pip install "sap-adt-cli>=1.5.0,<2.0.0"`.
- The old `sap-adt` name stays as a metadata-only **deprecation stub**
  (`sap-adt==1.5.0`) that depends on `sap-adt-cli==1.5.0`; `pip install -U
  sap-adt` therefore migrates once, but new installs should use the new name.
- Nothing else changes: the command is still **`sap-adt`**, the import
  package is still `sap_adt`, and configuration stays in `~/.sap-adt-cli`.

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
