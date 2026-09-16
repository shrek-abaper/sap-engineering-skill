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
| `where-used` | GET `/informationsystem/whereused?uri=...` → **405** | **open — not migrated** | successor: POST `/informationsystem/usageReferences?uri=...` (request body not yet fully determined; see below) | 2026-09-16 |

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

## where-used: usageReferences request body (open)

POST-only endpoint confirmed (GET → 405). Layered attempts on 2026-09-16:

1. Singular root `<usagereferences:usageReferenceRequest>` with empty
   `<affectedObjects/>` (full ADT resource uri in `?uri=`) → **500** "Error
   while converting object references".
2. Same body, `?uri=` as a VIT uri (`/vit/wb/object_type/clas/object_name/...`)
   → **500** same error.
3. `affectedObjects/<usagereferences:affectedObject …>` → **400** "System
   expected the element `{http://www.sap.com/adt/core}objectReference`".
4. `affectedObjects/<adtcore:objectReference uri name type="CLAS/OC">` with
   full resource uri in `?uri=` → structure accepted, but again **500**
   "Error while converting object references".

So the envelope/element names are known but the accepted identity of the
target object (query-`uri` form vs. body reference; resource uri vs. VIT uri)
is not. The command intentionally stays on the legacy call; no workaround or
endpoint downgrade was introduced. Needs the exact request body (or a
populated example) before migration. Empty results must remain
`ok:true,row_count:0,exit 0` afterwards.

## Other open items

- Non-empty `list-transports` tree: only an empty-tree fixture exists (the
  capture user owns no transports); `tasks[]` nesting and the
  `status`/`status_text` mapping need a populated tree fixture.
- ECC 6 / older-release shapes for fields / where-used / transports /
  syntax-check still need fixtures; those parsers accept the modern shapes
  only today.
