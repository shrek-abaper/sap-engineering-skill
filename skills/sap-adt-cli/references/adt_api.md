# SAP ADT REST API — Quick Reference

SAP ABAP Development Tools (ADT) exposes a REST API under `/sap/bc/adt/`.
Authentication is HTTP Basic Auth with the `X-SAP-Client` header for client selection.

## Write-side rule: 2xx means "accepted", never "completed"

> ADT write-side endpoints generally confirm only that the **request was
> accepted**. An HTTP 2xx response is never, by itself, evidence that the
> operation finished — an independent readback is required. Three measured
> cases (S/4HANA 2021 / Basis 7.56):
>
> 1. **release** — `newreleasejobs` 200/2xx must be followed by `tm:status`
>    readback (D vs R);
> 2. **activate** — POST 200 with an empty body must be followed by checking
>    `/activation/inactiveobjects` / `adtcore:version="active"`; a 200 with
>    failure messages in the body means the activation failed;
> 3. **unlock** — `?_action=UNLOCK` returns **200 with an empty body even when
>    it released nothing** (silent no-op from a foreign stateful context);
>    only a subsequent independent `_action=LOCK` (200 vs 403) proves the
>    enqueue is gone. The object resource's `program:lockedByEditor="false"`
>    is per-session state, NOT proof that SM12 is empty.

## Authentication

Every request requires:

```text
Authorization: Basic base64(username:password)
X-SAP-Client: <client_number>
```

For POST/PUT requests, first fetch a CSRF token:

```text
GET <any ADT URL>
x-csrf-token: fetch
→ Response header: x-csrf-token: <token>

Then include in POST/PUT:
x-csrf-token: <token>
```

## Verified protocol facts — S/4HANA 2021 / SAP_BASIS 7.56

The endpoint descriptions below reflect older documentation. Verified on a
real DEV system (old value → new value; fixtures under `tests/fixtures/`):

| # | Area | Old (fails on 7.56) | New (verified) | Date |
|---|------|--------------------|-----------------|------|
| 1 | Domain metadata | GET `/ddic/domains/{n}/source/main` → 404, silently fell back to data element | GET `/ddic/domains/{n}` (`vnd.sap.adt.domains.v2+xml`); fall back to data element only on genuine 404; output carries `resolved_as` | 2026-09-15 |
| 2 | Syntax check | POST `/abapsource/syntaxcheck` → 404 | POST `/checkruns`, body root `chk:checkObjectList` with inner `chk:reporter chk:name="abapCheckRun"`, CT `…checkobjects+xml`, Accept `…checkmessages+xml`; findings at `chk:checkMessage@type/shortText`, line from `uri #start=L,C` | 2026-09-15 |
| 3 | Transports | GET `/cts/transports` Accept `…transport.worklist+xml` → 406 | GET `/cts/transportrequests`, Accept `vnd.sap.adt.transportorganizertree.v1+xml` (empty `tm:root` when the user has none) | 2026-09-15 |
| 4 | Data preview (run-sql) | GET `freestyle?sqlCommand=…` → 405 | POST `freestyle?rowNumber=N`, `Content-Type: text/plain; charset=utf-8`, raw SQL body. **Accept must be `vnd.sap.adt.datapreview.table.v1+xml` — `application/xml` returns 406.** GET kept only as a 405 fallback. The `rowNumber` parameter is the hard row cap and overrides an SQL `UP TO N ROWS` clause (verified 2026-09-16) | 2026-09-16 |
| 5 | Where-used | GET `/informationsystem/whereused?uri=<full URL>` → 405 | POST `/informationsystem/usageReferences?uri=<RELATIVE lower-case object URI>`; CT and Accept both `application/*`; body `usageReferenceRequest` with empty `<affectedObjects/>`; response `…usagereferences.result.v1+xml` (`referencedObject/adtObject`, optional `#start=` fragment). Discovery declares no `app:accept` for this collection, so `application/*` is the only workable value today — re-probe after a Basis upgrade before narrowing | 2026-09-16 |
| 6 | Package contents | Parser qualified elements as `{http://www.sap.com/abapxml}…` → always `[]` on 7.56 | Response declares the namespace only on the `asx:` prefix; payload elements (`SEU_ADT_REPOSITORY_OBJ_NODE/OBJECT_*`) have **no** namespace — match by local name | 2026-09-15 |
| 7 | Transport release | Legacy `POST /cts/transports/{TR}?action=release` (no readback) | `POST /cts/transportrequests/{TR}/newreleasejobs` (Accept `application/*`) **+ readback** `GET /cts/transportrequests/{TR}` (`tm:status` D/R); 2xx is not completion | 2026-09-16 |
| 8 | Lock (enqueue) | `POST {object}?method=lock` with only `X-sap-adt-sessiontype: stateful` → **400** `contentTypeMissing`; adding `Content-Type: application/xml` → **415** (only `…programs.programs.v2+xml` accepted); vendor type + XML body → **400** `Enter a title` (treated as create) | `POST {object}?_action=LOCK&accessMode=MODIFY`, stateful header, `Accept: application/*,application/vnd.sap.as+xml;charset=UTF-8;dataname=com.sap.adt.lock.result`, **no body**; 200 ASX with handle at `asx:values/DATA/LOCK_HANDLE` | 2026-09-16 |
| 9 | Source PUT | Handle in `X-sap-adt-lock-handle` **header**; chosen transport as `?sap-cts-request=` (this shape never worked live) | `PUT {object}/source/main?lockHandle=<handle>` plus, for a chosen request, `&corrNr=<TRKORR>`; `Content-Type: text/plain; charset=utf-8`; 200 empty | 2026-09-16 |
| 10 | Unlock (dequeue) | `POST {object}?method=unlock` with the handle header (never worked live) | `POST {object}?_action=UNLOCK&lockHandle=<urlencoded handle>`. **200 empty is not proof of release** (see write-side rule): cross-process without the original stateful cookie = silent no-op (next LOCK still 403); measured real only inside the owning stateful session (same-process `finally` path confirmed by an independent fresh-process re-lock 200) or cross-process replaying the original cookie jar | 2026-09-16/17 |
| 11 | Activation | Bare `POST /activation` (no parameters) → **400** `ExceptionParameterNotFound` "Parameter method could not be found" | `POST /sap/bc/adt/activation?method=activate&preauditRequested=true` with the same `objectReferences` body; success verified by readback (`/activation/inactiveobjects`, `adtcore:version`), not by 200 alone | 2026-09-16 |

Also verified: `/ddic/tables/{n}/source/main` and
`/ddic/structures/{n}/source/main` return CDS-style DDL
(`define table/structure`) on 7.56, not field-metadata XML;
`/ddic/tables/{n}/objectstructure` is 404 (field descriptions unavailable).

## Source Code Endpoints (Read)

| Object Type | Method | URL Pattern |
|-------------|--------|-------------|
| Program (report) | GET | `/sap/bc/adt/programs/programs/{name}/source/main` |
| Class | GET | `/sap/bc/adt/oo/classes/{name}/source/main` |
| Interface | GET | `/sap/bc/adt/oo/interfaces/{name}/source/main` |
| Function Group | GET | `/sap/bc/adt/functions/groups/{fg_name}/source/main` |
| Function Module | GET | `/sap/bc/adt/functions/groups/{fg_name}/fmodules/{fm_name}/source/main` |
| Include | GET | `/sap/bc/adt/programs/includes/{name}/source/main` |
| CDS View (DDL) | GET | `/sap/bc/adt/ddic/ddl/sources/{name}/source/main` |
| Type Group | GET | `/sap/bc/adt/typegroups/groups/{name}/source/main` |
| DDIC Table | GET | `/sap/bc/adt/ddic/tables/{name}/source/main` |
| DDIC Structure | GET | `/sap/bc/adt/ddic/structures/{name}/source/main` |
| Domain | GET | `/sap/bc/adt/ddic/domains/{name}` (legacy `…/source/main` → 404 on 7.56) |
| Data Element | GET | `/sap/bc/adt/ddic/dataelements/{name}` |

Object names must be URL-encoded. Responses are plain text (ABAP source) or XML.

## Write Source — Lock / PUT / Unlock (verified 2026-09-16, Basis 7.56)

Stateful three-step flow inside ONE stateful session; unlock must always run
(use `finally`). The stateful context is selected by
`X-sap-adt-sessiontype: stateful`; the cookies set by the server then
accompany every request of the session. Observed under HTTP Basic auth on
the capture system: `SAP_SESSIONID_ECD_400`, `sap-contextid`,
`sap-usercontext` — **no `MYSAPSSO2`**.

### 1. Lock

```http
POST /sap/bc/adt/{object_uri}?_action=LOCK&accessMode=MODIFY
X-sap-adt-sessiontype: stateful
Accept: application/*,application/vnd.sap.as+xml;charset=UTF-8;dataname=com.sap.adt.lock.result
```

No request body. Response 200 is ABAP-serialized XML; the lock handle is the
text of `asx:abap/asx:values/DATA/LOCK_HANDLE` (sibling fields `CORRNR`,
`CORRUSER`, `CORRTEXT`, `IS_LOCAL`, `SCOPE_MESSAGES`). An existing enqueue
comes back as **403 `ExceptionResourceNoAccess`** "User … is currently
editing …".

### 2. Write (PUT)

```http
PUT /sap/bc/adt/{object_uri}/source/main?lockHandle=<handle>
Content-Type: text/plain; charset=utf-8
X-sap-adt-sessiontype: stateful

# optional transport assignment: append &corrNr=<TRKORR>
```

Body: plain text ABAP source. 200 with empty body. The handle goes in the
**query string**, not a header.

### 3. Unlock

```http
POST /sap/bc/adt/{object_uri}?_action=UNLOCK&lockHandle=<urlencoded handle>
X-sap-adt-sessiontype: stateful
```

200 with empty body. Per the write-side rule, the 200 alone proves nothing;
release was confirmed by an independent `_action=LOCK` in a fresh process
returning 200 (measured 2026-09-17).

### Cross-process / crash semantics (measured 2026-09-16)

- Lock and unlock belong to the **stateful server context** identified by the
  session cookie. An `_action=UNLOCK` from a different process **without**
  the original cookie jar returns 200 empty but is a **silent no-op** — the
  next LOCK still gets 403.
- A different process replaying the **original cookie jar + handle** does
  release the enqueue (verified by a crash-lock → cookie-restore → unlock →
  fresh LOCK 200 cycle).
- An orphaned enqueue whose owning process died also disappears when the
  server stateful context times out (the SM12 entry was gone the next
  morning). There is no cheap synchronous "is it locked" probe:
  `lockedByEditor="false"` on the object resource is per-session state.

### Legacy forms (rejected by 7.56 — do not reintroduce)

- `POST {object}?method=lock` + only the stateful header → 400
  `contentTypeMissing`; with `application/xml` → 415.
- `X-sap-adt-lock-handle: <handle>` request header and `?sap-cts-request=`
  transport parameter — not honored on 7.56 (use `?lockHandle=` / `?corrNr=`).
- `POST {object}?method=unlock` with the handle header.

## Activation (verified 2026-09-16, Basis 7.56)

```xml
POST /sap/bc/adt/activation?method=activate&preauditRequested=true
Content-Type: application/vnd.sap.adt.activation.request+xml; charset=utf-8

<?xml version="1.0" encoding="UTF-8"?>
<adtcore:objectReferences xmlns:adtcore="http://www.sap.com/adt/core">
  <adtcore:objectReference adtcore:uri="{object_uri}" adtcore:name="{OBJECT_NAME}"/>
</adtcore:objectReferences>
```

The `?method=activate` parameter is mandatory — a bare POST returns 400
`ExceptionParameterNotFound`. GET on the same URL returns 405 (but still
serves as a CSRF-token fetch). Activation needs **no lock handle and no
shared stateful session**: it succeeds from a separate process after
write-source has unlocked (measured lock→write→unlock in process A, activate
in process B).

200 with an empty body = accepted and (for an empty object) activated;
**read back to confirm**: `GET /sap/bc/adt/activation/inactiveobjects`
(Accept `application/vnd.sap.adt.inactivectsobjects.v1+xml`) must not list
the object, and the object resource must carry
`adtcore:version="active"` (inactive → `"inactive"`). Non-empty failure
bodies use `chkl:messages/msg` (`type` E/A/X) and `ioc:inactiveObjects` per
the reference implementation — see `docs/known-issues.md` for the parser
gap. (The older `error/message/checkResult` shape is what the current parser
looks for; a real failed activation fixture is still needed.)

## Syntax Check (legacy — see verified facts #2)

```http
POST /sap/bc/adt/abapsource/syntaxcheck
Content-Type: application/vnd.sap.adt.abapsource.syntaxcheckresult+xml; charset=utf-8

<?xml version="1.0" encoding="utf-8"?>
<adtcore:objectReferences xmlns:adtcore="http://www.sap.com/adt/core">
  <adtcore:objectReference adtcore:uri="{object_uri}" adtcore:name="{OBJECT_NAME}"/>
</adtcore:objectReferences>
```

Response: XML with `severity` (`error`/`warning`/`info`), `text`, and `line` attributes. Empty body = no issues.

## Where-Used (legacy — see verified facts #5)

```http
GET /sap/bc/adt/repository/informationsystem/whereused
    ?uri=<full_object_url>        ← full URL including scheme+host
    &maxResults=50
Accept: application/vnd.sap.adt.repository.informationsystem.whereused+xml
```

Response: XML with `adtcore:objectReference` elements (namespace `http://www.sap.com/adt/core`), attributes: `adtcore:name`, `adtcore:type`, `adtcore:uri`.

## Open SQL Data Preview (legacy GET — see verified facts #4)

```xml
GET /sap/bc/adt/datapreview/freestyle
    ?rowNumber=<max_rows>
    &sqlCommand=<url-encoded-SELECT>
Accept: application/xml
```

Response: XML with `<column name="...">` elements containing row data. Requires `/sap/bc/adt/datapreview` activated in SICF.

Only `SELECT` is valid. DML (`INSERT`, `UPDATE`, `DELETE`, `MERGE`, `MODIFY`, `TRUNCATE`) must be blocked at the CLI layer.

## Search

```http
GET /sap/bc/adt/repository/informationsystem/search
    ?operation=quickSearch
    &query=<url-encoded-query>      ← supports * wildcard
    &maxResults=100
```

Response: XML with matching objects.

## Package Contents

```http
POST /sap/bc/adt/repository/nodestructure
     ?parent_type=DEVC/K
     &parent_name=<url-encoded-package>
     &withShortDescriptions=true
```

Response: XML. Relevant nodes:

```xml
<SEU_ADT_REPOSITORY_OBJ_NODE>
  <OBJECT_TYPE>PROG</OBJECT_TYPE>
  <OBJECT_NAME>ZMYPROGRAM</OBJECT_NAME>
  <DESCRIPTION>My Program</DESCRIPTION>
  <OBJECT_URI>/sap/bc/adt/programs/programs/ZMYPROGRAM</OBJECT_URI>
</SEU_ADT_REPOSITORY_OBJ_NODE>
```

## Transaction Properties

```http
GET /sap/bc/adt/repository/informationsystem/objectproperties/values
    ?uri=%2Fsap%2Fbc%2Fadt%2Fvit%2Fwb%2Fobject_type%2Ftrant%2Fobject_name%2F{tx_name}
    &facet=package
    &facet=appl
```

## Transport Requests

### List transports (legacy — see verified facts #3)

```xml
GET /sap/bc/adt/cts/transports
    ?user=<username>
    &target=
    &category=Workbench
Accept: application/vnd.sap.cts.transport.worklist+xml; charset=utf-8
```

Response: XML with transport work items. Parse `TRKORR`, `AS4TEXT` (description), `TRSTATUS` (`D`=open, `R`=released), `AS4USER` (owner).

### Create transport

```http
POST /sap/bc/adt/cts/transports
Content-Type: application/vnd.sap.cts.transport.request+xml; charset=utf-8

<?xml version="1.0" encoding="utf-8"?>
<cts:transportRequest xmlns:cts="http://www.sap.com/cts">
  <cts:attributes>
    <cts:attribute name="category"    value="Workbench"/>
    <cts:attribute name="owner"       value="{username}"/>
    <cts:attribute name="description" value="{description}"/>
    <cts:attribute name="target"      value=""/>
  </cts:attributes>
</cts:transportRequest>
```

Response: `Location` header contains the new transport URI; extract the last path segment as `TRKORR`.
All attribute values must be XML-escaped before interpolation.

### Release transport (modern)

```http
POST /sap/bc/adt/cts/transportrequests/{TRKORR}/newreleasejobs
Accept: application/*
```

Response `tm:root/tm:releasereports/chkrun:checkReport` with
`chkrun:status="released"` or `"abortrelapifail"` (pre-release check failed).
Readback: `GET /cts/transportrequests/{TRKORR}`
(`vnd.sap.adt.transportorganizer.v1+xml`, `tm:request@tm:status`, D/R);
CLI polls 2s/120s and emits `RELEASE_UNVERIFIED` (unknown final state — do
not re-release, verify in SE09/SE10) or `RELEASE_REJECTED` (still D).

### Release transport (legacy)

```http
POST /sap/bc/adt/cts/transports/{TRKORR}?action=release
```

Response: 200 = released. Irreversible.

## SICF Service Activation

Activate in transaction `SICF` before use:

| Service path | Required for |
|---|---|
| `/sap/bc/adt` | All ADT endpoints |
| `/sap/bc/adt/datapreview` | `run-sql` (Open SQL Data Preview) |

## Common HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 401 | Wrong credentials |
| 403 | Missing authorization; expired CSRF token (body mentions `csrf`); **or object already enqueued** (`ExceptionResourceNoAccess` "is currently editing") on `_action=LOCK` |
| 404 | Object not found |
| 405 | Method not supported (e.g. GET on `/activation`) — response headers can still carry a fresh CSRF token |
| 415 | Unsupported media type — the error body names the accepted vendor type (e.g. `…programs.programs.v2+xml`) |
| 503 | ADT service not activated in SICF |

## Required Authorizations

| Operation | Authorization objects |
|---|---|
| All read operations | `S_ADT_RES`, `S_RFC` (ADT function groups) — or role `SAP_ADT_BASE` |
| `write-source`, `activate` | `S_DEVELOP` with `ACTVT=02` on relevant object types |
| `create-transport`, `release-transport` | `S_CTS_ADMI` or equivalent transport authorization |
| `list-transports` | Covered by `SAP_ADT_BASE` — no additional flag needed |
