# Regression and controlled development (CLI 1.6.5+)

Check `sap-adt --version` and the relevant command help. These additions are
not available in every runtime accepted by the general 1.x compatibility
range. Ask before upgrading, changing permissions or contacting SAP.

## Permission model

| Action | Required capability |
|---|---|
| Read signatures, definitions, source or compatibility evidence | Configured connection |
| Harmless Unit | Existing diagnostic behavior; harmless is not a sandbox |
| Dangerous/critical Unit, typed functions, Report wrappers | Independent `allow_execute`, non-PRD, fresh approval |
| Create, source/definition update, deletion, change manifests | `allow_write`, non-PRD, fresh approval |
| Manifest with high-risk final Unit | Both permissions, for distinct stages |

`allow_execute` does not authorize generic repository changes. Execution-only
wrappers may create/write/activate/clean up their invocation-owned `$TMP` Class
without `allow_write`; SAP development authorizations are still required.
`allow_write` does not authorize high-risk Unit. High-risk Unit used the older
write gate before CLI 1.6.5: do not copy old authorization advice.

For new mutation/execution commands, unattended `--yes` requires the exact
`--expect-plan-sha256` from a reviewed `--dry-run` with otherwise identical
arguments. Never invent hashes. Approval is specific to target, content and
options. No automatic COMMIT, rollback, mutation/execution replay, broad
prefix deletion or service publication.

## ABAP Unit regression

```bash
sap-adt --profile dev run-unit-test ZCL_ORDER ZCL_ITEM --require-tests --junit unit.xml
sap-adt --profile dev run-unit-test --package ZORDER --recursive --max-objects 100 --dry-run
sap-adt --profile dev run-unit-test --transport DEVK900001 --max-objects 100 --dry-run
sap-adt --profile dev run-unit-test ZCL_ORDER \
  --risk-level harmless --risk-level dangerous --duration short --duration medium --dry-run
```

Choose **explicit names OR package OR transport**, never combine scopes.
Package recursion is opt-in. TR selection includes its tasks. Objects are
deduplicated and bounded to 500 (default 100); unsupported containers are
listed in `plan.excluded`, not claimed tested. Explicit `--type` supports Class,
Program, Interface, Include, Function (`--group`) and Function Group.

Risk/duration flags are explicit sets, not maximum thresholds. `all` selects
every value. One request per selected object carries the entire selected set;
there is no Cartesian-product replay. Defaults remain harmless/short.
High-risk `--yes` requires the reviewed scope hash. Source/dependencies are
not atomically frozen by that hash.
The backend's own risk ceiling still applies. DEV acceptance observed a real
dangerous Class refused as exceeding that ceiling despite explicit selection.
Preserve that skipped/incomplete evidence and nonzero exit; do not lower a real
test's declared risk or change SAP settings to make a run appear passed.

Inspect `runs`, `test_classes`, `summary`, `evidence_gaps` and `meta.partial`.
`ok:true` confirms parsed evidence, not test success. No executed methods
means `not_run`, not passed; `--require-tests` makes this nonzero. Setup errors
can fail a class with zero methods. Incomplete evidence exits nonzero even
with `--fail-on never`. A request failure/unknown outcome stops later objects;
the output preserves completed and unattempted scope, never retries execution.

JUnit is written to a **new local path** only, never overwriting a report.
`--junit` may be included in the dry-run to bind that path to the reviewed
plan; dry-run itself never creates a report. Keep it identical for execution.
It preserves failed/skipped methods, fixture failures and missing/unattempted
evidence. If local report creation fails after tests ran, retain JSON evidence;
do not rerun tests just to recreate the report.

## Typed local function/BAPI execution

```bash
sap-adt --profile dev get-function-signature Z_ORDER_READ --group ZORDER
sap-adt --profile dev run-function Z_ORDER_READ --group ZORDER \
  --input-file inputs.json --dry-run
```

Example `inputs.json`, using names/types from the actual signature:

```json
{
  "importing": {"IV_ORDER": "0000000123"},
  "changing": {"CS_OPTIONS": {"DETAIL": "X"}},
  "tables": {"ET_RETURN": []}
}
```

The signature is parsed from **observed active function source**, including
the generated Local Interface header; no separate signature endpoint is
invented. Explicit named TYPE/LIKE and TABLES STRUCTURE declarations are
supported. Generic, reference, anonymous-table or ambiguous declarations are
refused rather than guessing types. Group is explicit; JSON keys/directions
must match the real interface. Required inputs cannot be silently omitted.
An output named `SUBRC` is refused because it collides with the wrapper status
field; do not silently rename parameters or substitute an unreviewed snippet.

The reviewed wrapper declares typed variables, deserializes inputs, calls the
local function once and serializes outputs using standard ABAP transformation
ID/SXML JSON APIs (not an assumed `/UI2/CL_JSON` dependency). It preserves
omitted optional IMPORTING defaults and returns EXPORTING/CHANGING/TABLES
parameters in `result`, plus integer `SUBRC`. It is not native RFC and exposes
no remote `DESTINATION` option.

The plan binds interface source hash, inputs, generated source, target and
execution limits; inputs and active main source are re-read after approval.
Dependent types/includes and variant contents are not atomic snapshots.
Result extraction requires exactly one complete marker pair, strict JSON and
numeric `SUBRC`; truncation/missing/duplicate/malformed output is incomplete,
not empty success. Nonzero `SUBRC` is a classical function exception (mapping
in the signature) or wrapper failure. Inspect business `RETURN` messages:
zero `SUBRC` never means business success. No automatic transaction decision.

## Report parameters and variants

Native `run-report NAME` still uses ADT `programs/programrun` with default
selections. Supplying `--variant` or `--parameters-file` explicitly selects
a **generated temporary-Class SUBMIT wrapper**, not invented ADT parameters:

```bash
sap-adt --profile dev run-report ZORDER_REPORT --variant TEST \
  --parameters-file selections.json --dry-run
```

```json
[
  {"name": "P_MODE", "low": "TEST"},
  {"name": "S_DATE", "kind": "S", "sign": "I", "option": "BT",
   "low": "20260101", "high": "20261231"}
]
```

Rows use RSPARAMS: at most 500, selection name at most 8 and LOW/HIGH at most
45 characters, internal SAP formats. Defaults are kind P/sign I/option EQ.
Duplicate P parameters, invalid options and unknown fields are refused.
Variant names are at most 14 safe SAP characters. Variant availability/content
and compatibility of actual selection names remain server-side checks.

The wrapper uses `SUBMIT ... USING SELECTION-SET ... WITH SELECTION-TABLE ...
EXPORTING LIST TO MEMORY AND RETURN`, then `LIST_FROM_MEMORY/LIST_TO_ASCI`.
Only classic List output is captured, in `result.LIST`; no GUI selection
screen, ALV-control, Spool or asynchronous cancellation is promised.
`SUBRC` here is **List capture** status, not a Report business return code.
No List or failed conversion exits nonzero after possible Report side effects;
never rerun to recover output. Both typed/Report wrappers require standard
Classrun, SXML and temporary-Class lifecycle support on the target.

## Object lifecycle matrix

All paths below are under `/sap/bc/adt/`. Writes require source permissions,
except the tightly scoped execution-owned temporary Class.

| CLI type | Resource | Editable representation |
|---|---|---|
| class / interface / program | oo/classes, oo/interfaces, programs/programs | Existing text source/parts |
| include | programs/includes | Text source |
| function-group | functions/groups | Text source; no container deletion |
| function / function-include | functions/groups/{group}/fmodules or includes | Text source; explicit parent group |
| domain / data-element | ddic/domains, ddic/dataelements | XML metadata at object root, not `/source/main` |
| structure / table | ddic/structures, ddic/tables | DDL text; Table name max 16 |
| cds / dcl | ddic/ddl/sources, acm/dcl/sources | DDL/DCL text |
| bdef / srvd | bo/behaviordefinitions, ddic/srvd/sources | Text source |
| srvb | businessservices/bindings | Create + read metadata only; no proven XML update contract |
| package | packages | Existing create; no text write or container deletion |

Create with `create-object TYPE NAME --package ... --description ...`.
Function/Function Include require `--group` matching the package. Function
Group names are at most 26, Include at most 40, other names at most 30.
Function Includes use the full `L{customer-group}{three-character suffix}` name
matching the explicit parent, for example `LZGROUPF01`.
New types negotiate a known MIME version from **that discovery collection**;
unadvertised/unsupported versions fail closed, not fallback mutation attempts.

SRVB additionally requires `--service-definition`, `--binding-protocol V2|V4`
and explicit numeric `--binding-category 0|1`; UI/API category labels differ
across clients, so do not guess a mapping. The referenced SRVD must exist.
Readback checks definition/protocol/category and confirmed unpublished state.
Creation is not publication and does not upload/activate other objects.

`get-definition domain|data-element|srvb NAME` returns an envelope containing
`data.xml`; save **that XML string**, not the whole JSON envelope, before
editing. `write-definition domain|data-element NAME --file definition.xml`
locks, rechecks the full metadata baseline, PUTs **the object root**, reads
back content and unlocks. Round-trip existing XML to preserve system fields.
No implicit activation. SRVB XML update is intentionally unavailable.

Existing Domain/Data Element storage-type changes and active Table schema
writes are blocked without a separate conversion assessment. Initial
unactivated definitions/tables with proven missing active versions can be
populated. No automatic technical settings, destructive table conversion,
data migration or restoration is attempted.
An identity-matched metadata `version=new` is also explicit no-active-version
evidence on backends that ignore the active-version query. Table writes and
activation require that confirmed new state; existing/uncertain tables remain
blocked even if their source endpoint echoes the same text for both versions.

SAP can regenerate Function headers and format DDIC DDL. Start from returned
source/backend formatting. A differing readback still prevents activation:
inspect the result, do not weaken the hash check or replay the write blindly.

`delete-object TYPE NAME --dry-run` plans one customer object only. Table,
Package and Function Group deletion is refused; SRVB deletion requires
confirmed `published=false`. One deletion POST must be followed by independent
object-not-found readback; HTTP 2xx or an unknown 404 route is not proof.
No cascade discovery, automatic dependency deletion or automatic cleanup.
Table Types, old Views, Search Helps and Lock Objects are outside this scope.

## Multi-object change manifests

```bash
sap-adt --profile dev apply-change-set --file changes.json --dry-run
```

```json
{
  "schema_version": 1,
  "operations": [
    {"id": "interface", "action": "write-source", "type": "interface",
     "name": "ZIF_ORDER", "file": "zif_order.abap"},
    {"id": "class", "depends_on": ["interface"], "action": "write-source",
     "type": "class", "name": "ZCL_ORDER", "file": "zcl_order.abap"}
  ],
  "activate": true,
  "unit": {"objects": ["ZCL_ORDER"], "risk_levels": ["harmless"], "durations": ["short"]},
  "atc": [{"type": "class", "name": "ZCL_ORDER", "variant": "STANDARD"}]
}
```

At most 100 operations with unique IDs/object-parts and an acyclic explicit
dependency graph. UTF-8 files are at most 2 MiB, relative to and contained in
the manifest directory (including symlink resolution). Unknown fields,
duplicate identities, cycles, missing dependencies and unobserved baselines
are refused before mutation. Source writes check candidates by default;
`"check":false` must be explicitly reviewed and does not waive readback.

Actions: `write-source`, `write-definition` or `create-object`. Creation is a
**separate reviewed phase** before writing generated stubs or creating children
of new containers. Re-read new objects and make a fresh source plan; do not
silently assume a not-yet-observed baseline. XML-definition activation is also
a separate explicit phase; the manifest combined-activation phase covers
text-source writes only.

Plan hash binds the manifest, DAG order, files, SAP baselines, target, transports
and gate options. Revalidated before the first change, then each object uses
its own lock/baseline/readback/unlock. Combined activation sends the explicit
objects once and verifies every active version and selected source part.
Unit/ATC are **final evidence gates after activation**, not proof of unactivated
local content. Final Unit requires actual passing methods, not an empty run.
Unfinished/unparsed ATC evidence or hard findings cannot pass the gate.

Failure or unknown outcome stops later mutations/gates and reports completed
and unattempted operations. Previous writes remain; no atomicity, automatic
rollback, source restoration, deletion of created objects or replay is claimed.
`WRITE_INCOMPLETE` after a final gate failure does not mean nothing changed.

## Compatibility and verification

`credentials doctor --coverage` adds `object_operations`: implementation
flags, discovery-advertised resource and `live_verification` are distinct.
Discovery does not prove methods, subresources, MIME support, authorizations,
backend versions or business execution correctness.

CLI 1.6.5 was accepted against isolated DEV-owned fixtures on 2026-11-22:
typed scalar/CHANGING/TABLES inputs and outputs, Unicode/long strings and
classical exceptions; Report selections and a real private variant; Include/
Function Group/Function creation and Function Include updates; Domain/Data
Element definition writes and activation; Structure, CDS, DCL, BDEF and SRVD
source/activation; unpublished SRVB creation/read/delete; new unactivated Table
DDL; two-object and recursive Package Unit/JUnit; ordered interface/Class writes
with combined activation and passing final Unit/ATC. Execution-only cases kept
generic writes disabled. Saved profile permissions were not changed.

DEV's risk ceiling prevented a dangerous Class from running; its incomplete
result/nonzero exit was verified, **not** counted as a passing dangerous test.
Both harmless methods really executed in the passing regression. No open
configured-user TR was available, so TR/task execution remains offline-tested.
Physical Table activation, existing DDIC conversion, service publication/V4
runtime, business BAPI commit, non-local transport mutation and other SAP
versions are not live-certified. All acceptance-owned fixtures were confirmed
absent, including retained temporary Classes cleaned only after dump-confirmed
termination and exact ownership/source verification. Request explicit
authorization and use isolated owned fixtures for any further live acceptance.
