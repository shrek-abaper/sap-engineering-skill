# SAP ADT REST API — Quick Reference

SAP ABAP Development Tools (ADT) exposes a REST API under `/sap/bc/adt/`.
Authentication is HTTP Basic Auth with the `X-SAP-Client` header for client selection.

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
| 4 | Data preview (run-sql) | GET `freestyle?sqlCommand=…` → 405 | POST `freestyle?rowNumber=N`, `Content-Type: text/plain; charset=utf-8`, raw SQL body. **Accept must be `vnd.sap.adt.datapreview.table.v1+xml` — `application/xml` returns 406.** GET kept only as a 405 fallback | 2026-09-16 |
| 5 | Where-used | GET `/informationsystem/whereused?uri=<full URL>` → 405 | POST `/informationsystem/usageReferences?uri=<RELATIVE lower-case object URI>`; CT and Accept both `application/*`; body `usageReferenceRequest` with empty `<affectedObjects/>`; response `…usagereferences.result.v1+xml` (`referencedObject/adtObject`, optional `#start=` fragment) | 2026-09-16 |
| 6 | Package contents | Parser qualified elements as `{http://www.sap.com/abapxml}…` → always `[]` on 7.56 | Response declares the namespace only on the `asx:` prefix; payload elements (`SEU_ADT_REPOSITORY_OBJ_NODE/OBJECT_*`) have **no** namespace — match by local name | 2026-09-15 |

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

## Write Source — Lock / PUT / Unlock

Three-step flow; unlock must always run (use `finally`).

### 1. Lock

```http
POST /sap/bc/adt/{object_uri}?method=lock
X-sap-adt-sessiontype: stateful
→ Response header: com.sap.adt.lock.handle: <handle>
```

If the header is absent, fall back to parsing `<handle>` or `<lockHandle>` from the XML response body.

### 2. Write (PUT)

```http
PUT /sap/bc/adt/{object_uri}/source/main
Content-Type: text/plain; charset=utf-8
X-sap-adt-lock-handle: <handle>

[optional] ?sap-cts-request=<TRKORR>    ← assign to specific transport
```

Body: plain text ABAP source.

### 3. Unlock

```http
POST /sap/bc/adt/{object_uri}?method=unlock
X-sap-adt-lock-handle: <handle>
```

## Activation

```xml
POST /sap/bc/adt/activation
Content-Type: application/vnd.sap.adt.activation.request+xml; charset=utf-8

<?xml version="1.0" encoding="utf-8"?>
<adtcore:objectReferences xmlns:adtcore="http://www.sap.com/adt/core">
  <adtcore:objectReference adtcore:uri="{object_uri}" adtcore:name="{OBJECT_NAME}"/>
</adtcore:objectReferences>
```

Response: empty (200) = success. Non-empty XML body = activation errors — parse `severity`, `text` attributes.

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

### Release transport

```xml
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
| 403 | Missing authorization OR expired CSRF token |
| 404 | Object not found |
| 503 | ADT service not activated in SICF |

## Required Authorizations

| Operation | Authorization objects |
|---|---|
| All read operations | `S_ADT_RES`, `S_RFC` (ADT function groups) — or role `SAP_ADT_BASE` |
| `write-source`, `activate` | `S_DEVELOP` with `ACTVT=02` on relevant object types |
| `create-transport`, `release-transport` | `S_CTS_ADMI` or equivalent transport authorization |
| `list-transports` | Covered by `SAP_ADT_BASE` — no additional flag needed |
