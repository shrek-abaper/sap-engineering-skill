# Report Format

> `sap-transport-gate` v1.2.0 — §1: Markdown report template; §2: JSON summary schema; §3: File naming

---

## §1 Markdown Report Template

Generate the Release Readiness Report by following this template exactly. Do not skip sections. If a section has no content (e.g., no required actions), write "None identified" rather than omitting the section.

Report language: **English** throughout.

---

```markdown
# Release Readiness Report

**Project**: sap-transport-gate  
**Generated**: {YYYY-MM-DD HH:MM UTC}  
**Reviewer**: AI Transport Gate (sap-transport-gate v1.2.0)

---

## 1. Executive Decision

| Field | Value |
|---|---|
| **Decision** | {GO / CONDITIONAL_GO / NO_GO / NEED_MORE_EVIDENCE} |
| **Evidence Level** | {HIGH / MEDIUM / LOW / UNKNOWN} |
| **Overall Risk** | {CRITICAL / HIGH / MEDIUM / LOW / NONE} |
| **Target Stage** | {DEV / QAS / PRD} |
| **Transport Request** | {TR_ID or "Not provided"} |
| **Review Mode** | {Offline Package Mode / Offline Local Mode / Online Transport Mode} |
| **Rule Pack** | {standard / strict / security / performance — or "default"} |
| **Review Date** | {YYYY-MM-DD} |

> **Summary**: {1–3 sentence plain-English summary of what was reviewed, what the key risk driver is, and why the decision was reached.}

---

## 2. Scope Reviewed

> Clearly state what was included in this review and what was not.

**Reviewed:**
- {Object 1: type and name}
- {Object 2: type and name}
- ...

**Not Reviewed / Excluded:**
- {Object or evidence category}: {reason — not provided / could not be read / outside scope}
- ...

**Scope Limitation Notice** (if applicable):
> {Declare any mode degradation, missing object classes, or partial coverage that limits the reliability of findings.}

---

## 3. Evidence Summary

### Present

| Evidence Category | Status | Notes |
|---|---|---|
| TR Identity | Present / Partial | |
| Object List | Present / Partial / Missing | {count of objects if known} |
| Source Files | Present / Partial / Missing | {objects with source vs. total} |
| Dependencies | Present / Partial / Missing | |
| Metadata | Present / Partial / Missing | |
| Functional Specification | Present / Partial / Missing | |
| Syntax Check Result | Present / Missing | {date of check if available} |
| Activation Status | Present / Missing | {all active / N inactive if known} |
| Test Evidence | Present / Partial / Missing | |
| Collection Log | Present / Missing | |

### Missing Evidence and Impact

| Missing Item | Impact on Review |
|---|---|
| {Item} | {How its absence restricts the review or decision} |
| ... | ... |

---

## 4. Key Findings

> Top findings by severity. Full detail in §5.

| ID | Type | Severity | Object | Summary |
|---|---|---|---|---|
| F-001 | {type} | {severity} | {object} | {one-line description} |
| F-002 | ... | ... | ... | ... |

**Finding counts by severity:**

| CRITICAL | HIGH | MEDIUM | LOW | INFO | EVIDENCE_GAP |
|---|---|---|---|---|---|
| {n} | {n} | {n} | {n} | {n} | {n} |

---

## 5. Review by Dimension

### 5.1 Code Quality

{Summary sentence.}

{Findings if any:}

**F-{id}** — {Severity} — {Object}
> **Evidence**: `{code snippet max 15 lines}`  
> **Reasoning**: {why this is a risk}  
> **Impact**: {what can go wrong}  
> **Recommendation**: {specific action}  
> **Human Confirmation Required**: {Yes / No}

{If no issues: "No issues found."}

---

### 5.2 Performance

{Same structure as 5.1}

---

### 5.3 Security

{Same structure as 5.1}

> **Note**: Any HIGH finding in this section is treated as CRITICAL for the release decision.

---

### 5.4 Authorization

{Same structure as 5.1}

> **Note**: Any HIGH finding in this section is treated as CRITICAL for the release decision.

---

### 5.5 Transaction Consistency

{Same structure as 5.1}

---

### 5.6 Integration Impact

{Same structure as 5.1}

{For each interface found, also state:}
- Interface type: {RFC / IDoc / OData / HTTP / File / BAPI / Proxy}
- Direction: {Inbound / Outbound}
- Target: {system or endpoint — anonymized if sensitive}
- Owner notification required: {Yes / No / Unknown}

---

### 5.7 Transport Completeness

{Summary.}

**Dependency Analysis:**
- Intra-TR dependencies: {complete / restricted — no dependency info provided}
- Extra-TR dependencies: {complete / restricted}
- DDIC dependencies: {complete / restricted}

{Findings if any.}

---

### 5.8 Functional Alignment

{If spec provided: summary of alignment analysis.}

{If spec NOT provided:}
> **Functional Alignment: Inferred / Limited — no functional specification provided.**  
> The code was reviewed for structural completeness and internal consistency only. No claims are made about whether the implementation matches business requirements.

{Findings if any.}

---

### 5.9 Release Readiness

| Item | Status |
|---|---|
| Syntax Check | {Passed / Failed / Not provided} |
| All Objects Activated | {Yes / No — N inactive / Not provided} |
| Unit Tests | {Passed / Failed / Not provided} |
| Manual Tests | {Evidence provided / Not provided} |
| Rollback Plan | {Documented / Not documented} |
| Transport Prerequisites | {Confirmed / Unconfirmed / Not provided} |

**Overall Release Readiness**: {Fully Ready / Partially Ready — {items missing} / Restricted — key evidence absent}

{Findings if any.}

---

### 5.10 Evidence Gap

{List all EVIDENCE_GAP findings in the same format as other findings.}

{Each finding explains the gap and its impact on the decision.}

---

## 6. Required Actions Before Release

> **SKILL BOUNDARY — human-only items only.**
>
> Required Actions must list ONLY tasks that require **human intervention**. The SKILL handles the following automatically and they must NOT appear here:
> - Object list retrieval (fetched via `tr_collector.py collect` in Online Transport Mode)
> - Source code fetching (fetched via `tr_collector.py` for all supported object types)
> - Syntax rule checks applied by the SKILL during dimensional review
>
> What belongs here: code fixes by the developer, manual test execution, UAT sign-off, FI/business consultant confirmation, security owner approval, Transport prerequisite deployment, and other tasks only a human can perform.
>
> For `CONDITIONAL_GO`: list fix/confirmation actions required before release.
> For `NO_GO`: list blocking issues that must be remediated.
> For `NEED_MORE_EVIDENCE`: list only evidence that **cannot be auto-fetched** (e.g., manual test results, functional spec, business confirmation).

| # | Action | Responsible | Evidence of Completion | Risk if Not Completed |
|---|---|---|---|---|
| 1 | {specific human action} | {Developer / Tech Lead / Security / Business Owner} | {what proof is expected} | {risk statement} |
| 2 | ... | ... | ... | ... |

{If no actions required: "None. Decision is GO — no actions required before release."}

---

## 7. Human Confirmation Checklist

> These items require sign-off from the named role. AI cannot confirm them on behalf of the organization.

| # | Item | Confirming Role | Based on | Risk if Not Confirmed |
|---|---|---|---|---|
| 1 | {what must be confirmed} | {SAP Consultant / Tech Lead / Business Owner / Release Manager / Security Owner} | {evidence basis} | {risk} |
| 2 | ... | ... | ... | ... |

{If no human confirmations required: "None. No items require human confirmation for this decision."}

---

## 8. Decision Rationale

> Explain why this decision was reached, not alternative decisions, and what the key evidence is.

**Decision**: {Decision}

**Primary decision drivers**:
- {Rule or finding that drove the decision — e.g., "Rule 2: CRITICAL SECURITY finding F-003 (dynamic SQL injection)"}
- {Secondary driver if applicable}

**Why not {alternative decision}**:
- {Reason}

**Key supporting evidence**:
- {Evidence item 1}: {how it supports the decision}
- {Evidence item 2}: ...

**Inferred conclusions** (if any):
> {List any conclusions that could not be directly verified and are labeled [Inferred] or [Needs confirmation] in §5.}

---

## 9. Appendix

### 9.1 Object List Summary

| Object Type | Object Name | Package | Changed By | Source Reviewed |
|---|---|---|---|---|
| {PROG/CLAS/FUGR/...} | {name} | {pkg} | {user} | Yes / No / Partial |

### 9.2 Evidence References

| Evidence Item | File / Source | Notes |
|---|---|---|
| Syntax Check | {filename or "Provided in conversation"} | {date} |
| Activation Status | {filename or "Provided in conversation"} | |
| Test Results | {filename or "Not provided"} | |
| Functional Spec | {filename or "Not provided"} | |

### 9.3 Assumptions

{List any assumptions made during the review that could affect findings or the decision.}

- Assumption: {statement}. Basis: {why this was assumed}. If wrong: {impact}.
- ...

### 9.4 Limitations and Unreviewed Scope

- {Limitation 1}: {impact}
- {Limitation 2}: {impact}
- ...

### 9.5 Sign-off Table

| Role | Name | Date | Signature / Approval |
|---|---|---|---|
| Developer | | | |
| Technical Lead | | | |
| Release Manager | | | |
| Security Owner (if SECURITY findings) | | | |
| Business Owner (if PRD release) | | | |
```

---

## §2 JSON Summary Schema

The JSON summary is generated alongside the Markdown report for CI pipeline integration, dashboard display, and audit archiving.

```json
{
  "project": "sap-transport-gate",
  "version": "1.2.0",
  "transportRequestId": "{TR_ID or null}",
  "reviewMode": "OfflinePackage | OfflineLocal | OnlineTransport",
  "targetStage": "DEV | QAS | PRD",
  "rulePack": "standard | strict | security | performance",
  "decision": "GO | CONDITIONAL_GO | NO_GO | NEED_MORE_EVIDENCE",
  "evidenceLevel": "HIGH | MEDIUM | LOW | UNKNOWN",
  "overallRisk": "CRITICAL | HIGH | MEDIUM | LOW | NONE",
  "reviewDate": "YYYY-MM-DD",
  "scopeReviewed": [
    "{Object type: Object name}"
  ],
  "scopeExcluded": [
    "{Object or evidence category}: {reason}"
  ],
  "evidencePresent": [
    "{evidence category}"
  ],
  "missingEvidence": [
    "{evidence category}"
  ],
  "findings": [
    {
      "id": "F-001",
      "type": "CODE_QUALITY | PERFORMANCE | SECURITY | AUTHORIZATION | TRANSACTION_CONSISTENCY | INTEGRATION_IMPACT | TRANSPORT_COMPLETENESS | FUNCTIONAL_ALIGNMENT | RELEASE_READINESS | EVIDENCE_GAP",
      "severity": "CRITICAL | HIGH | MEDIUM | LOW | INFO",
      "confidence": "HIGH | MEDIUM | LOW",
      "object": "{object name}",
      "location": "{file:method:line or section}",
      "evidence": "{code snippet or material excerpt, max 15 lines}",
      "reasoning": "{why this is a risk}",
      "impact": "{what can go wrong}",
      "recommendation": "{specific action}",
      "requiresHumanConfirmation": true
    }
  ],
  "findingCounts": {
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0,
    "info": 0,
    "evidenceGap": 0
  },
  "requiredActions": [
    {
      "id": "RA-001",
      "action": "{specific action}",
      "responsible": "{role}",
      "evidenceOfCompletion": "{what proof is expected}",
      "riskIfNotCompleted": "{risk statement}"
    }
  ],
  "humanConfirmations": [
    {
      "id": "HC-001",
      "item": "{what must be confirmed}",
      "confirmingRole": "{role}",
      "evidenceBasis": "{evidence basis}",
      "riskIfNotConfirmed": "{risk}"
    }
  ],
  "decisionRationale": {
    "primaryDrivers": ["{Rule or finding ID}: {description}"],
    "keyEvidence": ["{evidence item}: {how it supports the decision}"],
    "inferredConclusions": ["{any [Inferred] or [Needs confirmation] conclusions"]
  },
  "assumptions": [
    {
      "statement": "{assumption}",
      "basis": "{reason}",
      "impactIfWrong": "{impact}"
    }
  ],
  "limitations": [
    "{limitation}: {impact}"
  ]
}
```

---

## §3 File Naming

### Markdown Report

| Decision | Filename |
|---|---|
| GO | `TR_REVIEW_{TR_ID}_{YYYYMMDD}.md` |
| CONDITIONAL_GO | `TR_REVIEW_{TR_ID}_{YYYYMMDD}.md` |
| NO_GO | `NOGO_TR_REVIEW_{TR_ID}_{YYYYMMDD}.md` |
| NEED_MORE_EVIDENCE | `NME_TR_REVIEW_{TR_ID}_{YYYYMMDD}.md` |

When TR_ID is not available: replace with `PARTIAL` or a short descriptor.

Example: `NOGO_TR_REVIEW_DEVK900123_20260526.md`

### JSON Summary

Same naming convention with `.json` extension:
`TR_REVIEW_DEVK900123_20260526.json`

### Save Location

**Always save to a TR-specific subdirectory.** Never save directly to `reports/`.

| Mode | Save path |
|---|---|
| **Online Transport Mode** | `tr_collector.py collect --output-dir reports/{TR_ID}_package/` creates the directory. Save reports inside it alongside `manifest.json` and `sources/`. |
| **Offline Package Mode** | Save to the user-provided package path. If no path was specified, create `reports/{TR_ID}_package/` and save there. |
| **Offline Local Mode** | Create `reports/{TR_ID}_package/` even if no manifest exists. Save all reports and any user-provided evidence files there. |

Example resulting layout (all modes):
```
reports/DEVK900123_package/
├── manifest.json              ← present if tr_collector.py was run
├── sources/
│   └── CLAS_ZCL_MY_CLASS.abap
├── TR_REVIEW_DEVK900123_20260526.md     ← always saved here
└── TR_REVIEW_DEVK900123_20260526.json   ← always saved here
```

Create the target directory automatically if it does not exist. Never ask the user to create it manually.

---

## §4 Report Writing Rules

These apply to the Markdown report content — not format.

| Rule | Requirement |
|---|---|
| No "looks fine" | Never write "looks fine", "seems OK", "no obvious issues" without citing evidence |
| Every HIGH+ finding has a recommendation | All `HIGH` and `CRITICAL` findings must include a specific, actionable recommendation |
| Every evidence gap explains decision impact | Each `EVIDENCE_GAP` finding must state how the gap affects the release decision |
| Inferred conclusions labeled | Any conclusion that cannot be directly verified must be labeled `[Inferred]` or `[Needs confirmation]` |
| No partial objects assumed safe | An object that could not be read must be listed as "unreviewed" — never assumed clean |
| No credential references | No SAP passwords, tokens, or connection strings appear anywhere in the report |
| Scope limitations declared | Any partial coverage, mode degradation, or evidence absence is declared in §2 and §9 |
