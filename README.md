<div align="center">

<h3>SAP ABAP engineering know-how, shipped as agent skills — not another generic chatbot</h3>

<h4><i>SKILL.md spec · read-only by default · evidence-first review · framework-agnostic</i></h4>

> Four skills cover the ABAP development lifecycle: reading and writing source through the ADT REST API, a 9-dimension pre-release code review, a 10-dimension transport request gate, and production-grade SAP integration knowledge. Writes are capability-gated with per-operation confirmation; review skills cite real evidence or declare an explicit gap — they never invent conclusions. Built by a working SAP consultant for daily real-world work.

**ADT REST API · 9-Dimension Code Review · 10-Dimension Transport Gate · Integration Knowledge Base · Evidence-First · Framework-Agnostic**

**MIT · Self-hosted · No vendor lock-in · ECC 6.0 & S/4HANA**

<h4>AI agent skills for the SAP ABAP release workflow</h4>

[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3-3776AB?style=flat-square&logo=python&logoColor=white)](skills/sap-adt-cli/scripts)
[![SAP](https://img.shields.io/badge/SAP-ADT%20REST%20API-0FAAFF?style=flat-square&logo=sap&logoColor=white)](#skills)
[![Skills](https://img.shields.io/badge/skills-4-2EA043?style=flat-square)](#skills)
[![Agents](https://img.shields.io/badge/agents-opencode%20%C2%B7%20Claude%20Code%20%C2%B7%20Cursor-orange?style=flat-square)](#compatible-ai-agents)

**English** · **[中文](README.zh-CN.md)**

</div>

**[Skills](#skills)** · **[Quick Start](#quick-start)** · **[Repository Structure](#repository-structure)** · **[Compatible Agents](#compatible-ai-agents)** · **[License](#license)**

---

## What Is This?

`sap-engineering-skill` is a monorepo of **AI agent skills** that cover the core workflow of SAP ABAP development: reading and writing source code, reviewing code quality and security before release, assessing transport requests at the gate, and answering SAP integration questions with production-ready precision.

Each skill follows the standard `SKILL.md` specification and works with any compatible AI agent framework — [opencode](https://opencode.ai), [Claude Code](https://docs.anthropic.com/en/docs/claude-code), Cursor, or any framework that supports custom tool/skill injection.

The skills `abap-code-review`, `sap-transport-gate`, and `sap-integration-wiki` were previously maintained as standalone public repositories. Those repositories are now **archived** (read-only) - all future updates happen exclusively in this monorepo.

---

## Skills

### [`sap-adt-cli`](skills/sap-adt-cli/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/sap-engineering-skill/tree/main/skills/sap-adt-cli)

A command-line tool and AI agent skill for reading **and writing** ABAP source code, metadata, and transport requests from SAP systems via the [ADT REST API](https://help.sap.com/docs/abap-cloud/abap-development-tools-user-guide/about-abap-development-tools).

**Supports**: programs, classes, function modules (with function group), function groups, interfaces, includes, CDS views, type groups (TYPE POOL), DDIC tables/structures/domains/data elements, packages, transactions, object search (`*` wildcard), read-only Open SQL data preview, where-used analysis, syntax checks, and transport request management (list/create/release).

**Key features**:
- Read-only by default; write and transport operations require explicit capability flags + a per-operation `[y/N]` preview confirmation that is never cached or reused (`--yes` only for trusted automation)
- Multi-environment **profiles** (DEV/QAS/PRD…) in `~/.sap-adt-cli/config.json` (0600) — switch with `profile use` or per-command `--profile`
- Passwords live in the **OS keystore**, never in the config file: backend priority `env` → `keyring` (Credential Manager / Keychain / Secret Service) → `dpapi` (WSL2) → `pass` (GPG) → `file` (scrypt + Fernet fallback); manage with `credentials set|forget|status|doctor`; old plaintext configs are auto-migrated and verbose logs / HTTP tracebacks stay redacted
- Environment variables or a skill-local `.env` override profiles for CI/CD
- Windows one-click installer (`setup-opencode-abap-cli.bat`) that wires up opencode end-to-end

---

### [`abap-code-review`](skills/abap-code-review/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/sap-engineering-skill/tree/main/skills/abap-code-review)

An AI agent skill for SAP ABAP pre-release code review. Performs a comprehensive security and quality assessment across **9 dimensions** and produces a formal, sign-off-ready Markdown report.

| #   | Dimension                          | Focus                                                |
| --- | ---------------------------------- | ---------------------------------------------------- |
| 1   | **[SEC]** Security                 | SQL injection, code injection, hardcoded credentials |
| 2   | **[AUTH]** Authorization           | Missing AUTHORITY-CHECK, bypass patterns             |
| 3   | **[DATA]** Data Integrity          | SY-SUBRC handling, locking, exception handling       |
| 4   | **[PERF]** Performance             | SELECT-in-LOOP, SELECT *, full table scans           |
| 5   | **[STD]** Code Standards           | Deprecated statements, oversized methods, dead code  |
| 6   | **[INTERFACE]** Integration        | Dialog in RFC FMs, missing EXCEPTIONS, OData auth    |
| 7   | **[CHANGE]** Change Impact         | Affected tables, SAP standard modifications          |
| 8   | **[COMP]** Compliance              | PII, audit logs, SoD paths                           |
| 9   | **[FUNC]** Functional *(optional)* | Business scenario coverage vs. requirements          |

**Output**: `GO / CONDITIONAL GO / NO-GO` recommendation with evidence-cited findings and a sign-off table.

---

### [`sap-transport-gate`](skills/sap-transport-gate/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/sap-engineering-skill/tree/main/skills/sap-transport-gate)

An AI agent skill that performs structured, evidence-driven release readiness assessment for SAP Transport Requests. Produces an auditable `GO / CONDITIONAL_GO / NO_GO / NEED_MORE_EVIDENCE` decision.

Covers **10 review dimensions**: code quality, performance, security, authorization, transaction consistency, integration impact, transport completeness, functional alignment, release readiness, and evidence gaps.

**Three review modes**:
- **Offline Package** — structured Review Package exported from SAP *(preferred)*
- **Offline Local** — partial materials (source files only)
- **Online Transport** — TR ID + `tr_collector.py` CLI for live ADT collection

**Core principle**: Evidence-first. AI never invents conclusions from insufficient evidence.

- **Proactive online collection** — given a TR ID, the skill runs `tr_collector.py collect` itself and only falls back to Offline Local Mode when credentials or connectivity are missing; review scope (code-only vs functional + code) is confirmed before the review starts.

---

### [`sap-integration-wiki`](skills/sap-integration-wiki/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/sap-engineering-skill/tree/main/skills/sap-integration-wiki)

A composable knowledge-base skill that turns any AI assistant into a SAP integration specialist. Covers 9 business domains and 8 integration technologies — no more generic wrong answers.

**Business domains**: MM (Purchasing, Inventory), SD (Sales), FI (GL, AR/AP, Asset Accounting, FSSC — incl. Kingdee/金蝶 & 用友 interfacing and SAP Central Finance/CFIN replication), Master Data, PP (Production)

**Technologies**: OData V2/V4, RFC/JCo, SOAP over HTTP RFC (call RFCs without JCo), IDoc/PI-PO, BAPI & RAP, Authentication, BTP Integration Suite (iFlow, Cloud Connector, Event Mesh), Best Practices

**SAP versions**: ECC 6.0 · S/4HANA On-Prem 1909–2023+ · S/4HANA Cloud (Public & Private Edition)

---

## Repository Structure

```
sap-engineering-skill/
├── README.md                         ← This file (English)
├── README.zh-CN.md                   ← Chinese version
├── CONTRIBUTING.md                   ← Tests, CI matrix, secret-scanning notes
├── LICENSE
├── setup-opencode-abap-cli.bat       ← Windows one-click installer
├── .github/workflows/tests.yml       ← CI: 3-OS unittest matrix + gitleaks
├── .gitleaks.toml                    ← Secret-scan rules (also a pre-commit hook)
├── tests/                            ← Root-level unittest suite (keystore, credentials, security…)
└── skills/
    ├── sap-adt-cli/             ← ADT CLI tool & skill (source in this repo)
    ├── abap-code-review/        ← ABAP code review skill
    ├── sap-transport-gate/      ← Transport gate review skill (evals/ golden set included)
    └── sap-integration-wiki/    ← SAP integration knowledge base
```

The three skills above were historically tracked as git subtrees from standalone public repositories, which are now **archived** (read-only). All updates are maintained in this repo:

| Standalone repository (archived)              | Migrated to                                            |
| --------------------------------------------- | ------------------------------------------------------ |
| https://github.com/shrek-abaper/abap-code-review     | [`skills/abap-code-review/`](skills/abap-code-review/)     |
| https://github.com/shrek-abaper/sap-transport-gate   | [`skills/sap-transport-gate/`](skills/sap-transport-gate/) |
| https://github.com/shrek-abaper/sap-integration-wiki | [`skills/sap-integration-wiki/`](skills/sap-integration-wiki/) |

---

## Quick Start

### Windows — sap-adt-cli one-click installer

Download [`setup-opencode-abap-cli.bat`](setup-opencode-abap-cli.bat) and double-click. The script installs opencode, clones this repo, and wires up the skill automatically.

### Manual install (any OS)

```bash
# Clone the repository
git clone https://github.com/shrek-abaper/sap-engineering-skill
cd sap-engineering-skill

# Link skills into your agent's skill directory
ln -s "$(pwd)/skills/sap-adt-cli"         ~/.agents/skills/sap-adt-cli
ln -s "$(pwd)/skills/abap-code-review"    ~/.agents/skills/abap-code-review
ln -s "$(pwd)/skills/sap-transport-gate"  ~/.agents/skills/sap-transport-gate
ln -s "$(pwd)/skills/sap-integration-wiki" ~/.agents/skills/sap-integration-wiki

# Configure a SAP connection profile (interactive wizard; password goes to the OS keystore)
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure
# Add more environments with --profile dev/qas/prd; verify the active keystore backend:
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py credentials doctor
```

### Compatible AI agents

| Agent                                                         | Notes                                                                        |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| [opencode](https://opencode.ai)                               | Free, open-source. Supports 30+ model providers. Windows installer included. |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | Anthropic's official CLI agent — natively supports `SKILL.md`                |
| [Cursor](https://cursor.sh)                                   | AI-powered code editor; install via MCP tool adapter                         |

> ⚠️ **Data compliance**: ABAP source code may contain core business logic and sensitive data. Before sending code to cloud-based AI services, confirm compliance with your organization's data security policy.

---

## Skill Reference

| Skill                  | Use When                                                                      |
| ---------------------- | ----------------------------------------------------------------------------- |
| `sap-adt-cli`          | Read/write ABAP source, Open SQL preview, where-used/syntax-check, multi-environment profiles, manage transports via ADT API |
| `abap-code-review`     | Pre-release security & quality review of a single ABAP program (9 dimensions) |
| `sap-transport-gate`   | TR-level release gate assessment — evidence-based GO/NO-GO decision           |
| `sap-integration-wiki` | SAP integration patterns, API reference, troubleshooting by scenario          |

---

## Development

- **Tests** — a plain `unittest` suite lives at the repository root in `tests/` (keystore backends, plaintext-config migration, log redaction, write/DML guards — 148 tests):

  ```bash
  python3 -m unittest discover -s tests -v
  ```

  Only `click` / `requests` / `urllib3` are required; `keyring` and `cryptography` are optional native-backend dependencies.
- **CI** — [`.github/workflows/tests.yml`](.github/workflows/tests.yml) runs the suite on Ubuntu / Windows / macOS with Python 3.12, plus a gitleaks full-history secret scan.
- **Secret scanning** — gitleaks also runs as a pre-commit hook (`.pre-commit-config.yaml`). See [CONTRIBUTING.md](CONTRIBUTING.md) for placeholder rules and the WSL/DPAPI manual verification checklist.

---

## License

[MIT](LICENSE)

Skills contain reference content from:
- [SAP Clean ABAP Style Guide](https://github.com/SAP/styleguides/blob/main/clean-abap/CleanABAP.md) — CC BY 4.0 (used in `abap-code-review`)
- [SAP Business Accelerator Hub](https://api.sap.com), [SAP Help Portal](https://help.sap.com) — public SAP documentation (used in `sap-integration-wiki`)

This project is not affiliated with, endorsed by, or officially supported by SAP SE.
