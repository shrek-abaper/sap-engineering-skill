<div align="center">

<h3>SAP ABAP engineering know-how, shipped as agent skills — not another generic chatbot</h3>

<h4><i>SKILL.md spec · read-only by default · evidence-first review · framework-agnostic</i></h4>

> Four skills cover the ABAP development lifecycle: reading and writing source through the ADT REST API, a 9-dimension pre-release code review, a 10-dimension transport request gate, and production-grade SAP integration knowledge. Writes are capability-gated with per-operation confirmation; review skills cite real evidence or declare an explicit gap — they never invent conclusions. Built by a working SAP consultant for daily real-world work.

**ADT REST API · 9-Dimension Code Review · 10-Dimension Transport Gate · Integration Knowledge Base · Evidence-First · Framework-Agnostic**

**MIT · Self-hosted · No vendor lock-in · ECC 6.0 & S/4HANA**

<h4>AI agent skills for the SAP ABAP release workflow</h4>

[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3-3776AB?style=flat-square&logo=python&logoColor=white)](src/sap_adt)
[![SAP](https://img.shields.io/badge/SAP-ADT%20REST%20API-0FAAFF?style=flat-square&logo=sap&logoColor=white)](#skills)
[![Skills](https://img.shields.io/badge/skills-4-2EA043?style=flat-square)](#skills)
[![Agents](https://img.shields.io/badge/agents-opencode%20%C2%B7%20Claude%20Code%20%C2%B7%20Cursor-orange?style=flat-square)](#compatible-ai-agents)

**English** · **[中文](README.zh-CN.md)**

**[Skills](#skills)** · **[Quick Start](#quick-start)** · **[Repository Structure](#repository-structure)** · **[Compatible Agents](#compatible-ai-agents)** · **[License](#license)**

</div>

---

## What Is This?

`sap-engineering-skill` is a monorepo of **AI agent skills** that cover the core workflow of SAP ABAP development: reading and writing source code, reviewing code quality and security before release, assessing transport requests at the gate, and answering SAP integration questions with production-ready precision.

Each skill follows the standard `SKILL.md` specification and works with any compatible AI agent framework — [opencode](https://opencode.ai), [Claude Code](https://docs.anthropic.com/en/docs/claude-code), Cursor, or any framework that supports custom tool/skill injection.

The skills `abap-code-review`, `sap-transport-gate`, and `sap-integration-wiki` were previously maintained as standalone public repositories. Those repositories are now **archived** (read-only) - all future updates happen exclusively in this monorepo.

---

## Skills

### [`sap-adt-cli`](skills/sap-adt-cli/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/sap-engineering-skill/tree/main/skills/sap-adt-cli)

A command-line tool and AI agent skill for reading **and writing** ABAP source code, metadata, and transport requests from SAP systems via the [ADT REST API](https://help.sap.com/docs/abap-cloud/abap-development-tools-user-guide/about-abap-development-tools).

The CLI (`sap-adt`) is an installable product distributed separately from the skill docs: **npm** `npm install -g "sap-adt-cli@^1.4.0"` (Node ≥ 18, self-contained runtime; npx also works but keeps no PATH command), **PyPI** `pip install "sap-adt>=1.4.0,<2.0.0"` (Python ≥ 3.10), and a **Linux portable archive** on the [release page](https://github.com/shrek-abaper/sap-engineering-skill/releases). The skill folder itself contains documentation only — no execution code.

**Supports**: programs, classes, function modules (with function group), function groups, interfaces, includes, CDS views, type groups (TYPE POOL), DDIC tables/structures/domains/data elements, packages, transactions, object search (`*` wildcard), read-only Open SQL data preview, where-used analysis, syntax checks, and transport request management (list/create/release).

**Key features**:
- Read-only by default; write and transport operations require explicit capability flags + a per-operation `[y/N]` preview confirmation that is never cached or reused (`--yes` only for trusted automation)
- Multi-environment **profiles** (DEV/QAS/PRD…) in `~/.sap-adt-cli/config.json` (0600) — switch with `profile use` or per-command `--profile`
- Passwords live in the **OS keystore**, never in the config file: backend priority `env` → `keyring` (Credential Manager / Keychain / Secret Service) → `dpapi` (WSL2) → `pass` (GPG) → `file` (scrypt + Fernet fallback); manage with `credentials set|forget|status|doctor`; old plaintext configs are auto-migrated and verbose logs / HTTP tracebacks stay redacted
- Environment variables or a dotenv file declared by `SAP_ADT_DOTENV` override profiles for CI/CD (the CLI never scans the current directory)
- Windows one-click installer (`setup-opencode-abap-cli.bat`) that installs opencode, clones this repo and installs the `sap-adt` CLI from it

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
- **Online Transport** — TR ID + the `sap-adt` CLI for live ADT collection

**Core principle**: Evidence-first. AI never invents conclusions from insufficient evidence.

- **Proactive online collection** — given a TR ID, the skill runs `sap-adt transport collect` itself and only falls back to Offline Local Mode when credentials or connectivity are missing; review scope (code-only vs functional + code) is confirmed before the review starts.

---

### [`sap-integration-wiki`](skills/sap-integration-wiki/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/sap-engineering-skill/tree/main/skills/sap-integration-wiki)

A composable knowledge-base skill that turns any AI assistant into a SAP integration specialist. Covers 9 business domains and 8 integration technologies — no more generic wrong answers.

**Business domains**: MM (Purchasing, Inventory), SD (Sales), FI (GL, AR/AP, Asset Accounting, FSSC — incl. Kingdee/金蝶 & 用友 interfacing and SAP Central Finance/CFIN replication), Master Data, PP (Production)

**Technologies**: OData V2/V4, RFC/JCo, SOAP over HTTP RFC (call RFCs without JCo), IDoc/PI-PO, BAPI & RAP, Authentication, BTP Integration Suite (iFlow, Cloud Connector, Event Mesh), Best Practices

**SAP versions**: ECC 6.0 · S/4HANA On-Prem 1909–2023+ · S/4HANA Cloud (Public & Private Edition)

---

## Reference Documentation

Cross-project guides live under [`docs/`](docs/), independent of any single skill:

| Document | Description |
|---|---|
| [`docs/installation/`](docs/installation/) | CLI install channels (npm, PyPI, portable, source), readiness/diagnostics matrix, Windows and portable notes |
| [`docs/development/`](docs/development/) | Architecture, build/release tooling, migration notes, and the archived `sap-adt-cli` refactor history |
| [`docs/agents/`](docs/agents/) | Claude Code plugin usage and generic `SKILL.md` agent guidance (incl. verification status) |
| [`docs/authentication/`](docs/authentication/) | Authentication playbook for SAP↔AI integration (CLI / MCP / OData): decision tree, detailed pros/cons and step-by-step implementation for Basic, SPNEGO, X.509, OIDC/OAuth2, edge-gateway and client patterns. This is a synced copy; the authoritative version is maintained in the `sap-functional-skill` repository. |

---

## Repository Structure

```
sap-engineering-skill/
├── src/sap_adt/                      ← ONLY CLI implementation (installable package)
├── skills/                           ← Skill content only (SKILL.md + references; no code)
│   ├── sap-adt-cli/
│   ├── abap-code-review/
│   ├── sap-transport-gate/           ← evals/ golden set included
│   └── sap-integration-wiki/         ← incl. content generators under scripts/
├── packaging/                        ← PyInstaller spec, npm templates, Windows installer, targets.json
├── tools/                            ← build_runtime / build_npm / build_skills / build_plugin /
│                                       build_manifest / check_release / sync_skill_runtime_docs
├── tests/                            ← unittest suite + fixtures/sap_adt_cli/ (sanitized ADT captures)
├── docs/                             ← installation/, development/, agents/, authentication/,
│                                       development/archive/sap-adt-cli/ (refactor history)
├── .claude-plugin/                   ← marketplace.json + plugin.json (docs-only plugin)
├── compatibility.json                ← per-skill CLI requirement + compatible CLI range
├── pyproject.toml                    ← CLI version authority
├── README.md / README.zh-CN.md
├── CONTRIBUTING.md / SECURITY.md / CHANGELOG.md
├── setup-opencode-abap-cli.bat       ← Windows one-click installer (opencode + sap-adt CLI)
└── .gitleaks.toml                    ← Secret-scan rules (also a pre-commit hook)
```

Distribution outputs (`dist/`) are generated by `tools/` and never committed. Each skill also carries generated `references/setup.md` + `references/runtime-compatibility.json` snapshots so a copied skill folder is self-contained.

The three skills above were historically tracked as git subtrees from standalone public repositories, which are now **archived** (read-only). All updates are maintained in this repo:

| Standalone repository (archived)              | Migrated to                                            |
| --------------------------------------------- | ------------------------------------------------------ |
| https://github.com/shrek-abaper/abap-code-review     | [`skills/abap-code-review/`](skills/abap-code-review/)     |
| https://github.com/shrek-abaper/sap-transport-gate   | [`skills/sap-transport-gate/`](skills/sap-transport-gate/) |
| https://github.com/shrek-abaper/sap-integration-wiki | [`skills/sap-integration-wiki/`](skills/sap-integration-wiki/) |

---

## Quick Start

### Claude Code — install as a plugin (recommended)

This repository is a self-hosted Claude Code plugin marketplace. Inside Claude Code:

```text
/plugin marketplace add shrek-abaper/sap-engineering-skill
/plugin install sap-engineering-skills@sap-engineering
```

All four skills are then available under the `sap-engineering-skills` namespace (e.g. `/sap-engineering-skills:sap-adt-cli`). Update with `/plugin` → Manage, or `claude plugin update sap-engineering-skills@sap-engineering`.

> The plugin distributes **skill documentation only** — it does not install the CLI. Install `sap-adt` separately: npm `npm install -g "sap-adt-cli@^1.4.0"` (or npx with the package prefix), PyPI `pip install "sap-adt>=1.4.0,<2.0.0"`, or the Linux portable archive (Windows installer and macOS runtime are not built yet). See [`docs/installation/runtime-setup.md`](docs/installation/runtime-setup.md). Offline skills (`abap-code-review`, `sap-integration-wiki`) work without it. The archive-sourced plugin requires Claude Code ≥ 2.1.224. Maintainer note: the plugin ships a pinned `version` in `.claude-plugin/plugin.json` — it **must be bumped on every release** or existing installations will not receive updates.

### Windows — sap-adt-cli one-click installer (opencode)

Download [`setup-opencode-abap-cli.bat`](setup-opencode-abap-cli.bat) and double-click. The script installs opencode, clones this repo, installs the `sap-adt` CLI from the clone (`pip install`), and self-tests it. Requires Node.js, Python 3 and Git.

### Other AI agents — manual symlink install (any OS)

opencode, Cursor, Codex, Gemini CLI, Windsurf/Devin, Roo Code, Zed, and GitHub Copilot all discover skills under `~/.agents/skills/` (some also read `~/.claude/skills/`). Note that Claude Code itself does **not** read `~/.agents/skills/` — use the plugin install above for Claude Code.

```bash
# Clone the repository
git clone https://github.com/shrek-abaper/sap-engineering-skill
cd sap-engineering-skill

# Link skills into the cross-agent skill directory
ln -s "$(pwd)/skills/sap-adt-cli"         ~/.agents/skills/sap-adt-cli
ln -s "$(pwd)/skills/abap-code-review"    ~/.agents/skills/abap-code-review
ln -s "$(pwd)/skills/sap-transport-gate"  ~/.agents/skills/sap-transport-gate
ln -s "$(pwd)/skills/sap-integration-wiki" ~/.agents/skills/sap-integration-wiki

# Install the CLI once (pick one channel; see docs/installation/runtime-setup.md)
pip install "sap-adt>=1.4.0,<2.0.0"            # Python ≥ 3.10 (published)
# or: npm install -g "sap-adt-cli@^1.4.0" && sap-adt install   # Node ≥ 18, no Python
#     (npx: npx "sap-adt-cli@^1.4.0" install, then prefix calls with npx "sap-adt-cli@^1.4.0")
# or (developers, from this checkout): python3 -m pip install -e .

# Configure a SAP connection profile (interactive wizard; password goes to the OS keystore)
sap-adt configure
# Add more environments with --profile dev/qas/prd; verify the active keystore backend:
sap-adt credentials doctor
# Offline knowledge/review skills need no CLI at all — see each skill's references/setup.md
```

Exceptions: Amazon Kiro only reads `~/.kiro/skills/` (use its "Import a skill" UI), Cline only reads `~/.cline/skills/`, and Trae requires UI import.

### Compatible AI agents

| Agent                                                         | Notes                                                                        |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | One-click install via the bundled plugin marketplace above                   |
| [opencode](https://opencode.ai)                               | Free, open-source. Reads `~/.agents/skills/` and `~/.claude/skills/`         |
| [Cursor](https://cursor.com)                                  | Native Agent Skills support; discovers `~/.agents/skills/`                   |

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

- **Tests** — a plain `unittest` suite lives at the repository root in `tests/` (CLI contract, keystore backends, config migration, security gates, distribution snapshots, plugin payload — 320 tests). It imports the `sap_adt` package, so install it once in a venv:

  ```bash
  python3 -m venv .venv && .venv/bin/pip install -e . ".[keystore,file]" build pyinstaller
  .venv/bin/python -m unittest discover -s tests -v
  .venv/bin/python tests/check_contract.py          # SKILL.md ↔ code contract
  node --test packaging/npm/test/install.test.js    # npm installer error paths
  ```

  Core runtime dependencies are `click` / `requests` / `urllib3`; `keyring` and `cryptography` are optional native-backend dependencies.
- **Verification is local** — no cloud CI: hosted runners cannot reach real SAP systems. Run the suite and the contract check locally before pushing.
- **Secret scanning** — gitleaks also runs as a pre-commit hook (`.pre-commit-config.yaml`). See [CONTRIBUTING.md](CONTRIBUTING.md) for placeholder rules and the WSL/DPAPI manual verification checklist.

---

## License

[MIT](LICENSE)

Skills contain reference content from:
- [SAP Clean ABAP Style Guide](https://github.com/SAP/styleguides/blob/main/clean-abap/CleanABAP.md) — CC BY 4.0 (used in `abap-code-review`)
- [SAP Business Accelerator Hub](https://api.sap.com), [SAP Help Portal](https://help.sap.com) — public SAP documentation (used in `sap-integration-wiki`)

This project is not affiliated with, endorsed by, or officially supported by SAP SE.
