# Decision Policy

> `sap-transport-gate` v1.0.0 — §1: Evidence Level; §2: Finding Schema; §3: Release Decision Policy

---

## §1 Evidence Level

Evidence Level is determined before dimensional review begins. It constrains which Release Decisions are permitted.

### §1.1 Level Definitions

| Level | Meaning |
|---|---|
| `HIGH` | TR objects, source files, dependencies, functional spec, syntax/activation status, and test evidence are substantially complete. All major evidence categories are present and readable. |
| `MEDIUM` | Key evidence is largely complete, but some items are missing. Example: test evidence absent or incomplete, or dependencies partially provided. Dimensional review is meaningful but some conclusions are restricted. |
| `LOW` | Evidence is thin: only source fragments, object list incomplete or absent, functional spec missing, or release-critical evidence (syntax check, activation status) absent. Review scope is significantly restricted. |
| `UNKNOWN` | Input materials are unstructured, unreadable, or evidence scope cannot be determined. Dimensional review cannot proceed reliably. |

### §1.2 Determination Rules

Apply in order — the first matching rule wins:

1. Input is unstructured, unreadable, or no meaningful materials provided → `UNKNOWN`
2. Only a single ABAP file with no TR context → `LOW`
3. Object list missing or severely incomplete (more than 30% of TR objects without source) → `LOW`
4. Functional spec absent AND test evidence absent AND syntax/activation status absent → `LOW`
5. Object list present + sources present + dependencies present + functional spec present + syntax/activation present + test evidence present → `HIGH`
6. Object list present + sources present + functional spec present + syntax/activation present, BUT test evidence missing or dependencies incomplete → `MEDIUM`
7. Object list present + sources present, BUT functional spec absent OR syntax/activation absent → `MEDIUM` if other evidence is strong, otherwise `LOW`
8. Single object with full evidence (class + spec + syntax + test) but no broader TR context → `LOW` (cannot represent a TR-level gate)

### §1.3 Evidence Level and Permitted Decisions

| Evidence Level | GO | CONDITIONAL_GO | NO_GO | NEED_MORE_EVIDENCE |
|---|---|---|---|---|
| `HIGH` | ✅ | ✅ | ✅ | ✅ |
| `MEDIUM` | ❌ | ✅ | ✅ | ✅ |
| `LOW` | ❌ | ❌ | ✅ | ✅ |
| `UNKNOWN` | ❌ | ❌ | ❌ | ✅ (only) |

**Rule**: `GO` requires Evidence Level `HIGH` with no `CRITICAL` or unmitigated `HIGH` findings.
`CONDITIONAL_GO` requires at least Evidence Level `MEDIUM`.

---

## §2 Finding Schema

### §2.1 Required Fields

Every finding must include all fields below. Partial findings are not valid.

```
id                          String   Unique identifier within this review (e.g., "F-001", "EG-003")
type                        Enum     See §2.2
severity                    Enum     See §2.3
confidence                  Enum     See §2.4
object                      String   Affected object name (program, class, function group, table, etc.)
location                    String   File path, method name, line range, or section (e.g., "Z_PROG_MM01:METHOD process_data:line 45")
evidence                    String   Real code snippet (max 15 lines) or material excerpt; never fabricated
reasoning                   String   Why this is a risk; cite mechanism, not just pattern name
impact                      String   What can go wrong if unaddressed; be specific about system/business effect
recommendation              String   Specific, actionable fix or next step
requires_human_confirmation Boolean  true if human expert judgment is required to resolve or confirm
```

### §2.2 Finding Type

| Type | Dimension | When to Use |
|---|---|---|
| `CODE_QUALITY` | Dimension 1 | Naming, maintainability, exception handling, duplication, complexity |
| `PERFORMANCE` | Dimension 2 | SELECT-in-LOOP, full table scan, inefficient internal tables |
| `SECURITY` | Dimension 3 | Injection, dynamic code, OS commands, credential exposure |
| `AUTHORIZATION` | Dimension 4 | Missing auth checks, bypass patterns, privilege escalation |
| `TRANSACTION_CONSISTENCY` | Dimension 5 | COMMIT/ROLLBACK placement, BAPI commit, LUW integrity |
| `INTEGRATION_IMPACT` | Dimension 6 | RFC, IDoc, OData, HTTP interface risks |
| `TRANSPORT_COMPLETENESS` | Dimension 7 | Missing objects, dependencies not in TR, incomplete function groups |
| `FUNCTIONAL_ALIGNMENT` | Dimension 8 | Code vs. spec discrepancies |
| `RELEASE_READINESS` | Dimension 9 | Syntax errors, inactive objects, missing test evidence |
| `EVIDENCE_GAP` | Dimension 10 | Missing materials; used for any absent evidence category |

### §2.3 Severity

| Severity | Meaning | Release Impact |
|---|---|---|
| `CRITICAL` | Can cause severe data loss, security breach, production outage, unrecoverable release risk, or GDPR/SOX/financial compliance violation | Blocks release; forces `NO_GO` |
| `HIGH` | Significant function failure, major performance degradation, missing critical dependency, authorization gap, serious transaction risk | Blocks release or forces `CONDITIONAL_GO` at minimum |
| `MEDIUM` | Clear risk, mitigable by fix, test, or human confirmation before release | Requires action; compatible with `CONDITIONAL_GO` |
| `LOW` | Code quality or maintainability issue; does not directly block release | Advisory; compatible with `GO` |
| `INFO` | Informational observation; no action required | No release impact |

**Severity escalation rules:**
- `HIGH` finding in SECURITY or AUTHORIZATION dimension → treated as `CRITICAL` for decision purposes
- `CRITICAL` in any SECURITY / AUTHORIZATION / TRANSACTION_CONSISTENCY finding → automatic `NO_GO`
- Multiple `MEDIUM` findings in the same dimension without mitigation paths → consider escalating to `HIGH`

**When severity is uncertain**: choose the higher level.

### §2.4 Confidence

| Confidence | Meaning | When to Use |
|---|---|---|
| `HIGH` | Finding is backed by direct code evidence, metadata, or tool output | Direct code pattern found, syntax error present, auth check provably absent |
| `MEDIUM` | Finding is backed by indirect evidence; human confirmation strengthens it | Behavior inferred from call chain, risk exists but not directly observable in provided code |
| `LOW` | Finding is inferred from limited context; high uncertainty | Only partial code available, behavior depends on runtime state not visible in static analysis |

Findings with `Confidence: LOW` must be labeled `[Inferred]` in the report and must have `requires_human_confirmation: true`.

---

## §3 Release Decision Policy

### §3.1 Decision Definitions

| Decision | Meaning | Typical Conditions |
|---|---|---|
| `GO` | No blocking findings; evidence sufficient; safe to proceed to next stage | Evidence Level `HIGH`; only `LOW` / `INFO` findings; no evidence gaps affecting readiness |
| `CONDITIONAL_GO` | Proceed only after completing specified required actions | Evidence Level `MEDIUM`+; `MEDIUM` findings with clear mitigation paths; functional alignment requires confirmation |
| `NO_GO` | Serious risk present; do not release | Any `CRITICAL` finding; `HIGH` SECURITY or AUTH finding; critical evidence absent combined with critical risk |
| `NEED_MORE_EVIDENCE` | Evidence too thin for a reliable judgment | Evidence Level `LOW` or `UNKNOWN`; missing materials prevent dimensional review from being meaningful |

### §3.2 Decision Rules (apply in priority order)

All rules are mandatory. Apply them in the order listed — the first matching rule determines the outcome.

**Rule 1 — Evidence Level UNKNOWN:**
→ `NEED_MORE_EVIDENCE`. Stop. Do not proceed to other rules.

**Rule 2 — CRITICAL finding in SECURITY, AUTHORIZATION, or TRANSACTION_CONSISTENCY:**
→ `NO_GO`. List evidence gaps as additional risk items.

**Rule 3 — CRITICAL finding in any other dimension:**
→ `NO_GO`.

**Rule 4 — HIGH finding in SECURITY or AUTHORIZATION (treated as CRITICAL):**
→ `NO_GO`.

**Rule 5 — Evidence Level LOW:**
→ `NEED_MORE_EVIDENCE`. (Even if no findings are CRITICAL, LOW evidence does not support a release decision.)

**Rule 6 — Unmitigated HIGH finding (non-SECURITY/AUTH) with no clear fix path:**
→ `NO_GO`.

**Rule 7 — HIGH finding (non-SECURITY/AUTH) with clear mitigation path:**
→ `CONDITIONAL_GO`. List the mitigation as a Required Action.

**Rule 8 — Evidence gaps are more severe than code findings:**
→ `NEED_MORE_EVIDENCE` takes priority over `CONDITIONAL_GO`.
Example: no syntax check, no activation status, no test evidence → `NEED_MORE_EVIDENCE`.

**Rule 9 — Only MEDIUM findings, Evidence Level MEDIUM or higher:**
→ `CONDITIONAL_GO`. List all MEDIUM findings as Required Actions or confirm paths.

**Rule 10 — Only LOW / INFO findings, Evidence Level HIGH:**
→ `GO`.

### §3.3 Decision Priority Diagram

```
Highest priority
│
├── CRITICAL risk (Security / Auth / Transaction) or HIGH Security / Auth
│   └── NO_GO
│
├── CRITICAL risk (other dimensions)
│   └── NO_GO
│
├── Evidence Level LOW or UNKNOWN
│   └── NEED_MORE_EVIDENCE
│
├── Unmitigated HIGH risk (no fix path)
│   └── NO_GO
│
├── Evidence gaps dominate (more severe than code issues)
│   └── NEED_MORE_EVIDENCE
│
├── HIGH risk with mitigation OR MEDIUM findings only (EL: MEDIUM+)
│   └── CONDITIONAL_GO
│
└── LOW / INFO findings only AND Evidence Level HIGH
    └── GO
│
Lowest priority
```

If CRITICAL risk and evidence gap coexist → `NO_GO`; evidence gap is listed as an **additional risk**, not as the primary decision driver.

### §3.4 Required Actions

Every `CONDITIONAL_GO` decision must include a **Required Actions** list. Each action must specify:

1. What must be done (concrete action, not vague)
2. Who is responsible (developer / tech lead / security owner / business owner)
3. What evidence of completion is expected
4. What happens if the action is not completed (risk statement)

Example:
```
Action: Verify that AUTHORITY-CHECK is present before table BKPF write in METHOD post_document
Responsible: Developer + Technical Lead
Evidence of completion: Updated code reviewed and activated; screenshot of AUTHORITY-CHECK + SY-SUBRC check
Risk if not completed: Unauthorized financial document posting; HIGH AUTHORIZATION risk remains
```

### §3.5 Decision Rationale

The report must include a **Decision Rationale** section explaining:
- Which rule(s) were the primary drivers of the decision
- Why alternative decisions were not chosen
- What the key evidence supporting the decision is

Example:
```
Decision: CONDITIONAL_GO
Primary driver: Rule 9 — only MEDIUM findings, Evidence Level MEDIUM.
Why not GO: Test evidence is absent (EG-002), preventing Evidence Level HIGH.
Why not NO_GO: All findings are MEDIUM or lower with clear remediation paths.
Why not NEED_MORE_EVIDENCE: Syntax check and activation status are present;
  functional spec is provided; the evidence gap (test results) does not
  prevent dimensional review from being meaningful.
```
