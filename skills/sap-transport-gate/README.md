# sap-transport-gate

[English](README.md) | [中文](README.zh-CN.md)

> AI-assisted pre-release gate review for SAP Transport Requests.

An AI agent skill that performs structured, evidence-driven release readiness assessment for SAP Transport Requests. Produces an auditable `GO / CONDITIONAL_GO / NO_GO / NEED_MORE_EVIDENCE` decision and a formal Release Readiness Report.

---

## What It Does

`sap-transport-gate` guides an AI agent through a structured review workflow:

1. **Extract TR ID** — Detect Transport Request ID from user input (pattern: uppercase letters + K + 6 digits, e.g., `DEVK900123`); ask if not found
2. **Identify Review Mode** — Offline Package, Offline Local, or Online Transport; verify SAP credentials for Online mode
3. **Select Review Scope** — User confirms: **(A) Code Quality** only or **(B) Functional + Code Quality** (spec required for B)
4. **Evidence Intake** — Inventory all provided materials; flag gaps
5. **Evidence Level** — HIGH / MEDIUM / LOW / UNKNOWN based on completeness
6. **Multi-Dimension Review** — 10 dimensions covering the full release risk surface
7. **Finding Classification** — Structured findings with severity, confidence, evidence, and recommendation
8. **Release Decision** — Evidence-based GO / CONDITIONAL_GO / NO_GO / NEED_MORE_EVIDENCE
9. **Report Generation** — Markdown Release Readiness Report + JSON summary

---

## Core Principles

| Principle | Rule |
|---|---|
| **Evidence-first** | AI never invents conclusions from insufficient evidence. Every finding must trace to real code, metadata, or material. Every gap must be declared. |
| **No AI-side SAP login** | AI does not hold or request credentials. CLI performs read-only ADT calls only; AI consumes the collected evidence and never connects to SAP directly. |
| **Single file ≠ TR review** | One ABAP file cannot constitute a Transport Request-level release gate. Scope is always declared. |
| **LOW evidence → no GO** | If Evidence Level is `LOW`, decision is `NEED_MORE_EVIDENCE` or `NO_GO`. Never `GO`. |
| **No fabricated test results** | Unread objects are not assumed safe. Missing test evidence must be declared. |

---

## Review Dimensions

| # | Dimension | Key Risks |
|---|---|---|
| 1 | Code Quality | Naming, hardcoding, exception handling, dead code, complexity |
| 2 | Performance | SELECT-in-LOOP, full table scan, missing key conditions |
| 3 | Security | Dynamic SQL, OS commands, credential exposure, unvalidated input |
| 4 | Authorization | Missing AUTHORITY-CHECK, bypass patterns, privilege escalation |
| 5 | Transaction Consistency | COMMIT/ROLLBACK placement, BAPI commit inside LOOP, LUW integrity |
| 6 | Integration Impact | RFC, IDoc, OData, HTTP, BAPI, file interface risks |
| 7 | Transport Completeness | Missing objects, extra-TR dependencies, DDIC/CDS gaps |
| 8 | Functional Alignment | Code vs. spec — business rules, boundary conditions, exception flows |
| 9 | Release Readiness | Syntax check, activation status, test evidence, rollback plan |
| 10 | Evidence Gap | Missing materials and their decision impact |

---

## Release Decision Logic

```
Evidence Level UNKNOWN               → NEED_MORE_EVIDENCE (only)
Evidence Level LOW                   → NEED_MORE_EVIDENCE or NO_GO
CRITICAL Security / Auth / Txn risk  → NO_GO
CRITICAL risk (any dimension)        → NO_GO
HIGH Security or Auth risk           → NO_GO (treated as CRITICAL)
Unmitigated HIGH risk (other)        → NO_GO
Evidence gaps dominate               → NEED_MORE_EVIDENCE
MEDIUM findings + mitigation path    → CONDITIONAL_GO (EL: MEDIUM+)
LOW / INFO only + EL HIGH            → GO
```

---

## Review Modes

| Mode | When to Use |
|---|---|
| **Offline Package Mode** *(preferred)* | User provides a structured Review Package exported from SAP |
| **Offline Local Mode** | User provides partial materials (source files only, no manifest) |
| **Online Transport Mode** | TR ID provided + CLI output or internal tool access available |

In all modes: No AI-side SAP login; AI never holds or requests credentials. In Online Transport Mode, the CLI performs read-only ADT calls only.

---

## Evidence Level

| Level | Meaning | GO Allowed? |
|---|---|---|
| `HIGH` | Objects, source, dependencies, spec, syntax, activation, test evidence all present | ✅ Yes |
| `MEDIUM` | Key evidence present but some items missing (e.g., no test evidence) | ⚠️ CONDITIONAL_GO at best |
| `LOW` | Thin evidence: single file, missing object list, missing critical evidence | ❌ No |
| `UNKNOWN` | Materials unstructured or scope indeterminate | ❌ No (NEED_MORE_EVIDENCE only) |

---

## Quick Start (Online Transport Mode)

### 1. Install Dependencies

```bash
cd scripts
pip install -r requirements.txt
```

### 2. Configure SAP Credentials

**Option A: Environment file (recommended)**

```bash
cp .env.example .env
# Edit .env with your SAP connection details
```

`.env` content:

```ini
SAP_URL=https://your-sap-system.example.com:8000
SAP_USERNAME=YOUR_USERNAME
SAP_PASSWORD=YOUR_PASSWORD
SAP_CLIENT=100
SAP_LANGUAGE=EN
SAP_VERIFY_SSL=1   # set to 0 for self-signed certificates
```

**Option B: Interactive configure (saved to `~/.sap-transport-gate/config.json`)**

```bash
python3 scripts/tr_collector.py configure
```

Credential resolution order: `<skill_dir>/.env` → `~/.sap-transport-gate/config.json` → environment variables

### 3. Test Connectivity

```bash
python3 scripts/tr_collector.py ping
```

### 4. Collect Transport Review Package

```bash
python3 scripts/tr_collector.py collect DEVK900123
# Optional: specify output directory
python3 scripts/tr_collector.py collect DEVK900123 --output-dir ./my-review
```

After collection, provide the `review_package/` directory (containing `manifest.json` + source files) to the AI for review.

> **Note**: If the `/objects` ADT endpoint returns 404, the collector automatically falls back to E071 Data Preview SQL to retrieve the object list.

### 5. Submit to AI for Review

Hand the review package to an AI agent loaded with this skill:

```
Please review transport request DEVK900123. Materials are in review_package/DEVK900123/
```

---

## Output

### Markdown Report

Saved as `reports/TR_REVIEW_{TR_ID}_{YYYYMMDD}.md` (or `NOGO_...` prefix when decision is NO_GO).

**Structure**: Executive Decision → Scope Reviewed → Evidence Summary → Key Findings → Review by Dimension → Required Actions → Human Confirmation Checklist → Decision Rationale → Appendix

### JSON Summary

Saved alongside the Markdown report. Contains all findings, decision metadata, required actions, and human confirmation items in machine-readable format for CI pipelines, dashboards, and audit archives.

> Default save path: `reports/` under workspace root (auto-created if missing).

---

## Trigger Phrases

Load this skill when users say:

- "Review transport request DEVK900123 for QAS"
- "Can this TR go to production?"
- "Release gate check for this transport"
- "Is this transport ready to release?"
- "Audit this TR before import"
- "Generate a release readiness report"
- "Transport risk assessment"
- "Check if this ABAP code is safe to transport"

---

## Not for These Use Cases

- Standalone ABAP code explanation or debugging (use `abap-code-review` for single-program pre-release review)
- Executing transport release, import, or rollback operations
- Connecting to SAP systems directly
- Generating or accepting SAP passwords or connection strings
- Business result approval without a human approval process

---

## File Structure

```
sap-transport-gate/
├── .env.example                      ← Credential template (never commit .env)
├── .gitignore                        ← Git ignore rules
├── changelog.md                      ← Version history and migration notes
├── LICENSE                           ← MIT License
├── README.md                         ← English documentation (this file)
├── README.zh-CN.md                   ← Chinese documentation
├── SKILL.md                          ← Agent instructions
├── evals/
│   ├── evals.json                    ← Evaluation test cases (skill-creator format)
│   └── golden-set.yaml               ← Q&A pairs for knowledge retrieval coverage
├── references/
│   ├── abap-quality-rules.md         ← ABAP quality rule set
│   ├── abap-report-template.md       ← Report section templates
│   ├── abap-security-rules.md        ← Security rule catalog
│   ├── decision-policy.md            ← Evidence Level rules & Release Decision Policy
│   ├── human-loop.md                 ← Human confirmation triggers, role matrix
│   ├── regression-tests.md           ← 10 bad cases, 37 regression assertions
│   ├── report-format.md              ← Markdown report template & JSON schema
│   ├── review-dimensions.md          ← Detailed check items for all 10 dimensions
│   ├── review-modes.md               ← Mode detection, Review Package spec, evidence checklists
│   └── sap-connectivity.md           ← SAP connection configuration guide
└── scripts/
    ├── requirements.txt              ← Python dependencies
    ├── tr_collector.py               ← CLI: collect TR Review Package
    └── lib/
        ├── __init__.py
        ├── client.py                 ← SAP ADT HTTP client
        ├── config.py                 ← Credential loading (3-level priority)
        └── handlers.py              ← TR data handlers (with E071 fallback)
```

---

## Human Confirmation

Human confirmation is required for:

- Any release to **PRD**
- Any `HIGH` or `CRITICAL` finding
- Functional alignment when no spec is provided
- SECURITY / AUTHORIZATION findings (Security Owner required)
- INTEGRATION_IMPACT findings (Interface Owner required)
- Missing test evidence when release is still requested

Each confirmation item specifies: who confirms, what they confirm, based on what evidence, and what the risk is if they skip it.

---

## Related Skills

| Skill | Use When |
|---|---|
| `abap-code-review` | Single ABAP program pre-release code review (security, quality, 9 dimensions) without TR-level gate assessment |
| `sap-integration-wiki` | SAP integration patterns, API reference, best practices |
| `sap-adt-cli` | CLI tool for SAP ADT REST API access |

---

## License

MIT — see [LICENSE](LICENSE)
