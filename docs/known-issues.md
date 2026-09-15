# Known Issues — sap-adt-cli

Issues discovered from real-machine (S/4HANA 2021 / SAP_BASIS 7.56, client
DEV) fixture capture on 2026-09-15.

## Resolved in batch 3 (output standardization)

1. **`get-package` always returned `[]` (abapxml namespace bug).**
   Nodestructure payload declares the abapxml namespace only on the `asx`
   prefix; payload elements have no namespace. The shared `objects` parser
   matches by local name, so `get-package SABP_UNIT` now returns its objects
   (14 on the capture system). No HTTP change.

2. **`get-table` / `get-structure` returned DDL source, not field metadata.**
   The `fields` parser normalizes the S/4 DDL shape
   (`define table/structure`) into the unified `fields[]` shape;
   `length`/`decimals`/`description` are `null` because the DDL response does
   not carry them. `--format xml` passes the raw ADT response (DDL text on
   S/4) through unchanged. The older field-metadata XML shape is still to be
   added from an ECC fixture (`ParseError` until then).

3. **`get-type-info` domain lookup always 404'd and silently fell back.**
   The domain resource is `/sap/bc/adt/ddic/domains/{name}` (v2), not
   `.../source/main`. Fallback to the data element now happens only on a
   genuine HTTP 404, and the resolved branch is explicit as
   `data.resolved_as: "domain" | "dataelement"`.

The endpoint-level protocol migrations in the same batch:
`list-transports` → `/cts/transportrequests` (transportorganizer tree),
`syntax-check` → `/checkruns` (checkObjectList/checkmessages).

## Still open

- **`where-used` is not migrated yet.** The legacy GET
  `/repository/informationsystem/whereused` returns 405 on 7.56. Its
  successor `/repository/informationsystem/usageReferences` requires POST
  with a `?uri=` query parameter and a
  `application/vnd.sap.adt.repository.usagereferences.request.v1+xml` body;
  the request root must be the singular `usageReferenceRequest`
  (plural → 400), but the correct inner object-reference structure is not
  yet known (current attempts → 500 "Error while converting object
  references"). Until then the command keeps the legacy call and its error
  envelope; it is deliberately **not** downgraded with a workaround. The
  empty-result contract (`ok:true`, `row_count:0`, exit 0) must hold once
  migrated.

- **Non-empty `list-transports` tree parsing** is implemented but only
  covered by an empty-tree fixture (the capture service user owns no
  transports). A populated transport-organizer tree fixture is needed to
  verify `tasks[]` nesting and the `status`/`status_text` mapping end to end.

- **ECC 6 / older-release response shapes** for fields/where-used/transports/
  syntax-check are still to be supplied; parsers accept the modern shapes
  only for those kinds today.
