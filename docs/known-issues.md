# Known Issues — sap-adt-cli

Issues discovered from real-machine (S/4HANA 2021 / SAP_BASIS 7.56, client
DEV) fixture capture on 2026-09-15. They are **not** fixed in the output
pipeline batch (batch 1), because each changes command output and would break
the byte-level "zero external behavior change" guarantee. Fixes are scheduled
for the per-command parser batch (batch 3), covered by the fixtures under
`skills/sap-adt-cli/tests/fixtures/`.

## 1. `get-package` always returns `[]` on modern systems (XML namespace bug)

- **Symptom**: `get-package SABP_UNIT` exits 0 with `[]` even though the
  package contains objects. Fixture: `get-package.SABP_UNIT.cli-current.json`.
- **Root cause**: `lib/handlers.py` `get_package()` looks up abapxml nodes
  under the fully-qualified namespace
  `{http://www.sap.com/abapxml}SEU_ADT_REPOSITORY_OBJ_NODE`. On 7.56 the
  response declares the namespace only on the `asx:` prefix
  (`xmlns:asx="http://www.sap.com/abapxml"`); payload elements
  (`SEU_ADT_REPOSITORY_OBJ_NODE`, `OBJECT_NAME`, ...) are in **no**
  namespace, so every `findall`/`find` misses.
  Raw response fixture: `get-package.SABP_UNIT.asxml.xml`.
- **HTTP behavior**: unaffected — POST `nodestructure` returns HTTP 200.
- **Planned fix (batch 3)**: namespace-agnostic local-name matching in the
  new `objects` parser; no HTTP change.

## 2. `get-table` / `get-structure` return DDL source, not field metadata

- **Symptom**: on 7.56 both commands return CDS-style DDL source text
  (`define table vbak { key mandt : mandt not null; ... }`) instead of the
  field-metadata XML assumed by docs/older releases.
  Fixtures: `get-table.VBAK.s4hana.xml`, `get-table.T001.s4hana.xml`,
  `get-structure.VBAKKOM.s4hana.xml`.
- **Impact on contract**: the normalized `kind=fields` shape
  `{name, type, length, decimals, is_key, not_null, description}` can only be
  partly populated from DDL: `name`, `is_key`, `not_null`, and the referenced
  type name are available; `length`, `decimals`, `description` are absent
  from the response and must be emitted as `null`.
- **Planned fix (batch 3)**: fields parser detects DDL vs metadata XML and
  normalizes both; ECC/older-release XML fixtures still to be supplied.

## 3. `get-type-info` domain lookup always 404s → silent data-element fallback

- **Symptom**: domain-like names (e.g. `MATNR18`, `CHAR10`) are returned with
  `adtcore:type="DTEL/DE"` because the domain request fails and the handler
  silently falls back to the data-element endpoint.
  Fixtures: `get-type-info.MATNR18.dtel.xml` (misclassified),
  `get-type-info.CHAR10.domain.xml` (correct `DOMA/DD` payload).
- **Root cause**: the handler calls
  `/sap/bc/adt/ddic/domains/{name}/source/main`, which does not exist on 7.56
  (HTTP 404, "No suitable resource found"). The domain metadata resource is
  `/sap/bc/adt/ddic/domains/{name}`
  (`application/vnd.sap.adt.domains.v2+xml`).
- **Planned fix (batch 3)**: use the correct domain URL; expose the fallback
  outcome explicitly as `data.resolved_as: "domain" | "dataelement"`.

## Related (endpoint-level protocol migration, batch 3, pre-authorized)

These are incompatibilities rather than the three bugs above and are tracked
with the migration work rather than here: `where-used` (legacy GET retired;
new `usageReferences` POST request body still being reverse-engineered),
`list-transports` (worklist Accept 406; new `transportrequests` tree API),
`syntax-check` (legacy endpoint 404; new `/checkruns` API).
