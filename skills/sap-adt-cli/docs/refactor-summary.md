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
| 6 — verification | `f2707a3` | full DEV three-way comparison, contract checker in CI, current-exit baseline | 28/28 semantic checks; contract 16 codes / 31 commands / 7 kinds / 18 declarations |
| 7.1 — run-sql | `a6f4bce` | rowNumber/UP TO meta (measured, not inferred) | DEV measured |
| 7.2–7.4 — discovery | `f7f321e` | `discovery` (kind `capabilities`), `doctor --coverage`, application/* non-narrowing | DEV discovery capture |
| 7.5 — markdown | `9394719` | `discovery --emit-markdown`, no auto-merge | offline + DEV |
| 7.6 — coverage caveat | `5e5e69d` | explicit resource-root-only boundary | docs |
| 8 — quality gates | `5ddf576`, `9ba237a` | run-unit-test (risk gates/findings) + run-atc (stable IDs, exemptions) | empty-shell/alert-only and priority-3 real; counts/priority-1-2 synthetic |
| 9.1 — profile gates | `66eb7fc` | per-profile allow_write/transport + environment; prd hard refusal; SAP_ENVIRONMENT | gate matrix tests |
| 9.2 — release | `f57128f` | newreleasejobs + TRSTATUS readback poll, `--dry-run`, RELEASE_* codes | real empty-TR release DEV400 |
| post-9.2 | `d24bc88` | server status_text; real preflight/released fixtures | fixtures |
| 10 — write protocol | `d1bf649`, `80d35ef` | first real-machine write verification: lock/PUT/unlock/activate corrected to measured protocol; create-transport CreateCorrectionRequest; facts 7→12; 403 enqueue → LOCKED_BY_OTHER; 34-command verification matrix | DEV400 write/activate/create + readback; 293 tests |
| 10 — session layer | `40495b8` | cross-process session design **rejected by evidence** (separate-process activate works; orphan locks self-heal); archived with re-trigger condition | measured; no product code |
| 10 — docs | `f42bc09` + this commit | empty-root-tree false negative; docs moved inside the skill dir; inward-only link + cross-doc number assertions in check_contract | link checker green |

Tests: **293** (2026-09-17; was 232 at batch 5). CI also runs
`python tests/check_contract.py` (18 codes / 34 commands / 8 kinds /
21 command→kind declarations).

## Twelve verified ADT protocol facts (not in SAP's public documentation)

Capture system: S/4HANA 2021 / SAP_BASIS 7.56, client 400.
Canonical copy: `../references/adt_api.md` (dated old→new table plus the
write-side "2xx ≠ completed" and read-side "empty ≠ absent" rules). These
could only be learned by probing a live system.

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
   `application/vnd.sap.adt.transportorganizertree.v1+xml` (root carries
   per-request timestamps). **An empty `tm:root` is not evidence of "no
   requests"**: on 2026-09-17 the root tree came back empty while the user
   owned a modifiable D request; per-TR GET is the positive check (see
   `known-issues.md` "empty root tree" and the read-side rule in
   `../references/adt_api.md`). 2026-09-15/17.
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
7. **Transport release + readback** — the legacy
   `POST /cts/transports/{TR}?action=release` (no verification) is replaced
   by `POST /cts/transportrequests/{TR}/newreleasejobs`
   (Accept `application/*`; response `tm:releasereports/chkrun:checkReport`,
   status `released` / `abortrelapifail`) followed by readback of
   `GET /cts/transportrequests/{TR}` (`tm:request@tm:status`, D/R; the
   organizer reports a missing request as HTTP **400**
   `ADT_TM_COMMON_EXCEPTION`, not 404). **Measured 2026-09-16 on the empty
   request ECDK944391 (target blank): release finished within the first
   2 s poll — readback returned R on `poll_attempts: 1`; CLI wall time was
   dominated by the fixed 2 s interval, not the server.** Requests with a
   pre-release ATC check or populated objects can take far longer, hence
   the 120 s timeout (60 polls); that long path is not live-verified.
8. **Object lock (enqueue)** — the documented `?method=lock` form is
   rejected: no content type → 400 `contentTypeMissing`, `application/xml`
   → 415; the correct call is `POST {object}?_action=LOCK&accessMode=MODIFY`
   with `X-sap-adt-sessiontype: stateful` and
   `Accept: application/*,application/vnd.sap.as+xml;charset=UTF-8;dataname=com.sap.adt.lock.result`,
   no body; handle in ASX `DATA/LOCK_HANDLE`. Already-held locks return 403
   `ExceptionResourceNoAccess` "… currently editing …" (classify as
   LOCKED_BY_OTHER, not AUTH_FAILED). 2026-09-16.
9. **Source PUT** — the handle is a **query** parameter
   (`?lockHandle=<handle>`, transport `?corrNr=`), not the
   `X-sap-adt-lock-handle` header / `sap-cts-request` pair the old code
   sent. 2026-09-16.
10. **Unlock / cross-process semantics** — `POST {object}?_action=UNLOCK`
    with `lockHandle` query. A 200 empty body from a foreign stateful
    context is a **silent no-op** (next LOCK still 403); release is real
    only inside the owning stateful session (same-process `finally` path
    confirmed by independent fresh-process re-lock 200, 2026-09-17) or when
    a new process replays the original cookie jar. Observed Basic-auth
    cookies: `SAP_SESSIONID_ECD_400`, `sap-contextid`, `sap-usercontext`
    (no MYSAPSSO2); orphaned enqueues also vanish on server context
    timeout. 2026-09-16.
11. **Activation** — bare `POST /activation` → 400 "Parameter method could
    not be found"; it requires `?method=activate&preauditRequested=true`.
    No lock/shared session is needed: a separate process after unlock
    activates fine. 200 empty is accepted-not-completed; confirm via
    inactiveobjects / `adtcore:version` readback. 2026-09-16.
12. **Create transport** — the `cts.transport.request+xml`
    `<cts:transportRequest>` document (category/owner/description/target)
    → 400 `ExceptionDataTypeNotFound`. Creation is an ABAP-serialized
    `CreateCorrectionRequest`: POST `/cts/transports`, CT
    `application/vnd.sap.as+xml; charset=UTF-8; dataname=com.sap.adt.CreateCorrectionRequest`,
    Accept `text/plain`, ASX body `DATA{DEVCLASS,REQUEST_TEXT,REF,OPERATION=I}`;
    the 200 text body is `/com.sap.cts/object_record/<TRKORR>` (no Location
    header). Measured with `DEVCLASS=$TMP` (local, non-releasable request)
    and REF = an object `source/main` URI; readback per-TR gives
    `tm:status="D"`. The root transportrequests tree returned empty even
    while the user owned that D request. CLI fixed 2026-09-17
    (`--package`/`--ref` required, `--category` removed); whether REF is
    truly mandatory and how real packages behave remain unverified.

## Command × real-machine verification matrix (34 commands)

**"Offline only" is not "works".** Batch 10 proved this twice: write-source
and activate were 4-for-4 protocol-wrong with all 287 offline tests green,
and create-transport carried three protocol deviations through every
release. Offline tests mock below the protocol layer; only real-machine
runs establish write-side correctness.

| Status | # | Commands |
|---|---|---|
| **Real-verified (23)** | 23 | Eighteen read-side commands via the batch-6 DEV three-way comparison (28/28) plus real fixtures: get-program/class/function-group/function/include/interface/cds-view/type-group, get-table/structure, get-type-info, get-transaction, search-object, get-package, where-used, syntax-check, run-sql, list-transports¹; `discovery` (batch 7); `write-source`, `activate` (batch 10, `d1bf649`); `create-transport` (2026-09-17, ASX shape live-200, fixed CLI request byte-identical); `release-transport` (batch 9.2 — **empty-TR path only; long timeout paths, failing reports and non-empty object trees are not live-verified**) |
| **Partially real (2)** | 2 | `run-unit-test` (empty shell + alert-only real; `testMethod` counts synthetic), `run-atc` (priority-3 real; priority 1/2/exemptions synthetic) |
| **Offline only (0)** | 0 | — (create-transport moved out of this category on 2026-09-17) |
| **N/A — local state (9)** | 9 | `status`, `configure`, `profile list/use/remove`, `credentials set/forget/status/doctor` (local config/keystore only, no SAP object protocol) |

¹ `list-transports` protocol/path is real-verified, but its empty root tree
is a false negative signal: an empty tree was returned while the user owned
a modifiable D request (2026-09-17; per-TR GET is the reliable check).
Do not conclude "no open transports" from an empty result — see
`known-issues.md` ("empty root tree").

## Methodology lesson: 287 offline tests green, write path 4-for-4 wrong

On 2026-09-16 the first ever real write-source/activate verification
showed all four write-side protocol calls wrong (facts 8–11), while all
287 offline tests stayed green. Reason: the tests mock at the
`make_adt_request` seam, and the protocol mistakes live **below** that
seam — the mock accepts whatever URL/headers/params the handler invents.
Offline tests structurally cannot detect this class of error.

This is the same blind-spot class as `doctor --coverage`: "covered"
(resource root present / unit tests pass) is not "works". Rules taken
from this:

- write-side command correctness can only be established on a real system,
  like the read-side DEV fixtures;
- never treat a write-side 2xx as completion — always add the independent
  readback (release/activate/unlock, see the top rule in
  `../references/adt_api.md`);
- when a write path has never been live-verified, say so explicitly
  rather than implying it works.

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

The authoritative engineering backlog is **§4 of `refactor-handoff.md`**
(same directory); do not keep a second list here to avoid drift. Current
three items:

1. adt_api.md consolidation (12-row fact table + modern/legacy sections
   into one canonical old→new structure);
2. declarative object-type registry replacing the `get_object_uri`
   if/elif chain;
3. `configure` silent field reset — high/security.

Discovery self-introspection (`discovery`, batch 7.2–7.4) and
`doctor --coverage` (batches 7.2–7.6) are **already done** — listed here
only so they are not scheduled again. Remaining conditional follow-ups
(usageReferences vendor content type after a Basis upgrade, populated
transport fixtures, ECC shapes, real failed-activation capture) are in
handoff §6 and `known-issues.md`.
