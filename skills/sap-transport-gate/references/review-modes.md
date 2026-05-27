# Review Modes and Review Package Specification

> `sap-transport-gate` v1.2.0 — §1: Mode detection; §2: Evidence checklists; §3: Review Package structure

---

## §1 Review Mode Detection

The agent must identify the review mode before proceeding. Mode determines which evidence to expect and how to interpret gaps.

### Mode Decision Table

| Input Signal | Mode |
|---|---|
| User provides manifest file + object list + source files + evidence files as a structured package | **Offline Package Mode** |
| User provides only ABAP files, partial CDS/DDIC, or describes objects without a manifest | **Offline Local Mode** |
| User provides a TR ID (e.g. `DEVK900123`) and has CLI output, ADT export, or internal tool access | **Online Transport Mode** |
| User provides only natural language description, no code, no objects, no TR ID | **Insufficient — ask for materials** |

If the mode is ambiguous, ask the user ONE clarifying question:
> "Do you have a structured Review Package (with a manifest and full object export), or are you providing source files directly?"

Always declare the detected mode at the top of the report.

---

### §1.1 Offline Package Mode

**This is the preferred and most complete mode.**

The user provides a pre-assembled Transport Review Package — a structured collection of files that represents a single TR's evidence.

**When to use:**
- AI has no direct SAP system access
- Customer policy prohibits external tool connections to SAP
- User wants offline archiving, re-runnable review, or audit trail
- Evidence was exported via CLI or manual SE01/SE09/SE10/SE16 exports

**Mode flow:**
1. Read the package manifest (or equivalent index).
2. Cross-check manifest against `§2.1` Required Evidence Checklist.
3. Mark each evidence category: Present / Partial / Missing.
4. Produce `EVIDENCE_GAP` findings for missing categories.
5. Proceed with dimensional review using available materials.
6. Adjust Evidence Level downward for missing categories.
7. Output report and decision.

---

### §1.2 Offline Local Mode

The user provides partial materials only — no manifest, no structured package, no TR context at the TR level.

**When to use:**
- Review Package has not been assembled yet
- User wants a preliminary risk scan before formal review
- User wants code-level risk identification from a batch of ABAP files

**Key constraint — mandatory disclaimer:**

> "This is a partial review, NOT a Transport Request-level release gate review. The following findings are based on the code and materials provided. A full release-gate assessment requires: object list, dependencies, functional spec, activation status, and test evidence."

**Mode flow:**
1. Declare `Offline Local Mode` and partial-review scope.
2. Analyze only what is provided.
3. Do NOT output `GO` or `CONDITIONAL_GO` as a full release decision.
4. Output `NEED_MORE_EVIDENCE` or a local risk summary.
5. List what additional materials are needed for a complete review.

---

### §1.3 Online Transport Mode

The user provides a TR ID and has access to live system data via internal tools, CLI exports, or SAP ADT.

**Key boundary:**

> AI does NOT log in to SAP. AI does NOT hold SAP credentials. AI only consumes CLI/tool output.

**When to use:**
- User's environment has CLI tools that can read SAP DEV/QAS
- User can export TR objects, source, metadata, and evidence programmatically
- User wants to feed real-time CLI output into the review

**Mode flow:**
1. Identify the TR ID from user input.
2. **Proactively attempt auto-collection before asking the user for anything**:
   - Check for credentials (`.env`, `~/.sap-transport-gate/config.json`, env vars).
   - If credentials found: run `python3 scripts/tr_collector.py collect {TR_ID} --output-dir reports/{TR_ID}_package/ --verbose` using available shell tools.
   - If collection succeeds: treat as Offline Package Mode with the collected package.
   - If collection fails or credentials absent: fall back to Offline Local Mode. Inform the user of the reason and declare mode degradation in the report.
   - If shell execution is unavailable: ask the user to run the command and provide the output. Do NOT proceed with partial review until the user responds.
3. Never ask for SAP login credentials, passwords, or connection strings.
4. Never fabricate object content based on a TR ID alone.
5. If auto-collection is not possible, degrade gracefully to Offline Local Mode with scope limitation declared.

---

## §2 Evidence Completeness Checklists

### §2.1 Required Evidence — Offline Package Mode

For each item, mark the package as **Present (P)** / **Partial (X)** / **Missing (-)**.

#### TR Identity

| Item | Required | Notes |
|---|---|---|
| Transport Request ID | Yes | e.g. `DEVK900123` |
| TR Type | Yes | Workbench, Customizing, Transport of Copies |
| Owner / Created By | Yes | |
| Source System ID | Yes | e.g. `DEV`, `D01` |
| Target Stage | Yes | `DEV` / `QAS` / `PRD` |
| Creation Timestamp | Recommended | |
| Collection Timestamp | Recommended | When the package was assembled |

#### Object List

| Item | Required | Notes |
|---|---|---|
| Complete object list | Yes | All objects in the TR |
| Object type per entry | Yes | PROG, CLAS, FUGR, VIEW, TABL, DTEL, DOMA, TTYP, etc. |
| Object name per entry | Yes | |
| Package (Entwicklungspaket) | Recommended | |
| Changed By per object | Recommended | |
| Source file path per object | Yes | Path within the review package |

Missing or incomplete object list → Transport Completeness is `Restricted`; `EVIDENCE_GAP` finding required.

#### Source Code

| Item | Required | Notes |
|---|---|---|
| ABAP main programs / reports | Yes (if present in TR) | |
| ABAP global classes | Yes (if present in TR) | Include all methods |
| Function groups / function modules | Yes (if present in TR) | Include all FMs in the group |
| Includes | Yes (if present in TR) | |
| CDS views / CDS entities | Yes (if present in TR) | |
| DDIC definitions (tables, structures, data elements, domains) | Yes (if present in TR) | |
| Enhancement spots / BAdI implementations | Yes (if present in TR) | |

Objects present in the object list but without a source file → mark as `Unreviewed`; never assume safe.

#### Dependencies

| Item | Required | Notes |
|---|---|---|
| Intra-TR object dependencies | Yes | Dependencies within the same TR |
| Extra-TR object dependencies | Yes | Objects used but not in this TR |
| Table dependencies | Recommended | Tables read/written by the code |
| Interface dependencies | Recommended | RFC, IDoc, OData endpoints called |
| Authorization object dependencies | Recommended | Auth objects referenced in AUTHORITY-CHECK |

Missing dependencies → Transport Completeness is `Restricted`; `EVIDENCE_GAP` finding required.

#### Metadata

| Item | Required | Notes |
|---|---|---|
| Table metadata (field definitions, key structure, client-dependent flag) | Recommended | |
| CDS metadata (annotations, associations, parameters) | Recommended | |
| Authorization metadata (auth object fields and values) | Recommended | |
| Interface metadata (FM signatures, IDoc message types, OData entity sets) | Recommended | |
| Customizing metadata (relevant IMG nodes, table entries) | Recommended | |

#### Functional Materials

| Item | Required | Notes |
|---|---|---|
| Functional specification | Strongly Recommended | Without it, Functional Alignment is `Inferred / Limited` |
| Requirement note / change request | Recommended | |
| Test notes / test cases | Recommended | |

#### Release Evidence

| Item | Required | Notes |
|---|---|---|
| Syntax check result | Yes | Pass/fail; date of check |
| Activation status | Yes | All objects activated? |
| Unit test results | Recommended | ABAP Unit test report |
| Manual test results | Recommended | Test protocol or screenshot |
| Collection log | Recommended | CLI or tool collection log |
| Known limitations | Recommended | Any scope exclusions or known defects |

Missing syntax check or activation status → Release Readiness is `Restricted`; cannot claim objects are deployment-ready.

Missing test evidence → Release Readiness cannot be labeled `fully ready`; must list as `EVIDENCE_GAP`.

---

### §2.2 Minimum Evidence — Offline Local Mode

For partial reviews, minimum viable evidence to proceed:

| Minimum Required | Effect if Missing |
|---|---|
| At least one source file | Cannot review code; output `NEED_MORE_EVIDENCE` |
| Understanding of which object is being reviewed | Without this, scope cannot be stated |

Everything beyond source files is `EVIDENCE_GAP`. The review is limited to code-level observations only.

---

## §3 Review Package Structure

This is the conceptual model for a Transport Review Package. Physical format (files, directories, ZIP, JSON manifest) is defined by the CLI or export tool used — the SKILL does not mandate a specific layout.

### §3.1 Conceptual Contents

```
Transport Review Package for {TR_ID}
│
├── Manifest / Index
│   ├── transportRequestId
│   ├── trType
│   ├── owner
│   ├── sourceSystem
│   ├── targetStage
│   ├── createdAt
│   └── collectedAt
│
├── Object List
│   └── [{objectType, objectName, package, changedBy, sourceFilePath}]
│
├── Source Files
│   ├── ABAP programs (.abap)
│   ├── Classes (.abap / .xml)
│   ├── Function groups (.abap)
│   ├── Includes (.abap)
│   ├── CDS views (.cds / .ddls / .asddls)
│   └── DDIC definitions (.xml / .tabl / .dtel)
│
├── Dependencies
│   ├── intra_tr_deps.json / .txt
│   ├── extra_tr_deps.json / .txt
│   ├── table_deps.json / .txt
│   └── interface_deps.json / .txt
│
├── Metadata
│   ├── table_metadata/
│   ├── cds_metadata/
│   ├── auth_metadata/
│   └── interface_metadata/
│
├── Functional Materials
│   ├── functional_spec.md / .docx / .pdf
│   ├── requirement_note.md
│   └── test_note.md
│
└── Release Evidence
    ├── syntax_check.log / .txt / .json
    ├── activation_status.json / .txt
    ├── unit_test_results.xml / .txt
    ├── manual_test_evidence.md / screenshots/
    ├── collection.log
    └── known_limitations.md
```

### §3.2 Manifest Minimum Fields

When a manifest is present, it should express at minimum:

```json
{
  "transportRequestId": "DEVK900123",
  "trType": "Workbench",
  "owner": "DEVELOPER_ID",
  "sourceSystem": "DEV",
  "targetStage": "QAS",
  "createdAt": "2026-05-20T10:00:00Z",
  "collectedAt": "2026-05-25T14:30:00Z",
  "evidenceSummary": {
    "objectListPresent": true,
    "sourceFilesPresent": true,
    "dependenciesPresent": false,
    "metadataPresent": false,
    "functionalSpecPresent": true,
    "syntaxCheckPresent": true,
    "activationStatusPresent": true,
    "testEvidencePresent": false,
    "knownLimitations": "Dependencies not exported; no unit test coverage."
  }
}
```

If `evidenceSummary` is absent, the agent must infer completeness by inspecting available files and marking gaps explicitly.

---

## §4 Mode Degradation Rules

| Trigger | Degradation |
|---|---|
| Online Transport Mode: CLI not available, no evidence provided | Degrade to Offline Local Mode; declare scope limitation |
| Offline Package Mode: manifest missing but source files present | Continue with reduced Evidence Level; mark manifest as `Missing` |
| Any mode: zero source files provided | Cannot proceed with dimensional review; output `NEED_MORE_EVIDENCE` |
| Any mode: TR ID given but no objects or source available | Request evidence collection before review |

Degradation must always be declared in the report under "Scope Reviewed" and "Evidence Summary."
