# Output-standardization refactor — summary

Refactor scope: replace per-command raw/XML/JSON output with one envelope,
pure parsers, a closed error taxonomy with tiered exit codes, and migration
to the S/4HANA 2021 (SAP_BASIS 7.56) ADT endpoints. Verified against a real
DEV system with read-only calls and an offline golden test suite.

## Batches and commits

| Batch | Commit | What | Verification |
|---|---|---|---|
| 0 — fixtures | `021e3ed` | Sanitized S/4 DEV captures, `sanitize.py`, `raw/` gitignored | host/user/TR/business-name grep audit; byte-level baseline |
| 1 — pipeline | `f2b947e` | `lib/output.py` Envelope/render, `--format`/`SAP_ADT_FORMAT`; all commands still `kind=raw` | byte-identical DEV rerun vs baseline; 158 tests |
| 2 — parsers | `0aee386` | `lib/parsers/` seven pure `parse(bytes)->dict` modules + goldens | 12 offline tests, AST purity guard, golden pairs |
| 3 — wiring | `7f780a7` | commands emit kinds; protocol migrations (package namespace, syntax, transports, domain, type info); source stays verbatim text | DEV per-command json/text/xml; source redirect byte-identical |
| 3.5 — POST/DDL | `0f50149` | run-sql POST body; DDL built-in lengths + `meta.unparsed_types`; description key omitted (no objectstructure resource) | DEV + REPOSRC builtin fixture |
| 3.6 — where-used | `1af2d63` | POST `usageReferences` per abap-adt-api reference; optional `usage_line`/`usage_uri` | DEV 200, 939 results; trimmed SAP-only committed fixture |
| 4a — error enum | `cf879fb` | 16-code closed set, `EXIT_CODE_MAP`, single `classify()` | 20 table-driven tests incl. real error fixtures |
| 4b — exit tiers | `04980f5` | JSON error envelopes on stderr; exits 0/1/2/3/4; gates behavior unchanged; USER_ABORTED no longer exit 0 | 14 CLI tier tests; live gate verification before any HTTP |
| 5.0 — configure | `3932175` | flagged non-interactive configure uses envelopes (selection by flags, not TTY); docstrings to kind language | 2 tests, sandbox-HOME live check |
| 5 — docs | `15ad32a` | SKILL.md 522→118 lines; references split; adt_api verified facts; markdownlint clean | contract check; `tests/check_contract.py` |
| 6 — verification | this batch | full DEV three-way comparison, contract checker in CI, current-exit baseline | 28/28 semantic checks; contract 16 codes / 31 commands / 7 kinds / 18 declarations |

Tests: 232 at batch 5 (148 legacy + new). CI also runs
`python tests/check_contract.py`.

## Six verified ADT protocol facts (not in SAP's public documentation)

Capture system: S/4HANA 2021 / SAP_BASIS 7.56, client 400.
Canonical copy: `skills/sap-adt-cli/references/adt_api.md` (with dated
old→new table). These could only be learned by probing a live system.

1. **Domain metadata** — `/ddic/domains/{n}/source/main` is 404; the
   resource is `/ddic/domains/{n}` (`application/vnd.sap.adt.domains.v2+xml`,
   DOMA/DD). Verified 2026-09-15.
2. **Syntax check** — `/abapsource/syntaxcheck` is 404; use POST
   `/checkruns` with `chk:checkObjectList` containing
   `<chk:reporter chk:name="abapCheckRun"/>`, Content-Type
   `…checkobjects+xml`, Accept `…checkmessages+xml`; findings are
   `chk:checkMessage` with `type`/`shortText` and a `#start=line,col`
   fragment. 2026-09-15.
3. **Transport list** — `/cts/transports` worklist Accept returns 406;
   use GET `/cts/transportrequests` with
   `application/vnd.sap.adt.transportorganizertree.v1+xml` (an empty
   `tm:root` for a user with no requests; root carries per-request
   timestamps). 2026-09-15.
4. **Data preview** — GET `freestyle?sqlCommand=` is 405; POST
   `freestyle?rowNumber=N`, `Content-Type: text/plain; charset=utf-8`,
   raw SQL body. Accept **must** be
   `application/vnd.sap.adt.datapreview.table.v1+xml` (`application/xml`
   is 406). `rowNumber` limits rows regardless of SQL `UP TO`. 2026-09-16.
5. **Where-used** — GET `informationsystem/whereused` is 405; use POST
   `informationsystem/usageReferences?uri=<RELATIVE lower-case object
   URI>` with Content-Type **and** Accept both `application/*` and a body
   of `usageReferenceRequest` with an **empty** `<affectedObjects/>`
   (vendor `…request.v1+xml` content types cause 500 "converting object
   references"; a full URL in `?uri=` also 500s). Response
   `…usagereferences.result.v1+xml`, 939 results for
   CL_GUI_FRONTEND_SERVICES; non-existent object is 200
   `numberOfResults=0`. **The discovery document (2026-09-16) declares no
   `app:accept` for this collection, so `application/*` is currently the
   only workable value and cannot be narrowed to an explicit vendor
   version; re-probe after a Basis upgrade** (the output contract checker
   intentionally does not validate this — there is no declared source to
   check against). 2026-09-16.
6. **Package nodestructure** — on 7.56 the abapxml namespace is declared
   only on the `asx:` prefix; payload elements
   (`SEU_ADT_REPOSITORY_OBJ_NODE`/`OBJECT_*`) carry no namespace. Matching
   fully-qualified `{http://www.sap.com/abapxml}…` yields an empty list;
   local-name matching is required. The same DDL point:
   `/ddic/{tables,structures}/{n}/source/main` returns CDS-style DDL, and
   `/ddic/tables/{n}/objectstructure` is 404. 2026-09-15.

## Coverage matrix limitations (doctor --coverage)

"covered & available" is **not** "command verified working". Discovery lists
resource roots only — it has no sub-paths, HTTP methods, or required content
types. It can reveal a *missing root* (e.g. `/abapsource/syntaxcheck` gone)
but cannot reveal three of the four deviations found during this refactor:

1. sub-path changes (`/cts/transports` → `/cts/transportrequests`);
2. method requirements (run-sql and where-used are POST, their GET ancestors
   return 405);
3. content-type requirements (run-sql vendor Accept, where-used
   `application/*`).

Only real-machine fixture regression (the `tests/fixtures` + golden suite)
catches those. Read the coverage matrix as "resource present", and rely on
the offline/DEV fixtures for protocol correctness.

## Known volatile fields (normalized in committed fixtures)

Byte-level golden/XML regression breaks on fields the server regenerates
per call. They are normalized (fixed placeholders, not random values) by
`tests/fixtures/sanitize.py`:

- transport organizer `tm:root` `createdAt`/`changedAt` (per-request timestamps);
- data preview `<queryExecutionTime>`;
- ATC worklist `id`/`timestamp`/`worklistTimestamp`, 32-hex worklist and
  finding GUIDs, finding `/index/<n>`, and `author`/`processor`/`lastChangedBy`
  (→ `DEVELOPER`);
- where-used absolute service-root entries and the empty-result system ID.

## Known follow-ups (not bugs)

- **ATC quickfixes**: `atcfinding:quickfixes` exposes `manual`/`automatic`/
  `pseudo` booleans valuable for auto-fix workflows; not implemented in
  `run-atc` yet.

- **usageReferences content type is `application/*`** (per the reference
  implementation). After the discovery-completeness pass it should be
  narrowed to an explicit vendor version once a content-negotiation probe
  shows the server accepting it; document which release first required it.
- **`meta.unparsed_types`**: S/4 DDL uses element-reference types whose
  length/decimals are not in the response — 22 such references for T001,
  surfaced verbatim in `meta.unparsed_types` rather than guessed. Built-in
  forms (`abap.char(18)`, `abap.dec(13,2)`, `abap.rawstring(0)`) do
  populate length/decimals.
- **`fields.length/decimals = null` for data-element references is correct
  behavior**, not a parser gap; field `description` is intentionally
  absent (no objectstructure resource on 7.56).
- Non-empty transport tree `tasks[]` nesting is implemented but only
  covered by an empty-tree fixture; needs a populated capture.
- ECC/older-release response shapes (field-metadata XML, legacy worklist
  and syntax-check payloads) still need fixtures; fallbacks are in place
  but untested against real older systems.

## Next steps

1. **Discovery self-introspection** — drive a coverage report from
   `/sap/bc/adt/discovery` and `/compatibility/graph`: which resources the
   connected system actually exposes (incl. an explicit
   usageReferences content type and ATC/ABAP Unit reporters).
2. **`doctor --coverage`** — command × endpoint support matrix for the
   active system (e.g. "fields.description unavailable", transport tree
   empty/non-empty), using the same discovery data.
3. Then candidates: ATC findings and unit-test runs (checkrun reporters
   beyond `abapCheckRun`), populated transport fixtures, ECC shape goldens.
