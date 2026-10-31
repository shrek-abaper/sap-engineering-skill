# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Repository Overview

`sap-engineering-skill` is a monorepo of AI agent skills for SAP ABAP engineering. Each skill follows the `SKILL.md` specification and works with compatible AI agents (Claude Code, Codex, WorkBuddy).

### Skills

| Skill | Purpose | Location |
|-------|---------|----------|
| `sap-adt-cli` | Read/write ABAP source and metadata via ADT REST API | `skills/sap-adt-cli/` |
| `abap-code-review` | Pre-release security & quality review (9 dimensions) | `skills/abap-code-review/` |
| `sap-transport-gate` | Transport Request release gate assessment (10 dimensions) | `skills/sap-transport-gate/` |
| `sap-integration-wiki` | SAP integration knowledge base (9 domains, 8 technologies) | `skills/sap-integration-wiki/` |

The three skills `abap-code-review`, `sap-transport-gate`, and `sap-integration-wiki` were previously maintained as standalone public repositories tracked via git subtree. Those repositories were **archived in August 2026** - all updates now happen exclusively in this repo.

---

## Repository Structure

```
sap-engineering-skill/
├── src/sap_adt/                  ← ONLY CLI business implementation
│   ├── cli.py                    ← Click group `sap-adt`
│   ├── config.py, credentials*.py, errors.py, output.py
│   ├── adt/                      ← client, handlers, parsers, coverage
│   ├── keystore/                 ← env/keyring/dpapi/pass/file backends
│   └── transport/                ← collector, legacy config adapter (shared ADT client)
├── skills/                       ← Skill content (SKILL.md, references, evals)
│   ├── sap-adt-cli/              ← skill content only (no execution code)
│   ├── abap-code-review/
│   ├── sap-transport-gate/       ← skill content only (no execution code)
│   └── sap-integration-wiki/
├── packaging/                    ← pyinstaller spec, npm templates, windows iss, targets.json
├── tools/                        ← build_runtime/build_npm/build_skills/build_plugin/
│                                   build_manifest/check_release/sync_skill_runtime_docs
├── docs/                         ← installation/, development/, agents/, authentication/
├── tests/                        ← unittest suite (incl. distribution contracts)
├── compatibility.json            ← per-skill CLI requirement + compatible range
├── pyproject.toml                ← single CLI version source
└── .claude-plugin/               ← marketplace.json + plugin.json (docs-only plugin)
```

Generated outputs (`dist/`, per-skill `references/setup.md` +
`runtime-compatibility.json` snapshots) are produced by `tools/`; the
snapshots are committed so a source checkout's skill folder is
self-contained. Never hand-edit files marked GENERATED.

---

## Archived Standalone Repositories (Historical)

The three skills below were previously maintained as standalone public repositories tracked via git subtree. They were **archived in August 2026** and are now read-only; all changes are maintained directly in this repo. Do not pull from or push to these remotes.

| Remote (historical) | Repository (archived) | Subtree Path |
|--------|-----------|--------------|
| `pub-abap-code-review` | https://github.com/shrek-abaper/abap-code-review | `skills/abap-code-review/` |
| `pub-sap-transport-gate` | https://github.com/shrek-abaper/sap-transport-gate | `skills/sap-transport-gate/` |
| `pub-sap-integration-wiki` | https://github.com/shrek-abaper/sap-integration-wiki | `skills/sap-integration-wiki/` |

---

## Common Commands

### sap-adt CLI

Install once (editable, in a venv): `python3 -m pip install -e .`

**Configure SAP credentials:**
```bash
sap-adt configure
```

**Check connection status:**
```bash
sap-adt status
```

**Read ABAP objects (examples):**
```bash
sap-adt get-program SAPMV45A
sap-adt get-class ZCL_MY_CLASS
sap-adt get-table VBAK
sap-adt get-package ZMYPACKAGE
```

**Write operations (requires `allow_write: true` + confirmation):**
```bash
sap-adt write-source class ZCL_MY_CLASS --file /tmp/zcl.abap
sap-adt activate class ZCL_MY_CLASS
```

### Transport collection (read-only)

```bash
sap-adt transport collect DEVK900123 --output-dir reports/DEVK900123_package/ --verbose
sap-adt transport ping          # connectivity check
```

The old `tr_collector.py` entry point was removed in 1.4.0's source tree;
scripts that still call it must switch to `sap-adt transport collect|ping`.
The legacy plaintext config is read only via explicit `--legacy-config`.

### Testing

```bash
python -m unittest discover -s tests -v      # unit + contract + distribution
python tests/check_contract.py               # SKILL.md ↔ code contract
node --test packaging/npm/test/install.test.js
```

These local runs are the verification baseline. A manually dispatched macOS
workflow runs offline tests, native builds and isolated npm install checks;
hosted runners never connect to SAP. Each skill's evals live in `evals/`.

---

## Architecture Patterns

### CLI package (`src/sap_adt`)

```
src/sap_adt/
├── cli.py            ← Click group `sap-adt` (commands, gates, confirmations)
├── config.py         ← profiles/env/dotenv resolution, ~/.sap-adt-cli
├── credentials.py    ← keystore orchestration (+ credentials_reports.py for doctor)
├── errors.py         ← closed 23-code set + exit tiers
├── output.py         ← envelope rendering (format_version = 1)
├── adt/              ← client.py, handlers.py, parsers/, coverage.py
├── keystore/         ← env/keyring/dpapi/pass/file backends
└── transport/        ← collector.py (read-only), client.py, legacy_config.py
```

**config.py** - Handles:
- `~/.sap-adt-cli/config.json` v2 profiles (non-secret fields only, 0600)
- Process env > explicit dotenv (`SAP_ADT_DOTENV`) > profile; never scans CWD
- Capability flags (`allow_write`, `allow_transport`, independent profile-only `allow_debug`), environment (dev/qas/prd)
- Interactive and non-interactive setup wizards; old-config migration
- Password storage is delegated to `credentials.py` + the `keystore/` backends

**handlers.py** - Command implementation, ADT request/response handling,
one-time confirmation previews for write operations.

**transport/** — the collector injects its connection into the shared
ADT client via `set_config()` (no client of its own); the legacy plaintext
config is read only via `--legacy-config`.

**client.py** - Provides:
- HTTP session management (requests library)
- Authentication (Basic Auth)
- SSL verification configuration

### Skill Architecture

Each skill follows the `SKILL.md` frontmatter specification:

```yaml
---
name: skill-name
description: "..."
metadata:
  version: "x.y.z"
  type: docs | hybrid
  permissions:
    read_paths: ["<skill_dir>/references/"]
    write_paths: [...]
---
```

**skills/abap-code-review/** - References-first architecture:
1. Load `references/REF_ABAP_SECURITY.md` and `references/REF_CLEAN_ABAP.md`
2. Analyze ABAP source code across 9 dimensions
3. Generate sign-off-ready Markdown report from `references/REPORT_TEMPLATE.md`

**skills/sap-transport-gate/** - Evidence-first architecture:
1. Detect review mode (Offline Package, Offline Local, Online Transport)
2. Load reference documents from `references/` (decision policy, dimensions, etc.)
3. Grade evidence level (HIGH/MEDIUM/LOW/UNKNOWN)
4. Run 10-dimensional review
5. Generate Release Readiness Report with GO/CONDITIONAL_GO/NO_GO/NEED_MORE_EVIDENCE

**skills/sap-integration-wiki/** - Route-based architecture:
1. Route user question to scenario file in `references/scenarios/`
2. Load technology-specific file from `references/tech/`
3. If troubleshooting, load from `references/troubleshoot/`

### Reference File Dependencies

Skills have explicit reference loading requirements documented in their `SKILL.md`:

| Skill | Required Reference Files (loaded in order) |
|-------|--------------------------------------------|
| `abap-code-review` | `references/REF_ABAP_SECURITY.md`, `references/REF_CLEAN_ABAP.md`, `references/REPORT_TEMPLATE.md` |
| `sap-transport-gate` | `references/review-modes.md`, `references/decision-policy.md`, `references/review-dimensions.md`, `references/report-format.md`, `references/abap-security-rules.md`, `references/abap-quality-rules.md` |
| `sap-integration-wiki` | `references/scenarios/*.md` (business object), then `references/tech/*.md` (technology), optionally `references/troubleshoot/*.md` |

---

## Important Constraints

### sap-adt-cli

- **Read-only by default** - Write operations require `allow_write: true` in config
- **Independent debugger consent** - Setup/controls require `allow_debug: true`, non-PRD and fresh confirmation; no source/transport/global inheritance. Authorized session reads and cleanup do not require re-enabling flags. Debug execution can change business data even when source writes are disabled.
- **One-time confirmation** - Every write/activate/transport operation shows a preview and requires user `[y/N]` confirmation per operation (never cached)
- **Passwords stored in the OS keystore** - Non-secret connection settings live in `~/.sap-adt-cli/config.json` (0600, multi-environment profiles); profile passwords are stored only in the OS keystore — backend priority `env` (`SAP_ADT_<PROFILE>_PASSWORD`) → `keyring` → `dpapi` (WSL2) → `pass` → `file` (scrypt+Fernet fallback); manage with `credentials set|forget|status|doctor`; old plaintext-password configs are auto-migrated
- **Env vars / dotenv override config** - Set `SAP_URL`, `SAP_USERNAME`, `SAP_PASSWORD`, `SAP_CLIENT` per invocation or in a dotenv file declared by `SAP_ADT_DOTENV` (the CLI never scans the CWD or skill folder); `SAP_PROFILE` / `--profile` selects among profiles (a complete set of `SAP_*` connection vars bypasses profiles entirely)
- **SQL DML blocked** - `INSERT`/`UPDATE`/`DELETE`/`MODIFY`/`TRUNCATE` statements are unconditionally rejected in `run-sql`

### sap-transport-gate

- **No SAP login** - Skill never accepts SAP passwords; ADT API access is via the `sap-adt` CLI only
- **No evidence fabrication** - Every finding must cite real code or materials; gaps must be declared as `EVIDENCE_GAP`
- **Evidence Level LOW → NO GO** - If evidence is insufficient, the decision cannot be `GO`
- **Single file ≠ full TR review** - A single ABAP file does not constitute a Transport Request-level review
- **CRITICAL = NO_GO** - Any CRITICAL SECURITY/AUTHORIZATION/TRANSACTION_CONSISTENCY finding blocks release

### abap-code-review

- **Skip FUNC dimension without spec** - Do not independently infer requirements; if no functional spec is provided, mark `[FUNC]` as `N/A`
- **Rule citation required** - All [SEC]/[AUTH]/[STD] findings must cite specific rule IDs (e.g., `SEC-SQL-1`, `[E-2]`)
- **Evidence-first** - Every finding must include a real code snippet (≤15 lines)

---

## Development Notes

### Adding New Commands to sap-adt

1. Implement the handler in `src/sap_adt/adt/handlers.py`
2. Register the Click command in `src/sap_adt/cli.py`
3. Add a docstring explaining the output format (text/JSON/XML)
4. Reference the ADT REST API endpoint used
5. Update `skills/sap-adt-cli/SKILL.md`'s command index —
   `tests/check_contract.py` fails on drift (command count constants in
   `docs/development/archive/sap-adt-cli/refactor-*.md` must match too)
6. Add/extend tests; run the local verification baseline

### Helper Scripts

- `skills/sap-integration-wiki/scripts/gen-odata-postman.js` - Generate Postman collection for any OData service
- `skills/sap-integration-wiki/scripts/gen-jco-config.py` - Generate JCo `.jcoDestination` properties file
- `skills/sap-integration-wiki/scripts/gen-idoc-template.py` - Generate IDoc XML skeleton

### Distribution build

See `docs/development/building.md` for the full order. In short:
`python -m build` → `tools/build_runtime.py` → `tools/build_installer.py` →
`tools/build_npm.py` → `tools/sync_skill_runtime_docs.py` →
`tools/build_skills.py` → `tools/build_plugin.py` →
`tools/build_manifest.py` → `tools/check_release.py`. Publishing is a
separate authorized step (`docs/development/releasing.md`); never push,
tag, publish or switch the live marketplace without explicit approval.

### Windows

Windows x64 has an npm runtime, portable ZIP and unsigned desktop installer
from CLI 1.5.3; PyPI remains available with Python ≥ 3.10. Skill folders
are installed separately. Native runtime/npm installation and the Inno Setup
installer's silent per-user install, same-version upgrade and uninstall were
verified via WSL interop. Graphical wizard clicks, actual PATH mutation,
elevated installation and live SAP connectivity remain unverified.
See `docs/installation/windows.md` for the precise scope.

---

## SAP Version Support Matrix

| Version | Integration Recommendation |
|---------|---------------------------|
| ECC 6.0 | RFC/JCo + BAPIs, IDoc, SOAP over HTTP |
| S/4HANA On-Prem (1909–2023+) | OData V2/V4, RAP, RFC/JCo for non-exposed functions |
| S/4HANA Cloud (Public/Private) | OData V4/RAP via Communication Arrangement; RFC restricted |

See `skills/sap-integration-wiki/SKILL.md` for the complete quick technology decision matrix.