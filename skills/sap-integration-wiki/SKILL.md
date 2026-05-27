---
name: sap-integration-wiki
description: >
  Comprehensive integration guide for connecting external systems (Java, Python, .NET,
  Node.js, low-code platforms, etc.) to SAP (ECC, S/4HANA On-Premise, S/4HANA Cloud).
  Covers OData V2/V4, RFC/JCo, SOAP over HTTP RFC (no-JCo RFC calls via standard HTTPS),
  IDoc/PI-PO, BAPI, RAP REST APIs, BTP Integration Suite, SAP Event Mesh, FI-AA asset
  accounting, AR/AP open items, and Financial Shared Service Center (FSSC) integration
  patterns (Kingdee/金蝶 ↔ SAP, SAP Central Finance CFIN) with scenario-driven
  recommendations, working code examples, payload samples, and error troubleshooting.
  Activate this skill whenever someone asks how to integrate with SAP, call a SAP API,
  create or read SAP data (purchase orders, inventory, sales orders, financial documents,
  AR/AP open items, asset accounting, material master, business partner, production orders)
  from outside SAP, configure JCo or RFC, call SAP BAPI without JCo, use SOAP to call SAP
  RFC, call SAP from Python/Node.js/Go without installing SAP libraries, handle SAP IDoc
  messages, use BTP Cloud Integration or iFlow, set up Communication Arrangements for
  S/4HANA Cloud, troubleshoot SAP HTTP 400/401/403 errors, implement retry or idempotency
  for SAP calls, build a financial shared service center on SAP, connect Kingdee/金蝶/用友
  to SAP, replicate financial documents into SAP Central Finance (CFIN), or says things
  like "connect to SAP", "get data from SAP", "SAP keeps returning 401", "how do I call
  BAPI from Java", "how do I call SAP RFC from Python", "call SAP without JCo",
  "SAP SOAP endpoint", "/sap/bc/soap/rfc", "SAP OData not working",
  "CSRF token validation failed", "IDoc status 51", "BAPI_PO_CREATE1",
  "API_PURCHASEORDER_PROCESS_SRV", "JCo connection", "RFC destination", "BTP iFlow",
  "Cloud Connector", "SAP Event Mesh", "Communication Arrangement",
  "BAPI_FIXEDASSET_GETLIST", "BAPI_ASSET_ACQUISITION_POST", "CFIN OData V4",
  "API_CFinRpldSupplierInvoice", "财务共享中心" — even when the user does not say "SAP"
  and just describes the problem symptomatically.
---

# SAP Integration Wiki

This skill routes integration questions to the right reference based on your context.
Before loading any reference file, ask the following if not already clear from the
user's message:

## Clarifying questions (ask only what is unknown)

1. **SAP version**: ECC 6.0 / S/4HANA On-Premise / S/4HANA Cloud Public Edition / S/4HANA Cloud Private Edition?
2. **Integration direction**: External → SAP (write/trigger) / SAP → External (event/push) / Bidirectional / Read-only query?
3. **Latency requirement**: Synchronous (real-time response needed) / Asynchronous (fire-and-forget or queue)?
4. **Business object**: Purchase Order / Sales Order / Inventory/Stock / Financial Document / Material Master / Business Partner / Production Order / BOM / Other?
5. **Consumer technology**: Java/JVM / Python / .NET / Node.js / Low-code (Zapier, Power Automate) / Other?

---

## Routing logic

After clarifying, follow this decision tree to pick the right reference files:

### Step 1: Pick the scenario file

Read the relevant file from `references/scenarios/` based on the business object:

| Business Object | File |
|---|---|
| Purchase Order (create, read, change, approve) | `references/scenarios/mm-po.md` |
| Inventory / Stock query or reservation | `references/scenarios/mm-stock.md` |
| Sales Order (create, track, confirm) | `references/scenarios/sd-order.md` |
| Financial Document (post GL, read FI docs) | `references/scenarios/fi-doc.md` |
| AR / AP open items, supplier invoice, payment, down payment | `references/scenarios/fi-ar-ap.md` |
| Fixed Asset (read register, acquisition, retirement, transfer) | `references/scenarios/fi-asset.md` |
| Financial Shared Service Center (FSSC) — Kingdee↔SAP, CFIN | `references/scenarios/fi-fssc.md` |
| Material Master / Business Partner / Org Data (cost center, plant) | `references/scenarios/master-data.md` |
| Production Order / BOM / Goods Movement (261/101) / MRP | `references/scenarios/pp-production.md` |

**Always read the scenario file first** before reading any tech file.
The scenario file specifies which integration technology to recommend per version.

### Step 2: Pick the technology file

Read the relevant file from `references/tech/` based on the recommended approach from Step 1:

| Technology | File | Use when |
|---|---|---|
| OData REST V2/V4 | `references/tech/odata.md` | S/4HANA On-Prem or Cloud, standard scenario, HTTP-native client |
| RFC / JCo (Java remote function call) | `references/tech/rfc-jco.md` | ECC (primary), S/4 when no OData exists, bulk operations, Java-only |
| SOAP over HTTP RFC (no JCo) | `references/tech/soap-rfc-http.md` | Call any RFC-FM from non-JVM runtime via HTTPS — Python, Node.js, Go, curl; ECC or S/4 On-Prem |
| IDoc / SAP PI-PO | `references/tech/idoc-pi.md` | Async integration, EDI, partner/supplier message exchange |
| BAPI or RAP | `references/tech/bapi-rap.md` | ECC BAPIs, S/4HANA RAP OData V4 services, decision on which to use |
| Authentication (any technology) | `references/tech/auth.md` | Auth failures, first-time setup, OAuth2, SSL/TLS, ICF activation |
| BTP Integration Suite / iFlow / Cloud Connector / Event Mesh | `references/tech/btp-cloud-integration.md` | BTP-mediated integration, S/4HANA Cloud + BTP, Event Mesh consumers, Communication Arrangements |
| Retry / idempotency / security / monitoring / testing | `references/tech/best-practices.md` | Production hardening, error classification, structured logging, connection pooling, CI patterns |

### Step 3: If there is an error or failure

Read `references/troubleshoot/` based on symptom:

| Symptom | File |
|---|---|
| HTTP 4xx / 5xx from OData endpoint | `references/troubleshoot/odata-errors.md` |
| Login failures / token issues / CSRF errors | `references/troubleshoot/auth-errors.md` |
| IDoc stuck / status 51 / port not configured | `references/troubleshoot/idoc-errors.md` |
| Behavior differs between SAP versions | `references/troubleshoot/version-diff.md` |

---

## Quick technology decision matrix

Use this when the user has not specified a technology preference:

| SAP Version | Scenario | Recommended | Fallback |
|---|---|---|---|
| S/4HANA On-Prem 2020+ | Create/Read PO | OData V2 `API_PURCHASEORDER_PROCESS_SRV` | JCo + `BAPI_PO_CREATE1` |
| S/4HANA On-Prem 2023+ | Create/Read PO | OData V4 `API_PURCHASEORDER` (if released) | OData V2 |
| ECC 6.0 | Create/Read PO | JCo + `BAPI_PO_CREATE1` | IDoc `ORDERS` |
| ECC 6.0 (non-JVM client) | Call any RFC-FM without JCo | SOAP over HTTP (`/sap/bc/soap/rfc`) | Java JCo microservice proxy |
| S/4HANA Cloud Public | Any | OData V4 / RAP | None (RFC unavailable externally) |
| Any version | Stock query (real-time) | OData `API_MATERIAL_STOCK_SRV` | `BAPI_MATERIAL_STOCK_REQ_LIST` |
| Any version | FI posting | JCo + `BAPI_ACC_DOCUMENT_POST` | (no standard OData for posting) |
| S/4HANA On-Prem 1809+ | Query AR/AP open items | OData V2 `API_OPLACCTGDOCITEMCUBE_SRV` | JCo `BAPI_AR_ACC_GETOPENITEMS` / `BAPI_AP_ACC_GETOPENITEMS` |
| ECC 6.0 | Query AR/AP open items | JCo `BAPI_AR_ACC_GETOPENITEMS` / `BAPI_AP_ACC_GETOPENITEMS` | — |
| S/4HANA On-Prem 1809+ | Create supplier invoice | OData V2 `API_SUPPLIERINVOICE_PROCESS_SRV` | JCo `BAPI_INCOMINGINVOICE_CREATE` |
| Any version | Read fixed asset list/values | JCo `BAPI_FIXEDASSET_GETLIST` | — |
| Any version | Post asset acquisition/retirement/transfer | JCo `BAPI_ASSET_ACQUISITION_POST` / `_RETIREMENT_POST` / `_TRANSFER_POST` (always CHECK first) | — |
| S/4HANA Cloud | Fixed asset operations | OData V4 `CE_FIXEDASSET_0001` / `OP_FIXEDASSETACQUISITION_0001` (Comm. Arr. SAP_COM_0510) | — |
| S/4HANA CFIN | Post from non-SAP (Kingdee) to Central Finance | OData V4 `API_CFinRpldSupplierInvoice` / `API_CFinRpldBillingDocument` (Comm. Arr. SAP_COM_0453) | BTP iFlow + CFIN |
| Any version | Async supplier EDI | IDoc via PI/PO | File-based integration |
| S/4HANA On-Prem | Read Material Master | OData V2 `API_PRODUCT_SRV` | JCo + `BAPI_MATERIAL_GET_DETAIL` |
| S/4HANA On-Prem | Create/Change Material | JCo + `BAPI_MATERIAL_SAVEDATA` | IDoc `MATMAS05` |
| S/4HANA On-Prem 2020+ | Business Partner (Customer/Vendor) | OData V2 `API_BUSINESS_PARTNER` | JCo + `BAPI_BUPA_CREATE_FROM_DATA` |
| ECC 6.0 | Business Partner / Customer / Vendor | JCo + `BAPI_CUSTOMER_CREATEFROMDATA1` / `BAPI_VENDOR_CREATE` | IDoc `DEBMAS`/`CREMAS` |
| S/4HANA On-Prem | Production Order (create/change) | OData V2 `API_PP_ORDERS_SRV` | JCo + `BAPI_PRODORD_CREATE` |
| Any version | Goods Movement (261/101/etc.) | JCo + `BAPI_GOODSMVT_CREATE` | OData `API_MATERIAL_DOCUMENT_SRV` (S/4) |
| Any version | Production Order Confirmation | JCo + `BAPI_PRODORDCONF_CREATE_TT` | IDoc `LOIPRO` |
| Any | BTP-mediated integration to S/4HANA Cloud | BTP Integration Suite iFlow + Communication Arrangement | N/A |
| Any | Event-driven / decoupled async | SAP Event Mesh (BTP) | IDoc via PI/PO |

---

## Scripts and assets

Point users to these runnable artifacts when they need working code or templates:

| Need | Resource |
|---|---|
| Generate Postman Collection for any OData service | `scripts/gen-odata-postman.js` |
| Generate JCo `.jcoDestination` properties file | `scripts/gen-jco-config.py` |
| Generate IDoc XML skeleton for any message type | `scripts/gen-idoc-template.py` |
| PO creation payload (OData V2 POST body) | `assets/payloads/po-create.json` |
| PO item quantity update (PATCH body) | `assets/payloads/po-update.json` |
| IDoc ORDERS05 XML example | `assets/payloads/idoc-orders05.xml` |
| OAuth2 config template for S/4HANA On-Premise | `assets/configs/oauth-template.json` |
| JCo connection properties template (all properties) | `assets/configs/jco-props.template` |

---

## Response format

When answering an integration question, always structure the response as:

1. **Recommended approach** — one sentence naming the technology and why it fits the user's version and scenario
2. **Prerequisites** — what must be configured on the SAP side first (user roles, service activation, RFC destination, partner profile, etc.)
3. **Implementation steps** — numbered list with working code snippets (curl, Java, Python as appropriate to the user's tech stack)
4. **Common pitfalls** — 2–3 things that typically go wrong and exactly how to avoid or fix them
5. **Reference** — link to SAP API Business Hub or SAP Help Portal page when available

---

## Important SAP concepts for non-SAP developers

- **CSRF token**: SAP OData services require a two-step process for mutating operations (POST/PATCH/DELETE). First GET to fetch the token, then include it in all write calls. Token is tied to a session cookie.
- **BAPI_TRANSACTION_COMMIT**: Every write BAPI call in SAP must be followed by an explicit `BAPI_TRANSACTION_COMMIT` call, or the changes will be rolled back. This is a hard requirement, not optional.
- **OData $batch**: SAP OData supports `$batch` for grouping multiple operations, but has strict ordering and boundary requirements.
- **SAP system number (SYSNR)**: A two-digit instance number (e.g., `00`), not the host port. Do not confuse with port 3300+SYSNR.
- **Client**: SAP is multi-tenanted within a single system. Always specify the client (e.g., `100`, `800`) in every connection.
- **ICF node**: SAP Internet Communication Framework. OData services are only reachable if the corresponding ICF node is activated. Transaction: `SICF`.
- **SOAP over HTTP RFC**: SAP exposes all RFC-enabled function modules via a standard SOAP endpoint at `/sap/bc/soap/rfc`. No SAP-specific client library is required — any HTTP library works. The ICF node for this path must be activated in `SICF`. Use this when JCo is not practical (non-JVM runtimes, containerised workloads, rapid prototyping). Does not support IDoc, tRFC, or qRFC.
