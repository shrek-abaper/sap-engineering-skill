# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Repository Overview

`sap-engineering-skill` is a monorepo of AI agent skills for SAP ABAP engineering. Each skill follows the `SKILL.md` specification and works with compatible AI agent frameworks (opencode, Claude Code, Cursor).

### Skills

| Skill | Purpose | Location |
|-------|---------|----------|
| `sap-adt-cli` | Read/write ABAP source and metadata via ADT REST API | `skills/sap-adt-cli/` |
| `abap-code-review` | Pre-release security & quality review (9 dimensions) | `skills/abap-code-review/` |
| `sap-transport-gate` | Transport Request release gate assessment (10 dimensions) | `skills/sap-transport-gate/` |
| `sap-integration-wiki` | SAP integration knowledge base (9 domains, 8 technologies) | `skills/sap-integration-wiki/` |

The three subtree skills (`abap-code-review`, `sap-transport-gate`, `sap-integration-wiki`) are maintained as independent public repositories and are tracked via git subtree remotes.

---

## Repository Structure

```
sap-engineering-skill/
├── skills/
│   ├── sap-adt-cli/              ← Source in this repo (main skill)
│   │   ├── scripts/
│   │   │   ├── sap_adt_cli.py    ← Main CLI entry point
│   │   │   └── lib/              ← config.py, handlers.py, client.py
│   │   └── SKILL.md              ← Skill spec for agent frameworks
│   ├── abap-code-review/         ← [git subtree] independent repo
│   │   ├── references/           ← REF_ABAP_SECURITY.md, REF_CLEAN_ABAP.md
│   │   │                        └── REPORT_TEMPLATE.md
│   │   └── SKILL.md
│   ├── sap-transport-gate/       ← [git subtree] independent repo
│   │   ├── scripts/
│   │   │   ├── tr_collector.py   ← Online TR collection CLI
│   │   │   └── lib/              ← config.py, handlers.py, client.py
│   │   ├── references/           ← Decision policy, review dimensions, etc.
│   │   ├── evals/                ← Golden set, evals.json
│   │   └── SKILL.md
│   └── sap-integration-wiki/     ← [git subtree] independent repo
│       ├── references/           ├── scenarios/, tech/, troubleshoot/
│       ├── scripts/              ← gen-odata-postman.js, gen-jco-config.py, etc.
│       ├── assets/               ├── payloads/, configs/
│       └── SKILL.md
├── README.md
├── README.zh-CN.md
├── LICENSE
└── setup-opencode-abap-cli.bat   ← Windows one-click installer
```

---

## Git Subtree Management

Three skills are tracked as independent subtrees from public repositories:

| Remote | Repository | Subtree Path |
|--------|-----------|--------------|
| `pub-abap-code-review` | https://github.com/shrek-abaper/abap-code-review | `skills/abap-code-review/` |
| `pub-sap-transport-gate` | https://github.com/shrek-abaper/sap-transport-gate | `skills/sap-transport-gate/` |
| `pub-sap-integration-wiki` | https://github.com/shrek-abaper/sap-integration-wiki | `skills/sap-integration-wiki/` |

**Pull changes from subtree:**
```bash
git subtree pull --prefix=skills/abap-code-review pub-abap-code-review main --squash
git subtree pull --prefix=skills/sap-transport-gate pub-sap-transport-gate main --squash
git subtree pull --prefix=skills/sap-integration-wiki pub-sap-integration-wiki main --squash
```

**Push changes to subtree:**
```bash
git subtree push --prefix=skills/abap-code-review pub-abap-code-review main
```

When working within a subtree skill, changes should eventually be pushed to the corresponding public repository.

---

## Common Commands

### sap-adt-cli (ABAP CLI Tool)

The CLI entry point is `scripts/sap_adt_cli.py` inside the skill directory.

**Configure SAP credentials:**
```bash
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure
```

**Check connection status:**
```bash
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py status
```

**Read ABAP objects (examples):**
```bash
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py get-program SAPMV45A
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py get-class ZCL_MY_CLASS
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py get-table VBAK
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py get-package ZMYPACKAGE
```

**Write operations (requires `allow_write: true` + confirmation):**
```bash
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py write-source class ZCL_MY_CLASS --file /tmp/zcl.abap
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py activate class ZCL_MY_CLASS
```

### sap-transport-gate (TR Collection CLI)

**Configure SAP credentials:**
```bash
python3 skills/sap-transport-gate/scripts/tr_collector.py configure
```

**Collect transport package:**
```bash
python3 skills/sap-transport-gate/scripts/tr_collector.py collect DEVK900123 --output-dir reports/DEVK900123_package/ --verbose
```

### Testing

Each skill's evals are stored in `evals/` directories. Run evals using the skill creator's evaluation framework or the JSON-based eval definitions in `evals/evals.json`.

---

## Architecture Patterns

### CLI Tools (sap-adt-cli & sap-transport-gate)

Both Python CLI tools share a common `lib/` pattern:

```
scripts/
├── <entrypoint>.py          ← Main Click CLI
└── lib/
    ├── __init__.py
    ├── config.py            ← Config file loading, credential management
    ├── handlers.py          ← ADT/HTTP request handlers, command logic
    └── client.py            ← HTTP client (requests), session management
```

**config.py** - Handles:
- Configuration file at `~/.<skill>/config.json` (Python path: `os.path.expanduser`)
- Environment variable overrides (`SAP_URL`, `SAP_USERNAME`, `SAP_PASSWORD`, `SAP_CLIENT`, etc.)
- Capability flags (`allow_write`, `allow_transport`)
- Interactive and non-interactive setup wizards

**handlers.py** - Contains:
- Command implementation (get-program, get-class, etc.)
- ADT REST API request/response handling
- One-time confirmation prompts for write operations

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
- **One-time confirmation** - Every write/activate/transport operation shows a preview and requires user `[y/N]` confirmation per operation (never cached)
- **Credentials stored at `~/.sap-adt-cli/config.json`** with 0600 permissions (plain text, not encrypted)
- **Env vars override config** - Set `SAP_URL`, `SAP_USERNAME`, `SAP_PASSWORD`, `SAP_CLIENT` per invocation
- **SQL DML blocked** - `INSERT`/`UPDATE`/`DELETE`/`MODIFY`/`TRUNCATE` statements are unconditionally rejected in `run-sql`

### sap-transport-gate

- **No SAP login** - Skill never accepts SAP passwords; ADT API access is via `tr_collector.py` CLI only
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

### Adding New Commands to sap-adt-cli

1. Implement command handler in `scripts/lib/handlers.py`
2. Register Click command in `scripts/sap_adt_cli.py`
3. Add docstring explaining output format (text/JSON/XML)
4. Reference the ADT REST API endpoint used

### Helper Scripts

- `skills/sap-integration-wiki/scripts/gen-odata-postman.js` - Generate Postman collection for any OData service
- `skills/sap-integration-wiki/scripts/gen-jco-config.py` - Generate JCo `.jcoDestination` properties file
- `skills/sap-integration-wiki/scripts/gen-idoc-template.py` - Generate IDoc XML skeleton

### Windows Installer

`setup-opencode-abap-cli.bat` performs one-click setup of opencode + this skill suite. It installs opencode, clones the repo, and creates symlinks to `~/.agents/skills/`.

---

## SAP Version Support Matrix

| Version | Integration Recommendation |
|---------|---------------------------|
| ECC 6.0 | RFC/JCo + BAPIs, IDoc, SOAP over HTTP |
| S/4HANA On-Prem (1909–2023+) | OData V2/V4, RAP, RFC/JCo for non-exposed functions |
| S/4HANA Cloud (Public/Private) | OData V4/RAP via Communication Arrangement; RFC restricted |

See `skills/sap-integration-wiki/SKILL.md` for the complete quick technology decision matrix.