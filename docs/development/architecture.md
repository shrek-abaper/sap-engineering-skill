# Architecture

Two source assets, several generated distributions.

## Source of truth

| Asset | Path | Notes |
|---|---|---|
| CLI implementation | `src/sap_adt/` | the only business implementation |
| CLI version | `pyproject.toml` `[project] version` | read at run time via `importlib.metadata`; no second constant |
| Skill content | `skills/<name>/` | SKILL.md, references, templates, generators |
| Install guide body | `docs/installation/runtime-setup.md` | embedded into per-skill snapshots |
| Compatibility declaration | `compatibility.json` | per-skill CLI requirement + range |
| Plugin metadata | `.claude-plugin/plugin.json` | plugin version authority |

## Generated (never hand-edited)

| Output | Producer |
|---|---|
| `skills/<name>/references/{setup.md,runtime-compatibility.json}` + README cli-setup blocks | `tools/sync_skill_runtime_docs.py` |
| `dist/skills/`, `dist/plugin/` | `tools/build_skills.py`, `tools/build_plugin.py` |
| `dist/runtime/` | `tools/build_runtime.py` (PyInstaller onedir) |
| `dist/npm/` | `tools/build_npm.py` |
| `dist/release/` | `tools/build_manifest.py` |

`dist/` is ignored by git.

## Package layout

```
src/sap_adt/
├── cli.py            Click group `sap-adt` (commands, gates, confirmations)
├── config.py         profiles/env/dotenv resolution, ~/.sap-adt-cli
├── credentials.py    keystore orchestration (+ *_reports.py for doctor output)
├── errors.py         closed 18-code set + exit tiers
├── output.py         envelope rendering (format_version = 1)
├── adt/              ADT client, handlers, parsers, coverage
├── keystore/         env / keyring / dpapi / pass / file backends
└── transport/        collector (read-only), legacy config adapter
```

## Compatibility shims

`skills/sap-adt-cli/scripts/sap_adt_cli.py` and
`skills/sap-transport-gate/scripts/tr_collector.py` only forward to the
installed package (no business code, no auto-install). They exist so old
links keep working during the compat window and are excluded from every
generated distribution. The collector shim adds `--legacy-config` to
reproduce its old resolution and refuses `configure` (which used to write a
plaintext password); `sap-adt configure` is the replacement.

## Data & credentials (unchanged by packaging)

- Config: `~/.sap-adt-cli/config.json` (v2 profiles, 0600).
- Passwords: OS keystore; backend priority env → keyring → WSL DPAPI → pass
  → encrypted file (`SAP_ADT_MASTER_PASSPHRASE`).
- Env precedence: process env → explicit dotenv (`SAP_ADT_DOTENV`) →
  profile. The CLI never scans the CWD for `.env`.
- Legacy `~/.sap-transport-gate/config.json` (plaintext) is read only on the
  explicit `--legacy-config` path, with a migration warning.
