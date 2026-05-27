# Human-in-the-Loop Rules

> `sap-transport-gate` v1.2.0 — §1: When to require human confirmation; §2: Confirmation spec format; §3: Role matrix

---

## §1 Mandatory Human Confirmation Triggers

The following situations always require human confirmation. AI cannot substitute for human expert judgment in these cases.

### §1.1 Stage-Based Triggers

| Trigger | Why Human Confirmation is Required |
|---|---|
| Target stage is `PRD` (production) | Any production release must have an accountable human approver on record. AI can provide analysis but cannot authorize production changes. |
| Target stage is `QAS` with financial, HR, or master data objects | QAS promotion of sensitive data objects requires business sign-off before promoting further to PRD. |

### §1.2 Finding-Based Triggers

| Trigger | Confirming Role(s) | Why |
|---|---|---|
| Any `CRITICAL` finding | Technical Lead + Release Manager + Security Owner (if SECURITY/AUTH) | CRITICAL findings represent potential production-stopping risks that require human judgment on whether the risk is acceptable with mitigations in place. |
| Any `HIGH` finding | Technical Lead | HIGH findings may have context or mitigations that AI cannot assess from static analysis alone. |
| `SECURITY` or `AUTHORIZATION` finding at any severity | Security Owner | Security and auth findings require a security-qualified person to confirm the risk assessment and mitigation plan. |
| `TRANSACTION_CONSISTENCY` CRITICAL or HIGH finding | Technical Lead + Business Owner (if financial objects) | LUW and commit risk in financial or inventory flows require domain expert validation. |
| `INTEGRATION_IMPACT` MEDIUM or higher finding | Interface Owner for each affected interface | Integration risks require the owner of the downstream system or interface to confirm impact and readiness. |

### §1.3 Evidence-Based Triggers

> **SKILL BOUNDARY**: The SKILL automatically fetches the following when TR ID and credentials are available — these are NOT human confirmation triggers:
> - **Object list**: fetched via `tr_collector.py collect` (ADT `/objects` endpoint or E071 fallback)
> - **Source code**: fetched for all supported object types via `tr_collector.py`
>
> Only evidence that the SKILL **cannot obtain programmatically** requires human confirmation.

| Trigger | Confirming Role(s) | Why |
|---|---|---|
| Functional Alignment is `Inferred / Limited` (no spec provided) | Business Owner or Product Owner | Without a functional spec, only the business owner can confirm that the implementation does what was intended. |
| Test evidence absent but release requested | QA Lead or Technical Lead | Someone qualified must attest that adequate testing was performed, even if results were not provided in the package. |
| Syntax check result absent (Offline modes only) | Technical Lead | In Offline modes the SKILL cannot run syntax checks; someone must confirm the current system state. In Online Transport Mode the SKILL should attempt to fetch activation status from ADT before triggering this. |
| Dependency information absent | Technical Lead | Someone must confirm that required TR prerequisites are in place in the target system. |

### §1.4 Conflict-Based Triggers

| Trigger | Confirming Role(s) | Why |
|---|---|---|
| AI finding contradicts developer's stated assessment | Technical Lead | When developer documentation or comments claim something safe that AI assessment flags as risky, a technical lead must adjudicate. |
| Business logic appears to deviate from spec in a non-obvious way | Business Owner | Subtle business rule divergence requires domain knowledge to confirm whether the deviation is intentional or erroneous. |
| Auth object scope or sensitivity is disputed | Security Owner | Determining whether a given authorization object represents acceptable risk requires organizational context. |

---

## §2 Confirmation Specification Format

Human confirmation items in the report must not be vague. Each item must specify:

```
Item: {What must be confirmed — one specific statement, not a generic request}
Confirming Role: {Exact role — see §3 Role Matrix}
Evidence Basis: {What the AI found that triggered this confirmation requirement}
Confirmation Method: {How the human confirms — sign-off on report / Jira comment / email / system approval}
Risk if Not Confirmed: {What happens if this item is skipped}
```

### Example — Good Confirmation Item

```
Item: Confirm that AUTHORITY-CHECK on object 'F_BKPF_BUK' (company code level)
      in method POST_DOCUMENT is sufficient for the intended user authorization scope
      in PRD, given that the check uses a variable company code from the input parameter.
Confirming Role: Security Owner
Evidence Basis: Finding F-004 (AUTHORIZATION, HIGH): AUTHORITY-CHECK present but uses
      variable field value from external input without validation of allowed values.
Confirmation Method: Written sign-off in the Human Confirmation Checklist (§7 of report).
Risk if Not Confirmed: Users may be able to post documents to company codes they are
      not authorized for by passing an unexpected parameter value.
```

### Example — Bad Confirmation Item (too vague)

```
Item: Please confirm that the authorization is OK.  ← INVALID: does not specify what, who, or why
```

---

## §3 Role Matrix

| Role | Responsibilities in Human Confirmation |
|---|---|
| **Developer** | Confirms that findings have been understood and remediation actions have been completed; confirms that test evidence is accurate. |
| **Technical Lead** | Confirms that HIGH findings have acceptable mitigations; confirms that code design decisions are intentional; confirms dependency completeness. |
| **Security Owner** | Confirms that SECURITY and AUTHORIZATION findings are acceptable or mitigated; signs off on any security-related `CONDITIONAL_GO` items. |
| **QA Lead** | Confirms that testing was performed and results are valid; attests to test coverage when evidence was not provided in the package. |
| **Business Owner** | Confirms that the implementation aligns with business requirements when Functional Alignment is `Inferred / Limited`; approves release of business-critical changes. |
| **Interface Owner** | Confirms that an external interface or downstream system is prepared to handle the change; for Integration Impact findings. |
| **Release Manager** | Authorizes the final release decision; is accountable for the go/no-go sign-off. Required for all PRD releases. |

---

## §4 Special Cases

### §4.1 PRD Release — Full Sign-off Required

For `PRD` target stage, the Human Confirmation Checklist must include entries for:
1. Developer — code completeness and test confirmation
2. Technical Lead — technical readiness
3. Release Manager — release authorization
4. Security Owner — if any SECURITY / AUTH finding exists
5. Business Owner — if functional alignment is inferred or business-critical objects are involved

A `GO` decision for PRD without this checklist is incomplete.

### §4.2 Financial and Inventory Objects

For changes affecting `BKPF`, `BSEG`, `MKPF`, `MSEG`, `EKKO`, `EKPO`, `VBAK`, or `VBAP`:
- Business Owner confirmation is required for functional alignment regardless of spec presence.
- Finance Controller sign-off is recommended if the change affects financial postings.

### §4.3 HR and Personal Data Objects

For changes affecting `PA*` (infotypes), `HRP*`, or tables containing PII:
- Data Privacy Officer (DPO) or HR IT Owner confirmation is required.
- Compliance basis for PII processing must be documented.

### §4.4 AI Assessment vs. Developer Claim Conflict

When a developer's inline comment or documentation states "This is safe / authorized / tested" and the AI assessment contradicts it:

1. AI documents the conflict explicitly in the finding.
2. Sets `requires_human_confirmation: true` and `confidence: MEDIUM`.
3. Escalates to Technical Lead for adjudication.
4. Does NOT defer to the developer's claim without Technical Lead confirmation.

---

## §5 What Human Confirmation is NOT

Human confirmation in this SKILL is NOT:
- A rubber stamp ("please sign off on the report")
- A generic approval request without specific items
- A substitute for fixing a CRITICAL finding (`CRITICAL` requires fix, not just confirmation)
- An escape hatch from a `NO_GO` decision (confirmation cannot override `NO_GO` — the blocking finding must be remediated first)

`CRITICAL` findings must be **remediated** before the decision can be elevated. Human confirmation can be used for `MEDIUM` findings and some `HIGH` findings with clear mitigation paths, but not as a way to "confirm away" a `CRITICAL` risk.

---

## §6 Required Actions (§6 of report) vs. Human Confirmation (§7 of report)

These are two distinct sections in the report with different purposes. Do NOT conflate them.

| | Required Actions (§6) | Human Confirmation Checklist (§7) |
|---|---|---|
| **What it contains** | Specific tasks that must be completed before release | Facts or risk assessments that need sign-off from a named role |
| **Who acts** | Named role performs an action (writes code, runs a test, deploys a prereq TR) | Named role reviews the AI finding and signs off on acceptance or mitigation |
| **Example** | "Developer: fix the hardcoded company code in method POST_DOC" | "Security Owner: confirm that AUTHORITY-CHECK on F_BKPF_BUK is sufficient given variable input" |
| **Decision gate** | CONDITIONAL_GO / NO_GO / NEED_MORE_EVIDENCE | Any finding with `requires_human_confirmation: true` |

**Critical rule**: Items the SKILL can fetch automatically (object list, source code) must appear in **neither** section. They are SKILL responsibilities, not human tasks. If a `tr_collector.py` run fails, the fallback is Offline Local Mode — not a Required Action asking the human to provide what the SKILL should have fetched.
