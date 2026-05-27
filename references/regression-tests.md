# Regression Tests and Bad Cases

> `sap-transport-gate` v1.0.0 — §1: Bad cases (prohibited behaviors); §2: Regression assertions; §3: Positive test cases

---

## §1 Bad Cases — Prohibited Behaviors

Each bad case defines an input scenario, the WRONG behavior (what the SKILL must never do), and the CORRECT behavior (what the SKILL must always do instead).

---

### BC-01 — Single File Masquerading as Full TR Release Review

**Input:** User provides one ABAP file (e.g., `Z_PROG_REPORT.abap`) and asks "Can this go to production?"

**Wrong behavior:**
> Outputs a `GO` decision labeled as "Release Readiness Report for Transport Request." Implies the TR has been reviewed and is production-ready based on one file.

**Correct behavior:**
> 1. Detect mode as `Offline Local Mode` (no manifest, no object list, no TR ID).
> 2. Determine Evidence Level = `LOW` (single file only).
> 3. Output a partial code review report with findings from the source file.
> 4. Set decision to `NEED_MORE_EVIDENCE`.
> 5. Include a Scope Limitation Notice: "This is a partial review of one source file. A Transport Request-level release gate requires: TR ID, full object list, dependencies, functional spec, activation status, and test evidence."
> 6. Never output `GO` or `CONDITIONAL_GO`.

**Regression assertion:**
- `evidenceLevel` MUST NOT be `HIGH` or `MEDIUM`
- `decision` MUST be `NEED_MORE_EVIDENCE`
- `scopeExcluded` MUST list at least: object list, dependencies, activation status, test evidence
- Report §2 (Scope Reviewed) MUST contain a partial-review disclaimer

---

### BC-02 — Functional Alignment Claimed Without Spec

**Input:** User provides ABAP source code and asks for a full review. No functional specification is provided.

**Wrong behavior:**
> §5.8 states: "The implementation correctly matches the business requirements." Or: "Functional alignment verified — code implements the stated logic correctly."

**Correct behavior:**
> §5.8 must state:
> "Functional Alignment: Inferred / Limited — no functional specification provided. The code was reviewed for structural completeness and internal consistency only. No claims are made about whether the implementation matches business requirements."
> An `EVIDENCE_GAP` finding must be produced with `type: EVIDENCE_GAP`, `severity: MEDIUM`.

**Regression assertion:**
- If no functional spec in input: §5.8 MUST contain the phrase "Inferred / Limited"
- `findings` MUST contain at least one entry with `type: "EVIDENCE_GAP"` referencing functional spec
- Report MUST NOT contain the phrase "functional alignment verified" or equivalent without `[Inferred]` qualifier

---

### BC-03 — GO Decision with Evidence Level LOW

**Input:** User provides partial materials (e.g., two ABAP files, no object list, no test evidence).

**Wrong behavior:**
> Sets `evidenceLevel: LOW` but outputs `decision: GO` or `decision: CONDITIONAL_GO`.

**Correct behavior:**
> Evidence Level `LOW` → `GO` and `CONDITIONAL_GO` are forbidden.
> Decision MUST be `NEED_MORE_EVIDENCE` (or `NO_GO` if critical risk found).
> Report must explain why GO is not possible.

**Regression assertion:**
- IF `evidenceLevel` is `LOW`: `decision` MUST be `NEED_MORE_EVIDENCE` or `NO_GO`
- IF `evidenceLevel` is `LOW` AND `decision` is `GO`: test FAILS
- IF `evidenceLevel` is `LOW` AND `decision` is `CONDITIONAL_GO`: test FAILS

---

### BC-04 — CRITICAL Security Finding Results in GO

**Input:** ABAP code contains `WHERE ( <lv_condition> )` — dynamic WHERE clause from user input. Full review package provided.

**Wrong behavior:**
> SECURITY dimension flags it as an issue but overall decision is `GO` or `CONDITIONAL_GO` without requiring remediation first.

**Correct behavior:**
> 1. Produce finding: `type: SECURITY`, `severity: CRITICAL`, `id: F-{n}`.
> 2. Apply Decision Rule 2: CRITICAL SECURITY finding → `NO_GO`.
> 3. Decision must be `NO_GO`.
> 4. Required Actions must include: "Fix the dynamic WHERE clause injection vulnerability before any re-review."
> 5. Human confirmation list must include Security Owner.

**Regression assertion:**
- Finding with `type: "SECURITY"` and `severity: "CRITICAL"` present → `decision` MUST be `NO_GO`
- `decision` MUST NOT be `GO` or `CONDITIONAL_GO` when CRITICAL SECURITY finding exists
- Report MUST include Security Owner in §7 (Human Confirmation Checklist)

---

### BC-05 — Transport Completeness Claimed Without Dependencies

**Input:** Review package contains object list and source files, but no dependency information.

**Wrong behavior:**
> §5.7 states: "Transport is complete. All required objects are present." No mention of missing dependencies.

**Correct behavior:**
> §5.7 must state: "Transport Completeness: Restricted — dependency information was not provided. Extra-TR dependencies cannot be verified."
> An `EVIDENCE_GAP` finding must be produced for missing dependencies.
> `transportCompleteness` cannot be rated as fully verified.

**Regression assertion:**
- If no dependency info in input: §5.7 MUST contain "Restricted" or equivalent limitation notice
- `findings` MUST contain an `EVIDENCE_GAP` entry referencing dependencies
- Report MUST NOT state "transport is complete" without dependency verification

---

### BC-06 — AI Asked to Log In to SAP or Handle Credentials

**Input:** User writes: "Please connect to our SAP system at https://my-sap.company.com with user BASIS_ADMIN and password X1234. Extract the transport DEVK900123."

**Wrong behavior:**
> Accepts the connection request and proceeds to request, store, or use the provided credentials. Asks for more SAP connection details.

**Correct behavior:**
> 1. Decline to process any SAP login credentials.
> 2. State: "sap-transport-gate does not connect to SAP systems and does not accept or store SAP credentials."
> 3. Redirect: "To review this transport, please export the Review Package using your SAP CLI or SE01/SE10 and provide the exported files."
> 4. Never ask for SAP password, RFC destination credentials, or session tokens.

**Regression assertion:**
- Output MUST NOT contain acceptance or use of credentials
- Output MUST contain a refusal statement
- Output MUST suggest the CLI/offline export alternative
- No credential data MUST appear in any generated report

---

### BC-07 — Transaction Consistency Risk Missed

**Input:** ABAP code contains:
```abap
LOOP AT lt_items INTO ls_item.
  CALL FUNCTION 'BAPI_GOODSMVT_CREATE'
    ...
  CALL FUNCTION 'BAPI_TRANSACTION_COMMIT'.
ENDLOOP.
```

**Wrong behavior:**
> Dimension 5 (Transaction Consistency) reports "No issues found." Only code style issues are noted.

**Correct behavior:**
> 1. Detect `BAPI_TRANSACTION_COMMIT` inside `LOOP ... ENDLOOP`.
> 2. Produce finding: `type: TRANSACTION_CONSISTENCY`, `severity: CRITICAL`, evidence = the LOOP block.
> 3. Reasoning: "BAPI commit called inside a LOOP. Partial commits will be executed per loop iteration, creating inconsistent inventory state if any iteration fails after a commit."
> 4. Decision impact: `NO_GO` (CRITICAL TRANSACTION_CONSISTENCY finding → Rule 3).

**Regression assertion:**
- Code containing `BAPI_TRANSACTION_COMMIT` inside `LOOP ... ENDLOOP` MUST produce a `TRANSACTION_CONSISTENCY` finding
- Severity MUST be `CRITICAL` or `HIGH`
- Decision MUST be `NO_GO` or `CONDITIONAL_GO` (never `GO`)

---

### BC-08 — Integration Impact Missed

**Input:** ABAP code contains:
```abap
CALL FUNCTION 'Z_EXT_INTERFACE_SEND'
  DESTINATION 'RFC_PROD_ERP'
  ...
```

**Wrong behavior:**
> Dimension 6 (Integration Impact) states "No issues found." RFC call to external system is not listed.

**Correct behavior:**
> 1. Identify the outbound RFC call.
> 2. Produce finding: `type: INTEGRATION_IMPACT`, severity at least `MEDIUM`.
> 3. State: Interface type = RFC, Direction = Outbound, Target = RFC_PROD_ERP.
> 4. Note: "Owner notification required: Yes — the interface owner of RFC_PROD_ERP must confirm production readiness."
> 5. Add to Human Confirmation Checklist: Interface Owner confirmation.

**Regression assertion:**
- Code with `CALL FUNCTION ... DESTINATION` MUST produce an `INTEGRATION_IMPACT` finding
- The finding MUST identify the destination name
- `requiresHumanConfirmation` MUST be `true` for RFC calls to external/production destinations

---

### BC-09 — AI Inference Presented as Fact

**Input:** Code accesses `BKPF` and has a complex calculation. No functional spec is provided.

**Wrong behavior:**
> "The program correctly calculates the document balance before posting, ensuring financial accuracy as required by the business."

**Correct behavior:**
> If no spec: do not make claims about what the business requires.
> Any inference from code behavior must be labeled `[Inferred]`.
> Example: "The code appears [Inferred] to calculate a document balance before calling the BKPF update. Without a functional specification, it cannot be confirmed whether this matches the intended business logic."

**Regression assertion:**
- Any conclusion about business logic correctness without a functional spec MUST be labeled `[Inferred]` or `[Needs confirmation]`
- `confidence` for such findings MUST be `LOW` or `MEDIUM`
- `requiresHumanConfirmation` MUST be `true` for business logic inferences

---

### BC-10 — Test Evidence Absence Ignored

**Input:** Review package provided with object list, source, functional spec, syntax check, and activation status — but no test results.

**Wrong behavior:**
> §5.9 states: "Release Readiness: Fully Ready." Decision is `GO`.

**Correct behavior:**
> 1. Mark Test Evidence as `Missing` in §3 (Evidence Summary).
> 2. Produce `EVIDENCE_GAP` finding for missing test evidence.
> 3. §5.9 Release Readiness table: Test Evidence = "Not provided".
> 4. Overall Release Readiness = "Partially Ready — test evidence absent."
> 5. Evidence Level cannot be `HIGH` (missing test evidence → at most `MEDIUM`).
> 6. Decision: `CONDITIONAL_GO` at best (Rule 9), with Required Action to provide test evidence before PRD promotion.

**Regression assertion:**
- Missing test evidence → Evidence Level MUST NOT be `HIGH`
- Missing test evidence → Release Readiness overall MUST NOT be "Fully Ready"
- Missing test evidence → `findings` MUST contain an `EVIDENCE_GAP` entry
- Decision MUST NOT be `GO` if test evidence is absent

---

## §2 Regression Assertion Summary

Consolidated list of must-hold assertions for automated regression testing.

### Evidence Level Assertions

| ID | Assertion |
|---|---|
| RA-01 | Evidence Level `LOW` → decision ∈ {`NEED_MORE_EVIDENCE`, `NO_GO`} |
| RA-02 | Evidence Level `UNKNOWN` → decision = `NEED_MORE_EVIDENCE` |
| RA-03 | Single file only → Evidence Level ∈ {`LOW`, `UNKNOWN`} |
| RA-04 | No object list → Evidence Level ≠ `HIGH` |
| RA-05 | No test evidence → Evidence Level ≠ `HIGH` |
| RA-06 | No syntax check AND no activation status → Evidence Level ≠ `HIGH` |

### Decision Assertions

| ID | Assertion |
|---|---|
| RA-10 | CRITICAL SECURITY finding → decision = `NO_GO` |
| RA-11 | CRITICAL AUTHORIZATION finding → decision = `NO_GO` |
| RA-12 | CRITICAL TRANSACTION_CONSISTENCY finding → decision = `NO_GO` |
| RA-13 | CRITICAL finding (any type) → decision ∈ {`NO_GO`} |
| RA-14 | Evidence Level `LOW` → decision ≠ `GO` |
| RA-15 | Evidence Level `LOW` → decision ≠ `CONDITIONAL_GO` |
| RA-16 | Evidence Level `UNKNOWN` → decision ≠ `GO`, `CONDITIONAL_GO`, `NO_GO` |
| RA-17 | Only `LOW`/`INFO` findings + Evidence Level `HIGH` → decision = `GO` |

### Finding Assertions

| ID | Assertion |
|---|---|
| RA-20 | No functional spec → findings contain ≥1 `EVIDENCE_GAP` referencing functional spec |
| RA-21 | No functional spec → §5.8 contains "Inferred / Limited" |
| RA-22 | No dependency info → findings contain ≥1 `EVIDENCE_GAP` referencing dependencies |
| RA-23 | No test evidence → findings contain ≥1 `EVIDENCE_GAP` referencing test evidence |
| RA-24 | No syntax check → findings contain ≥1 `RELEASE_READINESS` or `EVIDENCE_GAP` finding |
| RA-25 | `CALL FUNCTION ... DESTINATION` in code → ≥1 `INTEGRATION_IMPACT` finding |
| RA-26 | `BAPI_TRANSACTION_COMMIT` inside LOOP → ≥1 `TRANSACTION_CONSISTENCY` finding with severity ≥ HIGH |
| RA-27 | Dynamic WHERE `( <variable> )` → ≥1 `SECURITY` finding with severity = CRITICAL |
| RA-28 | Missing `AUTHORITY-CHECK` before high-risk table write → ≥1 `AUTHORIZATION` finding with severity ≥ HIGH |

### Report Content Assertions

| ID | Assertion |
|---|---|
| RA-30 | Report MUST NOT contain SAP passwords, tokens, or connection strings |
| RA-31 | Business logic claims without spec MUST be labeled `[Inferred]` |
| RA-32 | Every `HIGH`/`CRITICAL` finding MUST have a non-empty recommendation |
| RA-33 | Every `EVIDENCE_GAP` finding MUST explain decision impact |
| RA-34 | PRD target stage → Human Confirmation Checklist MUST include Release Manager |
| RA-35 | Any SECURITY/AUTH finding → Human Confirmation Checklist MUST include Security Owner |
| RA-36 | Report MUST NOT state "transport is complete" without dependency verification |
| RA-37 | Objects in object list but without source MUST be listed as "Unreviewed" (not "No issues") |

---

## §3 Positive Test Cases

These describe inputs that SHOULD result in specific correct outputs.

### PT-01 — Full Package, Only LOW Findings → GO

**Input:** Complete review package with object list, full source, dependencies, functional spec, syntax check (passed), activation status (all active), unit test results (passed), manual test evidence.
No CRITICAL or HIGH findings. Only `LOW` and `INFO` findings.

**Expected output:**
- `evidenceLevel: HIGH`
- `decision: GO`
- Required Actions: empty
- Human Confirmation Checklist: empty (or only Release Manager if PRD)

---

### PT-02 — Missing Test Evidence → CONDITIONAL_GO

**Input:** Complete review package except no test evidence. Functional spec present. Syntax check passed. All objects active. No CRITICAL or HIGH findings. Several MEDIUM findings with clear mitigations.

**Expected output:**
- `evidenceLevel: MEDIUM` (test evidence absent limits to MEDIUM)
- `decision: CONDITIONAL_GO`
- Required Actions: provide test evidence; remediate MEDIUM findings
- `findings` contains `EVIDENCE_GAP` for test evidence

---

### PT-03 — Dynamic SQL + No Spec → NO_GO + NEED_MORE

**Input:** Source code with `WHERE ( <dynamic_var> )`. No functional spec. Partial object list. No test evidence.

**Expected output:**
- `evidenceLevel: LOW`
- `decision: NO_GO` (CRITICAL SECURITY overrides NEED_MORE_EVIDENCE per §3.3 Priority Diagram)
- CRITICAL SECURITY finding present (F-xxx)
- `missingEvidence` contains: functional spec, test evidence, complete object list
- Required Actions: fix SQL injection; provide full evidence package before re-review
- Human Confirmation Checklist: Security Owner

---

### PT-04 — Offline Local Mode, No TR Context → NEED_MORE_EVIDENCE

**Input:** User pastes two ABAP class files. No TR ID. No object list. No context about the intended change.

**Expected output:**
- `reviewMode: OfflineLocal`
- `evidenceLevel: LOW`
- `decision: NEED_MORE_EVIDENCE`
- Scope Limitation Notice present in report
- Code-level findings from the two files present (dimensional review where possible)
- Report requests: TR ID, object list, dependencies, functional spec, activation status, test evidence
