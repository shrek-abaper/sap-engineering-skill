---
name: abap-code-review
description: "Performs structured pre-release security and quality review of SAP ABAP programs across 9 dimensions (SEC, AUTH, DATA, PERF, STD, INTERFACE, CHANGE, COMP, FUNC), producing a formal sign-off-ready Markdown assessment report. Trigger when the user asks to review, audit, assess, or check ABAP code before release — phrases include: 'security review', 'risk check', 'release audit', 'code review', 'check before transport', 'safe to release', or 'can this go to production'; also when a program name (e.g. ZMMR0002) appears alongside 'review', 'check', or 'ready for transport'. Do not use for general ABAP syntax questions, runtime debugging, or performance tuning unrelated to a transport release gate."
metadata:
  version: "1.0.0"
  type: docs
  valid_until: "evergreen"
  source_urls:
    - "https://github.com/SAP/styleguides/blob/main/clean-abap/CleanABAP.md"
    - "https://help.sap.com/doc/abapdocu_latest_index_htm/latest/en-US/index.htm"
  output_schema:
    format: text
    description: "Markdown report; filename ABAP_REVIEW_[PROGRAM_NAME]_[YYYYMMDD].md saved to user-specified reports/ directory, or output inline if file write is unavailable"
  permissions:
    read_paths: ["<skill_dir>/references/"]
    write_paths: ["<user-specified reports directory>"]
    network_endpoints: []
    requires_elevation: false
    accesses_env_vars: []
---

# ABAP Code Review Skill

Performs pre-release security and quality assessment of SAP ABAP programs, producing a formal Markdown report ready for sign-off and circulation.

## Invocation

Any message matching the description above will load this skill. A complete invocation with full context:

```
Review program [PROGRAM_NAME] for release.
Transport: [DEVKXXXXXX], Change description: [one-line business purpose].
Save the report to the reports/ directory.
```

To include functional completeness checks ([FUNC] dimension), provide the requirements document path or describe the requirements in the conversation.

---

## Step 0 — Load References First

Before reading any ABAP source code, load the following two files in order. Do not load any other files from the references/ directory:

1. `references/REF_ABAP_SECURITY.md` — Authority reference for [SEC], [AUTH], and [INTERFACE] dimensions
2. `references/REF_CLEAN_ABAP.md` — Authority reference for the [STD] dimension

> Every [SEC] / [AUTH] / [STD] finding must cite the corresponding rule ID (e.g. `SEC-SQL-1`, `[E-2]`).
> Findings without a rule ID citation are invalid and must be removed.

> **If reference files are not accessible** (e.g., the agent cannot read from the skill directory): proceed using built-in ABAP knowledge. Record under Scope Limitations that reference files were unavailable; rule IDs must still be cited in findings.

---

## Step 1 — Read Source Code

Retrieve the complete source code of the target program using the appropriate method for your environment:

- **Tool-equipped agents**: Use the available ABAP source-reading capability (ABAP CLI tool, ADT API, MCP tool, or equivalent) to programmatically read the main program and all INCLUDEs.
- **Conversation-based agents / manual sessions**: Ask the user to paste the source code directly into the conversation, specifying which INCLUDEs, class methods, or function modules are in scope.

| Object Type | Scope to Read |
|-------------|--------------|
| REPORT | Main program + all INCLUDEs |
| Global Class | Class definition + all METHOD implementations |
| Function Module | Target FM + other FMs in the same function group |
| Enhancement / BAdI | Enhancement Spot definition + all active implementations |

Reading order: main program / class definition → INCLUDEs (in order of appearance) → METHODs (one by one).

Objects that cannot be retrieved: record in the report under Scope Limitations, mark as "unreviewed", and do not assume they are safe.

---

## Step 2 — Analyze (9 Dimensions)

Complete all 9 dimensions in the order listed below. No dimension may be skipped (if no issues are found, state "No issues found").

### [SEC] Security Vulnerabilities
Reference: `REF_ABAP_SECURITY.md`. Scan by priority:

```
Priority 1 (scan immediately):
  EXEC SQL                    → SEC-SQL-2
  GENERATE SUBROUTINE POOL    → SEC-CODE-1
  INSERT REPORT               → SEC-CODE-2
  CALL 'SYSTEM' / SXPG_*     → SEC-OS-1/2/3
  WHERE ( <variable> )        → SEC-SQL-1
  DESTINATION ( <variable> )  → SEC-RFC-1

Priority 2 (important checks):
  cl_sql_statement            → verify set_param parameterization is used
  OPEN DATASET                → path source + SY-SUBRC check
  CALL FUNCTION DESTINATION   → RFC destination source
  literals containing password/key/token → SEC-CRED-1
```

### [AUTH] Authorization & Access Control
Reference: `REF_ABAP_SECURITY.md` → AUTH-MISS-*, AUTH-BYP-*

High-risk tables (AUTHORITY-CHECK required before read/write): BKPF/BSEG, MKPF/MSEG, VBAK/VBAP, EKKO/EKPO, PA*/HRP*

Check: ① AUTHORITY-CHECK present before sensitive table operations → ② SY-SUBRC checked immediately after → ③ no SY-UNAME hardcoded bypass → ④ RFC FMs have authorization checks

> **Special rule**: Any HIGH finding in [SEC] or [AUTH] is treated as CRITICAL for the release decision (NO-GO).

### [DATA] Data Integrity & Exception Handling
Reference: `REF_CLEAN_ABAP.md` [E-2] [E-3]

Check: SY-SUBRC after CALL FUNCTION → SY-SUBRC after READ TABLE / SELECT SINGLE → SY-SUBRC after OPEN DATASET → ENQUEUE lock before write operations → COMMIT WORK not inside a loop → ROLLBACK WORK on error paths → no empty CATCH blocks that swallow exceptions

### [PERF] Performance Risks
Reference: `REF_CLEAN_ABAP.md` [T-1] [T-2] [T-3]

Check: SELECT inside LOOP (→ [T-2], CRITICAL for large tables) → SELECT * without projection (→ [T-3]) → full table scan (no WHERE clause) → READ TABLE WITH KEY inside LOOP (→ [T-1], switch to SORTED/HASHED) → high-volume tables (BKPF/BSEG/MKPF/MSEG) without row-count protection

### [STD] ABAP Code Standards
Reference: `REF_CLEAN_ABAP.md` [L-*] [C-*] [N-*] [M-*]

Check deprecated statements (`[L-3]`), hardcoded business values such as bukrs/werks/mandt (`[C-3]`, typically HIGH in enterprise settings), overly long methods (`[M-2]`, flag if > 20 statements), commented-out code blocks (`[CM-3]`), Unicode compatibility

### [INTERFACE] Interface & Integration Risks
Reference: `REF_ABAP_SECURITY.md` SEC-RFC-*, SEC-WEB-*

Check: RFC FM contains dialog messages MESSAGE TYPE A/I/W (→ SEC-RFC-3) → RFC FM parameters have type declarations → EXCEPTIONS fully declared → CALL FUNCTION DESTINATION has timeout configured → OData DPC Extension has backend authorization check (→ SEC-WEB-2)

### [CHANGE] Change Impact Assessment
Assess: affected database tables (list all read/write/delete operations) → whether SAP standard objects are modified → whether the program shares INCLUDEs or FMs with other programs → Transport prerequisites and cross-system dependencies

### [COMP] Compliance & Audit Trail
Check: PII data reads/exports have a compliance basis → FI/CO postings have dual-control → master data changes written to CDHDR/CDPOS → program logs executor/timestamp/parameters → no single person can both initiate and approve (SoD path)

### [FUNC] Functional Completeness *(Optional)*
**Execute only when the user provides a requirements specification**; otherwise state the reason for skipping in the report.

If executed: verify program entry points cover business scenarios → boundary condition handling (null/zero/oversized datasets) → core business logic matches requirements → calculation logic is accurate → output fields are complete → integration interfaces transmit data completely

---

## Step 3 — Severity Classification

| Level | Label | Release Impact |
|-------|-------|---------------|
| 🔴 | CRITICAL | Blocks release |
| 🟠 | HIGH | Should block release |
| 🟡 | MEDIUM | Fix in next sprint |
| 🟢 | LOW | Advisory |
| ℹ️ | INFO | No action required |

When severity is uncertain, choose the **higher** level.

---

## Step 4 — Release Decision

```
CRITICAL finding present                        → NO-GO
HIGH finding in [SEC] or [AUTH]                 → NO-GO (special rule)
HIGH finding in other dimensions                → CONDITIONAL GO (requires tech lead sign-off)
MEDIUM / LOW / INFO findings only               → GO
```

---

## Step 5 — Generate Report

Load `references/REPORT_TEMPLATE.md` and generate the report by strictly following the template structure.

Report language: titles and rule references in **English**; risk descriptions and remediation recommendations in **English**.

File naming: `ABAP_REVIEW_[PROGRAM_NAME]_[YYYYMMDD].md`
When a CRITICAL finding is present, prefix: `CRITICAL_ABAP_REVIEW_[PROGRAM_NAME]_[YYYYMMDD].md`

Save to the `reports/` directory specified by the user and confirm the file path upon completion.

> **If file system write access is unavailable**: output the complete report as formatted Markdown in the conversation. Inform the user that no file was saved and suggest they copy the output manually.

---

## Behavior Rules

| Rule | Requirement |
|------|------------|
| References first | Step 1 must not begin until Step 0 is complete |
| Evidence-first | Every finding must include a real code snippet (≤ 15 lines); findings without code evidence are invalid |
| Rule citation | [SEC] / [AUTH] / [STD] findings must cite a rule ID |
| No false negatives | Objects not retrieved → mark as "partially reviewed"; never write "no issues found" for unread objects |
| No duplication | Same pattern found in multiple locations → one finding listing all locations |
| FUNC gate | No requirements document → skip and state reason; do not infer requirements independently |
