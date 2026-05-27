# FI: Accounts Receivable & Accounts Payable Integration

## Table of Contents

1. [Scenario Overview](#scenario-overview)
2. [Query AR/AP Open Items via OData](#1-query-arap-open-items-via-odata)
3. [Read Payment Terms via Business Partner API](#2-read-payment-terms-via-business-partner-api)
4. [Create Supplier Invoice via OData](#3-create-supplier-invoice-via-odata)
5. [Post AP Document via BAPI (Vendor Invoice)](#4-post-ap-document-via-bapi-vendor-invoice)
6. [Post AR Document via BAPI (Customer Invoice)](#5-post-ar-document-via-bapi-customer-invoice)
7. [Post Vendor Payment (KZ) — Clearing Open Item](#6-post-vendor-payment-kz--clearing-open-item)
8. [Document Parking](#7-document-parking)
9. [Down Payments and Special GL Indicators](#8-down-payments-and-special-gl-indicators)
10. [ECC 6.0: JCo-Only AR/AP Path](#10-ecc-60-jco-only-arap-path)
11. [Common Pitfalls](#11-common-pitfalls)

---

## Scenario Overview

| Sub-scenario | S/4HANA On-Prem recommendation | ECC 6.0 recommendation |
|---|---|---|
| Query AR open items (receivables) | OData `API_OPLACCTGDOCITEMCUBE_SRV` (filter `FinancialAccountType eq 'D'`) | JCo `BAPI_AR_ACC_GETOPENITEMS` |
| Query AP open items (payables) | OData `API_OPLACCTGDOCITEMCUBE_SRV` (filter `FinancialAccountType eq 'K'`) | JCo `BAPI_AP_ACC_GETOPENITEMS` |
| Read payment terms for vendor/customer | OData `API_BUSINESS_PARTNER` → `A_SupplierCompany.PaymentTerms` | JCo `BAPI_VENDOR_GETDETAIL` |
| Create incoming supplier invoice (MM-based) | OData V2 `API_SUPPLIERINVOICE_PROCESS_SRV` (S/4HANA 1809+) | JCo `BAPI_INCOMINGINVOICE_CREATE` |
| Post FI vendor invoice (KR) or customer invoice (DR) | JCo `BAPI_ACC_DOCUMENT_POST` | Same |
| Post vendor payment / clear open item | JCo `BAPI_ACC_DOCUMENT_POST` (doc type KZ) | Same |
| Park document for approval workflow | JCo `BAPI_ACC_DOCUMENT_POST` (`DOC_STATUS = '2'`) | Same |
| Vendor/customer down payment | JCo `BAPI_ACC_DOCUMENT_POST` (`SP_GL_IND = 'F'` or `'A'`) | Same |

**Key architectural note**: Direct AR/AP posting via standard OData is limited in On-Premise releases. `API_OPLACCTGDOCITEMCUBE_SRV` is **read-only** (analytical). For posting, `BAPI_ACC_DOCUMENT_POST` via JCo is the standard. Exception: `API_SUPPLIERINVOICE_PROCESS_SRV` supports creating MM-linked supplier invoices via OData V2 in S/4HANA 1809+.

---

## 1. Query AR/AP Open Items via OData

### API_OPLACCTGDOCITEMCUBE_SRV

**Service**: `API_OPLACCTGDOCITEMCUBE_SRV`  
**Entity set**: `A_OperationalAcctgDocItemCube`  
**Availability**: S/4HANA On-Premise 1809+, read-only  
**Communication Scenario**: `SAP_COM_0303`

**`FinancialAccountType` filter values**:

| Value | Account type |
|---|---|
| `D` | Customer (AR receivables) |
| `K` | Vendor (AP payables) |
| `S` | G/L account |

**Key fields for open-item tracking**:

| Field | Description | Open item filter |
|---|---|---|
| `IsCleared` | Boolean — `false` = open, `true` = cleared | `IsCleared eq false` |
| `ClearingAccountingDocument` | Clearing document number | Blank = still open |
| `ClearingDate` | Date item was cleared | Blank = still open |
| `NetDueDate` | Payment due date | Compare to today |
| `PaymentBlockingReason` | Block indicator | Blank = no block |
| `PaymentTerms` | Payment terms key | Informational |
| `AmountInCompanyCodeCurrency` | Line amount (signed) | — |

### Query open AP items (vendor payables)

```bash
# All open vendor invoices — company 1000, fiscal year 2026, ordered by due date
curl -u "APIUSER:password" \
  -H "Accept: application/json" \
  -H "x-sap-client: 100" \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_OPLACCTGDOCITEMCUBE_SRV/\
A_OperationalAcctgDocItemCube?\
\$filter=CompanyCode eq '1000' \
and FiscalYear eq '2026' \
and FinancialAccountType eq 'K' \
and IsCleared eq false\
&\$select=CompanyCode,AccountingDocument,FiscalYear,Supplier,\
PostingDate,DocumentItemText,AmountInCompanyCodeCurrency,\
CompanyCodeCurrency,NetDueDate,PaymentTerms,PaymentBlockingReason,\
ClearingAccountingDocument,ClearingDate\
&\$orderby=NetDueDate asc\
&\$top=200\
&\$format=json"
```

### Query open AR items (customer receivables)

```python
import requests
from datetime import date

session = requests.Session()
session.auth = ("APIUSER", "password")
session.headers.update({"Accept": "application/json", "x-sap-client": "100"})

BASE = "https://s4hana.example.com:44300/sap/opu/odata/sap/API_OPLACCTGDOCITEMCUBE_SRV"

params = {
    "$filter": (
        "CompanyCode eq '1000' "
        "and FiscalYear eq '2026' "
        "and FinancialAccountType eq 'D' "   # D = Customer (AR)
        "and IsCleared eq false"
    ),
    "$select": (
        "CompanyCode,AccountingDocument,FiscalYear,Customer,"
        "PostingDate,DocumentItemText,AmountInCompanyCodeCurrency,"
        "CompanyCodeCurrency,NetDueDate,PaymentTerms,"
        "ClearingAccountingDocument,ClearingDate"
    ),
    "$orderby": "NetDueDate asc",
    "$top": "500",
    "$format": "json"
}

resp = session.get(f"{BASE}/A_OperationalAcctgDocItemCube", params=params)
resp.raise_for_status()

items = resp.json()["d"]["results"]
for item in items:
    print(
        f"Doc: {item['AccountingDocument']} "
        f"Customer: {item['Customer']} "
        f"Amount: {item['AmountInCompanyCodeCurrency']} {item['CompanyCodeCurrency']} "
        f"Due: {item['NetDueDate']}"
    )
```

**SAP verification**: Transaction `FBL5N` (customer line items) / `FBL1N` (vendor line items).

---

## 2. Read Payment Terms via Business Partner API

Payment terms are stored on the company-code-level assignment of the Business Partner.

**Service**: `API_BUSINESS_PARTNER`  
**Entities**: `A_SupplierCompany` (vendor) / `A_CustomerCompany` (customer)

```python
import requests

session = requests.Session()
session.auth = ("APIUSER", "password")
session.headers.update({"Accept": "application/json", "x-sap-client": "100"})

BASE = "https://s4hana.example.com:44300/sap/opu/odata/sap/API_BUSINESS_PARTNER"

# Vendor payment terms
supplier_no = "0000100000"   # 10-digit, zero-padded
resp = session.get(
    f"{BASE}/A_SupplierCompany(Supplier='{supplier_no}',CompanyCode='1000')",
    params={
        "$select": "Supplier,CompanyCode,PaymentTerms,HouseBank,ReconciliationAccount",
        "$format": "json"
    }
)
resp.raise_for_status()
data = resp.json()["d"]
print(f"Vendor {data['Supplier']} payment terms: {data['PaymentTerms']}")

# Customer payment terms
customer_no = "0000200001"
resp = session.get(
    f"{BASE}/A_CustomerCompany(Customer='{customer_no}',CompanyCode='1000')",
    params={
        "$select": "Customer,CompanyCode,CustomerPaymentTerms,ReconciliationAccount",
        "$format": "json"
    }
)
resp.raise_for_status()
data = resp.json()["d"]
print(f"Customer {data['Customer']} payment terms: {data['CustomerPaymentTerms']}")
```

---

## 3. Create Supplier Invoice via OData

### API_SUPPLIERINVOICE_PROCESS_SRV (S/4HANA 1809+)

The standard OData V2 service for creating incoming supplier invoices — with PO reference or GL account assignment.

**Service**: `API_SUPPLIERINVOICE_PROCESS_SRV`  
**Entity**: `A_SupplierInvoice`

**Key navigations**:

| Navigation | Description |
|---|---|
| `to_SuplrInvcItemPurOrdRef` | PO-referenced line items |
| `to_SupplierInvoiceItemGLAcct` | GL account line items (non-PO invoices) |
| `to_SupplierInvoiceTax` | Tax items |
| `to_SupplierInvoiceWhldgTax` | Withholding tax items |

### Step 1: Fetch CSRF token

```python
import requests

session = requests.Session()
session.auth = ("APIUSER", "password")
session.headers.update({"x-sap-client": "100"})

BASE = "https://s4hana.example.com:44300/sap/opu/odata/sap/API_SUPPLIERINVOICE_PROCESS_SRV"

# CSRF token is mandatory for all write operations
resp = session.get(
    f"{BASE}/A_SupplierInvoice",
    headers={"x-csrf-token": "Fetch"},
    params={"$top": "1", "$format": "json"}
)
resp.raise_for_status()
csrf_token = resp.headers.get("x-csrf-token")
session.headers.update({
    "x-csrf-token": csrf_token,
    "Content-Type": "application/json"
})
```

### Step 2: Post supplier invoice (PO-referenced)

```python
import json

invoice_payload = {
    "CompanyCode": "1000",
    "DocumentDate": "2026-04-30T00:00:00",
    "PostingDate": "2026-04-30T00:00:00",
    "SupplierInvoiceIDByInvcgParty": "EXT-INV-20260430",
    "InvoicingParty": "0000100000",            # Vendor number (10-digit)
    "DocumentCurrency": "USD",
    "InvoiceGrossAmount": "1190.00",            # Gross amount including tax
    "DocumentType": "RE",                       # RE = Incoming invoice (MM-LIV)
    "to_SuplrInvcItemPurOrdRef": {
        "results": [
            {
                "SupplierInvoiceItem": "0001",
                "PurchaseOrder": "4500012345",
                "PurchaseOrderItem": "00010",
                "DocumentCurrency": "USD",
                "SupplierInvoiceItemAmount": "1000.00",    # Net amount
                "QuantityInPurchaseOrderUnit": "10",
                "PurchaseOrderQuantityUnit": "EA"
            }
        ]
    },
    "to_SupplierInvoiceTax": {
        "results": [
            {
                "DocumentCurrency": "USD",
                "TaxCode": "V1",
                "TaxAmount": "190.00"
            }
        ]
    }
}

resp = session.post(
    f"{BASE}/A_SupplierInvoice",
    data=json.dumps(invoice_payload)
)
resp.raise_for_status()
created = resp.json()["d"]
print(f"Invoice created: {created['SupplierInvoice']} / FY {created['FiscalYear']}")
```

> **Document type note**: Use `RE` for MM invoices with PO reference. Use `KR` for FI-only vendor invoices. For non-PO invoices, use the `to_SupplierInvoiceItemGLAcct` navigation with `GLAccount`, `CompanyCode`, `SupplierInvoiceItemAmount`, and optional `CostCenter`.

---

## 4. Post AP Document via BAPI (Vendor Invoice)

### BAPI_ACC_DOCUMENT_POST with ACCOUNTPAYABLE

**When to use**: FI-only vendor invoices without PO reference; ECC systems; complex multi-line postings with CO assignment.

**BAPIACAP09 (ACCOUNTPAYABLE) key fields**:

| Field | Type | Description |
|---|---|---|
| `ITEMNO_ACC` | NUMC(10) | Line item number — links to CURRENCYAMOUNT |
| `VENDOR_NO` | CHAR(10) | Vendor account number (10-digit, zero-padded) |
| `COMP_CODE` | CHAR(4) | Company code |
| `PMNTTRMS` | CHAR(4) | Payment terms key (e.g., `Z001`) |
| `BLINE_DATE` | DATS(8) | Baseline date for due date calculation (YYYYMMDD) |
| `ITEM_TEXT` | CHAR(50) | Line item text |
| `ALLOC_NMBR` | CHAR(18) | Assignment number (used for matching/search) |
| `PYMT_METH` | CHAR(1) | Payment method (e.g., `T` = bank transfer) |
| `SP_GL_IND` | CHAR(1) | Special GL indicator (`F` = vendor advance, blank = normal) |
| `TAX_CODE` | CHAR(2) | Tax on sales/purchases code |
| `PMNT_BLOCK` | CHAR(1) | Payment block reason (blank = not blocked, `R` = review) |

**Amount sign convention** (applies to all `AMT_DOCCUR` entries in CURRENCYAMOUNT):

| Sign | Meaning |
|---|---|
| **Positive** | Debit entry |
| **Negative** | Credit entry |

The **sum of all `AMT_DOCCUR` across all line items must equal zero** (balanced document rule). Violating this returns error `F5701`.

### Java example: KR vendor invoice

```java
public static String postVendorInvoice(JCoDestination dest) throws JCoException {
    JCoFunction bapi = dest.getRepository().getFunction("BAPI_ACC_DOCUMENT_POST");

    String today = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
    double invoiceAmount = 1000.00;

    // Document header
    JCoStructure docHeader = bapi.getImportParameterList().getStructure("DOCUMENTHEADER");
    docHeader.setValue("BUS_ACT",    "RFBU");           // Business activity: Accountant posting
    docHeader.setValue("USERNAME",   "RFCUSER");
    docHeader.setValue("COMP_CODE",  "1000");
    docHeader.setValue("DOC_DATE",   today);
    docHeader.setValue("PSTNG_DATE", today);
    docHeader.setValue("DOC_TYPE",   "KR");             // KR = Vendor invoice
    docHeader.setValue("REF_DOC_NO", "EXT-INV-001");
    docHeader.setValue("HEADER_TXT", "Vendor invoice from FSSC");

    // Vendor AP line (credit — negative amount)
    JCoTable apTable = bapi.getTableParameterList().getTable("ACCOUNTPAYABLE");
    apTable.appendRow();
    apTable.setValue("ITEMNO_ACC",  "0000000001");
    apTable.setValue("VENDOR_NO",   "0000100000");      // 10-digit, zero-padded
    apTable.setValue("COMP_CODE",   "1000");
    apTable.setValue("PMNTTRMS",    "Z001");
    apTable.setValue("BLINE_DATE",  today);
    apTable.setValue("ITEM_TEXT",   "Vendor invoice");
    apTable.setValue("ALLOC_NMBR",  "EXT-INV-001");

    // Expense GL line (debit — positive amount)
    JCoTable glTable = bapi.getTableParameterList().getTable("ACCOUNTGL");
    glTable.appendRow();
    glTable.setValue("ITEMNO_ACC",  "0000000002");
    glTable.setValue("GL_ACCOUNT",  "600000");          // Expense GL account
    glTable.setValue("COMP_CODE",   "1000");
    glTable.setValue("COSTCENTER",  "10001000");        // Required for cost element accounts
    glTable.setValue("ITEM_TEXT",   "External service");

    // Currency amounts — must balance to zero
    JCoTable amtTable = bapi.getTableParameterList().getTable("CURRENCYAMOUNT");
    amtTable.appendRow();
    amtTable.setValue("ITEMNO_ACC",  "0000000001");
    amtTable.setValue("CURR_TYPE",   "00");             // Transaction currency
    amtTable.setValue("CURRENCY",    "USD");
    amtTable.setValue("AMT_DOCCUR",  -invoiceAmount);   // NEGATIVE = credit to vendor (liability increases)

    amtTable.appendRow();
    amtTable.setValue("ITEMNO_ACC",  "0000000002");
    amtTable.setValue("CURR_TYPE",   "00");
    amtTable.setValue("CURRENCY",    "USD");
    amtTable.setValue("AMT_DOCCUR",  invoiceAmount);    // POSITIVE = debit to expense account

    bapi.execute(dest);

    // Check RETURN table — BAPI_ACC_DOCUMENT_POST signals errors here, not via exception
    JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
    for (int i = 0; i < returnTable.getNumRows(); i++) {
        returnTable.setRow(i);
        if ("E".equals(returnTable.getString("TYPE")) || "A".equals(returnTable.getString("TYPE"))) {
            throw new RuntimeException("BAPI_ACC_DOCUMENT_POST error: " + returnTable.getString("MESSAGE"));
        }
    }

    // ALWAYS commit — without this, the posting is rolled back on connection close
    JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
    commit.getImportParameterList().setValue("WAIT", "X");
    commit.execute(dest);

    // Extract document number from OBJ_KEY: <CompanyCode(4)><FiscalYear(4)><DocumentNo(10)>
    String objKey = bapi.getExportParameterList().getString("OBJ_KEY");
    if (objKey != null && objKey.length() >= 18) {
        System.out.printf("Posted: company=%s, year=%s, doc=%s%n",
            objKey.substring(0, 4), objKey.substring(4, 8), objKey.substring(8));
        return objKey.substring(8);
    }
    return objKey;
}
```

**SAP verification**: Transaction `FB03` → enter company code + document number → verify line items.

---

## 5. Post AR Document via BAPI (Customer Invoice)

### BAPIACAR09 (ACCOUNTRECEIVABLE) key fields

| Field | Type | Description |
|---|---|---|
| `ITEMNO_ACC` | NUMC(10) | Line item number — links to CURRENCYAMOUNT |
| `CUSTOMER` | CHAR(10) | Customer account number (10-digit, zero-padded) |
| `COMP_CODE` | CHAR(4) | Company code |
| `PMNTTRMS` | CHAR(4) | Payment terms key |
| `BLINE_DATE` | DATS(8) | Baseline date for due date calculation |
| `DSCT_DAYS1` | NUMC(3) | Cash discount period 1 (days) |
| `DSCT_AMT1` | DEC(5,3) | Cash discount percentage 1 |
| `ITEM_TEXT` | CHAR(50) | Line item text |
| `ALLOC_NMBR` | CHAR(18) | Assignment number |
| `PYMT_METH` | CHAR(1) | Payment method |
| `SP_GL_IND` | CHAR(1) | Special GL indicator (`A` = customer down payment) |
| `TAX_CODE` | CHAR(2) | Tax code |
| `TAX_DATE` | DATS(8) | Date relevant for tax rate determination |

### Java example: DR customer invoice

```java
public static String postCustomerInvoice(JCoDestination dest) throws JCoException {
    JCoFunction bapi = dest.getRepository().getFunction("BAPI_ACC_DOCUMENT_POST");

    String today = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
    double invoiceAmount = 1000.00;

    JCoStructure docHeader = bapi.getImportParameterList().getStructure("DOCUMENTHEADER");
    docHeader.setValue("BUS_ACT",    "RFBU");
    docHeader.setValue("USERNAME",   "RFCUSER");
    docHeader.setValue("COMP_CODE",  "1000");
    docHeader.setValue("DOC_DATE",   today);
    docHeader.setValue("PSTNG_DATE", today);
    docHeader.setValue("DOC_TYPE",   "DR");             // DR = Customer invoice
    docHeader.setValue("REF_DOC_NO", "CUST-INV-001");
    docHeader.setValue("HEADER_TXT", "Customer invoice from FSSC");

    JCoTable arTable = bapi.getTableParameterList().getTable("ACCOUNTRECEIVABLE");
    arTable.appendRow();
    arTable.setValue("ITEMNO_ACC",  "0000000001");
    arTable.setValue("CUSTOMER",    "0000200001");      // 10-digit, zero-padded
    arTable.setValue("COMP_CODE",   "1000");
    arTable.setValue("PMNTTRMS",    "Z001");
    arTable.setValue("BLINE_DATE",  today);
    arTable.setValue("ITEM_TEXT",   "Customer invoice");
    arTable.setValue("ALLOC_NMBR",  "CUST-INV-001");

    JCoTable glTable = bapi.getTableParameterList().getTable("ACCOUNTGL");
    glTable.appendRow();
    glTable.setValue("ITEMNO_ACC",  "0000000002");
    glTable.setValue("GL_ACCOUNT",  "500000");          // Revenue GL account
    glTable.setValue("COMP_CODE",   "1000");
    glTable.setValue("ITEM_TEXT",   "Revenue recognition");

    JCoTable amtTable = bapi.getTableParameterList().getTable("CURRENCYAMOUNT");
    amtTable.appendRow();
    amtTable.setValue("ITEMNO_ACC",  "0000000001");
    amtTable.setValue("CURR_TYPE",   "00");
    amtTable.setValue("CURRENCY",    "USD");
    amtTable.setValue("AMT_DOCCUR",  invoiceAmount);    // POSITIVE = debit to customer (receivable increases)

    amtTable.appendRow();
    amtTable.setValue("ITEMNO_ACC",  "0000000002");
    amtTable.setValue("CURR_TYPE",   "00");
    amtTable.setValue("CURRENCY",    "USD");
    amtTable.setValue("AMT_DOCCUR",  -invoiceAmount);   // NEGATIVE = credit to revenue

    bapi.execute(dest);

    JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
    for (int i = 0; i < returnTable.getNumRows(); i++) {
        returnTable.setRow(i);
        if ("E".equals(returnTable.getString("TYPE")) || "A".equals(returnTable.getString("TYPE"))) {
            throw new RuntimeException("BAPI error: " + returnTable.getString("MESSAGE"));
        }
    }

    JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
    commit.getImportParameterList().setValue("WAIT", "X");
    commit.execute(dest);

    String objKey = bapi.getExportParameterList().getString("OBJ_KEY");
    System.out.println("AR invoice posted: " + (objKey != null && objKey.length() >= 18 ? objKey.substring(8) : objKey));
    return objKey;
}
```

---

## 6. Post Vendor Payment (KZ) — Clearing Open Item

To clear an open vendor invoice, post a vendor payment (doc type `KZ`). SAP auto-clears the open item when the amounts match and the `ALLOC_NMBR` references the original invoice.

```java
public static String postVendorPayment(JCoDestination dest) throws JCoException {
    JCoFunction bapi = dest.getRepository().getFunction("BAPI_ACC_DOCUMENT_POST");

    String today = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
    double paymentAmount = 1000.00;

    JCoStructure docHeader = bapi.getImportParameterList().getStructure("DOCUMENTHEADER");
    docHeader.setValue("BUS_ACT",    "RFBU");
    docHeader.setValue("USERNAME",   "RFCUSER");
    docHeader.setValue("COMP_CODE",  "1000");
    docHeader.setValue("DOC_DATE",   today);
    docHeader.setValue("PSTNG_DATE", today);
    docHeader.setValue("DOC_TYPE",   "KZ");             // KZ = Vendor payment
    docHeader.setValue("REF_DOC_NO", "PAY-EXT-001");
    docHeader.setValue("HEADER_TXT", "Payment for EXT-INV-001");

    JCoTable apTable = bapi.getTableParameterList().getTable("ACCOUNTPAYABLE");
    apTable.appendRow();
    apTable.setValue("ITEMNO_ACC",  "0000000001");
    apTable.setValue("VENDOR_NO",   "0000100000");
    apTable.setValue("COMP_CODE",   "1000");
    apTable.setValue("ITEM_TEXT",   "Vendor payment");
    apTable.setValue("ALLOC_NMBR",  "EXT-INV-001");    // Match to original invoice for auto-clearing

    JCoTable glTable = bapi.getTableParameterList().getTable("ACCOUNTGL");
    glTable.appendRow();
    glTable.setValue("ITEMNO_ACC",  "0000000002");
    glTable.setValue("GL_ACCOUNT",  "113100");          // Bank / house bank clearing account
    glTable.setValue("COMP_CODE",   "1000");
    glTable.setValue("ITEM_TEXT",   "Bank payment");

    JCoTable amtTable = bapi.getTableParameterList().getTable("CURRENCYAMOUNT");
    amtTable.appendRow();
    amtTable.setValue("ITEMNO_ACC",  "0000000001");
    amtTable.setValue("CURR_TYPE",   "00");
    amtTable.setValue("CURRENCY",    "USD");
    amtTable.setValue("AMT_DOCCUR",  paymentAmount);    // POSITIVE = debit to vendor (reduces liability)

    amtTable.appendRow();
    amtTable.setValue("ITEMNO_ACC",  "0000000002");
    amtTable.setValue("CURR_TYPE",   "00");
    amtTable.setValue("CURRENCY",    "USD");
    amtTable.setValue("AMT_DOCCUR",  -paymentAmount);   // NEGATIVE = credit to bank (cash out)

    bapi.execute(dest);

    JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
    for (int i = 0; i < returnTable.getNumRows(); i++) {
        returnTable.setRow(i);
        if ("E".equals(returnTable.getString("TYPE")) || "A".equals(returnTable.getString("TYPE"))) {
            throw new RuntimeException("BAPI error: " + returnTable.getString("MESSAGE"));
        }
    }

    JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
    commit.getImportParameterList().setValue("WAIT", "X");
    commit.execute(dest);

    String objKey = bapi.getExportParameterList().getString("OBJ_KEY");
    System.out.println("Payment posted: " + (objKey != null && objKey.length() >= 18 ? objKey.substring(8) : objKey));
    return objKey;
}
```

> **Clearing note**: Matching `ALLOC_NMBR` to the original invoice helps SAP auto-clear in many configurations, but is not guaranteed. For guaranteed clearing of specific open items, use SAP's automatic payment program (`F110`) or manual clearing (`F-44` vendor, `F-32` customer) after posting the payment.

**SAP verification**: `FBL1N` → verify vendor item is cleared (open indicator blanked).

---

## 7. Document Parking

Parking saves the document without posting — it is stored in the parking area (`VBKPF` table) and **does not affect account balances**. Use for approval workflows before final posting.

**Set `DOC_STATUS = '2'`** in `DOCUMENTHEADER`:

| `DOC_STATUS` | Meaning |
|---|---|
| `''` (blank) | Post immediately |
| `'2'` | Park document (visible in `FBV0`, not posted) |
| `'3'` | Save as complete (all required fields filled, still not posted) |

```java
public static String parkDocument(JCoDestination dest) throws JCoException {
    JCoFunction bapi = dest.getRepository().getFunction("BAPI_ACC_DOCUMENT_POST");

    String today = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));

    JCoStructure docHeader = bapi.getImportParameterList().getStructure("DOCUMENTHEADER");
    docHeader.setValue("BUS_ACT",    "RFBU");
    docHeader.setValue("USERNAME",   "RFCUSER");
    docHeader.setValue("COMP_CODE",  "1000");
    docHeader.setValue("DOC_DATE",   today);
    docHeader.setValue("PSTNG_DATE", today);
    docHeader.setValue("DOC_TYPE",   "KR");
    docHeader.setValue("REF_DOC_NO", "PARK-INV-001");
    docHeader.setValue("DOC_STATUS", "2");              // <<< Park — do not post

    JCoTable apTable = bapi.getTableParameterList().getTable("ACCOUNTPAYABLE");
    apTable.appendRow();
    apTable.setValue("ITEMNO_ACC", "0000000001");
    apTable.setValue("VENDOR_NO",  "0000100000");
    apTable.setValue("COMP_CODE",  "1000");
    apTable.setValue("ITEM_TEXT",  "Parked invoice for approval");

    JCoTable glTable = bapi.getTableParameterList().getTable("ACCOUNTGL");
    glTable.appendRow();
    glTable.setValue("ITEMNO_ACC", "0000000002");
    glTable.setValue("GL_ACCOUNT", "600000");
    glTable.setValue("COMP_CODE",  "1000");

    JCoTable amtTable = bapi.getTableParameterList().getTable("CURRENCYAMOUNT");
    amtTable.appendRow();
    amtTable.setValue("ITEMNO_ACC", "0000000001");
    amtTable.setValue("CURR_TYPE",  "00");
    amtTable.setValue("CURRENCY",   "USD");
    amtTable.setValue("AMT_DOCCUR", -1000.00);

    amtTable.appendRow();
    amtTable.setValue("ITEMNO_ACC", "0000000002");
    amtTable.setValue("CURR_TYPE",  "00");
    amtTable.setValue("CURRENCY",   "USD");
    amtTable.setValue("AMT_DOCCUR", 1000.00);

    bapi.execute(dest);

    // Parked documents do NOT require BAPI_TRANSACTION_COMMIT
    String parkedKey = bapi.getExportParameterList().getString("OBJ_KEY");
    System.out.println("Document parked: " + parkedKey);
    // Post later via SAP transaction FBV0, or PRELIMINARY_POSTING_POST_ALL
    return parkedKey;
}
```

> **SAP Note 2092366** documents `DOC_STATUS` behavior. Parked documents are visible in `FBV0` for review and can be posted or rejected by an authorised user.

---

## 8. Down Payments and Special GL Indicators

Down payments use a Special GL (SGL) indicator to redirect the posting to a separate reconciliation account (e.g., "Vendor Advances" instead of the normal payables account).

| `SP_GL_IND` | Account type | Meaning |
|---|---|---|
| `A` | Customer | Customer down payment (advance received) |
| `F` | Vendor | Vendor down payment (advance paid to vendor) |
| `V` | Vendor | Vendor noted item (payment request) |

### Vendor down payment (equivalent to F-48)

```java
public static String postVendorDownPayment(JCoDestination dest) throws JCoException {
    JCoFunction bapi = dest.getRepository().getFunction("BAPI_ACC_DOCUMENT_POST");

    String today = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
    double advanceAmount = 5000.00;

    JCoStructure docHeader = bapi.getImportParameterList().getStructure("DOCUMENTHEADER");
    docHeader.setValue("BUS_ACT",    "RFBU");
    docHeader.setValue("USERNAME",   "RFCUSER");
    docHeader.setValue("COMP_CODE",  "1000");
    docHeader.setValue("DOC_DATE",   today);
    docHeader.setValue("PSTNG_DATE", today);
    docHeader.setValue("DOC_TYPE",   "KZ");             // Vendor payment doc type
    docHeader.setValue("REF_DOC_NO", "DP-VEN-001");
    docHeader.setValue("HEADER_TXT", "Advance payment to vendor");

    JCoTable apTable = bapi.getTableParameterList().getTable("ACCOUNTPAYABLE");
    apTable.appendRow();
    apTable.setValue("ITEMNO_ACC",  "0000000001");
    apTable.setValue("VENDOR_NO",   "0000100000");
    apTable.setValue("COMP_CODE",   "1000");
    apTable.setValue("SP_GL_IND",   "F");               // F = Vendor advance / down payment
    apTable.setValue("ITEM_TEXT",   "Advance payment");

    JCoTable glTable = bapi.getTableParameterList().getTable("ACCOUNTGL");
    glTable.appendRow();
    glTable.setValue("ITEMNO_ACC",  "0000000002");
    glTable.setValue("GL_ACCOUNT",  "113100");          // Bank / house bank clearing account
    glTable.setValue("COMP_CODE",   "1000");
    glTable.setValue("ITEM_TEXT",   "Bank payment for advance");

    JCoTable amtTable = bapi.getTableParameterList().getTable("CURRENCYAMOUNT");
    amtTable.appendRow();
    amtTable.setValue("ITEMNO_ACC", "0000000001");
    amtTable.setValue("CURR_TYPE",  "00");
    amtTable.setValue("CURRENCY",   "USD");
    amtTable.setValue("AMT_DOCCUR", advanceAmount);     // POSITIVE = debit to vendor advance account (asset)

    amtTable.appendRow();
    amtTable.setValue("ITEMNO_ACC", "0000000002");
    amtTable.setValue("CURR_TYPE",  "00");
    amtTable.setValue("CURRENCY",   "USD");
    amtTable.setValue("AMT_DOCCUR", -advanceAmount);    // NEGATIVE = credit to bank (cash out)

    bapi.execute(dest);

    JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
    for (int i = 0; i < returnTable.getNumRows(); i++) {
        returnTable.setRow(i);
        if ("E".equals(returnTable.getString("TYPE")) || "A".equals(returnTable.getString("TYPE"))) {
            throw new RuntimeException("BAPI error: " + returnTable.getString("MESSAGE"));
        }
    }

    JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
    commit.getImportParameterList().setValue("WAIT", "X");
    commit.execute(dest);

    String objKey = bapi.getExportParameterList().getString("OBJ_KEY");
    System.out.println("Down payment posted: " + objKey);
    return objKey;
}
```

> **Down payment requests** (F-47 equivalent) require `BAPI_TRANSACTION_COMMIT` and may additionally need a `BAdI ACC_DOCUMENT` implementation to set `BSTAT = 'S'` (noted item status). Consult SAP Note on document statuses before implementing down payment requests via BAPI.

---

## 10. ECC 6.0: JCo-Only AR/AP Path

> **ECC constraint**: SAP ECC 6.0 does not expose `API_OPLACCTGDOCITEMCUBE_SRV`, `API_BUSINESS_PARTNER`, or `API_SUPPLIERINVOICE_PROCESS_SRV`. All AR/AP read and write integration on ECC must go through JCo (RFC/BAPI). The posting BAPIs (`BAPI_ACC_DOCUMENT_POST`, `BAPI_TRANSACTION_COMMIT`) are identical between ECC and S/4HANA and are covered in §4–§8 above. This section covers the ECC-specific **read** and **MM invoice creation** paths only.

### 10.1 Read AP Open Items — `BAPI_AP_ACC_GETOPENITEMS`

**Function module**: `BAPI_AP_ACC_GETOPENITEMS`  
**Transport**: JCo synchronous RFC call  
**Authorization objects required**: `F_KNA1_BUK` (company code) + `F_BKPF_BUK`

| Parameter | Type | Description |
|---|---|---|
| `COMPANYCODE` | Import | 4-char company code |
| `VENDOR` | Import | 10-char vendor number (zero-padded) |
| `KEYDATE` | Import | Items open as of this date (`YYYYMMDD`) |
| `OPEN_ITEMS` | Table | Output — type `BAPIACAP09` |
| `RETURN` | Table | Standard SAP return messages |

> **No server-side pagination**: This BAPI returns all open items in a single call. For vendors with thousands of open items, the response can be large. If performance is a concern, split calls by fiscal year using `KEYDATE` anchored to prior year-end dates and filter results client-side.

**Key fields in `OPEN_ITEMS` table (`BAPIACAP09`)**:

| Field | Description |
|---|---|
| `BELNR` | Accounting document number |
| `BUKRS` | Company code |
| `GJAHR` | Fiscal year |
| `BUZEI` | Line item number |
| `BLDAT` | Document date |
| `BUDAT` | Posting date |
| `BLART` | Document type (`KR`=vendor invoice, `KZ`=payment, `KG`=credit memo) |
| `WRBTR` | Amount in document currency |
| `WAERS` | Document currency |
| `DMBTR` | Amount in local (company code) currency |
| `ZFBDT` | Baseline date for due date calculation |
| `ZTERM` | Payment terms key |
| `ZBD1T` / `ZBD2T` / `ZBD3T` | Cash discount days 1 / 2 / 3 |
| `ZLSCH` | Payment method |
| `ZLSPR` | Payment block key (blank = not blocked) |
| `XBLNR` | Reference document number (vendor's invoice number) |
| `SGTXT` | Item text |
| `AUGBL` | Clearing document number — **blank = still open** |
| `AUGDT` | Clearing date |

```java
public static List<Map<String, String>> getApOpenItemsEcc(
        JCoDestination dest, String companyCode, String vendorNo, String keyDate)
        throws JCoException {
    if (keyDate == null) keyDate = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));

    JCoFunction bapi = dest.getRepository().getFunction("BAPI_AP_ACC_GETOPENITEMS");
    bapi.getImportParameterList().setValue("COMPANYCODE", companyCode);
    bapi.getImportParameterList().setValue("VENDOR",      String.format("%10s", vendorNo).replace(' ', '0'));
    bapi.getImportParameterList().setValue("KEYDATE",     keyDate);
    bapi.execute(dest);

    JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
    for (int i = 0; i < returnTable.getNumRows(); i++) {
        returnTable.setRow(i);
        if ("E".equals(returnTable.getString("TYPE")) || "A".equals(returnTable.getString("TYPE"))) {
            throw new RuntimeException("BAPI_AP_ACC_GETOPENITEMS error: " + returnTable.getString("MESSAGE"));
        }
    }

    List<Map<String, String>> result = new ArrayList<>();
    JCoTable items = bapi.getTableParameterList().getTable("OPEN_ITEMS");
    for (int i = 0; i < items.getNumRows(); i++) {
        items.setRow(i);
        if (!items.getString("AUGBL").isBlank()) continue;  // cleared items — skip
        Map<String, String> row = new LinkedHashMap<>();
        row.put("belnr",    items.getString("BELNR"));
        row.put("gjahr",    items.getString("GJAHR"));
        row.put("buzei",    items.getString("BUZEI"));
        row.put("blart",    items.getString("BLART"));
        row.put("budat",    items.getString("BUDAT"));
        row.put("bldat",    items.getString("BLDAT"));
        row.put("amount",   items.getString("WRBTR"));
        row.put("currency", items.getString("WAERS"));
        row.put("zfbdt",    items.getString("ZFBDT"));
        row.put("zterm",    items.getString("ZTERM"));
        row.put("xblnr",    items.getString("XBLNR"));
        row.put("sgtxt",    items.getString("SGTXT"));
        row.put("zlspr",    items.getString("ZLSPR"));  // payment block
        result.add(row);
    }
    return result;
}
```

### 10.2 Read AR Open Items — `BAPI_AR_ACC_GETOPENITEMS`

Identical structure to the AP variant; substitute `VENDOR` with `CUSTOMER`. The output table type is `BAPIACAR09`.

| Parameter | Type | Description |
|---|---|---|
| `COMPANYCODE` | Import | 4-char company code |
| `CUSTOMER` | Import | 10-char customer number (zero-padded) |
| `KEYDATE` | Import | Items open as of this date |
| `OPEN_ITEMS` | Table | Output — type `BAPIACAR09` |

```java
public static List<Map<String, String>> getArOpenItemsEcc(
        JCoDestination dest, String companyCode, String customerNo, String keyDate)
        throws JCoException {
    if (keyDate == null) keyDate = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));

    JCoFunction bapi = dest.getRepository().getFunction("BAPI_AR_ACC_GETOPENITEMS");
    bapi.getImportParameterList().setValue("COMPANYCODE", companyCode);
    bapi.getImportParameterList().setValue("CUSTOMER",    String.format("%10s", customerNo).replace(' ', '0'));
    bapi.getImportParameterList().setValue("KEYDATE",     keyDate);
    bapi.execute(dest);

    JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
    for (int i = 0; i < returnTable.getNumRows(); i++) {
        returnTable.setRow(i);
        if ("E".equals(returnTable.getString("TYPE")) || "A".equals(returnTable.getString("TYPE"))) {
            throw new RuntimeException("BAPI_AR_ACC_GETOPENITEMS error: " + returnTable.getString("MESSAGE"));
        }
    }

    List<Map<String, String>> result = new ArrayList<>();
    JCoTable items = bapi.getTableParameterList().getTable("OPEN_ITEMS");
    for (int i = 0; i < items.getNumRows(); i++) {
        items.setRow(i);
        if (!items.getString("AUGBL").isBlank()) continue;
        Map<String, String> row = new LinkedHashMap<>();
        row.put("belnr",    items.getString("BELNR"));
        row.put("gjahr",    items.getString("GJAHR"));
        row.put("buzei",    items.getString("BUZEI"));
        row.put("blart",    items.getString("BLART"));
        row.put("budat",    items.getString("BUDAT"));
        row.put("amount",   items.getString("WRBTR"));
        row.put("currency", items.getString("WAERS"));
        row.put("zfbdt",    items.getString("ZFBDT"));
        row.put("zterm",    items.getString("ZTERM"));
        row.put("xblnr",    items.getString("XBLNR"));
        row.put("augbl",    items.getString("AUGBL"));  // keep for AR ageing analysis
        result.add(row);
    }
    return result;
}
```

### 10.3 Read Vendor Payment Terms — `BAPI_VENDOR_GETDETAIL`

On ECC, `API_BUSINESS_PARTNER` does not exist. Use `BAPI_VENDOR_GETDETAIL` to retrieve vendor master and company-level data.

| Parameter | Type | Structure |
|---|---|---|
| `VENDORACCOUNTNUMBER` | Import | 10-char, zero-padded |
| `COMPANYCODE` | Import | 4-char company code |
| `VENDORGENERAL` | Export | `BAPILFA1` — general data (NAME1, LAND1, STCD1) |
| `VENDORCOMPANY` | Export | `BAPILVAP1` — company-level data |

**Key fields from `VENDORCOMPANY` (`BAPILVAP1`)**:

| Field | Description |
|---|---|
| `ZTERM` | Payment terms key |
| `ZAHLS` | Payment method |
| `HBKID` | House bank key |
| `AKONT` | Reconciliation account (GL) |
| `BUSAB` | Accounting clerk |
| `ZWELS` | Permitted payment methods (string of single-char codes) |

```java
public static Map<String, String> getVendorPaymentTermsEcc(
        JCoDestination dest, String companyCode, String vendorNo)
        throws JCoException {
    JCoFunction bapi = dest.getRepository().getFunction("BAPI_VENDOR_GETDETAIL");
    bapi.getImportParameterList().setValue("VENDORACCOUNTNUMBER", String.format("%10s", vendorNo).replace(' ', '0'));
    bapi.getImportParameterList().setValue("COMPANYCODE", companyCode);
    bapi.execute(dest);

    JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
    for (int i = 0; i < returnTable.getNumRows(); i++) {
        returnTable.setRow(i);
        if ("E".equals(returnTable.getString("TYPE")) || "A".equals(returnTable.getString("TYPE"))) {
            throw new RuntimeException("BAPI_VENDOR_GETDETAIL error: " + returnTable.getString("MESSAGE"));
        }
    }

    JCoStructure comp = bapi.getExportParameterList().getStructure("VENDORCOMPANY");
    JCoStructure gen  = bapi.getExportParameterList().getStructure("VENDORGENERAL");
    Map<String, String> result = new LinkedHashMap<>();
    result.put("vendor_no",      String.format("%10s", vendorNo).replace(' ', '0'));
    result.put("name",           gen.getString("NAME1"));
    result.put("zterm",          comp.getString("ZTERM"));
    result.put("payment_method", comp.getString("ZAHLS"));
    result.put("house_bank",     comp.getString("HBKID"));
    result.put("recon_account",  comp.getString("AKONT"));
    return result;
}
```

### 10.4 Read Customer Payment Terms — `BAPI_CUSTOMER_GETDETAIL1`

| Parameter | Type | Description |
|---|---|---|
| `CUSTOMERNO` | Import | 10-char customer number (zero-padded) |
| `COMPANYCODE` | Import | 4-char company code |
| `CUSTOMERCOMPANY` | Export | Company-level data |
| `CUSTOMERGENERAL` | Export | General data (NAME1, address) |

**Key fields from `CUSTOMERCOMPANY`**:

| Field | Description |
|---|---|
| `PMNTTRMS` | Payment terms key |
| `PAYMENT_METH` | Payment method |
| `CRED_LIMIT` | Credit limit (numeric string) |
| `CREDITGROUP` | Credit group |
| `AKONT` | Reconciliation account |

```java
public static Map<String, Object> getCustomerPaymentTermsEcc(
        JCoDestination dest, String companyCode, String customerNo)
        throws JCoException {
    JCoFunction bapi = dest.getRepository().getFunction("BAPI_CUSTOMER_GETDETAIL1");
    bapi.getImportParameterList().setValue("CUSTOMERNO",  String.format("%10s", customerNo).replace(' ', '0'));
    bapi.getImportParameterList().setValue("COMPANYCODE", companyCode);
    bapi.execute(dest);

    JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
    for (int i = 0; i < returnTable.getNumRows(); i++) {
        returnTable.setRow(i);
        if ("E".equals(returnTable.getString("TYPE")) || "A".equals(returnTable.getString("TYPE"))) {
            throw new RuntimeException("BAPI_CUSTOMER_GETDETAIL1 error: " + returnTable.getString("MESSAGE"));
        }
    }

    JCoStructure comp = bapi.getExportParameterList().getStructure("CUSTOMERCOMPANY");
    JCoStructure gen  = bapi.getExportParameterList().getStructure("CUSTOMERGENERAL");
    Map<String, Object> result = new LinkedHashMap<>();
    result.put("customer_no",    String.format("%10s", customerNo).replace(' ', '0'));
    result.put("name",           gen.getString("NAME1"));
    result.put("zterm",          comp.getString("PMNTTRMS"));
    result.put("payment_method", comp.getString("PAYMENT_METH"));
    String credLimit = comp.getString("CRED_LIMIT");
    result.put("cred_limit",     Double.parseDouble(credLimit == null || credLimit.isBlank() ? "0" : credLimit));
    result.put("recon_account",  comp.getString("AKONT"));
    return result;
}
```

### 10.5 Create MM-Based Supplier Invoice — `BAPI_INCOMINGINVOICE_CREATE`

On ECC, `API_SUPPLIERINVOICE_PROCESS_SRV` is not available. Use `BAPI_INCOMINGINVOICE_CREATE` for purchase-order-referenced invoices (logistics invoice verification — LIV).

**`HEADERDATA` fields (structure `BAPI_INCINV_CREATE_HEADER`)**:

| Field | Description |
|---|---|
| `INVOICE_IND` | `'X'` = invoice; `''` = credit memo |
| `DOC_TYPE` | `RE` (LIV standard) or `KR` (FI-only vendor invoice) |
| `DOC_DATE` | Vendor invoice date (`YYYYMMDD`) |
| `PSTNG_DATE` | Posting date (`YYYYMMDD`) |
| `COMP_CODE` | 4-char company code |
| `GROSS_AMOUNT` | Invoice gross amount including tax (numeric string) |
| `CURRENCY` | Document currency (ISO 3-char) |
| `CALC_TAX_IND` | `'X'` = SAP auto-calculates tax from `TAX_CODE` |
| `BLINE_DATE` | Baseline date for payment terms (`YYYYMMDD`) |
| `REF_DOC_NO` | External invoice reference — stored in `BKPF.XBLNR` (max 16 chars) |
| `HEADER_TXT` | Header text (max 25 chars) |

**`ITEMDATA` fields (structure `BAPI_INCINV_CREATE_ITEM`)** — one row per PO line:

| Field | Description |
|---|---|
| `INVOICE_DOC_ITEM` | Sequential item counter (0001, 0002…) |
| `PO_NUMBER` | Purchase order number (10-char, zero-padded) |
| `PO_ITEM` | PO line item (00010, 00020…) |
| `TAX_CODE` | Input tax code (e.g. `V1`, `VN`, `V0`) |
| `ITEM_AMOUNT` | Net amount for this PO line (numeric string) |
| `QUANTITY` | Invoiced quantity |
| `PO_UNIT` | Unit of measure |

```java
/**
 * Create MM-based supplier invoice on ECC via BAPI_INCOMINGINVOICE_CREATE.
 * Returns the SAP invoice document number (INVOICEDOCNUMBER).
 * Throws RuntimeException on BAPI error or blank document number after commit.
 *
 * @param poItems List of maps with keys: po_number, po_item, amount, qty, uom, tax_code
 */
public static String createSupplierInvoiceEcc(
        JCoDestination dest,
        String companyCode,
        String docDate,          // "YYYYMMDD"
        String postingDate,      // "YYYYMMDD"
        double grossAmount,
        String currency,
        String refDocNo,         // vendor's invoice number (max 16 chars → XBLNR)
        List<Map<String, Object>> poItems,
        String baselineDate,     // nullable — defaults to postingDate
        String headerText)
        throws JCoException {

    JCoFunction bapi = dest.getRepository().getFunction("BAPI_INCOMINGINVOICE_CREATE");

    JCoStructure header = bapi.getImportParameterList().getStructure("HEADERDATA");
    header.setValue("INVOICE_IND",  "X");
    header.setValue("DOC_TYPE",     "RE");
    header.setValue("DOC_DATE",     docDate);
    header.setValue("PSTNG_DATE",   postingDate);
    header.setValue("COMP_CODE",    companyCode);
    header.setValue("GROSS_AMOUNT", String.valueOf(grossAmount));
    header.setValue("CURRENCY",     currency);
    header.setValue("CALC_TAX_IND", "X");
    header.setValue("BLINE_DATE",   baselineDate != null ? baselineDate : postingDate);
    header.setValue("REF_DOC_NO",   refDocNo.length() > 16 ? refDocNo.substring(0, 16) : refDocNo);
    header.setValue("HEADER_TXT",   headerText.length() > 25 ? headerText.substring(0, 25) : headerText);

    JCoTable itemTable = bapi.getTableParameterList().getTable("ITEMDATA");
    Set<String> taxCodes = new LinkedHashSet<>();
    int idx = 1;
    for (Map<String, Object> pi : poItems) {
        itemTable.appendRow();
        itemTable.setValue("INVOICE_DOC_ITEM", String.format("%04d", idx++));
        itemTable.setValue("PO_NUMBER",   String.format("%10s", pi.get("po_number")).replace(' ', '0'));
        itemTable.setValue("PO_ITEM",     String.format("%05d", Integer.parseInt(pi.get("po_item").toString())));
        itemTable.setValue("TAX_CODE",    pi.getOrDefault("tax_code", "").toString());
        itemTable.setValue("ITEM_AMOUNT", pi.get("amount").toString());
        itemTable.setValue("QUANTITY",    pi.getOrDefault("qty", "0").toString());
        itemTable.setValue("PO_UNIT",     pi.getOrDefault("uom", "").toString());
        String tc = pi.getOrDefault("tax_code", "").toString();
        if (!tc.isBlank()) taxCodes.add(tc);
    }

    // Pass tax rows with zero amount; SAP recalculates when CALC_TAX_IND='X'
    JCoTable taxTable = bapi.getTableParameterList().getTable("TAXDATA");
    for (String tc : taxCodes) {
        taxTable.appendRow();
        taxTable.setValue("TAX_CODE",   tc);
        taxTable.setValue("TAX_AMOUNT", "0.00");
    }

    bapi.execute(dest);

    JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
    for (int i = 0; i < returnTable.getNumRows(); i++) {
        returnTable.setRow(i);
        if ("E".equals(returnTable.getString("TYPE")) || "A".equals(returnTable.getString("TYPE"))) {
            throw new RuntimeException("BAPI_INCOMINGINVOICE_CREATE failed: " + returnTable.getString("MESSAGE"));
        }
    }

    JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
    commit.getImportParameterList().setValue("WAIT", "X");
    commit.execute(dest);

    String invDoc = bapi.getExportParameterList().getString("INVOICEDOCNUMBER").strip();
    if (invDoc.isBlank()) {
        throw new RuntimeException(
            "BAPI_INCOMINGINVOICE_CREATE: blank INVOICEDOCNUMBER after commit — " +
            "check RBKP table manually");
    }
    return invDoc;
}
```

> **Post-commit verification**: After calling `BAPI_TRANSACTION_COMMIT`, re-read `RBKP` (LIV invoice header table) via `RFC_READ_TABLE` to confirm `BELNR = inv_doc` exists. A successful commit call does not guarantee persistence if a parallel session triggered a rollback.

### 10.6 Bulk Extract Accounting Documents — `RFC_READ_TABLE`

For FSSC reconciliation (nightly GL balance sync, aged-item reports), `RFC_READ_TABLE` is the universal ECC read path when no specific BAPI exists for the required fields.

> **512-byte row limit**: `RFC_READ_TABLE` serialises each record into a 512-byte string. `BSEG` rows are wide — always pass a narrow `FIELDS` list to stay within the limit. For production FSSC, replace `RFC_READ_TABLE` on `BSEG` with a custom function module (`Z_RFC_READ_FI_ITEMS`) that uses a typed table and server-side `SELECT` with proper indexing.

**Read `BKPF` (accounting document header)**:

```java
public static List<Map<String, String>> readBkpf(
        JCoDestination dest,
        String companyCode,
        String fiscalYear,
        List<String> docTypes,   // nullable
        String fromDate,         // "YYYYMMDD", nullable
        String toDate)           // "YYYYMMDD", nullable
        throws JCoException {

    JCoFunction bapi = dest.getRepository().getFunction("RFC_READ_TABLE");
    bapi.getImportParameterList().setValue("QUERY_TABLE", "BKPF");
    bapi.getImportParameterList().setValue("DELIMITER",   "|");
    bapi.getImportParameterList().setValue("ROWCOUNT",    0);   // 0 = no row limit

    JCoTable fields = bapi.getTableParameterList().getTable("FIELDS");
    for (String f : new String[]{"BELNR","BUKRS","GJAHR","BLART","BUDAT","BLDAT","WAERS","XBLNR","BKTXT","USNAM"}) {
        fields.appendRow();
        fields.setValue("FIELDNAME", f);
    }

    JCoTable options = bapi.getTableParameterList().getTable("OPTIONS");
    options.appendRow(); options.setValue("TEXT", "BUKRS EQ '" + companyCode + "'");
    options.appendRow(); options.setValue("TEXT", "AND GJAHR EQ '" + fiscalYear + "'");
    if (docTypes != null && !docTypes.isEmpty()) {
        String blartFilter = docTypes.stream()
            .map(dt -> "BLART EQ '" + dt + "'").collect(Collectors.joining(" OR "));
        options.appendRow(); options.setValue("TEXT", "AND ( " + blartFilter + " )");
    }
    if (fromDate != null) { options.appendRow(); options.setValue("TEXT", "AND BUDAT GE '" + fromDate + "'"); }
    if (toDate   != null) { options.appendRow(); options.setValue("TEXT", "AND BUDAT LE '" + toDate   + "'"); }

    bapi.execute(dest);

    JCoTable fieldsOut = bapi.getTableParameterList().getTable("FIELDS");
    List<String> colNames = new ArrayList<>();
    for (int i = 0; i < fieldsOut.getNumRows(); i++) {
        fieldsOut.setRow(i);
        colNames.add(fieldsOut.getString("FIELDNAME"));
    }

    List<Map<String, String>> result = new ArrayList<>();
    JCoTable data = bapi.getTableParameterList().getTable("DATA");
    for (int i = 0; i < data.getNumRows(); i++) {
        data.setRow(i);
        String[] vals = data.getString("WA").split("\\|");
        Map<String, String> row = new LinkedHashMap<>();
        for (int j = 0; j < colNames.size(); j++) {
            row.put(colNames.get(j), j < vals.length ? vals[j].strip() : "");
        }
        result.add(row);
    }
    return result;
}
```

**Read `BSEG` line items for a single document**:

```java
public static List<Map<String, String>> readBsegForDoc(
        JCoDestination dest, String companyCode, String belnr, String gjahr)
        throws JCoException {

    JCoFunction bapi = dest.getRepository().getFunction("RFC_READ_TABLE");
    JCoParameterList imp = bapi.getImportParameterList();
    imp.setValue("QUERY_TABLE", "BSEG");
    imp.setValue("DELIMITER", "|");

    // BSEG is a cluster table — keep FIELDS list narrow to stay within 512-byte row limit
    String[] fields = {
        "BELNR", "BUKRS", "GJAHR", "BUZEI", "HKONT",
        "WRBTR", "DMBTR", "WAERS", "SHKZG", "KOSTL",
        "AUFNR", "LIFNR", "KUNNR", "SGTXT"
    };
    JCoTable fieldsIn = bapi.getTableParameterList().getTable("FIELDS");
    for (String f : fields) {
        fieldsIn.appendRow();
        fieldsIn.setValue("FIELDNAME", f);
    }

    JCoTable options = bapi.getTableParameterList().getTable("OPTIONS");
    options.appendRow(); options.setValue("TEXT", "BUKRS EQ '" + companyCode + "'");
    options.appendRow(); options.setValue("TEXT", "AND BELNR EQ '" + belnr + "'");
    options.appendRow(); options.setValue("TEXT", "AND GJAHR EQ '" + gjahr + "'");

    bapi.execute(dest);

    JCoTable fieldsOut = bapi.getTableParameterList().getTable("FIELDS");
    List<String> colNames = new ArrayList<>();
    for (int i = 0; i < fieldsOut.getNumRows(); i++) {
        fieldsOut.setRow(i);
        colNames.add(fieldsOut.getString("FIELDNAME"));
    }

    List<Map<String, String>> result = new ArrayList<>();
    JCoTable data = bapi.getTableParameterList().getTable("DATA");
    for (int i = 0; i < data.getNumRows(); i++) {
        data.setRow(i);
        String[] vals = data.getString("WA").split("\\|");
        Map<String, String> row = new LinkedHashMap<>();
        for (int j = 0; j < colNames.size(); j++) {
            row.put(colNames.get(j), j < vals.length ? vals[j].strip() : "");
        }
        // SHKZG='S' = debit (positive), 'H' = credit (negative)
        String wrb = row.getOrDefault("WRBTR", "").isBlank() ? "0" : row.get("WRBTR");
        double sign = "S".equals(row.get("SHKZG")) ? 1.0 : -1.0;
        row.put("amount_signed", String.valueOf(sign * Double.parseDouble(wrb)));
        result.add(row);
    }
    return result;
}
```

> **ECC vs S/4HANA summary table**:
>
> | Operation | S/4HANA path | ECC 6.0 path |
> |---|---|---|
> | Query AP open items | OData `API_OPLACCTGDOCITEMCUBE_SRV` | JCo `BAPI_AP_ACC_GETOPENITEMS` |
> | Query AR open items | OData `API_OPLACCTGDOCITEMCUBE_SRV` | JCo `BAPI_AR_ACC_GETOPENITEMS` |
> | Read vendor master / payment terms | OData `API_BUSINESS_PARTNER` | JCo `BAPI_VENDOR_GETDETAIL` |
> | Read customer master / payment terms | OData `API_BUSINESS_PARTNER` | JCo `BAPI_CUSTOMER_GETDETAIL1` |
> | Create MM supplier invoice | OData `API_SUPPLIERINVOICE_PROCESS_SRV` | JCo `BAPI_INCOMINGINVOICE_CREATE` |
> | Post FI document (KR/DR/KZ/KG) | JCo `BAPI_ACC_DOCUMENT_POST` | Same |
> | Bulk GL extract | OData or AMDP | JCo `RFC_READ_TABLE` on BKPF/BSEG |

---

## 11. Common Pitfalls

1. **Amount sign errors — the most common mistake**: Always verify two things: (a) the **sum of all `AMT_DOCCUR` = zero** across all CURRENCYAMOUNT entries; (b) credits use negative, debits use positive. Error `F5701` = balanced-posting failure. Sign quick reference: KR vendor invoice → vendor `-`, expense `+`; KZ vendor payment → vendor `+`, bank `-`; DR customer invoice → customer `+`, revenue `-`.

2. **`BAPI_TRANSACTION_COMMIT` is non-negotiable**: After every successful `BAPI_ACC_DOCUMENT_POST` that is NOT a parked document (`DOC_STATUS = '2'`), call `BAPI_TRANSACTION_COMMIT` with `WAIT="X"`. Without it, the changes are silently rolled back when the connection closes.

3. **Account number must be 10-digit zero-padded**: SAP account numbers are always 10 characters. Vendor `100000` must be passed as `"0000100000"`. Failing to zero-pad causes a `VENDOR_NO not found` error. Python: `vendor_no.zfill(10)`.

4. **Cost center required for expense accounts**: GL accounts configured as cost elements require `COSTCENTER` or `ORDERID` in ACCOUNTGL. Missing this causes `KI235` or `F5117`. Verify the field status group of the account in `FS00`.

5. **`API_OPLACCTGDOCITEMCUBE_SRV` is S/4HANA only**: This OData service does not exist in ECC. For ECC, use JCo: `BAPI_AP_ACC_GETOPENITEMS` (AP) or `BAPI_AR_ACC_GETOPENITEMS` (AR).

6. **`OBJ_KEY` parsing**: The document number is returned in `OBJ_KEY`, not in a dedicated export parameter. Parse it as: `company_code = obj_key[0:4]`, `fiscal_year = obj_key[4:8]`, `doc_number = obj_key[8:]`. An empty `OBJ_KEY` means the posting failed — always check the `RETURN` table first.

7. **CSRF token required for OData writes**: `API_SUPPLIERINVOICE_PROCESS_SRV` POST operations require a valid CSRF token. Fetch it with a GET + `x-csrf-token: Fetch` header. Tokens expire after the SAP session timeout (typically 30–60 minutes). On `403 Forbidden`, re-fetch and retry once.

8. **Open posting period**: The `PSTNG_DATE` must fall within an open fiscal period. Check open periods with `OB52`. Posting into a closed period returns `F5 201`. During FSSC month-end, always validate the SAP calendar before initiating bulk postings.
