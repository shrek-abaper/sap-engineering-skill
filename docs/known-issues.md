# Known Issues — sap-adt-cli

Discovered and verified against a real **S/4HANA 2021 / SAP_BASIS 7.56** DEV
system (client 400). Verification dates noted per item.

## Endpoint deviations (old → new)

| Command | Old call (fails on 7.56) | Status | New call (verified) | Verified |
|---|---|---|---|---|
| `list-transports` | GET `/sap/bc/adt/cts/transports`, Accept `application/vnd.sap.cts.transport.worklist+xml` → **406** | migrated | GET `/sap/bc/adt/cts/transportrequests`, Accept `application/vnd.sap.adt.transportorganizertree.v1+xml` | 2026-09-15 |
| `syntax-check` | POST `/sap/bc/adt/abapsource/syntaxcheck` → **404** | migrated | POST `/sap/bc/adt/checkruns`, request `checkObjectList`/Content-Type `application/vnd.sap.adt.checkobjects+xml`, Accept `application/vnd.sap.adt.checkmessages+xml`, reporter `abapCheckRun` | 2026-09-15 |
| `get-type-info` domain branch | GET `/ddic/domains/{name}/source/main` → **404** (always fell back to data element) | migrated | GET `/ddic/domains/{name}` (`vnd.sap.adt.domains.v2+xml`); fallback to `/ddic/dataelements/{name}` only on a genuine 404; `data.resolved_as` is explicit | 2026-09-15 |
| `run-sql` | GET `freestyle?sqlCommand=...`, POST only as a 405 fallback | migrated (batch 3.5) | **POST** `/datapreview/freestyle?rowNumber=<N>`, `Content-Type: text/plain; charset=utf-8`, body = raw SQL; `Accept: application/vnd.sap.adt.datapreview.table.v1+xml` (**`application/xml` is rejected with 406**); GET kept only as a 405 fallback for older releases | 2026-09-16 |
| `where-used` | GET `/informationsystem/whereused?uri=...` → **405** | migrated (batch 3.6) | POST `/informationsystem/usageReferences?uri=<relative lower-case object URI>`, `Content-Type: application/*`, `Accept: application/*`, body `usageReferenceRequest/affectedObjects` (empty); legacy GET kept as a 404/405 fallback for older releases | 2026-09-16 |

DML rejection, the `allow_write`/`allow_transport` gates, per-operation
`[y/N]` confirmation and lock/unlock are unaffected. run-sql still rejects
write statements before any request is sent.

## Fields: DDL shape on S/4

`get-table`/`get-structure` serve CDS-style DDL (`define table/structure`),
not field-metadata XML (2026-09-15):

- built-in types resolve: `abap.char(18)` → `CHAR`/18, `abap.dec(13,2)` →
  `DEC`/13/2; parenless fixed types (`abap.int4`) resolve with `length: null`;
- data-element references (`mandt`, `vbeln_va`, …) keep `length`/`decimals`
  null and are collected in `meta.unparsed_types`;
- field descriptions are **not available**: `/ddic/tables/{name}/objectstructure`
  returns 404 and the generic `/repository/objectstructure` does not serve
  field text (2026-09-16). Field objects therefore omit `description`
  entirely rather than emitting a permanently-null key.

## where-used: usageReferences request body (resolved 2026-09-16)

The endpoint is POST-only (GET → 405). Failed constructions during the
layered investigation:

1. Singular root with empty `affectedObjects`, but the **full URL**
   (`https://host/...`) in `?uri=` and vendor v1 content types → **500**
   "Error while converting object references".
2. Same body with a VIT uri in `?uri=` → **500**.
3. `affectedObjects/<usagereferences:affectedObject>` → **400** "expected
   element `{...adt/core}objectReference`".
4. `affectedObjects/<adtcore:objectReference …>` → **500** again.

Resolution came from the production reference implementation
(github.com/marcellourbani/abap-adt-api, `src/api/syntax.ts`
`usageReferences`):

- `?uri=` is the **relative, lower-case** object root URI
  (`/sap/bc/adt/oo/classes/cl_gui_frontend_services`); an optional
  `#start=line,column` fragment selects a position;
- body is exactly `usageReferenceRequest` with an empty `affectedObjects`
  (no child reference elements, no adtcore declaration needed in the body);
- request `Content-Type` **and** `Accept` are `application/*` (the vendor
  `…request.v1+xml` content type is what triggered the conversion errors);
- response is `application/vnd.sap.adt.repository.usagereferences.result.v1+xml`
  (`usageReferenceResult/referencedObjects/referencedObject`, each with an
  `adtObject` + `packageRef`).

Verified: 200 with `numberOfResults=939` for CL_GUI_FRONTEND_SERVICES; a
non-existent class returns 200 `numberOfResults=0` (normalized to
`ok:true,row_count:0,exit 0`). `objects[]` gains the optional `usage_line` /
`usage_uri` keys only when a referenced object URI carries a `#start=`
fragment; search-object/get-package never emit them. The committed fixture
is a trimmed SAP-only subset (the real tree contains customer Z/Y paths).

## ABAP Unit: testMethod path unverified (synthetic fixture)

`run-unit-test` is implemented against the checkrun/abap-adt-api structure,
but on the capture S/4HANA DEV system no healthy, executable test class was
found via `where-used CL_ABAP_UNIT_ASSERT` (30 referencing classes +
source-scanned candidates all return an empty 99-byte shell; one local class
returns an alert-only response). Therefore:

- **verified on a real system**: empty shell → `no_tests_found:true,total:0`;
  alert-only (defective test class) → warning finding with
  `source_severity`, still `no_tests_found:true`; risk-level gating and
  explicit config `v4` content type (response `…result.v2+xml`);
- **NOT verified**: the `testMethod` pass/fail/skipped counts,
  `executionTime` duration, failed-assertion text extraction and the
  `unit` status attribute values. These are exercised only by
  `tests/fixtures/synthetic/unit.methods.synthetic.xml`, inferred from
  abap-adt-api `src/api/unittest.ts`.

Verification trigger: when the first REAL response containing `testMethod`
nodes arrives (recommended: a QAS with self-developed unit tests, or any
system with complete SABP_UNIT sample content), every field path in the
synthetic fixture MUST be checked against it; on mismatch, change the
parser/fixture to match the real payload. Unexpected node names are
surfaced in `meta.unparsed_nodes` rather than ignored.

## ATC: priority 1/2 mapping unverified (synthetic fixture)

The real ATC capture (`atc.findings.xml`) contains only priority-3
findings. Priority 1→error, 2→warning and exemption suppression are
exercised solely by `synthetic/atc.priorities.synthetic.xml` (inferred
from `abap-adt-api` and the priority-3 shape). On the first real ATC
worklist carrying priority 1/2 findings or `exemptionKind` values other
than `""`/`"A"`, verify the mapping and update the fixture/parser to
match the real payload. Unknown priority values already map to info and
surface in `meta.unparsed_nodes`.

## Other open items

- Non-empty `list-transports` tree: only an empty-tree fixture exists (the
  capture user owns no transports); `tasks[]` nesting and the
  `status`/`status_text` mapping need a populated tree fixture.
- ECC 6 / older-release shapes for fields / where-used / transports /
  syntax-check still need fixtures; those parsers accept the modern shapes
  only today.
