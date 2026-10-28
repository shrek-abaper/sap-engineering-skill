<div align="center">

<h3>SAP ABAP engineering skills and an ADT CLI for AI agents</h3>

<h4><i>SKILL.md spec · evidence-first reviews · read-only by default · plain skill folders</i></h4>

> Four skills handle pre-release ABAP code review, transport request gate assessment, SAP integration reference, and read/write access to ABAP development objects through the ADT REST API. Each one is a `SKILL.md` workflow with its own rules and references, usable from Claude Code, Codex, WorkBuddy and other agent tools that load skills.

**ADT REST API · Code Review · Transport Gate · Integration Knowledge · Evidence-First**

**MIT · Self-hosted · ECC 6.0 & S/4HANA**

<h4>Offline review works without SAP · live operations need the CLI and a connection</h4>

[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3-3776AB?style=flat-square&logo=python&logoColor=white)](src/sap_adt)
[![SAP](https://img.shields.io/badge/SAP-ADT%20REST%20API-0FAAFF?style=flat-square&logo=sap&logoColor=white)](#what-you-can-do)
[![Skills](https://img.shields.io/badge/skills-4-2EA043?style=flat-square)](#what-you-can-do)
[![Agents](https://img.shields.io/badge/agents-Claude%20Code%20%C2%B7%20Codex%20%C2%B7%20WorkBuddy-orange?style=flat-square)](#supported-agents)

**English** · **[中文](README.zh-CN.md)**

**[What you can do](#what-you-can-do)** · **[Quick start](#quick-start)** · **[Usage examples](#usage-examples)** · **[How it works](#how-it-works)** · **[Support and safety](#support-and-safety)** · **[Documentation](#documentation)** · **[License](#contributing-and-license)**

</div>

---

## What you can do

| Task | Skill | SAP connection |
|---|---|---|
| Review ABAP code before release | [`abap-code-review`](skills/abap-code-review/) | Not needed — you provide the source |
| Assess a transport request before import | [`sap-transport-gate`](skills/sap-transport-gate/) | Not needed with a review package or source files; online collection uses the CLI |
| Look up how to integrate SAP with Java, Python, .NET, Node.js or BTP | [`sap-integration-wiki`](skills/sap-integration-wiki/) | Not needed |
| Read or write ABAP objects and transports on a live system | [`sap-adt-cli`](skills/sap-adt-cli/) | Required — installed CLI, connection profile, matching permissions |

`abap-code-review` covers 9 review dimensions and `sap-transport-gate` covers 10. The per-dimension checks, supported object types and report contracts are documented in each skill's README and `references/` files; this page does not repeat them.

Both review skills produce a Markdown report with severity-ranked findings and an explicit decision — `GO / CONDITIONAL GO / NO-GO` for code review, `GO / CONDITIONAL_GO / NO_GO / NEED_MORE_EVIDENCE` for the transport gate. Findings cite the code or material they came from. Missing evidence is listed as a gap rather than assumed to be safe.

---

## Quick start

Two independent steps: install the skills into your agent, and — only if you need live SAP access — install and configure the CLI.

### 1. Add the skills

**Claude Code** installs them from this repository's plugin marketplace:

```text
/plugin marketplace add shrek-abaper/sap-engineering-skill
/plugin install sap-engineering-skills@sap-engineering
```

The four skills then appear under the `sap-engineering-skills` namespace (for example `/sap-engineering-skills:sap-adt-cli`). Update through `/plugin` → Manage, or `claude plugin update sap-engineering-skills@sap-engineering`. The plugin distributes skill documentation only and does not install the CLI. This plugin source requires Claude Code ≥ 2.1.224.

**Other agents** load plain `SKILL.md` folders: copy the complete skill folder — references included, not just `SKILL.md` — into the directory your agent scans. Some discover `~/.agents/skills/`; others use their own directory or an import UI. See [docs/agents/generic-skills.md](docs/agents/generic-skills.md) for the documented flows and [Supported agents](#supported-agents) below.

### 2. Install the CLI (only for live SAP access)

`sap-adt-cli` needs the CLI for every online operation, and `sap-transport-gate` needs it for online transport collection. `abap-code-review` and `sap-integration-wiki` never do.

With Node.js ≥ 18 (no Python required for this channel):

```bash
npm install -g "sap-adt-cli@^1.5.0"
sap-adt install
sap-adt --version
```

The npm package installs a launcher; `sap-adt install` fetches, verifies and installs the platform runtime. A normal `sap-adt` call never downloads or upgrades anything. The self-contained runtime is currently published for Linux x86_64 only — the Windows installer and the macOS runtime are not built yet.

Without a global install, npx keeps nothing on `PATH`: run `npx "sap-adt-cli@^1.5.0" install` and keep that package prefix on every later call.

With Python ≥ 3.10, no Node.js needed:

```bash
pip install "sap-adt-cli>=1.5.0,<2.0.0"
sap-adt --version
```

Then point it at a system:

```bash
sap-adt configure            # interactive wizard; the password is entered locally
sap-adt status               # local configuration state only — it does not contact SAP
sap-adt credentials doctor   # which keystore backend is active, without showing secrets
```

Do not pass a password on the command line or paste one into the chat. For multiple environments use `--profile dev|qas|prd`; environment variables or a dotenv file declared by `SAP_ADT_DOTENV` override profiles for CI/CD.

Full channel list, the portable Linux archive, credential precedence and the diagnostics matrix: [docs/installation/runtime-setup.md](docs/installation/runtime-setup.md).

---

## Usage examples

These are example requests, not recorded runs.

**Review code you already have (no SAP connection):**

```text
Review the ABAP report I'm pasting below for release. It reads VBAK/VBAP and
writes an ALV list. Flag security, authorization, performance and standards
issues, and tell me whether anything blocks release.

[paste the report source, including any INCLUDEs]
```

Expected output: findings grouped by severity, each with a code excerpt, location, cited rule ID and a fix; a `GO / CONDITIONAL GO / NO-GO` recommendation with a sign-off table; and a list of objects or INCLUDEs that could not be reviewed.

**Assess a transport request from materials you provide:**

```text
Assess transport DEVK900123 before import to QAS. I'm attaching the object list
and the source files; there is no functional spec and no test evidence.
```

Expected output: a question about review scope (code quality only, or functional + code quality), an explicit evidence level, `EVIDENCE_GAP` findings for the missing spec and test evidence, and a decision that low evidence cannot push to `GO`. The report is written under `reports/DEVK900123_package/` with a Markdown report and a JSON summary.

**Ask an integration question:**

```text
How do I create a purchase order in S/4HANA from Python?
```

Expected output: the recommended technology for your SAP version and scenario, SAP-side prerequisites, implementation steps with working snippets, and 2–3 common pitfalls.

Review output is an input to your release process, not the approval itself. A developer, technical lead or release manager still has to sign off, test and import.

---

## How it works

| Component | What it is |
|---|---|
| **Skill** | A folder containing `SKILL.md` (workflow steps, hard constraints), check rules and reference files. Your agent loads it; no executable code is involved. |
| **CLI** | The `sap-adt` command, a separate program that talks to the SAP ADT REST API for live reads, writes and transport collection. Packaged for npm and PyPI; source lives in this repository. |
| **Plugin** | How Claude Code installs and updates the four skill folders from this repository. Documentation only — the CLI is always installed separately. |

The repository is a single distribution point for the four skills and the CLI source, but you do not need its build layout to use either. The same skill folders can be loaded by other agents that support `SKILL.md`; discovery paths vary.

---

## Support and safety

### Platforms

| Platform | Available today |
|---|---|
| Linux x86_64 | npm runtime, portable archive (glibc 2.39 build verified on Ubuntu 24.04), PyPI |
| Windows x86_64 | PyPI with Python ≥ 3.10; copy the skill folders into your agent's skill directory; no standalone Windows runtime installer yet |
| macOS | PyPI with Python ≥ 3.10; no runtime build yet |

The Windows Inno Setup installer is implemented but has not been built or verified on a Windows host, and the macOS runtime is planned only. Do not rely on either until a real build and install test exists.

### SAP prerequisites

ECC 6.0 and S/4HANA are the target systems. Online use requires the ADT services to be active on the system (ICF node `/sap/bc/adt`), a network route from your machine, and a user authorized for the objects and actions you request. Individual ADT endpoints differ by release: `sap-adt discovery` and `sap-adt credentials doctor --coverage` report what a given system exposes. Not every ECC/S/4HANA release and endpoint combination has been verified here.

### Safety defaults

- **Read-only by default.** Writes, activation and transport release require the capability to be enabled in the profile and a fresh `[y/N]` preview for each operation. `--yes` exists for trusted automation; it is not a blanket approval. A profile marked `environment=prd` refuses all write-class operations regardless of flags.
- **SQL preview is SELECT-only.** Non-SELECT DML is rejected before any request is sent.
- **Secrets stay out of the config file.** Passwords go through the OS keystore or an explicit environment/dotenv layer, depending on what is available on the machine; `sap-adt credentials doctor` shows the active backend.
- **Transport gate never executes transports** and never asks for SAP credentials. Online collection is read-only and performed by the CLI.
- **Installing the CLI does not sandbox the agent.** It defines which SAP operations the agent can reach; it does not restrict what else the agent may do on your machine.
- **Reviews are advisory.** AI output does not replace human testing, architecture review, security approval or release accountability.
- **Check your data policy first.** ABAP source can contain core business logic and personal data. Before sending it to a cloud-hosted agent, confirm this is allowed by your organization. A locally installed CLI does not mean nothing leaves the machine: online calls reach your SAP system, and the agent may send context to its model provider.

### Supported agents

| Agent | How to use it |
|---|---|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | Plugin install from this repository (see Quick start) |
| Codex | Generic `SKILL.md` agent — copy the complete skill folders into the directory it scans; see [docs/agents/generic-skills.md](docs/agents/generic-skills.md) |
| WorkBuddy | Same generic folder flow — copy the complete skill folders into the directory it scans |
| Amazon Kiro, Cline, Trae and similar tools | Use the agent's own skill directory or import UI; paths vary by tool |

Discovery paths vary between agents — see [docs/agents/](docs/agents/).

---

## Documentation

| Document | Contents |
|---|---|
| [docs/installation/](docs/installation/) | CLI channels (npm, npx, PyPI, portable, source), credential precedence, readiness checks, diagnostics matrix |
| [docs/agents/](docs/agents/) | Claude Code plugin details and generic `SKILL.md` agent guidance |
| [docs/authentication/](docs/authentication/) | SAP↔AI authentication playbook: Basic, SPNEGO, X.509, OIDC/OAuth2, gateway and client patterns (synced copy; authoritative version in `sap-functional-skill`) |
| [docs/development/](docs/development/) | Architecture, build and release tooling, migration notes, archived refactor history |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Local test baseline, secret scanning, WSL/DPAPI verification checklist |
| [SECURITY.md](SECURITY.md) | How to report a vulnerability |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

Each skill also has its own README and references: [`sap-adt-cli`](skills/sap-adt-cli/), [`abap-code-review`](skills/abap-code-review/), [`sap-transport-gate`](skills/sap-transport-gate/), [`sap-integration-wiki`](skills/sap-integration-wiki/).

---

## Contributing and license

Contributions are welcome. The test suite is plain `unittest` and runs locally. There is no cloud CI — hosted runners cannot reach real SAP systems, so the meaningful verification is done on a machine with system access. Start with [CONTRIBUTING.md](CONTRIBUTING.md).

[MIT](LICENSE)

Skills contain reference content from:

- [SAP Clean ABAP Style Guide](https://github.com/SAP/styleguides/blob/main/clean-abap/CleanABAP.md) — CC BY 4.0 (used in `abap-code-review`)
- [SAP Business Accelerator Hub](https://api.sap.com), [SAP Help Portal](https://help.sap.com) — public SAP documentation (used in `sap-integration-wiki`)

This project is not affiliated with, endorsed by, or officially supported by SAP SE.
