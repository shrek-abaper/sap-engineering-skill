# sap-abap-cli

[English](README.md) | [中文](README.zh-CN.md)

> A collection of AI agent skills for SAP ABAP engineering — built by a SAP consultant for daily real-world work.

---

## What Is This?

`sap-abap-cli` is a monorepo of **AI agent skills** that cover the core workflow of SAP ABAP development: reading and writing source code, reviewing code quality and security before release, assessing transport requests at the gate, and answering SAP integration questions with production-ready precision.

Each skill follows the standard `SKILL.md` specification and works with any compatible AI agent framework — [opencode](https://opencode.ai), [Claude Code](https://docs.anthropic.com/en/docs/claude-code), Cursor, or any framework that supports custom tool/skill injection.

The three subtree skills are also maintained as independent public repositories so they can be used standalone.

---

## Skills

### [`sap-adt-cli`](skills/sap-adt-cli/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/sap-abap-cli)

A command-line tool and AI agent skill for reading **and writing** ABAP source code, metadata, and transport requests from SAP systems via the [ADT REST API](https://help.sap.com/docs/abap-cloud/abap-development-tools-user-guide/about-abap-development-tools).

**Supports**: programs, classes, function modules, function groups, interfaces, includes, CDS views, DDIC tables/structures/types, packages, transactions, SQL queries, where-used analysis, syntax checks, transport management.

**Key features**:
- Read-only by default; write and transport operations require explicit capability flags + per-operation `[y/N]` confirmation
- Windows one-click installer (`setup-opencode-abap-cli.bat`) that wires up opencode end-to-end
- Credentials stored at `~/.sap-adt-cli/config.json`; environment variable override for CI/CD

---

### [`abap-code-review`](skills/abap-code-review/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/abap-code-review)

An AI agent skill for SAP ABAP pre-release code review. Performs a comprehensive security and quality assessment across **9 dimensions** and produces a formal, sign-off-ready Markdown report.

| # | Dimension | Focus |
|---|-----------|-------|
| 1 | **[SEC]** Security | SQL injection, code injection, hardcoded credentials |
| 2 | **[AUTH]** Authorization | Missing AUTHORITY-CHECK, bypass patterns |
| 3 | **[DATA]** Data Integrity | SY-SUBRC handling, locking, exception handling |
| 4 | **[PERF]** Performance | SELECT-in-LOOP, SELECT *, full table scans |
| 5 | **[STD]** Code Standards | Deprecated statements, oversized methods, dead code |
| 6 | **[INTERFACE]** Integration | Dialog in RFC FMs, missing EXCEPTIONS, OData auth |
| 7 | **[CHANGE]** Change Impact | Affected tables, SAP standard modifications |
| 8 | **[COMP]** Compliance | PII, audit logs, SoD paths |
| 9 | **[FUNC]** Functional *(optional)* | Business scenario coverage vs. requirements |

**Output**: `GO / CONDITIONAL GO / NO-GO` recommendation with evidence-cited findings and a sign-off table.

---

### [`sap-transport-gate`](skills/sap-transport-gate/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/sap-transport-gate)

An AI agent skill that performs structured, evidence-driven release readiness assessment for SAP Transport Requests. Produces an auditable `GO / CONDITIONAL_GO / NO_GO / NEED_MORE_EVIDENCE` decision.

Covers **10 review dimensions**: code quality, performance, security, authorization, transaction consistency, integration impact, transport completeness, functional alignment, release readiness, and evidence gaps.

**Three review modes**:
- **Offline Package** — structured Review Package exported from SAP *(preferred)*
- **Offline Local** — partial materials (source files only)
- **Online Transport** — TR ID + `tr_collector.py` CLI for live ADT collection

**Core principle**: Evidence-first. AI never invents conclusions from insufficient evidence.

---

### [`sap-integration-wiki`](skills/sap-integration-wiki/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/sap-integration-wiki)

A composable knowledge-base skill that turns any AI assistant into a SAP integration specialist. Covers 9 business domains and 8 integration technologies — no more generic wrong answers.

**Business domains**: MM (Purchasing, Inventory), SD (Sales), FI (GL, AR/AP, Asset Accounting, FSSC), Master Data, PP (Production)

**Technologies**: OData V2/V4, RFC/JCo, SOAP over HTTP RFC, IDoc/PI-PO, BAPI & RAP, Authentication, BTP Integration Suite, Best Practices

**SAP versions**: ECC 6.0 · S/4HANA On-Prem 1909–2023+ · S/4HANA Cloud (Public & Private Edition)

---

## Repository Structure

```
sap-abap-cli/
├── README.md                         ← This file (English)
├── README.zh-CN.md                   ← Chinese version
├── LICENSE
├── setup-opencode-abap-cli.bat       ← Windows one-click installer
└── skills/
    ├── sap-adt-cli/             ← ADT CLI tool & skill (source in this repo)
    ├── abap-code-review/        ← ABAP code review skill  [git subtree]
    ├── sap-transport-gate/      ← Transport gate review skill  [git subtree]
    └── sap-integration-wiki/    ← SAP integration knowledge base  [git subtree]
```

The three subtree skills are tracked via named git remotes:

| Remote | Repository |
|--------|-----------|
| `pub-abap-code-review` | https://github.com/shrek-abaper/abap-code-review |
| `pub-sap-transport-gate` | https://github.com/shrek-abaper/sap-transport-gate |
| `pub-sap-integration-wiki` | https://github.com/shrek-abaper/sap-integration-wiki |

---

## Quick Start

### Windows — sap-adt-cli one-click installer

Download [`setup-opencode-abap-cli.bat`](setup-opencode-abap-cli.bat) and double-click. The script installs opencode, clones this repo, and wires up the skill automatically.

### Manual install (any OS)

```bash
# Clone the repository
git clone https://github.com/shrek-abaper/sap-abap-cli
cd sap-abap-cli

# Link skills into your agent's skill directory
ln -s "$(pwd)/skills/sap-adt-cli"         ~/.agents/skills/sap-adt-cli
ln -s "$(pwd)/skills/abap-code-review"    ~/.agents/skills/abap-code-review
ln -s "$(pwd)/skills/sap-transport-gate"  ~/.agents/skills/sap-transport-gate
ln -s "$(pwd)/skills/sap-integration-wiki" ~/.agents/skills/sap-integration-wiki

# Configure SAP credentials for sap-adt-cli
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure
```

### Compatible AI agents

| Agent | Notes |
|-------|-------|
| [opencode](https://opencode.ai) | Free, open-source. Supports 30+ model providers. Windows installer included. |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | Anthropic's official CLI agent — natively supports `SKILL.md` |
| [Cursor](https://cursor.sh) | AI-powered code editor; install via MCP tool adapter |

> ⚠️ **Data compliance**: ABAP source code may contain core business logic and sensitive data. Before sending code to cloud-based AI services, confirm compliance with your organization's data security policy.

---

## Skill Reference

| Skill | Use When |
|-------|----------|
| `sap-adt-cli` | Read/write ABAP source, run SQL, manage transports via ADT API |
| `abap-code-review` | Pre-release security & quality review of a single ABAP program (9 dimensions) |
| `sap-transport-gate` | TR-level release gate assessment — evidence-based GO/NO-GO decision |
| `sap-integration-wiki` | SAP integration patterns, API reference, troubleshooting by scenario |

---

## Development Paradigm

This project was built using an AI-native, spec-driven development loop:

1. **Specification** — Requirements were worked out in conversation with **Claude Sonnet 4.6**, producing structured Markdown prompt files encoding the full spec (scope, acceptance criteria, anti-patterns).
2. **Execution** — Prompt files were consumed end-to-end by **[opencode](https://opencode.ai) + [Oh My OpenAgent](https://github.com/oh-my-opencode/oh-my-openagent)** running on a **GitHub Copilot Pro** subscription — which planned, implemented, tested, and verified changes autonomously.
3. **Review** — The human role was limited to deciding *what* to build, reviewing outputs, and iterating on the spec.

> The author is a SAP consultant with over ten years of project experience and no software development background. This project grew from a practical daily need and became a personal experiment in how an AI-native workflow can reshape what domain experts are able to build — shared here in the hope it's useful to others on a similar path.

---

## License

[MIT](LICENSE)

Skills contain reference content from:
- [SAP Clean ABAP Style Guide](https://github.com/SAP/styleguides/blob/main/clean-abap/CleanABAP.md) — CC BY 4.0 (used in `abap-code-review`)
- [SAP Business Accelerator Hub](https://api.sap.com), [SAP Help Portal](https://help.sap.com) — public SAP documentation (used in `sap-integration-wiki`)

This project is not affiliated with, endorsed by, or officially supported by SAP SE.
