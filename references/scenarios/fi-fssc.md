# Financial Shared Service Center (FSSC) — SAP Integration

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Pattern A: Direct API Integration](#2-pattern-a-direct-api-integration)
3. [Pattern B: BTP-Mediated Integration](#3-pattern-b-btp-mediated-integration)
4. [Pattern C: SAP Central Finance (CFIN)](#4-pattern-c-sap-central-finance-cfin)
5. [Kingdee ↔ SAP Data Mapping by Domain](#5-kingdee--sap-data-mapping-by-domain)
6. [SAP API Catalog for FSSC Use Cases](#6-sap-api-catalog-for-fssc-use-cases)
7. [Implementation Checklist](#7-implementation-checklist)
8. [Common Pitfalls](#8-common-pitfalls)
9. [ECC 6.0 Architecture Constraints](#9-ecc-60-architecture-constraints)

---

## 1. Architecture Overview

A **Financial Shared Service Center (FSSC)** is an organizational model where financial processing functions (AP, AR, GL, asset accounting, tax, etc.) are centralized in a single service unit that serves multiple business units. In China, many large enterprises run the FSSC on platforms like **Kingdee Cloud (金蝶云·星空 / 苍穹)** or **Yonyou NC** while retaining **SAP S/4HANA or ECC** as the upstream operational system.

The FSSC integration problem has three layers:

```
Business Units / Entities
         │ transactions
         ▼
  FSSC Platform (e.g., Kingdee)   ◄──── Primary system of record for shared finance
         │
   ┌─────┴──────┐
   │  SAP ERP   │   ◄──── Source of: procurement, inventory, production, invoicing
   │ (S/4HANA   │   ◄──── Target of: FI document postings created by FSSC
   │  or ECC)   │
   └────────────┘
```

### Three Integration Patterns

| Pattern | Description | Best for |
|---|---|---|
| **A — Direct API** | FSSC calls SAP OData/JCo directly over the network | On-Premise SAP, simple topology, small team |
| **B — BTP-Mediated** | BTP Integration Suite (iFlow) sits between FSSC and SAP | Hybrid cloud, S/4HANA Cloud, complex routing, protocol translation |
| **C — Central Finance** | SAP CFIN replicates source-system documents into a central SAP system | Multi-ERP consolidation, real-time financial reporting, regulatory compliance |

Each pattern is not mutually exclusive. Large enterprises commonly combine A (for simple reads) and B or C (for cross-entity consolidation or cloud deployments).

---

## 2. Pattern A: Direct API Integration

### Architecture

```
Kingdee / FSSC Platform
│
├── Read flows (scheduled or on-demand)
│   ├── GET /API_OPLACCTGDOCITEMCUBE_SRV  → AR/AP open items
│   ├── GET /API_BUSINESS_PARTNER         → Supplier/customer master
│   ├── GET /API_COMPANYCODE_SRV          → Company codes
│   └── JCo BAPI_FIXEDASSET_GETLIST       → Asset register
│
└── Write flows (real-time or batch)
    ├── JCo BAPI_ACC_DOCUMENT_POST        → GL / AP / AR journal entries
    ├── OData POST API_SUPPLIERINVOICE    → Supplier invoices (S/4 1809+)
    └── JCo BAPI_ASSET_ACQUISITION_POST  → Asset capitalizations
```

### Network requirements

- SAP application server must be reachable from the FSSC platform network
- RFC gateway port: `33xx` (where xx = system number, e.g., `3300` for SYSNR=00)
- OData/HTTP port: `44300` (HTTPS) or `8000` (HTTP — not recommended for production)
- SAP Web Dispatcher is strongly recommended in front of application servers
- For S/4HANA Cloud: requires BTP Cloud Connector (Pattern B); direct HTTPS access is not possible from on-premise networks without Cloud Connector

### SAP-side prerequisites

| Component | Transaction / Config | Purpose |
|---|---|---|
| RFC user | `SU01` | Technical user with `S_RFC` authorization, password never expires |
| OData services activated | `SOAMANAGER` or `/IWFND/MAINT_SERVICE` | Activate each OData service before first call |
| ICF nodes active | `SICF` | HTTP services for OData reachable |
| Communication system | `SM59` | Test RFC destination from SAP side |
| Firewall rules | Network team | Open ports 33xx (RFC) and 443/44300 (HTTPS) |

### Authentication recommendations

- **OData**: Basic Auth over HTTPS for on-premise; OAuth2 Client Credentials for S/4HANA Cloud
- **JCo/RFC**: SAP logon credentials stored in `jco.client.user` / `jco.client.passwd`; use a dedicated RFC-only user with minimal authorizations
- **Credential storage**: Never hardcode. Use environment variables, a secrets manager (HashiCorp Vault, AWS Secrets Manager), or the platform's key store

### Scheduled read flow — Python polling example

```python
"""
Daily AR/AP open item sync from SAP to Kingdee FSSC.
Run as a cron job: 0 6 * * * python sync_open_items.py
"""
import os
import requests
from datetime import date, timedelta
from requests.auth import HTTPBasicAuth

SAP_HOST     = os.environ["SAP_HOST"]       # e.g. s4hana.example.com:44300
SAP_CLIENT   = os.environ["SAP_CLIENT"]     # e.g. 100
SAP_USER     = os.environ["SAP_USER"]
SAP_PASSWORD = os.environ["SAP_PASSWORD"]
COMPANY_CODE = os.environ["SAP_COMPANY_CODE"]

BASE = f"https://{SAP_HOST}/sap/opu/odata/sap/API_OPLACCTGDOCITEMCUBE_SRV"
AUTH = HTTPBasicAuth(SAP_USER, SAP_PASSWORD)
HEADERS = {"Accept": "application/json", "x-sap-client": SAP_CLIENT}

FISCAL_YEAR = str(date.today().year)


def fetch_open_items(account_type: str) -> list[dict]:
    """Fetch all open AP (K) or AR (D) items for the current fiscal year."""
    params = {
        "$filter": (
            f"CompanyCode eq '{COMPANY_CODE}' "
            f"and FiscalYear eq '{FISCAL_YEAR}' "
            f"and FinancialAccountType eq '{account_type}' "
            f"and IsCleared eq false"
        ),
        "$select": (
            "CompanyCode,AccountingDocument,FiscalYear,DocumentItemText,"
            "Supplier,Customer,PostingDate,NetDueDate,"
            "AmountInCompanyCodeCurrency,CompanyCodeCurrency,"
            "PaymentTerms,PaymentBlockingReason,ClearingAccountingDocument"
        ),
        "$orderby": "NetDueDate asc",
        "$format": "json",
    }
    url = f"{BASE}/A_OperationalAcctgDocItemCube"
    resp = requests.get(url, params=params, headers=HEADERS, auth=AUTH, timeout=60)
    resp.raise_for_status()
    return resp.json()["d"]["results"]


def sync_to_kingdee(items: list[dict], account_type: str):
    """
    Placeholder: push items to Kingdee via its Open API.
    Replace with actual Kingdee API call.
    """
    print(f"Syncing {len(items)} {'AP' if account_type == 'K' else 'AR'} items to Kingdee...")
    # kingdee_client.upsert_open_items(items)


if __name__ == "__main__":
    ap_items = fetch_open_items("K")   # vendor (payables)
    ar_items = fetch_open_items("D")   # customer (receivables)
    sync_to_kingdee(ap_items, "K")
    sync_to_kingdee(ar_items, "D")
    print("Sync complete.")
```

### Write flow — post FI document from Kingdee

See `references/scenarios/fi-ar-ap.md` for the full `BAPI_ACC_DOCUMENT_POST` pattern. The key additional constraint for FSSC use cases is **idempotency**: FSSC platforms batch-process thousands of documents per day and must ensure no duplicate postings.

**Idempotency strategy for `BAPI_ACC_DOCUMENT_POST`**:

```python
# Before posting, check if this FSSC document reference was already posted
def is_already_posted(conn, company_code: str, ref_doc_no: str, fiscal_year: str) -> bool:
    """
    Check BKPF (accounting document header) by reference document number.
    Uses BAPI_ACC_DOCUMENT_FIND or direct JCo table query.
    """
    result = conn.call(
        "RFC_READ_TABLE",
        QUERY_TABLE="BKPF",
        DELIMITER="|",
        FIELDS=[{"FIELDNAME": "BELNR"}, {"FIELDNAME": "BUKRS"}, {"FIELDNAME": "GJAHR"}],
        OPTIONS=[
            {"TEXT": f"BUKRS EQ '{company_code}'"},
            {"TEXT": f"AND GJAHR EQ '{fiscal_year}'"},
            {"TEXT": f"AND XBLNR EQ '{ref_doc_no[:16]}'"},   # XBLNR = reference doc no
        ],
    )
    return len(result["DATA"]) > 0


def post_fi_document_idempotent(conn, header, gl_items, ref_doc_no: str):
    if is_already_posted(conn, header["COMP_CODE"], ref_doc_no, header["FISC_YEAR"]):
        return {"skipped": True, "reason": "already_posted", "ref": ref_doc_no}

    return post_fi_document(conn, header, gl_items)  # your post function
```

### ECC 6.0 Variant — JCo-Only Direct Integration

> **Architecture note**: SAP ECC 6.0 does not support the OData services used in the S/4HANA polling example above (`API_OPLACCTGDOCITEMCUBE_SRV`, `API_BUSINESS_PARTNER`, `API_SUPPLIERINVOICE_PROCESS_SRV`). Replace OData calls with direct JCo BAPI calls. The Pattern A network topology remains identical — FSSC connects directly to the SAP application server with no middleware.

**ECC constraints for FSSC direct integration**:

| Constraint | Impact on FSSC design |
|---|---|
| No `API_OPLACCTGDOCITEMCUBE_SRV` | Replace with `BAPI_AP_ACC_GETOPENITEMS` / `BAPI_AR_ACC_GETOPENITEMS` |
| No `API_BUSINESS_PARTNER` | Replace with `BAPI_VENDOR_GETDETAIL` / `BAPI_CUSTOMER_GETDETAIL1` |
| No `API_SUPPLIERINVOICE_PROCESS_SRV` | Replace with `BAPI_INCOMINGINVOICE_CREATE` |
| No SAP Event Mesh | No push notifications — polling only; real-time sync is not natively supported |
| No BTP Cloud Connector (native ECC) | FSSC connects directly to RFC gateway (port `33xx` / `48xx` for SNC); BTP Cloud Connector can be separately deployed as an on-premise agent pointing at ECC if the architecture requires BTP integration |
| PI/PO is the only standard async middleware | For mediated integration (equivalent to Pattern B) on ECC, SAP Process Orchestration (PI/PO, also known as SAP Integration Suite — PO profile) is the standard path |
| `RFC_READ_TABLE` 512-byte row limit | Keep `FIELDS` list narrow on `BSEG`; for production FSSC use a custom `Z_RFC_READ_FI_ITEMS` function module with a properly typed table |

**SAP-side prerequisites (ECC)**:

| Prerequisite | Transaction / Note |
|---|---|
| RFC destination from FSSC to SAP | `SM59` — create type-3 TCP/IP RFC destination for JCo; verify with **Test Connection** |
| RFC user with minimal authorizations | `SU01` — assign profile `S_RFC`; add `F_BKPF_BUK` (company code), `F_KNA1_BUK` (customer), `F_LFA1_BUK` (vendor), `M_RECH_BUK` (LIV) |
| SAP application server reachable from FSSC host | Network — open port `33xx` (dialog) or `48xx` (SNC/secure) to SAP app server |
| `BAPI_INCOMINGINVOICE_CREATE` released for RFC | `SE37` — open FM, check **Remote-Enabled Module** checkbox; should be standard |
| Open posting periods | `OB52` — verify fiscal periods open before bulk posting runs |
| Connection pool sizing | JCo pool parameters: `jco.destination.pool_capacity = 5`, `jco.destination.peak_limit = 10` as a baseline; tune up under FSSC load |

**ECC scheduled read flow — Java JCo polling example**:

```java
/**
 * ECC AR/AP open item sync for FSSC.
 * JCo manages the underlying connection pool via JCoDestinationManager —
 * no explicit connection open/close required per call.
 * Schedule: cron every 15–60 minutes for open-item sync.
 */

public static List<Map<String, Object>> syncVendorOpenItems(
        JCoDestination dest, String companyCode,
        List<String> vendorList, String keyDate) throws JCoException {

    List<Map<String, Object>> allItems = new ArrayList<>();
    for (String vendor : vendorList) {
        String vendorPadded = String.format("%10s", vendor).replace(' ', '0');
        JCoFunction fn = dest.getRepository().getFunction("BAPI_AP_ACC_GETOPENITEMS");
        fn.getImportParameterList().setValue("COMPANYCODE", companyCode);
        fn.getImportParameterList().setValue("VENDOR",      vendorPadded);
        fn.getImportParameterList().setValue("KEYDATE",     keyDate);  // YYYYMMDD
        fn.execute(dest);

        boolean hasError = false;
        JCoTable ret = fn.getTableParameterList().getTable("RETURN");
        for (int i = 0; i < ret.getNumRows(); i++) {
            ret.setRow(i);
            String type = ret.getString("TYPE");
            if ("E".equals(type) || "A".equals(type)) {
                System.err.println("WARN: vendor " + vendor + " BAPI error: " + ret.getString("MESSAGE"));
                hasError = true;
                break;
            }
        }
        if (hasError) continue;  // log and skip — do not abort the full batch

        JCoTable items = fn.getTableParameterList().getTable("OPEN_ITEMS");
        for (int i = 0; i < items.getNumRows(); i++) {
            items.setRow(i);
            if (!items.getString("AUGBL").isBlank()) continue;  // already cleared
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("vendor",   vendorPadded);
            item.put("belnr",    items.getString("BELNR"));
            item.put("gjahr",    items.getString("GJAHR"));
            item.put("buzei",    items.getString("BUZEI"));
            item.put("blart",    items.getString("BLART"));
            item.put("budat",    items.getString("BUDAT"));
            item.put("amount",   parseDouble(items.getString("WRBTR")));
            item.put("currency", items.getString("WAERS"));
            item.put("zfbdt",    items.getString("ZFBDT"));
            item.put("zterm",    items.getString("ZTERM"));
            item.put("xblnr",    items.getString("XBLNR"));
            item.put("zlspr",    items.getString("ZLSPR"));
            allItems.add(item);
        }
    }
    return allItems;
}

public static List<Map<String, Object>> syncCustomerOpenItems(
        JCoDestination dest, String companyCode,
        List<String> customerList, String keyDate) throws JCoException {

    List<Map<String, Object>> allItems = new ArrayList<>();
    for (String customer : customerList) {
        String customerPadded = String.format("%10s", customer).replace(' ', '0');
        JCoFunction fn = dest.getRepository().getFunction("BAPI_AR_ACC_GETOPENITEMS");
        fn.getImportParameterList().setValue("COMPANYCODE", companyCode);
        fn.getImportParameterList().setValue("CUSTOMER",    customerPadded);
        fn.getImportParameterList().setValue("KEYDATE",     keyDate);
        fn.execute(dest);

        boolean hasError = false;
        JCoTable ret = fn.getTableParameterList().getTable("RETURN");
        for (int i = 0; i < ret.getNumRows(); i++) {
            ret.setRow(i);
            String type = ret.getString("TYPE");
            if ("E".equals(type) || "A".equals(type)) {
                System.err.println("WARN: customer " + customer + " BAPI error: " + ret.getString("MESSAGE"));
                hasError = true;
                break;
            }
        }
        if (hasError) continue;

        JCoTable items = fn.getTableParameterList().getTable("OPEN_ITEMS");
        for (int i = 0; i < items.getNumRows(); i++) {
            items.setRow(i);
            if (!items.getString("AUGBL").isBlank()) continue;
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("customer", customerPadded);
            item.put("belnr",    items.getString("BELNR"));
            item.put("gjahr",    items.getString("GJAHR"));
            item.put("budat",    items.getString("BUDAT"));
            item.put("amount",   parseDouble(items.getString("WRBTR")));
            item.put("currency", items.getString("WAERS"));
            item.put("zterm",    items.getString("ZTERM"));
            item.put("xblnr",    items.getString("XBLNR"));
            allItems.add(item);
        }
    }
    return allItems;
}
```

where `parseDouble` is the null-safe helper: if `s == null || s.isBlank()` return `0.0`, else `Double.parseDouble(s.trim())`.

> See `references/scenarios/fi-ar-ap.md §10` for full BAPI reference: `BAPI_VENDOR_GETDETAIL`, `BAPI_CUSTOMER_GETDETAIL1`, `BAPI_INCOMINGINVOICE_CREATE`, and `RFC_READ_TABLE` bulk extract patterns.

---

## 3. Pattern B: BTP-Mediated Integration

### Architecture

```
FSSC Platform (Kingdee / on-premise)
         │
         │  HTTPS (JSON/XML)
         ▼
┌─────────────────────────────┐
│   SAP BTP Integration Suite │
│  ┌─────────────────────────┐│
│  │        iFlow             ││  ← protocol translation, error handling,
│  │  receive → transform     ││    retry, monitoring, auditing
│  │     → route → send       ││
│  └─────────────────────────┘│
└──────────┬──────────────────┘
           │
           │  SAP Cloud Connector (secure tunnel)
           ▼
┌─────────────────────┐
│  SAP S/4HANA        │
│  (On-Prem or Cloud) │
└─────────────────────┘
```

### When to use BTP-Mediated

- SAP S/4HANA Cloud Public Edition (RFC not directly accessible; requires Cloud Connector)
- Multi-system fan-out: one FSSC event triggers updates in multiple SAP systems
- Protocol translation needed: Kingdee speaks REST/JSON; target system expects IDoc or SOAP
- Centralized error management, retry queues, and audit logs
- Compliance: need immutable message log for regulatory audit

### iFlow design for AP invoice posting

**iFlow sequence**:

```
Kingdee → [HTTP Sender Adapter] → [Groovy Script: validate & map] 
        → [Content Modifier: set headers] 
        → [Request-Reply: call BAPI via RFC adapter OR OData adapter] 
        → [Error Handling: dead letter + alert]
        → [HTTP Reply: return SAP doc number to Kingdee]
```

**iFlow design principles**:

1. **Exactly-once**: Use BTP Integration Suite's idempotency feature. Store `message_id` (Kingdee's unique ID) in the JMS correlation header. Check before forwarding.
2. **Retry with backoff**: Configure the JMS adapter with `Maximum Retries = 5`, exponential backoff starting at 30 seconds.
3. **Dead Letter Queue**: Route permanently failed messages to a separate JMS queue for manual review.
4. **Alert notification**: Configure an email alert (integration operations → alerts) for error-rate threshold breach.

**Cloud Connector configuration**:

```
Cloud Connector Admin → Backend Systems → Add System Mapping
  Type:               ABAP System (RFC/OData)
  Internal Host:      s4hana.internal.example.com
  Internal Port:      44300
  Virtual Host:       s4hana-virtual
  Principal Propagation: Enabled if using OAuth/SAML
  
For RFC (JCo):
  Internal Host:      s4hana.internal.example.com
  Internal Port:      3300   (SYSNR=00)
```

**Groovy mapping script (BTP iFlow — JSON to BAPI parameter)**:

```groovy
import groovy.json.JsonSlurper

def Message processData(Message message) {
    def body = message.getBody(String)
    def json = new JsonSlurper().parseText(body)

    // Build BAPI_ACC_DOCUMENT_POST parameter structure
    def header = [
        BUS_ACT:    "RFBU",
        USERNAME:   "BATCHPOST",
        COMP_CODE:  json.companyCode,
        DOC_DATE:   json.documentDate,
        PSTNG_DATE: json.postingDate,
        FISC_YEAR:  json.fiscalYear,
        REF_DOC_NO: json.referenceDocNo?.take(16),
        HEADER_TXT: json.headerText?.take(25),
    ]

    def items = json.lineItems.collect { li -> [
        ITEMNO_ACC:  li.itemNo.toString().padLeft(10, "0"),
        GL_ACCOUNT:  li.glAccount,
        COMP_CODE:   json.companyCode,
        ITEM_TEXT:   li.text?.take(50) ?: "",
        AMT_DOCCUR:  li.amount.toString(),
        CURRENCY:    json.currency,
        COSTCENTER:  li.costCenter ?: "",
        PROFIT_CTR:  li.profitCenter ?: "",
    ]}

    // Set as exchange properties for JCo adapter
    message.setProperty("DOC_HEADER", header)
    message.setProperty("ACCOUNTGL",  items)
    return message
}
```

### BTP event-driven write-back (SAP → Kingdee)

For real-time notification when SAP posts a clearing document (payment against open item), configure SAP Event Mesh:

```
SAP S/4HANA
  → Business Event (Accounting Document Posted)
  → SAP Event Mesh topic: sap/s4/beh/accountingdocument/v1/AccountingDocument/Posted/v1
  → BTP iFlow (Event Mesh → HTTP → Kingdee webhook)
  → Kingdee: mark receivable/payable as cleared
```

SAP Business Event enablement (S/4HANA 2020+):

```
Transaction: /IWXBE/CONFIG
Channel:     SAP_CP_XB (Enterprise Eventing to Event Mesh)
Topic namespace: sap/s4/beh/
Event: com.sap.s4.beh.accountingdocument.v1.AccountingDocument.Posted.v1
```

---

## 4. Pattern C: SAP Central Finance (CFIN)

### What is Central Finance?

SAP Central Finance (CFIN) is an SAP S/4HANA add-on that replicates financial documents from source systems (SAP or non-SAP) into a central SAP S/4HANA system in real time. The FSSC operates on the CFIN system and gets a unified, harmonized view of all financial data without migrating source systems.

```
Business Unit A          Business Unit B          Business Unit C
SAP ECC 6.0              Kingdee Cloud            Oracle EBS
    │                        │                        │
    │ SLT replication         │ CFIN OData V4           │ CFIN OData V4
    ▼                        ▼                        ▼
┌──────────────────────────────────────────────────────┐
│         SAP S/4HANA — Central Finance (CFIN)          │
│   Unified FI/CO   +   Harmonized master data mapping  │
└──────────────────────────────────────────────────────┘
                          │
                    FSSC operations
                    (AP, AR, GL, tax)
```

### Replication channels

| Source system | Replication method |
|---|---|
| SAP ECC / S/4HANA | SAP Landscape Transformation Replication Server (SLT) |
| SAP S/4HANA Cloud | SAP Integration Suite (API-based replication) |
| Non-SAP (Kingdee, Oracle, SAP B1) | **CFIN OData V4 APIs** (direct POST into CFIN) |

### CFIN OData V4 APIs for non-SAP sources

These APIs allow non-SAP systems like Kingdee to write financial documents directly into the CFIN system, which then replicates them to the appropriate subledgers.

**Communication Scenario**: `SAP_COM_0453` — Central Finance Integration

#### API_CFinRpldSupplierInvoice — Replicate supplier invoice

```bash
# Fetch CSRF token first
TOKEN=$(curl -s -u "cfinuser:password" \
  -H "x-csrf-token: fetch" -I \
  "https://cfin.example.com:44300/sap/opu/odata4/sap/api_cfinrpldsupplierinvoice/srvd/sap/cfin_rpld_supplier_invoice/0001/" \
  | grep -i "x-csrf-token:" | awk '{print $2}' | tr -d '\r')

curl -u "cfinuser:password" -X POST \
  -H "Content-Type: application/json" \
  -H "x-csrf-token: $TOKEN" \
  "https://cfin.example.com:44300/sap/opu/odata4/sap/api_cfinrpldsupplierinvoice/srvd/sap/cfin_rpld_supplier_invoice/0001/SupplierInvoice" \
  -d '{
    "SourceLedger":           "0L",
    "SourceCompanyCode":      "KDES",
    "SourceDocumentNumber":   "INV-2026-00145",
    "SourceFiscalYear":       "2026",
    "DocumentDate":           "2026-04-30",
    "PostingDate":            "2026-05-01",
    "DocumentType":           "KR",
    "DocumentHeaderText":     "AP invoice from Kingdee",
    "CompanyCode":            "1000",
    "InvoicingParty":         "VENDOR001",
    "InvoiceGrossAmount":     "113000.00",
    "DocumentCurrency":       "CNY",
    "to_SupplierInvoiceItem": {
      "results": [
        {
          "SupplierInvoiceItem":         "1",
          "DocumentItemText":            "Office supplies",
          "SupplierInvoiceItemAmount":   "100000.00",
          "TaxCode":                     "V1",
          "GLAccount":                   "550101",
          "CostCenter":                  "CC1000"
        }
      ]
    },
    "to_SupplierInvoiceTax": {
      "results": [
        {
          "TaxCode":       "V1",
          "TaxAmount":     "13000.00",
          "TaxBaseAmount": "100000.00"
        }
      ]
    }
  }'
```

#### API_CFinRpldBillingDocument — Replicate billing/AR document

Used to replicate customer billing documents (invoices, credit memos) from non-SAP source systems:

```bash
curl -u "cfinuser:password" -X POST \
  -H "Content-Type: application/json" \
  -H "x-csrf-token: $TOKEN" \
  "https://cfin.example.com:44300/sap/opu/odata4/sap/api_cfinrpldbillingdocument/srvd/sap/cfin_rpld_billing_document/0001/BillingDocument" \
  -d '{
    "SourceLedger":           "0L",
    "SourceCompanyCode":      "KDES",
    "SourceDocumentNumber":   "SO-2026-00312",
    "SourceFiscalYear":       "2026",
    "BillingDocumentDate":    "2026-04-30",
    "PostingDate":            "2026-05-01",
    "BillingDocumentType":    "F2",
    "CompanyCode":            "1000",
    "SoldToParty":            "CUST001",
    "BillingDocumentNetAmount": "200000.00",
    "TransactionCurrency":    "CNY",
    "to_BillingDocumentItem": {
      "results": [
        {
          "BillingDocumentItem":       "10",
          "BillingDocumentItemText":   "Service fee Q2",
          "BillingDocItemNetAmount":   "200000.00",
          "TaxCode":                   "A1",
          "GLAccount":                 "600101"
        }
      ]
    }
  }'
```

#### API_CFinRpldSalesDocument — Replicate sales order for CO allocation

```bash
curl -u "cfinuser:password" -X POST \
  -H "Content-Type: application/json" \
  -H "x-csrf-token: $TOKEN" \
  "https://cfin.example.com:44300/sap/opu/odata4/sap/api_cfinrpldsalesdocument/srvd/sap/cfin_rpld_sales_document/0001/SalesDocument" \
  -d '{
    "SourceLedger":        "0L",
    "SourceCompanyCode":   "KDES",
    "SourceDocumentNumber":"SD-2026-001",
    "PostingDate":         "2026-05-01",
    "DocumentCurrency":    "CNY",
    "CompanyCode":         "1000",
    "SalesOrganization":   "1000",
    "to_SalesDocumentItem": {
      "results": [
        {
          "SalesDocumentItem": "10",
          "NetAmount":         "50000.00",
          "ProfitCenter":      "PC1000",
          "CostCenter":        "CC1000"
        }
      ]
    }
  }'
```

### CFIN master data mapping

CFIN requires pre-configured **mapping rules** that translate source-system keys (Kingdee's account codes, cost center codes, entity codes) to SAP keys (GL accounts, cost centers, company codes).

| Kingdee concept | SAP CFIN mapping target | Configuration object |
|---|---|---|
| 科目 (Account code) | GL Account (`SAKNR`) | Initial Mapping + Account mapping group |
| 核算维度 (Cost object) | Cost Center / Profit Center / WBS | CO mapping group |
| 业务实体 (Entity) | Company Code (`BUKRS`) | Company code mapping |
| 供应商编码 | Supplier (`LIFNR`) | Business Partner mapping |
| 客户编码 | Customer (`KUNNR`) | Business Partner mapping |

Master data mapping is maintained in CFIN transaction `FINS_CFIN_MAPP` (or via BAdI `FINS_CFIN_MAPPING_EXTENSION` for complex rules).

---

## 5. Kingdee ↔ SAP Data Mapping by Domain

### 5.1 AP — Accounts Payable

| Kingdee field | SAP field | API / BAPI | Notes |
|---|---|---|---|
| 供应商 (vendor) | `Supplier` / `LIFNR` | `API_BUSINESS_PARTNER` | BP category `LIF`; Kingdee vendor code → SAP BP number; may not be 1:1 |
| 付款条件 (payment terms) | `PaymentTerms` / `ZTERM` | `API_BUSINESS_PARTNER → A_SupplierCompany` | e.g., `NT30`, `Z001` |
| 基准日期 (baseline date) | `BLINE_DATE` | `BAPI_ACC_DOCUMENT_POST → ACCOUNTPAYABLE` | Date from which payment terms are calculated |
| 到期日 (due date) | `NetDueDate` | Read: `API_OPLACCTGDOCITEMCUBE_SRV` | Calculated by SAP from baseline date + payment terms |
| 发票号 (invoice no.) | `XBLNR` (ref doc no.) | `BAPI_ACC_DOCUMENT_POST → DOCUMENTHEADER.REF_DOC_NO` | Used for idempotency check |
| 会计凭证号 | `BELNR` / `AccountingDocument` | Returned by `BAPI_ACC_DOCUMENT_POST` | Must be stored in Kingdee for clearing reference |
| 预付款 (advance payment) | `SP_GL_IND = 'F'` | `BAPI_ACC_DOCUMENT_POST → ACCOUNTPAYABLE` | Special G/L indicator for vendor advance |

### 5.2 AR — Accounts Receivable

| Kingdee field | SAP field | API / BAPI | Notes |
|---|---|---|---|
| 客户 (customer) | `Customer` / `KUNNR` | `API_BUSINESS_PARTNER → A_CustomerCompany` | BP category `KNA`; in S/4HANA, customer BP = `CRM000` role |
| 账期 (payment period) | `PaymentTerms` / `ZTERM` | `API_BUSINESS_PARTNER → A_CustomerCompany` | |
| 应收款余额 | `AmountInCompanyCodeCurrency` | `API_OPLACCTGDOCITEMCUBE_SRV (D)` | Filter `IsCleared eq false` |
| 客户预收款 | `SP_GL_IND = 'A'` | `BAPI_ACC_DOCUMENT_POST → ACCOUNTRECEIVABLE` | Special G/L for customer down payment |
| 票据号 (bill no.) | `ZUONR` (allocation number) | `BAPI_ACC_DOCUMENT_POST → ACCOUNTRECEIVABLE.ALLOC_NMBR` | For matching and reconciliation |

### 5.3 GL — General Ledger

| Kingdee concept | SAP equivalent | Notes |
|---|---|---|
| 科目编码 (account code) | G/L Account `SAKNR` | Chinese COA standard uses 4/6-digit codes; SAP typically 6-digit |
| 辅助核算项 (auxiliary dimension) | Cost Center / Profit Center / WBS / Internal Order | Each CO object maps to a different BAPI field in `ACCOUNTGL` |
| 账套 (accounting set) | Company Code `BUKRS` | 1-to-1 if single company; 1-to-many if FSSC serves multiple entities |
| 会计期间 (period) | Posting Period `MONAT` | Must be an open period in `OB52` |
| 科目余额 (GL balance) | `API_GL_ACCOUNT_LINE_ITEM_SRV` | S/4HANA On-Prem read service for GL line items |

### 5.4 Asset Accounting (FA)

| Kingdee field | SAP BAPI field | Notes |
|---|---|---|
| 资产编号 (asset no.) | `ASSETMAINO` (12-char zero-padded) | See `fi-asset.md` for zero-padding requirement |
| 资产原值 (gross value) | `CURRENT_APC` from `BAPI_FIXEDASSET_GETLIST` | Acquisition cost |
| 累计折旧 | `ACCUM_DEPR` | Accumulated depreciation |
| 净值 (NBV) | `NET_BOOK_VAL` | Net book value |
| 本年折旧 | `DEPR_CURR_YEAR` | Current year depreciation |
| 资本化日期 | `CAPITALDATE` from `GENERALDATA` | Capitalization date |
| 资产类别 | `ASSET_CLASS` | Maps to SAP asset class configuration |

### 5.5 Tax

| Kingdee field | SAP field | API | Notes |
|---|---|---|---|
| 税码 (tax code) | `TaxCode` | `BAPI_ACC_DOCUMENT_POST → ACCOUNTTAX` | Must match SAP tax code configuration (transaction `FTXP`) |
| 增值税率 | Derived from tax code configuration | — | Do not pass tax rate; SAP derives from tax code |
| 税额 | `TAX_AMT` in `ACCOUNTTAX` | `BAPI_ACC_DOCUMENT_POST` | Must balance: net amount + tax amount = gross |

---

## 6. SAP API Catalog for FSSC Use Cases

### Read APIs (FSSC → SAP)

| Use Case | API / BAPI | Protocol | SAP Version |
|---|---|---|---|
| AP open items | `API_OPLACCTGDOCITEMCUBE_SRV / A_OperationalAcctgDocItemCube` (filter K) | OData V2 | S/4HANA 1809+ |
| AR open items | Same service, filter `D` | OData V2 | S/4HANA 1809+ |
| AP open items (ECC) | `BAPI_AP_ACC_GETOPENITEMS` | JCo | ECC 6.0+ |
| AR open items (ECC) | `BAPI_AR_ACC_GETOPENITEMS` | JCo | ECC 6.0+ |
| Vendor master | `API_BUSINESS_PARTNER / A_Supplier, A_SupplierCompany` | OData V2 | S/4HANA |
| Customer master | `API_BUSINESS_PARTNER / A_Customer, A_CustomerCompany` | OData V2 | S/4HANA |
| GL balance / line items | `API_GL_ACCOUNT_LINE_ITEM_SRV` | OData V2 | S/4HANA |
| FI document header/items | `API_JOURNALENTRYITEMBASIC_SRV` | OData V2 | S/4HANA |
| Asset register | `BAPI_FIXEDASSET_GETLIST` | JCo | ECC + S/4HANA |
| Asset detail | `BAPI_FIXEDASSET_GETDETAIL` | JCo | ECC + S/4HANA |
| Asset master (Cloud) | `CE_FIXEDASSET_0001` | OData V4 | S/4HANA Cloud |
| Cost center / profit center | `API_COSTCENTER_0002`, `API_PROFITCENTER_SRV` | OData V2 | S/4HANA |
| Company code list | `API_COMPANYCODE_SRV` | OData V2 | S/4HANA |
| Exchange rates | `API_EXCHANGERATE_SRV` | OData V2 | S/4HANA |
| Payment terms | `API_PAYMENTTERMS_SRV` | OData V2 | S/4HANA |
| Purchasing info record | `API_PURCHASEINFORECORD_SRV` | OData V2 | S/4HANA |

### Write APIs (FSSC → SAP)

| Use Case | API / BAPI | Protocol | SAP Version |
|---|---|---|---|
| Post GL document | `BAPI_ACC_DOCUMENT_POST` | JCo | ECC + S/4HANA |
| Post AP vendor invoice | `BAPI_ACC_DOCUMENT_POST` (doc type KR) | JCo | ECC + S/4HANA |
| Post AR customer invoice | `BAPI_ACC_DOCUMENT_POST` (doc type DR) | JCo | ECC + S/4HANA |
| Post vendor payment (clearing) | `BAPI_ACC_DOCUMENT_POST` (doc type KZ) | JCo | ECC + S/4HANA |
| Create supplier invoice (MM-linked) | `API_SUPPLIERINVOICE_PROCESS_SRV` | OData V2 | S/4HANA 1809+ |
| Park document for approval | `BAPI_ACC_DOCUMENT_POST` (`DOC_STATUS='2'`) | JCo | ECC + S/4HANA |
| Asset acquisition | `BAPI_ASSET_ACQUISITION_POST` | JCo | ECC + S/4HANA |
| Asset retirement | `BAPI_ASSET_RETIREMENT_POST` | JCo | ECC + S/4HANA |
| Asset transfer | `BAPI_ASSET_TRANSFER_POST` | JCo | ECC + S/4HANA |
| Asset acquisition (Cloud) | `OP_FIXEDASSETACQUISITION_0001` | OData V4 | S/4HANA Cloud |
| Post to CFIN from non-SAP | `API_CFinRpldSupplierInvoice` | OData V4 | CFIN S/4HANA |
| Post AR to CFIN | `API_CFinRpldBillingDocument` | OData V4 | CFIN S/4HANA |
| Replicate sales doc to CFIN | `API_CFinRpldSalesDocument` | OData V4 | CFIN S/4HANA |
| Create payment | `BAPI_INCOMINGINVOICE_PARKDOCUMENT` | JCo | ECC |

### Event APIs (SAP → FSSC, push notification)

| SAP Event | Topic | Trigger |
|---|---|---|
| Accounting document posted | `sap/s4/beh/accountingdocument/v1/AccountingDocument/Posted/v1` | FI posting (payment, clearing) |
| Payment run completed | `sap/s4/beh/paymentrequests/v1/PaymentRequest/Paid/v1` | F110 payment run |
| Purchase order changed | `sap/s4/beh/purchaseorder/v1/PurchaseOrder/Changed/v1` | PO price/qty change |
| Goods receipt posted | `sap/s4/beh/materialdocument/v1/MaterialDocument/Posted/v1` | 101/105 GR posting |

---

## 7. Implementation Checklist

### Phase 1: SAP-side prerequisites

- [ ] Create dedicated RFC/API technical user (`SU01`): `RFC_FSSC_USR`, type System, password-expiry disabled
- [ ] Assign minimum required authorization roles:
  - `SAP_BC_BAPI_RFC_OPERATOR` — basic RFC access
  - `SAP_FIN_GL_POSTING` — GL posting authorization
  - `SAP_FIN_AA_REPORTING` — FI-AA read authorization
  - Custom role with `F_BKPF_BUK` (company code restriction) and `F_BKPF_KOA` (account type restriction)
- [ ] Activate OData services in `/IWFND/MAINT_SERVICE`:
  - `API_OPLACCTGDOCITEMCUBE_SRV`
  - `API_BUSINESS_PARTNER`
  - `API_JOURNALENTRYITEMBASIC_SRV`
  - `API_SUPPLIERINVOICE_PROCESS_SRV` (if using OData for supplier invoices)
- [ ] Open ICF nodes in `SICF`:
  - `/sap/opu/odata/sap/` — OData V2 services
  - `/sap/opu/odata4/sap/` — OData V4 services (CFIN)
- [ ] Verify RFC gateway is accessible from FSSC server: `telnet s4hana.example.com 3300`
- [ ] Open FI posting periods (`OB52`) for all relevant company codes
- [ ] Open FI-AA posting periods (`OAAQ`) if using asset BAPIs
- [ ] Configure exchange rates (`OB08`) for all required currency pairs
- [ ] Test BAPI_TRANSACTION_COMMIT behavior in QA system before go-live

### Phase 2: FSSC-side development

- [ ] Implement credential management: secrets manager or encrypted keystore, never plaintext config
- [ ] Implement CSRF token refresh logic for OData writes (token valid per session, not per request)
- [ ] Implement idempotency: track SAP document numbers against source reference IDs in a local DB
- [ ] Implement retry with exponential backoff for all SAP API calls (HTTP 5xx, JCo `JCO_ERROR_COMMUNICATION`)
- [ ] Implement dead-letter queue for permanently failed postings with alert to finance team
- [ ] Implement master data sync: daily delta pull of vendor/customer from `API_BUSINESS_PARTNER` with change tracking using `LastChangeDateTime`
- [ ] Implement reconciliation report: daily comparison of FSSC totals vs SAP G/L balances by company code

### Phase 3: Testing

- [ ] Unit test each BAPI call with representative test data in SAP QA
- [ ] Test posting period boundary: fiscal year-end, closed period handling
- [ ] Test duplicate prevention: call the same post twice, verify only one document created in SAP
- [ ] Test error handling: post to closed period, invalid GL account, missing cost center
- [ ] Load test: simulate end-of-month batch — typical volumes are 5,000–50,000 documents/day
- [ ] Test connectivity failover: stop SAP application server, verify FSSC queues messages and retries

### Phase 4: Go-live and monitoring

- [ ] Monitor `SM58` (tRFC/qRFC error log) for failed async RFC calls
- [ ] Monitor `/IWFND/ERROR_LOG` for OData errors
- [ ] Set up SAP CCMS alert for RFC gateway errors
- [ ] Configure FSSC dashboard: daily posting volumes, error rate, open-item sync lag
- [ ] Establish daily reconciliation procedure with finance team for the first 30 days

---

## 8. Common Pitfalls

### 1. SAP client number missing from OData calls
**Symptom**: HTTP 200 but returns data from wrong company / empty result.  
**Cause**: Without `x-sap-client` header, SAP uses the default client (usually `000`), which has no business data.  
**Fix**: Always include `x-sap-client: 100` (or whatever your client number is) in every OData request header.

### 2. Kingdee account codes not mapped to SAP GL accounts
**Symptom**: `BAPI_ACC_DOCUMENT_POST` returns `GL account XXXXXX does not exist in company code`.  
**Cause**: Kingdee uses its own chart of accounts (e.g., Chinese standard `GB/T 14765`). SAP has a separately configured chart of accounts. These don't auto-map.  
**Fix**: Build a static mapping table in the integration middleware. Maintain it in a configuration database, not hardcoded. Include account descriptions in your mapping table so reconciliation is easier.

### 3. Business Partner number ≠ vendor/customer number
**Symptom**: Vendor lookup by legacy vendor number fails after S/4HANA migration.  
**Cause**: S/4HANA uses Business Partner (`LIFNR`/`KUNNR` in BKPF) but the BP number may differ from the old ECC vendor number. They are linked via `BUT000` and `LFB1`/`KNB1`.  
**Fix**: Query `API_BUSINESS_PARTNER` to find the BP number, not the old vendor number. If migrated from ECC, check `BUT000-PARTNER` vs old `LIFNR` in `LFB1`.

### 4. Posting date vs document date vs asset value date
**Symptom**: FI document posts but asset values are wrong / depreciation calculation incorrect.  
**Cause**: FI-AA uses `ASSET_VALUE_DATE` (not `POSTING_DATE`) to calculate depreciation for the period. These three dates serve different purposes and are independently validated.  
**Fix**: Always set all three dates explicitly:
- `DOC_DATE`: the external invoice or transaction date
- `POSTING_DATE`: when the entry is posted in FI (must be in an open FI period)
- `ASSET_VALUE_DATE`: determines depreciation period entry point (must be in an open FI-AA period)

### 5. RFC connection pool exhaustion under load
**Symptom**: JCo throws `JCO_ERROR_RESOURCE: Max connections exceeded` during month-end batch.  
**Cause**: Month-end processing hits a spike; the pool size was sized for normal daily volume.  
**Fix**: Configure `jco.destination.pool_capacity` and `jco.destination.peak_limit` appropriately. Standard sizing: pool=10, peak=20 for 5,000 docs/day; increase for higher volumes. Implement a semaphore in your application to queue requests when pool is near capacity rather than throwing exceptions.

### 6. CFIN replication fails on unmapped cost objects
**Symptom**: CFIN OData V4 POST returns `Mapping not found for cost center XXXX`.  
**Cause**: CFIN requires all CO objects (cost centers, profit centers, WBS) in the source document to have a mapping rule configured. Kingdee's internal cost dimension codes must be mapped in CFIN mapping configuration.  
**Fix**: Before go-live, extract all cost centers/profit centers from Kingdee, map them in `FINS_CFIN_MAPP`, and validate with a test document. Automate mapping rule extraction from Kingdee's API and load into CFIN via `FINS_CFIN_MAPP` mass upload.

### 7. Exchange rate mismatch between FSSC and SAP
**Symptom**: Postings succeed but FI document amounts in company currency differ from FSSC records.  
**Cause**: FSSC and SAP may use different exchange rates (different sources, different rate types). SAP uses rate type `M` (standard translation rate) by default, loaded via `OB08`.  
**Fix**: Sync exchange rates daily from a common source (e.g., PBOC for CNY pairs) into both systems. Pass the explicit `RATE` and `RATE_TYPE` in `BAPI_ACC_DOCUMENT_POST.CURRENCYAMOUNT` to avoid SAP using its own rate:

```python
# Pass explicit exchange rate to avoid SAP looking up its own
currency_amounts = [
    {
        "CURRENCY":    "USD",
        "AMT_DOCCUR":  "10000.00",
        "CURRENCY_LC": "CNY",
        "AMT_LC":      "71580.00",   # calculated by FSSC
        "RATE":        "7.1580",     # explicit rate
        "RATE_TYPE":   "M",
    }
]
```

### 8. Open-item sync showing stale data
**Symptom**: Kingdee shows an invoice as open, but SAP has already cleared it.  
**Cause**: Polling interval too long, or SAP clearing event not propagated to FSSC in time. Typical polling is hourly or daily.  
**Fix**: 
- Short term: reduce polling interval to 15 minutes for critical AP items.
- Long term: subscribe to SAP Event Mesh event `AccountingDocument.Posted` to get real-time clearing notifications (see Pattern B). On event receipt, immediately re-query the specific document in SAP to confirm cleared status before updating Kingdee.

---

## 9. ECC 6.0 Architecture Constraints

This section consolidates all ECC-specific constraints in one place for teams assessing whether Pattern A, B, or C is viable on an ECC landscape.

### 9.1 What Is and Is Not Available on ECC

| Capability | S/4HANA On-Prem (1809+) | ECC 6.0 (all EHP) |
|---|---|---|
| `API_OPLACCTGDOCITEMCUBE_SRV` (read AR/AP) | ✅ | ❌ |
| `API_BUSINESS_PARTNER` (vendor/customer master) | ✅ | ❌ |
| `API_SUPPLIERINVOICE_PROCESS_SRV` (MM invoice OData) | ✅ (1809+) | ❌ |
| `API_JOURNALENTRYITEMBASIC_SRV` (GL journal OData) | ✅ | ❌ |
| `BAPI_ACC_DOCUMENT_POST` (FI posting via JCo) | ✅ | ✅ |
| `BAPI_AP_ACC_GETOPENITEMS` / `BAPI_AR_ACC_GETOPENITEMS` | ✅ | ✅ |
| `BAPI_VENDOR_GETDETAIL` / `BAPI_CUSTOMER_GETDETAIL1` | ✅ | ✅ |
| `BAPI_INCOMINGINVOICE_CREATE` | ✅ | ✅ |
| `RFC_READ_TABLE` | ✅ | ✅ |
| SAP Event Mesh (push events) | ✅ (requires BTP subscription) | ❌ |
| BTP Cloud Connector (native) | ✅ | Possible — requires separate CC agent install |
| SAP PI/PO | Maintenance mode (use Integration Suite) | ✅ (still mainstream on ECC) |
| CFIN (Pattern C) | ✅ (target system) | ECC is source only; S/4HANA required as CFIN target |

### 9.2 Pattern Applicability Matrix for ECC

| Pattern | ECC feasibility | Notes |
|---|---|---|
| **Pattern A — Direct JCo** | ✅ **Recommended** | Replace all OData calls with BAPI equivalents; no other changes |
| **Pattern B — BTP-Mediated** | ⚠️ Partial | BTP Cloud Connector can relay OData if ECC OData services are manually activated; most key FI OData services are absent. Use JCo adapter in iFlow instead of OData adapter |
| **Pattern C — CFIN** | ❌ ECC cannot be CFIN target | ECC can be a CFIN *source* (replication from ECC → S/4HANA CFIN target); the CFIN central system must be S/4HANA |

### 9.3 Recommended ECC Integration Architecture

```
Kingdee FSSC (on-premise)
        │
        │  JCo  (TCP port 33xx)
        │
        ▼
SAP ECC 6.0 Application Server
  ├── BAPI_AP_ACC_GETOPENITEMS     ← read AP open items
  ├── BAPI_AR_ACC_GETOPENITEMS     ← read AR open items
  ├── BAPI_VENDOR_GETDETAIL        ← vendor master / payment terms
  ├── BAPI_CUSTOMER_GETDETAIL1     ← customer master / payment terms
  ├── BAPI_INCOMINGINVOICE_CREATE  ← MM-based supplier invoice
  ├── BAPI_ACC_DOCUMENT_POST       ← FI document posting (KR/DR/KZ/KG)
  ├── BAPI_TRANSACTION_COMMIT      ← mandatory after every post
  └── RFC_READ_TABLE               ← bulk BKPF/BSEG extract
```

**Key design principles for ECC FSSC**:

1. **Polling replaces events**: Since ECC has no event mesh, schedule cron jobs at appropriate intervals (open-item sync: every 15–60 minutes; master data sync: nightly; GL extract: daily at business-day start).

2. **Idempotency is mandatory**: Before posting any document, check `BKPF` for an existing entry with the same `XBLNR` (external reference). See the idempotency example in §2 Pattern A Write Flow.

3. **JCo connection pool management**: Use `JCoDestinationManager.getDestination()` — JCo manages the underlying connection pool automatically. Configure `jco.destination.pool_capacity = 5` and `jco.destination.peak_limit = 10` as a baseline; opening and closing a connection has ~200–500ms overhead, so let JCo reuse connections across calls within a batch rather than creating a new destination per request.

4. **Error handling by severity**: `BAPI RETURN` table items with `TYPE = 'E'` or `'A'` are errors; `'W'` is a warning (document may still be created). Always log full `RETURN` table on failure.

5. **Amount sign consistency**: `BAPI_ACC_DOCUMENT_POST` requires balanced entries. The sum of all `AMT_DOCCUR` values must be zero. Refer to `fi-ar-ap.md §11` pitfall #1 for the sign convention quick reference.

6. **Zero-padding**: All account numbers (vendor, customer, GL) are 10-char zero-padded in ECC. In Java: `String.format("%10s", accountNo).replace(' ', '0')` before passing to any BAPI.

### 9.4 Migration Path: ECC → S/4HANA

When the customer upgrades from ECC to S/4HANA, the integration code change is bounded:

| Code change | Effort |
|---|---|
| Replace `BAPI_AP_ACC_GETOPENITEMS` calls with OData `API_OPLACCTGDOCITEMCUBE_SRV` | Medium — different response shape, pagination added |
| Replace `BAPI_VENDOR_GETDETAIL` with `API_BUSINESS_PARTNER` | Low — similar fields, different JSON structure |
| Replace `BAPI_INCOMINGINVOICE_CREATE` with `API_SUPPLIERINVOICE_PROCESS_SRV` | Medium — OData deep insert, CSRF token required |
| Posting BAPIs (`BAPI_ACC_DOCUMENT_POST`) | **No change** — identical on S/4HANA |
| Add SAP Event Mesh subscriptions for real-time clearing | New feature — adds real-time clearing sync capability |

> **Architect's note**: Design the ECC integration with a clean adapter layer (one class per SAP API call) so that the S/4HANA migration replaces adapter implementations without touching business logic. The FSSC workflow orchestration, idempotency checks, and error handling layers are identical across both SAP versions.
