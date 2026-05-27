# abap-code-review

[English](README.md) | [中文](README.zh-CN.md)

An AI agent skill for SAP ABAP pre-release code review. Performs a comprehensive security and quality assessment across 9 dimensions and produces a formal, sign-off-ready Markdown report.

---

## Overview

`abap-code-review` is an AI agent skill that guides any AI agent through a structured, repeatable ABAP code review workflow. It is designed to catch security vulnerabilities, authorization gaps, performance risks, and code quality issues before a transport is promoted to production.

### Why use it?

- **Consistent coverage** — 9 review dimensions, no dimension is ever skipped
- **Evidence-based findings** — every finding requires a real code snippet; no speculation
- **Rule-cited** — security and standards findings are always tied to a named rule (e.g. `SEC-SQL-1`, `[T-2]`)
- **Release-decision ready** — output is a structured report with GO / CONDITIONAL GO / NO-GO recommendation and a sign-off table

---

## Review Dimensions

| # | Dimension | Key Checks |
|---|-----------|-----------|
| 1 | **[SEC]** Security Vulnerabilities | SQL injection, code injection, OS command injection, file path attacks, hardcoded credentials |
| 2 | **[AUTH]** Authorization & Access Control | Missing AUTHORITY-CHECK, unchecked SY-SUBRC, authorization bypass patterns |
| 3 | **[DATA]** Data Integrity & Exception Handling | SY-SUBRC after FM calls, locking before writes, empty CATCH blocks |
| 4 | **[PERF]** Performance Risks | SELECT inside LOOP, SELECT *, full table scans, wrong internal table type |
| 5 | **[STD]** ABAP Code Standards | Deprecated statements, hardcoded business values, oversized methods, commented-out code |
| 6 | **[INTERFACE]** Interface & Integration Risks | Dialog messages in RFC FMs, missing EXCEPTIONS, OData backend auth |
| 7 | **[CHANGE]** Change Impact Assessment | Affected tables, modifications to SAP standard objects, shared INCLUDEs, transport dependencies |
| 8 | **[COMP]** Compliance & Audit Trail | PII handling, dual-control for postings, audit log coverage, SoD paths |
| 9 | **[FUNC]** Functional Completeness *(optional)* | Business scenario coverage, boundary conditions, logic vs. requirements |

---

## How to Use

### Invoke the agent

```
Review program [PROGRAM_NAME] for release.
Transport: [DEVKXXXXXX], Change description: [one-line business purpose].
Save the report to the reports/ directory.
```

### Include functional review (optional)

Append the requirements document path or describe the requirements inline if you also want the [FUNC] dimension evaluated.

### Output

The agent saves a Markdown report to the `reports/` directory you specify:

- Default filename: `ABAP_REVIEW_[PROGRAM_NAME]_[YYYYMMDD].md`
- CRITICAL findings present: `CRITICAL_ABAP_REVIEW_[PROGRAM_NAME]_[YYYYMMDD].md`

---

## Report Structure

Each generated report contains:

1. **Report Header** — program, transport, change description, reviewer, date, scope
2. **Executive Summary** — 3–5 sentence overview of findings and recommendation
3. **Release Recommendation** — 🔴 NO-GO / 🟡 CONDITIONAL GO / 🟢 GO with justification
4. **Risk Summary** — finding counts by severity level
5. **Detailed Findings** — code evidence, rule citation, risk description, remediation for each issue
6. **Dimension Coverage Summary** — confirmation that all 9 dimensions were completed
7. **Scope Limitations** — any objects that could not be retrieved
8. **Remediation Checklist** — action items for CRITICAL and HIGH findings
9. **Sign-off Table** — slots for Developer, Technical Lead, Release Manager, Security Owner

---

## Severity Levels

| Level | Label | Release Impact |
|-------|-------|---------------|
| 🔴 | CRITICAL | Blocks release |
| 🟠 | HIGH | Should block release |
| 🟡 | MEDIUM | Fix in next sprint |
| 🟢 | LOW | Advisory |
| ℹ️ | INFO | No action required |

**Special rule**: Any HIGH finding in [SEC] or [AUTH] is treated as CRITICAL (automatic NO-GO).

---

## Release Decision Logic

```
CRITICAL finding present               → NO-GO
HIGH finding in [SEC] or [AUTH]        → NO-GO  (special rule)
HIGH finding in other dimensions       → CONDITIONAL GO  (tech lead sign-off required)
MEDIUM / LOW / INFO findings only      → GO
```

---

## File Structure

```
abap-code-review/
├── SKILL.md                          ← Agent instructions (SKILL definition; loaded by the agent host)
├── README.md                         ← This file (English)
├── README.zh-CN.md                   ← Chinese version
└── references/
    ├── REF_ABAP_SECURITY.md          ← Security rules for [SEC] and [AUTH] dimensions
    ├── REF_CLEAN_ABAP.md             ← Clean ABAP rules for [STD] dimension
    └── REPORT_TEMPLATE.md            ← Report template loaded in Step 5
```

---

## Reference Sources

| Reference File | Source |
|----------------|--------|
| `REF_ABAP_SECURITY.md` | SAP ABAP Keyword Documentation; SAP CVA categories; RedRays ABAP Scanner (164 rules); CVE-2025-0063, CVE-2025-42957; DSAG ABAP Development Recommendations |
| `REF_CLEAN_ABAP.md` | SAP Clean ABAP Style Guide (`github.com/SAP/styleguides`, CC BY 4.0) |

---

## Supported Object Types

| Type | Scope Read |
|------|-----------|
| REPORT | Main program + all INCLUDEs |
| Global Class | Class definition + all METHOD implementations |
| Function Module | Target FM + other FMs in the same function group |
| Enhancement / BAdI | Enhancement Spot definition + all active implementations |

---

## License

Reference content derived from the [SAP Clean ABAP Style Guide](https://github.com/SAP/styleguides/blob/main/clean-abap/CleanABAP.md) is used under the [Creative Commons Attribution 4.0 International License (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).

All other content in this repository is original work.
