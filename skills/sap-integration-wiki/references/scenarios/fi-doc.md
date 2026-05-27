# FI: Financial Document Integration

## Table of Contents

1. [Scenario Overview](#scenario-overview)
2. [Post FI Document via BAPI_ACC_DOCUMENT_POST](#1-post-fi-document-via-bapi_acc_document_post)
3. [Read FI Documents via OData](#2-read-fi-documents-via-odata)
4. [Read GL Posting Detail via RFC](#3-read-gl-posting-detail-via-rfc)
5. [Important Limitations and Recommendations](#4-important-limitations-and-recommendations)
6. [Common Pitfalls](#5-common-pitfalls)

---

## Scenario Overview

| Sub-scenario | S/4HANA On-Prem recommendation | ECC 6.0 recommendation |
|---|---|---|
| Post FI/GL document from external system | `BAPI_ACC_DOCUMENT_POST` via JCo | Same |
| Post vendor invoice | `BAPI_INCOMINGINVOICE_CREATE` via JCo | Same |
| Read FI documents (line items) | OData `API_OPLACCTGDOCITEMCUBE_SRV` or `BAPI_ACC_GL_POSTING_GET_DETAIL` | `BAPI_ACC_GL_POSTING_GET_DETAIL` via JCo |
| Read account balances | RFC `BAPI_GL_GETGLACCCURRENTBALANCE` | Same |
| Clear open items | `BAPI_ACC_DOCUMENT_POST` with clearing | Same |

**Key architectural note**: Direct FI document creation via standard OData is very limited in SAP On-Premise releases. The `API_OPLACCTGDOCITEMCUBE_SRV` OData service is read-only (analytical). For posting, `BAPI_ACC_DOCUMENT_POST` via JCo is the standard and most reliable method across all supported SAP releases.

---

## 1. Post FI Document via BAPI_ACC_DOCUMENT_POST

### BAPI: BAPI_ACC_DOCUMENT_POST

This BAPI is the primary standard interface for posting accounting documents externally. It replaces the older `BAPI_ACC_GL_POSTING_POST`.

**Key import structures:**

| Structure | Description |
|---|---|
| `DOCUMENTHEADER` | Document header (date, type, company code) |
| `CUSTOMERCPD` | Customer one-time account data (optional) |

**Key tables:**

| Table | Description |
|---|---|
| `ACCOUNTGL` | G/L line items |
| `ACCOUNTPAYABLE` | Vendor (AP) line items |
| `ACCOUNTRECEIVABLE` | Customer (AR) line items |
| `CURRENCYAMOUNT` | Amounts per line item and currency |
| `RETURN` | Error/success messages |

### DOCUMENTHEADER required fields

| Field | Description | Example |
|---|---|---|
| `USERNAME` | SAP user posting the doc | `"RFCUSER"` |
| `COMP_CODE` | Company code | `"1000"` |
| `DOC_DATE` | Document date | `"20260430"` |
| `PSTNG_DATE` | Posting date | `"20260430"` |
| `FISC_YEAR` | Fiscal year (leave blank for auto) | `""` |
| `DOC_TYPE` | Document type | `"SA"` (GL), `"KR"` (vendor invoice), `"DR"` (customer invoice) |
| `REF_DOC_NO` | Reference document number | `"EXT-INV-001"` |

### Java example: Post simple GL document (debit/credit pair)

```java
import com.sap.conn.jco.*;
import java.math.BigDecimal;

public class PostGLDocument {

    public static String postDocument(JCoDestination dest) throws JCoException {

        JCoFunction bapi = dest.getRepository().getFunction("BAPI_ACC_DOCUMENT_POST");

        // --- Document Header ---
        JCoStructure header = bapi.getImportParameterList().getStructure("DOCUMENTHEADER");
        header.setValue("USERNAME",   "RFCUSER");
        header.setValue("COMP_CODE",  "1000");
        header.setValue("DOC_DATE",   "20260430");
        header.setValue("PSTNG_DATE", "20260430");
        header.setValue("DOC_TYPE",   "SA");
        header.setValue("REF_DOC_NO", "EXT-INV-001");
        header.setValue("HEADER_TXT", "Integration test posting");

        // --- G/L Line Items ---
        JCoTable glItems = bapi.getTableParameterList().getTable("ACCOUNTGL");

        // Debit line (positive amount = debit for expense accounts)
        glItems.appendRow();
        glItems.setValue("ITEMNO_ACC",  "0000000001");
        glItems.setValue("GL_ACCOUNT",  "400000");     // Expense account
        glItems.setValue("COMP_CODE",   "1000");
        glItems.setValue("COSTCENTER",  "10001000");   // Required for expense GL
        glItems.setValue("ITEM_TEXT",   "External service charge");

        // Credit line (negative amount = credit)
        glItems.appendRow();
        glItems.setValue("ITEMNO_ACC",  "0000000002");
        glItems.setValue("GL_ACCOUNT",  "113100");     // Bank/clearing account
        glItems.setValue("COMP_CODE",   "1000");
        glItems.setValue("ITEM_TEXT",   "Payment clearing");

        // --- Currency Amounts (one entry per line item) ---
        JCoTable amounts = bapi.getTableParameterList().getTable("CURRENCYAMOUNT");

        // Amount for item 1 (debit: positive)
        amounts.appendRow();
        amounts.setValue("ITEMNO_ACC",  "0000000001");
        amounts.setValue("CURRENCY",    "USD");
        amounts.setValue("AMT_DOCCUR",  new BigDecimal("1500.00"));
        amounts.setValue("CURRENCY_ISO","USD");

        // Amount for item 2 (credit: negative)
        amounts.appendRow();
        amounts.setValue("ITEMNO_ACC",  "0000000002");
        amounts.setValue("CURRENCY",    "USD");
        amounts.setValue("AMT_DOCCUR",  new BigDecimal("-1500.00"));
        amounts.setValue("CURRENCY_ISO","USD");

        // --- Execute ---
        bapi.execute(dest);

        // --- ALWAYS commit ---
        JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
        commit.getImportParameterList().setValue("WAIT", "X");
        commit.execute(dest);

        // --- Check RETURN ---
        JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
        String docNumber = "";
        for (int i = 0; i < returnTable.getNumRows(); i++) {
            returnTable.setRow(i);
            String type = returnTable.getString("TYPE");
            String msg  = returnTable.getString("MESSAGE");
            if ("E".equals(type) || "A".equals(type)) {
                throw new RuntimeException("FI posting failed: " + msg);
            }
            // Document number is in the return message for successful posts
            if ("S".equals(type) && msg.contains("Document")) {
                docNumber = returnTable.getString("MESSAGE_V2"); // often in V2 field
            }
        }

        // The document number is also in OBJECTSYS table
        JCoTable objects = bapi.getTableParameterList().getTable("RETURN");
        System.out.println("Document posted successfully");
        return docNumber;
    }
}
```

**SAP verification**: Transaction `FB03` → enter company code + document number → verify line items and amounts.

---

## 2. Read FI Documents via OData

### API_OPLACCTGDOCITEMCUBE_SRV (S/4HANA only, read-only)

This is an analytical OData service for reporting on accounting document line items. It is read-only and cannot be used for posting.

**Service**: `API_OPLACCTGDOCITEMCUBE_SRV`  
**Entity set**: `A_OperationalAcctgDocItemCube`

```bash
# Query FI documents for company code 1000, fiscal year 2026
curl -u "APIUSER:password" \
  -H "Accept: application/json" \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_OPLACCTGDOCITEMCUBE_SRV/\
A_OperationalAcctgDocItemCube?\
\$filter=CompanyCode eq '1000' and FiscalYear eq '2026'\
and ReferenceDocument eq 'EXT-INV-001'\
&\$select=CompanyCode,AccountingDocument,FiscalYear,PostingDate,\
DocumentItemText,AmountInCompanyCodeCurrency,CompanyCodeCurrency,\
GLAccount,CostCenter\
&\$top=50\
&\$format=json"
```

**Availability**: This service is available in S/4HANA On-Premise 1809+. Not available in ECC.

---

## 3. Read GL Posting Detail via RFC

### BAPI_ACC_GL_POSTING_GET_DETAIL (ECC and S/4HANA)

```java
JCoFunction bapi = dest.getRepository().getFunction("BAPI_ACC_GL_POSTING_GET_DETAIL");
bapi.getImportParameterList().setValue("COMPANYCODE", "1000");
bapi.getImportParameterList().setValue("DOCUMENTNO",  "0100000001");
bapi.getImportParameterList().setValue("FISCALYEAR",  "2026");

bapi.execute(dest);

// Document header
JCoStructure docHeader = bapi.getExportParameterList().getStructure("DOCUMENTHEADER");
System.out.println("Doc Date: " + docHeader.getString("DOC_DATE"));
System.out.println("Posting Date: " + docHeader.getString("PSTNG_DATE"));

// Line items
JCoTable glItems = bapi.getTableParameterList().getTable("ACCOUNTGL");
for (int i = 0; i < glItems.getNumRows(); i++) {
    glItems.setRow(i);
    System.out.println(
        "Item: " + glItems.getString("ITEMNO_ACC") +
        " GL: " + glItems.getString("GL_ACCOUNT") +
        " Amount: " + glItems.getString("AMT_DOCCUR")
    );
}
```

### Alternative: BAPI_GL_GETGLACCCURRENTBALANCE (account balance)

```java
JCoFunction bapi = dest.getRepository().getFunction("BAPI_GL_GETGLACCCURRENTBALANCE");
bapi.getImportParameterList().setValue("COMPANYCODE", "1000");
bapi.getImportParameterList().setValue("GL_ACCOUNT",  "400000");
bapi.getImportParameterList().setValue("FISCALYEAR",  "2026");
bapi.execute(dest);

// Returns period-by-period balance
JCoTable balances = bapi.getTableParameterList().getTable("PERIODBALANCES");
for (int i = 0; i < balances.getNumRows(); i++) {
    balances.setRow(i);
    System.out.println(
        "Period: " + balances.getString("PERIOD") +
        " Balance: " + balances.getString("BALANCE_PER")
    );
}
```

---

## 4. Important Limitations and Recommendations

### Why not use OData for FI posting?

As of 2024, there is **no standard SAP OData service** for directly posting a generic GL document in SAP On-Premise releases. The available OData APIs for FI are either:
- **Read-only analytics** (`API_OPLACCTGDOCITEMCUBE_SRV`)
- **Specific process-bound** (e.g., `API_BANKACCOUNTINTERNALID_SRV` for bank master data)

For **vendor invoice posting specifically**, the `API_SUPPLIERINVOICE_PROCESS_SRV` OData V2 service exists in S/4HANA 1809+ and supports creating incoming invoices. But for general FI/GL postings, JCo + `BAPI_ACC_DOCUMENT_POST` remains the standard.

### S/4HANA Cloud Public Edition

In Cloud Public Edition, RFC/JCo access is restricted. FI integration must use:
- **SAP Business Technology Platform (BTP)** with OData V4 services
- **In-App Extensibility** via RAP
- **API Business Hub** services — check `api.sap.com` for your specific release

### Document types and their use

| Document Type | Use case |
|---|---|
| `SA` | G/L account posting |
| `KR` | Vendor invoice |
| `KZ` | Vendor payment |
| `DR` | Customer invoice |
| `DZ` | Customer payment |
| `AA` | Asset posting |
| `AB` | Accounting document (general) |

---

## 5. Common Pitfalls

1. **Debit/credit balance mismatch**: `BAPI_ACC_DOCUMENT_POST` enforces balanced posting. The sum of all `AMT_DOCCUR` values across all line items (GL + AP + AR) must equal zero. Imbalanced documents return error `F5-701`.

2. **Cost center missing for expense GL accounts**: Expense accounts (cost element accounts in CO) require a `COSTCENTER` or `ORDERID` in the line item. Missing this causes error `KI235` or `F5117`. Check account configuration in `FS00` → "Create/Bank/Interest" tab for field status.

3. **Fiscal year mismatch**: If `DOC_DATE` falls in fiscal year 2025 but `PSTNG_DATE` falls in 2026, and the fiscal year 2025 is closed, SAP will reject with period closing error. Always use a posting date in an open period. Check open periods with `OB52`.

4. **Currency translation required**: If posting in foreign currency, SAP needs exchange rate information. Either pass `RATE` in the `CURRENCYAMOUNT` table, or ensure the exchange rate table (`OB08`) has the required rates. Missing rates produce error `FF703`.

5. **Document number in RETURN table**: Unlike other BAPIs, `BAPI_ACC_DOCUMENT_POST` does not have a dedicated export parameter for the document number. The document number appears in the `MESSAGE_V2` field of the success entry in the `RETURN` table, or in the `OBJECTSYS` table. Always parse the RETURN table carefully.
