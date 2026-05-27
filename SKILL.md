---
name: sap-transport-gate
description: |
  Use for SAP Transport Request pre-release gate review (QAS/PRD). Triggers on any TR number in input (pattern: uppercase letters + K + 6 digits, e.g., DEVK900123, ECDK943668). Asks user: code-quality-only or functional+code review. Performs 10-dimension risk review of ABAP/CDS/DDIC source, object list, dependencies, spec, and release evidence; detects evidence gaps; generates Release Readiness Report with GO / CONDITIONAL_GO / NO_GO / NEED_MORE_EVIDENCE.
  Also triggers for: "can this TR go to production", "release gate check", "audit TR before import", "transport risk assessment", "generate release readiness report".
  Do NOT use for: executing transports, SAP login, single ABAP file without TR context (use abap-code-review), or no transport artifacts.
license: MIT
allowed-tools: [Read, Write]
metadata:
  version: "1.2.0"
  type: hybrid
  author: Shrek
  tags: ["sap", "transport", "release-gate", "abap", "review"]
  valid_until: "evergreen"
  source_urls: []
  output_schema:
    format: mixed
    description: "Primary: Markdown Release Readiness Report. Secondary: JSON summary for CI/audit pipelines."
  permissions:
    read_paths: ["<skill_dir>/references/"]
    write_paths: ["reports/", "reports/*/"]
    network_endpoints:
      ["SAP ADT REST API (Online Transport Mode only, read-only)"]
    requires_elevation: false
    accesses_env_vars:
      [
        "SAP_URL",
        "SAP_USERNAME",
        "SAP_PASSWORD",
        "SAP_CLIENT",
        "SAP_LANGUAGE",
        "SAP_VERIFY_SSL",
      ]
  mcp_hints:
    readOnlyHint: false
    destructiveHint: false
    idempotentHint: true
    openWorldHint: false
---

# SAP Transport Gate Skill

AI-assisted pre-release review for SAP Transport Requests. Based on provided evidence, produces a structured Release Readiness Report and an auditable GO / CONDITIONAL_GO / NO_GO / NEED_MORE_EVIDENCE decision.

**Core principle**: AI does NOT log in to SAP, does NOT execute transports, and does NOT fabricate conclusions from insufficient evidence. Every finding must trace to real evidence. Every gap must be declared.

---

## Hard Constraints (enforce at all times)

| Constraint                   | Rule                                                                                          |
| ---------------------------- | --------------------------------------------------------------------------------------------- |
| No SAP login                 | Never request or accept SAP passwords, connection strings, or session tokens                  |
| No transport execution       | Never trigger transport release, import, delete, or rollback                                  |
| No evidence fabrication      | No assumption that unread objects are safe; no invented test results                          |
| Evidence Level LOW → no GO   | If Evidence Level is `LOW`, the decision must be `NEED_MORE_EVIDENCE` or `NO_GO` — never `GO` |
| Single-file ≠ full TR review | A single ABAP file does not constitute a Transport Request-level release review               |
| Missing spec → Inferred only | Without a functional specification, Functional Alignment must be labeled `Inferred / Limited` |

Violations of these constraints invalidate the review output. Check them before generating any decision.

---

## Step 0 — Load References

Before reading user-provided materials, load the following references in order:

1. `references/review-modes.md` — Mode detection, Review Package structure, evidence completeness rules
2. `references/decision-policy.md` — Evidence Level rules, Finding taxonomy, Release Decision Policy
3. `references/review-dimensions.md` — 10 review dimensions with detailed checks
4. `references/report-format.md` — Markdown report template and JSON schema
5. `references/abap-security-rules.md` — Full SEC-_ and AUTH-_ security rule library (load for Dimension 3 and 4)
6. `references/abap-quality-rules.md` — Full Clean ABAP quality rule library (load for Dimension 1 and 2)

Load `references/sap-connectivity.md` when:

- Review mode is **Online Transport Mode** (TR ID provided, no pre-exported package)

Load `references/human-loop.md` when:

- Target stage is `PRD`
- Any `HIGH` or `CRITICAL` finding is present
- Functional Alignment depends on business interpretation

Load `references/regression-tests.md` only if asked to run regression checks or build eval cases.

---

## Step 0.5 — Extract Transport Request ID

Scan the user's input for a Transport Request ID **before proceeding**. TR IDs follow the pattern: **3–4 uppercase letters + K + 6 digits** (e.g., `DEVK900123`, `ECDK943668`, `NPLK000045`).

| Case                                     | Action                                                                                                                                 |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| TR ID found in input                     | Record it as `{TR_ID}`. Use it in the report filename, header, and all references throughout this review.                              |
| User provides a Review Package directory | Extract TR ID from `manifest.json` → `meta.tr_id` field.                                                                               |
| No TR ID found but review was requested  | Ask: _"Please provide the Transport Request ID (e.g., DEVK900123) to begin the review."_ Do not proceed until a TR ID is supplied.     |
| User confirms no TR ID exists            | Declare scope as `Partial / No TR Identity`. Evidence Level is capped at `LOW`. Proceed only to produce a `NEED_MORE_EVIDENCE` report. |

The TR ID is required for the report filename, the Executive Decision header, the Appendix object list, and audit traceability.

---

## Step 1 — Identify Review Mode

Determine the review mode from the input. Full rules in `references/review-modes.md §1`.

| Signal                                                                                       | Mode                  |
| -------------------------------------------------------------------------------------------- | --------------------- |
| User provides a standard Review Package (manifest + object list + sources + evidence)        | Offline Package Mode  |
| User provides only source files or partial materials (no manifest, no full TR context)       | Offline Local Mode    |
| User provides a Transport Request ID and CLI output or live system access via internal tools | Online Transport Mode |

**Online Transport Mode — Proactive Collection Protocol:**

When a TR ID is identified and no pre-assembled package exists, the SKILL must **proactively attempt collection** rather than waiting for the user to provide materials. Execute the following in order:

1. **Check credential availability** — inspect `.env` in the skill directory, `~/.sap-transport-gate/config.json`, and process environment variables for `SAP_URL`, `SAP_USERNAME`, `SAP_PASSWORD`, `SAP_CLIENT`.

2. **Credentials found → run `tr_collector.py collect` automatically**:

   Using available shell execution tools (e.g., Bash), run:
   ```bash
   python3 scripts/tr_collector.py collect {TR_ID} --output-dir reports/{TR_ID}_package/ --verbose
   ```

   - **Collection succeeds** → proceed as Offline Package Mode with the collected package at `reports/{TR_ID}_package/`. Do NOT ask the user to run the script.
   - **Collection fails** (HTTP 401, 403, connection refused, SSL error, timeout):
     > "SAP connection failed: `{error}`. Proceeding with Offline Local Mode. See `references/sap-connectivity.md §11` for the step-by-step manual export guide if you want a complete evidence package."

     Reclassify to Offline Local Mode and continue.

3. **Credentials not configured** — no `.env`, no config file, no env vars:

   > "No SAP credentials found. Proceeding with Offline Local Mode using materials already provided.
   >
   > To enable automatic TR collection in future reviews, configure credentials via:
   > - **Option A**: Copy `.env.example` to `.env` and fill in `SAP_URL`, `SAP_USERNAME`, `SAP_PASSWORD`, `SAP_CLIENT`.
   > - **Option B**: Run `python3 scripts/tr_collector.py configure` for interactive setup, then `python3 scripts/tr_collector.py ping` to verify."

   Reclassify to Offline Local Mode and continue.

4. **Shell execution not available** — if the AI agent has no shell/bash capability:

   > "Shell execution is not available in this environment. To use automatic collection, run:
   > ```bash
   > python3 scripts/tr_collector.py collect {TR_ID} --output-dir reports/{TR_ID}_package/ --verbose
   > ```
   > Once the package is ready, provide the path and I will proceed as Offline Package Mode. Or confirm you cannot run it to proceed now with Offline Local Mode."

   Wait for user response before continuing. Do NOT fabricate materials.

When falling back to Offline Local Mode at any point, reclassify mode, declare the fallback reason in the report, and continue.

**Offline Package Mode** is the preferred and most complete mode. Always declare the mode at the top of the report.

If mode cannot be determined from the input, ask the user one clarifying question before proceeding.

---

## Step 1.5 — Review Scope Selection

**Human confirmation required before proceeding.**

Ask the user:

> "I'll be reviewing Transport Request **{TR_ID}**.
>
> Which review scope do you need?
>
> **(A) Code Quality Review** — Covers: code quality, performance, security, authorization, transaction consistency, integration impact, transport completeness, release readiness, and evidence gaps. Assesses whether the code is well-written and safe to release. Does not evaluate whether the implementation matches business requirements.
>
> **(B) Functional + Code Quality Review** — All of the above, plus **Functional Alignment** (Dimension 8): verifies that the code correctly implements the stated business requirements. Requires a functional specification or requirements document.
>
> Which scope? (A or B)"

**If user selects (A) — Code Quality Review:**

- Exclude Dimension 8 (Functional Alignment) from the review. Mark it as `N/A — excluded by user choice`.
- Proceed to Step 2.

**If user selects (B) — Functional + Code Quality Review:**

- Check whether a functional specification or requirements document is present in the provided materials.
- **Spec is present** → proceed to Step 2 with all 10 dimensions active.
- **Spec is absent** → do not start the review. Prompt:

  > "Functional + Code Quality Review requires a functional specification. Please provide one of:
  >
  > - A functional spec document (Markdown, Word, PDF, or plain text)
  > - A requirements ticket, Jira issue, or user story
  > - A change request or design document
  >
  > Once provided, I will include Dimension 8 (Functional Alignment) in the review."

  If the user confirms no spec exists but still wants a Functional + Code Quality review:
  - Proceed with all 10 dimensions.
  - Set Dimension 8 outcome to `Inferred / Limited — no spec provided` per the Hard Constraint.
  - Record an `EVIDENCE_GAP` finding with severity `HIGH` for the missing functional specification.
  - This gap will restrict Evidence Level and the final decision.

---

## Step 2 — Evidence Intake and Completeness Check

Inventory all materials provided by the user. Required evidence varies by mode — see `references/review-modes.md §2` for full checklists.

Quick reference — evidence categories:

| Category            | Items                                                                            |
| ------------------- | -------------------------------------------------------------------------------- |
| TR Identity         | Transport Request ID, type, owner, source system, target stage, creation time    |
| Object List         | Object type, name, package, changed-by, source file path for each object         |
| Source Code         | ABAP programs, classes, function groups, includes, CDS views, DDIC definitions   |
| Dependencies        | Intra-TR, extra-TR, table, interface, authorization-object dependencies          |
| Metadata            | Table / CDS / authorization / interface / customizing metadata                   |
| Functional Material | Functional spec, requirement note, test note                                     |
| Release Evidence    | Syntax check result, activation status, unit/manual test results, collection log |

For each category, mark: **Present** / **Partial** / **Missing**.

Missing evidence does not stop the review — it restricts what can be concluded. Every missing item must be flagged as an `EVIDENCE_GAP` finding.

---

## Step 3 — Evidence Level

Determine Evidence Level before beginning dimensional review. Full rules in `references/decision-policy.md §1`.

| Level     | Meaning                                                                                                                   |
| --------- | ------------------------------------------------------------------------------------------------------------------------- |
| `HIGH`    | TR objects, source, dependencies, functional spec, syntax/activation status, and test evidence are substantially complete |
| `MEDIUM`  | Key evidence is largely complete but some items are missing (e.g., test evidence incomplete or dependencies partial)      |
| `LOW`     | Only source fragments, incomplete object list, missing functional spec, or missing release-critical evidence              |
| `UNKNOWN` | Input materials are unstructured, unreadable, or scope cannot be determined                                               |

**Decision gates by Evidence Level:**

- `UNKNOWN` → immediately output `NEED_MORE_EVIDENCE`; do not proceed with dimensional review
- `LOW` → proceed with dimensional review, but the final decision must be `NEED_MORE_EVIDENCE` or `NO_GO`; `GO` and `CONDITIONAL_GO` are forbidden

---

## Step 4 — Multi-Dimension Review

Complete all 10 dimensions below. Never skip a dimension — if nothing was found, state "No issues found."

Full detail for each dimension in `references/review-dimensions.md`.

| #   | Dimension               | Focus                                                                                          |
| --- | ----------------------- | ---------------------------------------------------------------------------------------------- |
| 1   | Code Quality            | Naming, maintainability, exception handling, duplication, hardcoding, complexity               |
| 2   | Performance             | SELECT IN LOOP, full table scan, missing key condition, inefficient internal table ops         |
| 3   | Security                | Dynamic SQL, dangerous functions, external calls, sensitive data exposure, unvalidated input   |
| 4   | Authorization           | AUTHORITY-CHECK coverage, auth object correctness, privilege escalation paths, bypass patterns |
| 5   | Transaction Consistency | COMMIT/ROLLBACK placement, BAPI commit, LUW integrity, update consistency                      |
| 6   | Integration Impact      | RFC, IDoc, OData, HTTP, BAPI, file interfaces — impact on external systems                     |
| 7   | Transport Completeness  | Object list completeness, missing extra-TR dependencies, DDIC/CDS/config dependencies          |
| 8   | Functional Alignment    | Code vs. functional spec — business rules, boundary conditions, exception flows                |
| 9   | Release Readiness       | Syntax check status, activation status, test evidence, rollback plan, pre-conditions           |
| 10  | Evidence Gap            | Missing materials, unverifiable assumptions, items requiring human confirmation                |

For **Functional Alignment**: skip if no functional spec is provided and label as `Inferred / Limited — no spec provided`. Do not infer requirements independently.

For **Evidence Gap**: always produce at least one finding per missing evidence category.

---

## Step 5 — Findings

Each finding must include all fields. Full schema in `references/decision-policy.md §2`.

Required fields per finding:

- `id` — unique identifier within this review (e.g., `F-001`)
- `type` — one of: `CODE_QUALITY`, `PERFORMANCE`, `SECURITY`, `AUTHORIZATION`, `TRANSACTION_CONSISTENCY`, `INTEGRATION_IMPACT`, `TRANSPORT_COMPLETENESS`, `FUNCTIONAL_ALIGNMENT`, `RELEASE_READINESS`, `EVIDENCE_GAP`
- `severity` — `INFO` / `LOW` / `MEDIUM` / `HIGH` / `CRITICAL`
- `confidence` — `HIGH` (direct evidence) / `MEDIUM` (indirect evidence) / `LOW` (inferred)
- `object` — affected object name
- `location` — file, line, or section reference
- `evidence` — real code snippet or material excerpt (max 15 lines); never fabricated
- `reasoning` — why this is a risk
- `impact` — what can go wrong if unaddressed
- `recommendation` — specific, actionable fix
- `requires_human_confirmation` — `true` / `false`

**Severity calibration** (abbreviated; full rules in `references/decision-policy.md §2.2`):

- `CRITICAL`: severe data loss, security breach, production outage, unrecoverable release risk
- `HIGH`: significant function failure, major performance degradation, missing critical dependency, release blocker
- `MEDIUM`: clear risk, mitigable by fix or human confirmation
- `LOW`: code quality or maintainability, does not directly block release
- `INFO`: advisory, informational

When severity is uncertain, choose the higher level.

---

## Step 6 — Release Decision

Derive a single decision from Evidence Level + Findings. Full policy in `references/decision-policy.md §3`.

| Decision             | Meaning                                                              |
| -------------------- | -------------------------------------------------------------------- |
| `GO`                 | No blocking findings; evidence sufficient; safe to proceed           |
| `CONDITIONAL_GO`     | Proceed only after completing specified fixes or human confirmations |
| `NO_GO`              | Serious risk present; do not release                                 |
| `NEED_MORE_EVIDENCE` | Insufficient evidence for a reliable judgment                        |

**Decision priority (highest wins):**

```
NO_GO               ← CRITICAL risk or severe unmitigated HIGH risk
NEED_MORE_EVIDENCE  ← Evidence too thin for reliable judgment
CONDITIONAL_GO      ← Risk exists but mitigable before release
GO                  ← Sufficient evidence, no blocking risk
```

**Non-negotiable rules:**

1. Evidence Level `LOW` → `GO` and `CONDITIONAL_GO` are forbidden
2. Evidence Level `UNKNOWN` → always `NEED_MORE_EVIDENCE`
3. Any `CRITICAL` SECURITY / AUTHORIZATION / TRANSACTION_CONSISTENCY finding → `NO_GO`
4. If `CRITICAL` risk and evidence gap coexist → `NO_GO`; list evidence gap as additional risk

---

## Step 7 — Generate Reports

Generate both outputs. Templates in `references/report-format.md`.

### Markdown Report (primary)

Structure:

1. Executive Decision (Decision, Evidence Level, Overall Risk, Target Stage, TR ID, Review Mode, Rule Pack)
2. Scope Reviewed (what was reviewed, what was not)
3. Evidence Summary (present / missing / restricted)
4. Key Findings (by severity)
5. Review by Dimension (all active dimensions; Dimension 8 marked N/A if user selected Code Quality Review)
6. Required Actions Before Release
7. Human Confirmation Checklist
8. Decision Rationale
9. Appendix:
   - **§9.1 Object List Summary** _(mandatory)_ — every TR object listed by type, name, and whether its source was reviewed
   - §9.2 Evidence References
   - §9.3 Assumptions
   - §9.4 Limitations and Unreviewed Scope
   - §9.5 Sign-off Table

Report rules:

- Every high-risk finding must have a recommendation
- Every evidence gap must explain its impact on the decision
- All inferred conclusions must be labeled `[Inferred]` or `[Needs confirmation]`
- Never write "looks fine" or "seems OK" without citing evidence
- Report language: English

File naming: `TR_REVIEW_{TR_ID}_{YYYYMMDD}.md`  
When `NO_GO`: prefix `NOGO_TR_REVIEW_{TR_ID}_{YYYYMMDD}.md`  
When `NEED_MORE_EVIDENCE`: prefix `NME_TR_REVIEW_{TR_ID}_{YYYYMMDD}.md`  
Full naming table in `references/report-format.md §3`.

Save location — **always use a TR-specific subdirectory**:

Always save reports to `reports/{TR_ID}_package/` regardless of review mode. Never save directly to `reports/`.

| Mode | Directory creation |
| ---- | ------------------ |
| **Online Transport Mode** | `tr_collector.py collect --output-dir reports/{TR_ID}_package/` creates the directory automatically. Reports are saved inside it alongside `manifest.json` and `sources/`. |
| **Offline Package Mode** | If the user provided a package at a different path, save reports to that path. If no path was specified, create `reports/{TR_ID}_package/` and save there. |
| **Offline Local Mode** | Create `reports/{TR_ID}_package/` even if no manifest exists. Save all reports and any user-provided evidence files there. |

Create the target directory automatically. Never ask the user to create it manually.

### JSON Summary (secondary)

For CI pipelines, dashboards, and audit archives. Schema in `references/report-format.md §2`.

---

## References Index

| File                                 | When to read                                                              |
| ------------------------------------ | ------------------------------------------------------------------------- |
| `references/review-modes.md`         | Mode detection, Review Package structure, evidence checklists             |
| `references/review-dimensions.md`    | Detailed check items per dimension                                        |
| `references/decision-policy.md`      | Evidence Level rules, Finding schema, Release Decision Policy             |
| `references/report-format.md`        | Markdown report template, JSON schema                                     |
| `references/abap-security-rules.md`  | SEC-_ and AUTH-_ security rule library (Dimensions 3 & 4)                 |
| `references/abap-quality-rules.md`   | Clean ABAP quality rules (Dimensions 1 & 2)                               |
| `references/abap-report-template.md` | Structured Markdown report template for individual object reviews         |
| `references/sap-connectivity.md`     | SAP ADT auth, TR extraction CLI, credential setup (Online Transport Mode) |
| `references/human-loop.md`           | Who confirms what, when, based on what evidence                           |
| `references/regression-tests.md`     | Bad cases, regression assertions, eval cases                              |
