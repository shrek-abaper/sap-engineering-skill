# Review Dimensions

> `sap-transport-gate` v1.0.0 — §1–10: Detailed check items per dimension
>
> Rule citations reference files in `references/`:
> - Security rules → `abap-security-rules.md` (SEC-SQL-*, SEC-CODE-*, SEC-OS-*, SEC-FILE-*, SEC-RFC-*, AUTH-MISS-*, AUTH-BYP-*, SEC-CRED-*, SEC-DATA-*, SEC-WEB-*)
> - Quality rules → `abap-quality-rules.md` ([N-*], [L-*], [C-*], [V-*], [T-*], [S-*], [B-*], [CO-*], [M-*], [E-*], [CM-*], [F-*], [TS-*])

---

## Dimension 1 — Code Quality

**Goal**: Identify issues that reduce maintainability, readability, or reliability — including patterns that make the code harder to test, debug, or hand over to other developers.

**Rule reference**: `abap-quality-rules.md`

### Check Items

| Check | Pattern / Signal | Default Severity | Rule |
|---|---|---|---|
| Meaningful naming | Single-character variable names outside of loop counters; abbreviations that are not standard ABAP conventions | LOW | [N-1] |
| Hardcoded business values | Company code, plant, storage location, document type, material group, etc. hardcoded as literals in program logic | MEDIUM | [C-3] |
| Hardcoded system/client values | `SY-MANDT` or client ID hardcoded in WHERE clauses; hardcoded system IDs in RFC destinations | MEDIUM | [C-3] |
| Exception handling completeness | SY-SUBRC not checked after CALL FUNCTION, SELECT SINGLE, READ TABLE, OPEN DATASET | MEDIUM | [E-2] |
| Empty CATCH blocks | `CATCH ... . ENDTRY.` with no error handling (silently swallows exceptions) | HIGH | [E-3] |
| Dead code | Commented-out ABAP blocks exceeding 5 lines; unreachable code paths | LOW | [CM-3] |
| Method / subroutine length | FORMs or METHODs exceeding 100 executable statements without clear decomposition | LOW–MEDIUM | [M-2] |
| Duplicate logic | Identical or near-identical code blocks in the same program (copy-paste patterns) | LOW | [M-1] |
| Magic numbers | Numeric or string literals used as constants without a named `CONSTANTS` declaration | LOW | [C-1] |
| Deprecated statements | Use of `SELECT ... ENDSELECT`, `MOVE ... TO`, `COMPUTE`, `WRITE ... TO`, `SET EXTENDED CHECK OFF` | MEDIUM | [L-3] |
| Unicode compatibility | Character-by-character operations on strings without Unicode-compatible methods | MEDIUM | — |
| Obsolete function modules | Use of deprecated FMs when newer equivalents exist (e.g., old date/time FMs) | LOW | [L-3] |

### Special Cases

- Multiple `SY-SUBRC` checks in sequence without intermediate reset: flag as potential logic error.
- Exception text `MESSAGE ... TYPE 'A'` inside a called FORM/METHOD: may silently abort calling program.

---

## Dimension 2 — Performance

**Goal**: Identify patterns that can cause runtime degradation, especially on large data volumes in production.

**Rule reference**: `abap-quality-rules.md`

### Check Items

| Check | Pattern / Signal | Default Severity | Rule |
|---|---|---|---|
| SELECT inside LOOP | `SELECT ... FROM ... WHERE ... ENDSELECT` or `SELECT SINGLE` inside a `LOOP ... ENDLOOP` — each iteration executes a DB round-trip | HIGH (CRITICAL for high-volume tables) | [T-2] |
| Full table scan | `SELECT ... FROM table WHERE ...` with no indexed key condition, or `SELECT ... FROM table` with no WHERE clause | HIGH | [T-2] |
| SELECT * without projection | `SELECT *` when only specific fields are needed; produces unnecessary data transfer | MEDIUM | [T-3] |
| READ TABLE WITH KEY inside LOOP | Linear scan on standard table inside loop; use SORTED TABLE WITH KEY or HASHED TABLE | HIGH | [T-1] |
| Missing `UP TO N ROWS` on large tables | Query on BKPF, BSEG, MKPF, MSEG, VBAK, VBAP, EKKO, EKPO, etc. with no row-count guard | HIGH | — |
| Inefficient internal table build | Using `APPEND` in a loop when `COLLECT` or pre-sized table would be more efficient | LOW | [T-1] |
| Nested LOOP with quadratic complexity | LOOP inside LOOP on internal tables both potentially large | MEDIUM–HIGH | [T-1] |
| Large result set passed over RFC | RFC function module returning unbounded internal table (`TABLES` parameter) to remote caller | MEDIUM | — |
| Missing `PACKAGE SIZE` on mass exports | `SELECT ... INTO TABLE ... PACKAGE SIZE n` not used for very large dataset iteration | MEDIUM | — |
| Excessive `SORT` calls | SORT on large internal table inside a loop; sort only once outside the loop | MEDIUM | — |

### High-Volume Table Watchlist

Any SELECT on these tables without key conditions or row limits is at minimum `HIGH`:

- FI: `BKPF`, `BSEG`, `BSIS`, `BSAS`, `BSIK`, `BSAK`
- MM: `MKPF`, `MSEG`, `EKKO`, `EKPO`, `EBAN`, `EKET`
- SD: `VBAK`, `VBAP`, `VBFA`, `LIPS`, `LIKP`
- PP: `AUFK`, `RESB`, `AFKO`, `AFPO`
- HR: `PA0001`, `PA0002`, `HRP1001`

---

## Dimension 3 — Security

**Goal**: Identify patterns that can expose the system to injection attacks, unauthorized external calls, sensitive data leakage, or OS-level exploitation.

**Rule reference**: `abap-security-rules.md`

### Check Items

| Check | Pattern / Signal | Default Severity | Rule |
|---|---|---|---|
| Dynamic SQL injection | `WHERE ( <dynamic_variable> )` — WHERE clause built from unvalidated user input | CRITICAL | SEC-SQL-1 |
| EXEC SQL | Use of Native SQL (`EXEC SQL`) — bypasses ABAP runtime safety | CRITICAL | SEC-SQL-2 |
| Dynamic code generation | `GENERATE SUBROUTINE POOL`, `INSERT REPORT` | CRITICAL | SEC-CODE-1, SEC-CODE-2 |
| OS command execution | `CALL 'SYSTEM'`, `SXPG_CALL_SYSTEM`, `SXPG_COMMAND_EXECUTE` | CRITICAL | SEC-OS-1, SEC-OS-2 |
| Dynamic RFC destination | `CALL FUNCTION ... DESTINATION ( <variable> )` — destination from unvalidated source | HIGH | SEC-RFC-1 |
| Unparameterized SQL via cl_sql_statement | `cl_sql_statement` without `set_param` (string concatenation into SQL) | CRITICAL | SEC-SQL-3 |
| Sensitive data in logs | Output of password, token, credit card, national ID fields to application log or syslog | HIGH | SEC-DATA-1 |
| Hardcoded credentials | String literals containing "password", "passwd", "token", "secret", "apikey" or similar | CRITICAL | SEC-CRED-1 |
| Unvalidated file paths | `OPEN DATASET <variable> FOR INPUT` where path is not validated or restricted | HIGH | SEC-FILE-1 |
| HTTP without TLS | `cl_http_client` with non-HTTPS endpoint or TLS verification disabled | HIGH | SEC-RFC |
| Unvalidated external input used in processing | RFC or OData parameter passed directly to DB query, FM call, or file operation without sanitization | MEDIUM–HIGH | SEC-SQL-1 |

### Special Rule

Any `CRITICAL` Security finding produces an automatic `NO_GO` decision, regardless of other findings.

---

## Dimension 4 — Authorization

**Goal**: Ensure the program checks user permissions before accessing or modifying sensitive data, and that authorization checks cannot be bypassed.

**Rule reference**: `abap-security-rules.md`

### Check Items

| Check | Pattern / Signal | Default Severity | Rule |
|---|---|---|---|
| Missing AUTHORITY-CHECK before sensitive table access | Read/write to FI, HR, MM, SD key tables without preceding AUTHORITY-CHECK | HIGH–CRITICAL | AUTH-MISS-1 |
| SY-SUBRC not checked after AUTHORITY-CHECK | `AUTHORITY-CHECK OBJECT ...` followed by code that runs regardless of `SY-SUBRC` | HIGH | AUTH-MISS-2 |
| Hardcoded SY-UNAME bypass | `IF SY-UNAME = 'ADMIN' OR SY-UNAME = 'SUPPORT'.` used to skip auth checks | CRITICAL | AUTH-BYP-1 |
| RFC function module without auth check | RFC-enabled FM with write operations and no AUTHORITY-CHECK inside | HIGH | SEC-RFC-2 |
| Authorization bypass pattern | IF condition that allows circumventing auth check based on parameter value | CRITICAL | AUTH-BYP-2 |
| Over-permissive object check | `AUTHORITY-CHECK OBJECT 'S_TCODE' ID 'TCD' FIELD '*'.` — wildcard on sensitive objects | HIGH | AUTH-BYP-3 |
| Missing auth check for sensitive transactions | Code calling a transaction that modifies FI/HR/MM data without own auth check | MEDIUM | AUTH-MISS-3 |

### High-Risk Tables Requiring AUTHORITY-CHECK

Before reading or writing: `BKPF`, `BSEG`, `MKPF`, `MSEG`, `VBAK`, `VBAP`, `EKKO`, `EKPO`, `PA*`, `HRP*`, `USR*`, `T5*`, `KNA1`, `LFA1`.

### Special Rule

Any `HIGH` Authorization finding is treated as `CRITICAL` for the release decision → automatic `NO_GO`.

---

## Dimension 5 — Transaction Consistency

**Goal**: Ensure that database updates are consistent, that LUW (Logical Unit of Work) boundaries are correctly managed, and that error paths trigger appropriate rollback.

### Check Items

| Check | Pattern / Signal | Default Severity |
|---|---|---|
| COMMIT WORK inside LOOP | `COMMIT WORK` inside `LOOP ... ENDLOOP` — partial commits create inconsistent state | CRITICAL |
| COMMIT WORK without error handling | `COMMIT WORK` without checking `SY-SUBRC` or handling commit failure | HIGH |
| ROLLBACK WORK missing on error path | Error path exists (exception, non-zero SY-SUBRC) but no `ROLLBACK WORK` | HIGH |
| BAPI transaction not committed | BAPI called (e.g., `BAPI_GOODSMVT_CREATE`) without `BAPI_TRANSACTION_COMMIT` | HIGH |
| BAPI commit not called after RETURN check | `BAPI_TRANSACTION_COMMIT` called before checking RETURN table for errors | HIGH |
| Mixed update techniques | `CALL FUNCTION ... IN UPDATE TASK` combined with direct `UPDATE`/`INSERT` in the same LUW | HIGH |
| Missing ENQUEUE before write | Write to a locking-relevant object without prior `ENQUEUE_*` call | HIGH |
| ENQUEUE without DEQUEUE | Lock acquired (`ENQUEUE`) but no corresponding `DEQUEUE` in all exit paths | MEDIUM |
| Dialog transaction with long-running DB lock | Enqueue held across multiple ABAP dialog steps | MEDIUM |
| UPDATE TASK without corresponding COMMIT | `CALL FUNCTION ... IN UPDATE TASK` but no `COMMIT WORK` to trigger the update | HIGH |

---

## Dimension 6 — Integration Impact

**Goal**: Identify risks to external systems, interfaces, or downstream consumers that could be affected by this TR.

### Check Items

| Check | Pattern / Signal | Default Severity |
|---|---|---|
| RFC call to external system | `CALL FUNCTION ... DESTINATION` — identify the system and whether it is production | MEDIUM–HIGH |
| RFC FM contains dialog messages | `MESSAGE ... TYPE 'A'` or `TYPE 'I'` inside RFC-enabled FM — blocks remote callers | HIGH |
| RFC EXCEPTIONS not fully declared | `CALL FUNCTION ... EXCEPTIONS ... OTHERS = 1` without specific exception handling | MEDIUM |
| IDoc outbound trigger | `CALL FUNCTION 'MASTER_IDOC_DISTRIBUTE'` or equivalent — assess volume and timing | MEDIUM |
| IDoc inbound processing change | Modification to inbound FM or processing code for an existing message type | HIGH |
| OData backend change | Change to DPC Extension methods or CDS-based OData entities — assess API consumers | HIGH |
| HTTP outbound call | `cl_http_client=>create_by_url` or equivalent — assess endpoint availability, auth, error handling | MEDIUM |
| BAPI call to external or cross-client system | BAPI called with external RFC destination | MEDIUM |
| File interface impact | `OPEN DATASET` for output — check path, format, downstream consumer | MEDIUM |
| Message output / print | `NAST` or `CALL FUNCTION 'NAST_TRIGGER_PRINT'` — assess whether batch jobs or output queues are affected | LOW–MEDIUM |
| Proxy or PI/PO interface change | Modification to a proxy class or outbound proxy method | HIGH |

### For Every Interface Found

State:
- Interface type (RFC / IDoc / OData / HTTP / File / BAPI / Proxy)
- Direction (inbound / outbound)
- Target system or endpoint (anonymized if sensitive)
- Risk level
- Whether the interface owner should be notified

---

## Dimension 7 — Transport Completeness

**Goal**: Verify that all objects required for the change to work correctly in the target system are included in the TR, or are already present there.

### Check Items

| Check | Pattern / Signal | Default Severity |
|---|---|---|
| Object in source code not in object list | Code references a program, class, FM, or table that is not in the TR and may not exist in target | HIGH |
| DDIC object missing from TR | Table, structure, data element, or domain used in code but not included in TR | HIGH |
| CDS view missing from TR | CDS view referenced but not transported | HIGH |
| Authorization object missing | Auth object referenced in `AUTHORITY-CHECK` not in TR and may differ between systems | MEDIUM |
| Customizing entry dependency | Code depends on a table entry (e.g., IMG config) that must exist in target — not transported | MEDIUM |
| Program group / function group incomplete | Only some FMs from a function group are in TR; others may be affected | MEDIUM |
| Class with missing method implementation | Global class in TR but one or more methods have been changed and not included | HIGH |
| Enhancement spot / BAdI incomplete | Enhancement filter or exit condition references objects outside the TR | MEDIUM |
| Transport prerequisite not listed | TR depends on another TR that has not yet been imported to the target system | HIGH |
| No rollback plan | No documentation of how to roll back if the transport causes issues in production | MEDIUM |

**Without dependency information**: All completeness checks are limited to intra-TR consistency only. Flag as `EVIDENCE_GAP` and mark Transport Completeness as `Restricted`.

---

## Dimension 8 — Functional Alignment

**Goal**: Verify that the implemented code matches the stated business requirements, including business rules, boundary conditions, and exception flows.

### Precondition

**This dimension requires a functional specification, requirement note, or test specification.**

If no functional material is provided:
- Label the entire dimension: `Inferred / Limited — no functional specification provided`
- Do not infer or assume what the business requirement is
- Do not claim the code is functionally correct
- List as `EVIDENCE_GAP` finding with severity `MEDIUM`

### Check Items (when spec is available)

| Check | Signal | Default Severity |
|---|---|---|
| Entry point coverage | Business scenarios in the spec are handled in code (entry points, conditions, branches) | HIGH if missing |
| Boundary condition handling | Null / zero / empty / oversized inputs handled as per spec | MEDIUM |
| Core business logic match | Calculation, selection, or transformation logic matches spec rules | HIGH if mismatch |
| Error / exception flow | Error scenarios from spec are handled; error messages are spec-compliant | MEDIUM |
| Output completeness | All output fields defined in spec are populated and formatted correctly | MEDIUM |
| Data source match | Code reads data from the tables/views specified; no undocumented data source substitution | MEDIUM |
| Authorization alignment | Auth checks reflect the roles defined in the spec | MEDIUM |

### Labeling Rules

- Findings based on spec comparison: `Confidence: HIGH`
- Findings where behavior is inferred from code structure without spec support: `Confidence: LOW`, label `[Inferred]`
- Findings that require business expert confirmation: `requires_human_confirmation: true`

---

## Dimension 9 — Release Readiness

**Goal**: Confirm that the technical preconditions for a safe transport are in place.

### Check Items

| Check | Required | Impact if Missing |
|---|---|---|
| Syntax check passed | Yes | Cannot claim code is syntactically valid; `EVIDENCE_GAP`, Release Readiness `Restricted` |
| All objects activated | Yes | Inactive objects will not work in the target system; `EVIDENCE_GAP`, HIGH finding |
| No activation errors | Yes | Activation errors block functional operation |
| Unit tests passing | Recommended | Without unit test evidence, test coverage is unverified; `EVIDENCE_GAP` |
| Manual / integration test evidence | Recommended | Without test evidence, Release Readiness cannot be labeled `fully ready` |
| Rollback plan documented | Recommended | Without rollback plan, emergency recovery is undefined; MEDIUM finding |
| Transport prerequisites confirmed | Recommended | Dependent TRs must be imported first; HIGH if unconfirmed |
| No open defects blocking release | Recommended | Known defects must be listed in Known Limitations |
| Performance test evidence | Conditional | Required if code accesses high-volume tables; MEDIUM if missing |

### Activation Status Rules

- If activation status is `Present`: list all inactive objects as `HIGH` findings.
- If activation status is `Missing`: flag as `EVIDENCE_GAP`; do not assume all objects are active.

---

## Dimension 10 — Evidence Gap

**Goal**: Surface all missing materials explicitly so that consumers of the report understand what was NOT reviewed, and how gaps affect the decision.

### Rule

Every missing evidence category identified in Step 2 (Evidence Intake) must produce at least one `EVIDENCE_GAP` finding.

### Finding Template for Evidence Gaps

```
id: EG-{n}
type: EVIDENCE_GAP
severity: MEDIUM (or HIGH if the gap directly blocks release judgment)
confidence: HIGH (the absence of the evidence is certain)
object: {affected category or "Review Package"}
location: {evidence category name}
evidence: "Not provided in the review package."
reasoning: {what this evidence would have shown}
impact: {how its absence affects the release decision}
recommendation: {what to provide, from whom, by when}
requires_human_confirmation: true
```

### Evidence Gap Impact on Decision

| Gap | Decision Impact |
|---|---|
| No syntax check result | Cannot confirm objects are syntactically valid; Release Readiness `Restricted` |
| No activation status | Cannot confirm objects are active; Release Readiness `Restricted` |
| No functional spec | Functional Alignment `Inferred / Limited`; `CONDITIONAL_GO` or lower |
| No test evidence | Release Readiness not `fully ready`; affects GO eligibility |
| No object list | Transport Completeness `Restricted`; scope of review indeterminate |
| No dependencies | Transport Completeness `Restricted`; extra-TR risks unknown |
| Multiple critical gaps | Likely `NEED_MORE_EVIDENCE` overall |
