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

## Release: RELEASE_UNVERIFIED / RELEASE_REJECTED long paths unverified

The happy path is live-verified (2026-09-16, empty request ECDK944391,
blank target): preflight D, `newreleasejobs`, readback R on poll attempt
1 within the 2 s interval. NOT verified against a real system:

- **RELEASE_UNVERIFIED** — requires a release whose final status stays
  unknown past the 120 s timeout (60 × 2 s polls) or a failing readback.
  The empty TR completes too quickly to trigger it; needs a large request
  or a system with slow/pre-release ATC. Covered only by offline tests with
  injected poll failures/timeout.
- **RELEASE_REJECTED via release-report failure**
  (`chkrun:status=abortrelapifail` / E messages) — the real
  `newreleasejobs` POST response for ECDK944391 was one-shot and was not
  captured; the response shape comes from abap-adt-api and is covered by
  `synthetic/transport.release-report.synthetic.xml`. Capture a real
  report (especially a failing one) at the first opportunity.

Verification trigger: any release on a populated request or a system with
mandatory pre-release checks.

## ATC: priority 1/2 mapping unverified (synthetic fixture)

The real ATC capture (`atc.findings.xml`) contains only priority-3
findings. Priority 1→error, 2→warning and exemption suppression are
exercised solely by `synthetic/atc.priorities.synthetic.xml` (inferred
from `abap-adt-api` and the priority-3 shape). On the first real ATC
worklist carrying priority 1/2 findings or `exemptionKind` values other
than `""`/`"A"`, verify the mapping and update the fixture/parser to
match the real payload. Unknown priority values already map to info and
surface in `meta.unparsed_nodes`.

## configure silently resets unspecified fields (queued fix; high)

Logged 2026-09-16 during batch 10 (session layer) design. The non-interactive
`configure` path rebuilds the profile section from Click defaults, so any
flag left at its default is indistinguishable from an explicitly supplied
value and overwrites the stored field. Concrete cases:

- omitting `--no-verify-ssl` resets `verify_ssl` to `true` — a self-signed
  system becomes unreachable after an unrelated flag change;
- passing `--no-verify-ssl` once keeps certificate verification disabled
  until explicitly reverted — a security downgrade that survives future
  invocations the user did not associate with TLS settings.

Correct behavior: `configure` updates ONLY fields passed explicitly on that
invocation; every other field keeps its stored value (distinguish "flag
absent" from default `False`, e.g. via `required=False, default=None`).

Priority **high** (security-relevant, both flip directions); queued as the
first fix after the three remaining real-machine verifications listed in
`refactor-handoff.md` §4. Not changed in batch 10.

## activate: failure-response parser shape unverified (potential false success)

Logged 2026-09-16 during the real-machine write-path verification (batch 10).
The happy path is live-verified: `POST /sap/bc/adt/activation?method=activate`
200 empty body, followed by readback showing the object gone from
`/activation/inactiveobjects` and `adtcore:version="active"`.

NOT verified: a real **failed** activation. Per the reference implementation
(abap-adt-api `src/api/activate.ts`) the failure body is
`chkl:messages/msg` with `type` E/A/X plus an `ioc:inactiveObjects` list;
the product parser `_parse_activation_errors` instead looks for
`error`/`message`/`checkResult` elements. A real failure could therefore be
reported as success if the body is non-empty but uses the `chkl:msg` shape.

The parser is intentionally NOT changed without a real failed response.
Trigger: capture the first genuine failed activation on the DEV system
(e.g. an object with a syntax error), verify the element paths, then align
parser + add a sanitized fixture. Until then treat an activation as complete
only with an independent readback (inactiveobjects list / `version`).

## create-transport: fixed 2026-09-17; two parameter questions still open

The old `create-transport` had never succeeded on a real system. A
two-variant real probe on S/4HANA 2021 / 7.56 measured the deviations,
and the command was fixed the same day:

| Dimension | Old CLI (rejected) | Current form (verified) |
|---|---|---|
| Content-Type | `application/vnd.sap.cts.transport.request+xml` → **400** `ExceptionDataTypeNotFound` | `application/vnd.sap.as+xml; charset=UTF-8; dataname=com.sap.adt.CreateCorrectionRequest` |
| Accept | none | `text/plain` |
| Body | `<cts:transportRequest><cts:attributes>` category/owner/description/target | ASX `DATA{DEVCLASS,REQUEST_TEXT,REF,OPERATION=I}` |
| Response | `Location` header first | text/plain `/com.sap.cts/object_record/<TRKORR>` |
| CLI options | `--category` (no server-side equivalent) | `--package` + `--description` + `--ref`, all required |

Evidence: old shape → 400 (`tests/fixtures/transport.create.400-old-shape.xml`);
ASX probe (`DEVCLASS=$TMP`, REF = probe program source URI, `OPERATION=I`)
→ 200 creating local request ECDK944393; direct readback
`GET /cts/transportrequests/ECDK944393` confirmed `tm:status="D"` /
"Modifiable" and the description
(`tests/fixtures/transport.create.success.txt`). The fixed CLI emits a
request byte-identical to that live-200 probe (offline harness
assertion); a second end-to-end creation was deliberately not run.
Also measured: root `GET /cts/transportrequests` returned empty even
while the user owned that modifiable D request — per-TR readback is the
reliable check (see "non-empty tree" item below).

Still unverified — do NOT loosen the interface until measured:

1. whether `REF` is truly mandatory or any object URI is accepted;
2. behavior with a real transportable package instead of `$TMP`
   (transport layer, target, task creation);
3. `OPERATION` values other than `I`.

Trigger: first real creation against a transportable package, or a
probe omitting `REF`. Relaxing a required option later is backward
compatible; the command starts conservative on purpose.

## CSRF prefetch GET /activation returns 405 (harmless)

For the first POST/PUT of a process, `client._fetch_csrf_token` issues GET
against the request URL. On `/sap/bc/adt/activation` the GET returns 405
`ExceptionMethodNotSupported`, but the response still carries a valid
`x-csrf-token` header, so the following POST succeeds (measured
2026-09-16). Functional impact: none. Recorded in case the client is later
changed to prefetch tokens from a fixed URL instead.

## Other open items

- Non-empty `list-transports` tree: only an empty-tree fixture exists (the
  capture user owns no transports); `tasks[]` nesting and the
  `status`/`status_text` mapping need a populated tree fixture.
- ECC 6 / older-release shapes for fields / where-used / transports /
  syntax-check still need fixtures; those parsers accept the modern shapes
  only today.
