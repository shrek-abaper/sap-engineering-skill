<div align="center">

<h1>Watt</h1>

<h3>Power your SAP Engineering.</h3>

<h4><i>An engineering CLI for SAP lifecycle work · evidence first · explicit authority · traceable outcomes</i></h4>

> Controlled operations and traceable evidence for SAP work, from understanding a system to reviewing and delivering change.

**Independent community project · not an official SAP product · no embedded LLM**

**ADT REST API · Code Review · Transport Gate · Integration Knowledge · Evidence-First**

**MIT · Self-hosted · ECC 6.0 & S/4HANA**

<h4>Offline review works without SAP · live operations need the CLI and a connection</h4>

[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3-3776AB?style=flat-square&logo=python&logoColor=white)](src/sap_adt)
[![SAP](https://img.shields.io/badge/SAP-ADT%20REST%20API-0FAAFF?style=flat-square&logo=sap&logoColor=white)](#what-you-can-do)
[![Skills](https://img.shields.io/badge/skills-4-2EA043?style=flat-square)](#what-you-can-do)
[![Agents](https://img.shields.io/badge/agents-Claude%20Code%20%C2%B7%20Codex%20%C2%B7%20WorkBuddy-orange?style=flat-square)](#supported-agents)

**English** · **[中文](README.zh-CN.md)**

**[Meet Watt](#meet-watt)** · **[What you can do](#what-you-can-do)** · **[Quick start](#quick-start)** · **[Usage examples](#usage-examples)** · **[How it works](#how-it-works)** · **[Support and safety](#support-and-safety)** · **[Roadmap](#roadmap)** · **[Documentation](#documentation)** · **[License](#contributing-and-license)**

</div>

---

## Meet Watt

**Watt is an engineering CLI for SAP lifecycle work.** It provides controlled
operations and inspectable evidence that people can use directly or AI agents
can compose into workflows. It is a tool for doing and verifying SAP work,
not an embedded LLM or a general-purpose conversation assistant.

### Why Watt?

Watt takes its name from the unit of power, named in honor of James Watt.
Power is the rate of doing work. For this project, the name expresses a goal:
**steady, sustained and controllable engineering work**, rather than a burst
of automation whose effects are hard to inspect.

That means gathering facts, making changes within explicit boundaries and
checking outcomes. The name is a design intention, not a throughput guarantee.
Watt stands on its own as an independent community project, not an official
SAP product.

### Who it serves

Watt is for SAP teams, not a single job title. Implementation and functional
consulting, development, testing, delivery and operations all depend on reliable
technical facts and controlled actions. People remain responsible for decisions
and approvals; agents can help interpret evidence and coordinate the work.

### Why this project

SAP work crosses roles and system boundaries. Reading source is only one part:
teams also need attributable diagnostics, reviewed changes, transport evidence
and clear approval boundaries. Watt turns current ADT capabilities into a
deterministic CLI and layers portable `SKILL.md` workflows on top. Its question
is not just whether an operation can run, but **whether its intent, evidence
and outcome can be inspected and trusted**.

### Core principles

1. **Evidence first.** Separate observed facts, hypotheses and missing evidence. An accepted request is not a verified outcome.
2. **Explicit authority.** Read-only by default; changes, execution and debugging need their own authorization. Human approval stays human.
3. **Clear tool boundaries.** The CLI supplies deterministic operations and structured results; Skills supply workflows and references; agents supply reasoning.
4. **Verified progress.** Expand through tested SAP scenarios. State what is supported and what remains unverified, rather than promising universal coverage.
5. **Compatibility is reliability.** Preserve working scripts, configuration and credential identifiers as the product evolves.

**ADT and ABAP are the current foundation, not the long-term boundary.**
Today Watt covers source and metadata access, diagnostic evidence, governed
changes, testing and execution. Companion Skills add code review, transport risk
assessment and integration guidance. Broader lifecycle coverage is a direction,
not a claim that every SAP task is already supported.

For the mechanisms behind these principles, see
[engineering principles and boundaries](docs/design-principles.md).

---

## What you can do

| Task | Skill | SAP connection |
|---|---|---|
| Review ABAP code before release | [`abap-code-review`](skills/abap-code-review/) | Not needed — you provide the source |
| Assess a transport request before import | [`sap-transport-gate`](skills/sap-transport-gate/) | Not needed with a review package or source files; online collection uses the CLI |
| Look up how to integrate SAP with Java, Python, .NET, Node.js or BTP | [`sap-integration-wiki`](skills/sap-integration-wiki/) | Not needed |
| Read or write ABAP objects and transports on a live system | [`sap-adt-cli`](skills/sap-adt-cli/) | Required — installed CLI, connection profile, matching permissions |
| Diagnose ABAP Unit failures and runtime dumps | [`sap-adt-cli`](skills/sap-adt-cli/) | Supplied evidence works offline; new evidence reads require CLI 1.6.1+ and SAP access |
| Explicitly debug an approved non-production target | [`sap-adt-cli`](skills/sap-adt-cli/references/debugging.md) | Experimental CLI 1.6.1+; bounded foreground owner, independent `allow_debug` and fresh control approval; no automatic escalation from diagnosis |
| Execute a Class, Report or ABAP snippet with local function/BAPI calls | [`sap-adt-cli`](skills/sap-adt-cli/references/execution.md) | CLI 1.6.3+; independent `allow_execute`, non-production and hash-bound approval; CLI 1.6.4+ snippets do not require `allow_write` |
| Develop Class parts, check candidate buffers, create basic objects and inspect read-only RAP/OData | [`sap-adt-cli`](skills/sap-adt-cli/references/development.md) | CLI 1.6.4+; controlled creation/writes, explicit missing-include consent, same-origin bounded runtime reads; no RAP publication |
| Run Unit regression/JUnit, typed functions, Report selections and reviewed multi-object DDIC/RAP development | [`sap-adt-cli`](skills/sap-adt-cli/references/core-workflows.md) | CLI 1.6.5+; isolated DEV acceptance, separate execution/write consent, no automatic conversion/publication/rollback; server Unit risk limits still apply |
| Bind targets, inspect enhancement/transport impact, compare configuration, aggregate quality and package requirement evidence | [`sap-adt-cli`](skills/sap-adt-cli/references/executor.md) | CLI 1.6.6+; explicit gaps, supplied coverage/lint binding, local Git/TR mappings, no LLM/index/orchestration or automatic release; packaging existing evidence works offline |

`abap-code-review` covers 9 review dimensions and `sap-transport-gate` covers 10. The per-dimension checks, supported object types and report contracts are documented in each skill's README and `references/` files; this page does not repeat them.

Both review skills produce a Markdown report with severity-ranked findings and an explicit decision — `GO / CONDITIONAL GO / NO-GO` for code review, `GO / CONDITIONAL_GO / NO_GO / NEED_MORE_EVIDENCE` for the transport gate. Findings cite the code or material they came from. Missing evidence is listed as a gap rather than assumed to be safe.

---

## Quick start

Two independent steps: install the skills into your agent, and — only if you need live SAP access — install and configure the CLI.

### 1. Add the skills

**Claude Code** installs them from this repository's plugin marketplace:

```text
/plugin marketplace add shrek-abaper/sap-watt
/plugin install sap-engineering-skills@sap-engineering
```

The four skills then appear under the `sap-engineering-skills` namespace (for example `/sap-engineering-skills:sap-adt-cli`). Update through `/plugin` → Manage, or `claude plugin update sap-engineering-skills@sap-engineering`. The plugin distributes skill documentation only and does not install the CLI. This plugin source requires Claude Code ≥ 2.1.224.

**Other agents** load plain `SKILL.md` folders: copy the complete skill folder — references included, not just `SKILL.md` — into the directory your agent scans. Some discover `~/.agents/skills/`; others use their own directory or an import UI. See [docs/agents/generic-skills.md](docs/agents/generic-skills.md) for the documented flows and [Supported agents](#supported-agents) below.

### 2. Install the CLI (only for live SAP access)

`sap-adt-cli` needs the CLI for every online operation, and `sap-transport-gate` needs it for online transport collection. `abap-code-review` and `sap-integration-wiki` never do.

With Node.js ≥ 18 (no Python required for this channel):

```bash
npm install -g "sap-watt@^1.6.7"
sap-watt install
sap-watt --version
```

The npm package installs a launcher; `sap-watt install` fetches, verifies and installs the platform runtime. A normal `sap-watt` call never downloads or upgrades anything. Linux x86_64 and Windows x86_64 runtimes are available, plus experimental macOS 15+ runtimes for Intel and Apple Silicon.

On Windows without Node.js or Python, download the unsigned `sap-adt-<ver>-windows-x86_64-setup.exe` from the [releases](https://github.com/shrek-abaper/sap-watt/releases). See the [Windows guide](docs/installation/windows.md) for verified scope and limitations.

Without a global install, npx keeps nothing on `PATH`: run `npx "sap-watt@^1.6.7" install` and keep that package prefix on every later call.

With Python ≥ 3.10, no Node.js needed:

```bash
python -m pip install "sap-watt>=1.6.7,<2.0.0"
sap-watt --version
```

Then point it at a system:

```bash
sap-watt configure            # interactive wizard; the password is entered locally
sap-watt status               # local configuration state only — it does not contact SAP
sap-watt credentials doctor   # which keystore backend is active, without showing secrets
```

Do not pass a password on the command line or paste one into the chat. For multiple environments use `--profile dev|qas|prd`; environment variables or a dotenv file declared by `SAP_ADT_DOTENV` override profiles for CI/CD.

Full channel list, the portable Linux archive, credential precedence and the diagnostics matrix: [docs/installation/runtime-setup.md](docs/installation/runtime-setup.md).

**Already using `sap-adt`?** Keep it: existing scripts, Skill IDs, `SAP_*`
variables, `~/.sap-adt-cli` configuration and credential identifiers are
unchanged. Watt starts at 1.6.7; install the new package to obtain `sap-watt`.
It owns only the new command. Python shares an exact-version core dependency;
npm packages have independent runtime slots. Native assets/installers retain
the `sap-adt` name. See the [migration guide](docs/installation/runtime-setup.md#watt-installation-and-migration-167).

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

**Diagnose a failed Unit run (CLI 1.6.1+):**

```text
Diagnose the supplied ZCL_EXAMPLE Unit failure on qas. Read the returned
test include location; use dump details only when attributable to this run.
Give me evidence, gaps and next actions, without changing code or rerunning
with broader risk or duration.
```

The Skill composes `run-unit-test --require-tests`, `get-source` and
`get-dump`; it does not introduce a workflow engine. Empty runs are not
passes, and unsupported dump detail degrades explicitly to ST22. Python and
native npm runtimes expose the same commands and JSON contract. See the
[diagnosis reference](skills/sap-adt-cli/references/test-failure-diagnosis.md)
and [release status](CHANGELOG.md) before upgrading.

Review output is an input to your release process, not the approval itself. A developer, technical lead or release manager still has to sign off, test and import.

---

## How it works

| Component | What it is |
|---|---|
| **Skill** | A folder containing `SKILL.md` (workflow steps, hard constraints), check rules and reference files. Your agent loads it; no executable code is involved. |
| **CLI** | Watt (`sap-watt`, compatible `sap-adt`), a separate deterministic program for SAP operations and evidence. Packaged for npm and PyPI; one implementation lives in this repository. No embedded LLM. |
| **Plugin** | How Claude Code installs and updates the four skill folders from this repository. Documentation only — the CLI is always installed separately. |

The repository is a single distribution point for the four skills and the CLI source, but you do not need its build layout to use either. The same skill folders can be loaded by other agents that support `SKILL.md`; discovery paths vary.

---

## Support and safety

### Platforms

| Platform | Available today |
|---|---|
| Linux x86_64 | npm runtime, portable archive (glibc 2.39 build verified on Ubuntu 24.04), PyPI |
| Windows x86_64 | npm runtime, portable ZIP and desktop installer from CLI 1.5.3; PyPI with Python ≥ 3.10 |
| macOS 15+ Intel / Apple Silicon | Experimental npm runtime and portable archive from CLI 1.6.0; PyPI with Python ≥ 3.10 |

Windows npm installation and the desktop installer's silent per-user install, same-version upgrade and uninstall were verified on Windows 11 x64 through WSL interop. Graphical wizard clicks, actual PATH mutation and elevated installation remain unverified; the installer is unsigned. macOS releases are gated by native GitHub Actions builds, offline tests and isolated npm install checks on both architectures. Personal Macs, older macOS, Keychain, Gatekeeper/quarantine, signing/notarization and live SAP on macOS remain unverified. Install the skill folders separately from the CLI on every platform.

### SAP prerequisites

ECC 6.0 and S/4HANA are the target systems. Online use requires the ADT services to be active on the system (ICF node `/sap/bc/adt`), a network route from your machine, and a user authorized for the objects and actions you request. Individual ADT endpoints differ by release: `sap-adt discovery` and `sap-adt credentials doctor --coverage` report what a given system exposes. Not every ECC/S/4HANA release and endpoint combination has been verified here.

### Safety defaults

- **Read-only by default.** Writes, activation and transport release require the capability to be enabled in the profile and a fresh `[y/N]` preview for each operation. `--yes` exists for trusted automation; it is not a blanket approval. A profile marked `environment=prd` refuses all write-class operations regardless of flags.
- **Debug permission is independent.** `allow_debug` defaults to false; source writes can stay disabled. Non-production and per-action confirmation still apply. Debug execution can let the target write business data; this is not a read-only sandbox.
- **ABAP execution is separately authorized.** `run-class`, `run-report` and `run-abap` require independent `allow_execute`, non-PRD and fresh approval. `--yes` requires a reviewed dry-run plan hash. From CLI 1.6.4, snippets use an owned temporary Class in `$TMP` under execution authorization without requiring `allow_write`; generic source-write commands remain gated. SAP development permissions are still needed, and execution may change business data even with source writes disabled. No native RFC dependency, automatic COMMIT, rollback or execution replay. Unknown execution may leave a temporary object for operator inspection.
- **CLI 1.6.5 high-risk Unit uses execution consent.** Dangerous/critical Unit, typed `run-function` and parameterized Report wrappers require `allow_execute`, not generic `allow_write`. Repository manifests require `allow_write`; adding a high-risk final Unit gate requires both, for separate stages. Existing DDIC storage conversions, container/table deletion and service publication are excluded.
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

## Roadmap

Direction, not commitments; each item ships only with offline regression and real-system verification.

| Theme | Goal |
|---|---|
| **Change sets** | Multi-object plans bound by one hash: lock all, verify each, activate together, report every stage — from changing an object to delivering a requirement |
| **Object lifecycle** | Create programs, classes (incl. local and test includes), function groups, then DDIC and CDS, within allowed namespaces and packages |
| **Gates in the write path** | Syntax check, ATC and ABAP Unit as configurable pre-write gates whose results feed the transport gate as evidence |
| **Policy and audit** | Package/namespace allow-lists per environment; a local audit trail of every plan hash, transport and stage result |
| **Compatibility matrix** | Feature detection via ADT discovery; protocol facts verified on additional releases (7.50 / ECC, S/4HANA 2023) |
| **Enterprise authentication** | SSO / X.509 first, then OAuth for SAP BTP |
| **Scenario evaluation** | Sandbox benchmarks for requirement → code → test → transport, measuring agent success and unsafe-action rates |

---

## Documentation

| Document | Contents |
|---|---|
| [docs/design-principles.md](docs/design-principles.md) | Evidence semantics, authorization mechanisms, tool boundaries, verification limits and compatibility |
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

Contributions are welcome. The test suite is plain `unittest` and runs locally; a manually dispatched macOS workflow also runs offline tests and native packaging checks. Hosted runners never connect to SAP, so real-system verification remains local. Start with [CONTRIBUTING.md](CONTRIBUTING.md).

[MIT](LICENSE)

Skills contain reference content from:

- [SAP Clean ABAP Style Guide](https://github.com/SAP/styleguides/blob/main/clean-abap/CleanABAP.md) — CC BY 4.0 (used in `abap-code-review`)
- [SAP Business Accelerator Hub](https://api.sap.com), [SAP Help Portal](https://help.sap.com) — public SAP documentation (used in `sap-integration-wiki`)

This project is not affiliated with, endorsed by, or officially supported by SAP SE.
