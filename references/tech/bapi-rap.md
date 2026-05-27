# BAPI and RAP Integration Reference

## Table of Contents

1. [What is a BAPI](#1-what-is-a-bapi)
2. [Key BAPIs by Domain](#2-key-bapis-by-domain)
3. [RAP — RESTful Application Programming](#3-rap--restful-application-programming)
4. [Decision Matrix: BAPI vs OData V2 vs OData V4/RAP](#4-decision-matrix-bapi-vs-odata-v2-vs-odata-v4rap)
5. [Custom BAPI Wrapper Pattern](#5-custom-bapi-wrapper-pattern)
6. [BAPI Browser](#6-bapi-browser)

---

## 1. What is a BAPI

A **BAPI** (Business Application Programming Interface) is a standardized RFC-enabled function module in SAP that exposes a business operation with a stable, documented interface.

BAPIs differ from plain RFC function modules in important ways:

| Aspect | Plain RFC function module | BAPI |
|---|---|---|
| Naming convention | Custom names (e.g., `Z_CREATE_PO`) | `BAPI_<OBJECT>_<METHOD>` (e.g., `BAPI_PO_CREATE1`) |
| Release stability | Not guaranteed | SAP guarantees backward compatibility within a release |
| Commit handling | Developer's choice | Write BAPIs never auto-commit — caller must call `BAPI_TRANSACTION_COMMIT` |
| Registration | Not required | Registered in BAPI Business Object Repository (BOR) — browse with transaction `BAPI` |
| Error handling | Varies | Standardized `RETURN` table with TYPE/ID/NUMBER/MESSAGE |
| Documentation | Optional | SAP provides formal parameter documentation |
| Test tool | `SE37` | `BAPI` transaction browser or `SE37` |

### BAPI commit rule (non-negotiable)

**Every write BAPI call MUST be followed by `BAPI_TRANSACTION_COMMIT`.**

```java
// Write BAPI
bapi.execute(dest);

// MANDATORY — without this, SAP rolls back all changes
JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
commit.getImportParameterList().setValue("WAIT", "X");  // Synchronous commit
commit.execute(dest);
```

Setting `WAIT = "X"` makes the commit synchronous — the call blocks until the commit completes. This is required when your next step depends on the committed data being visible (e.g., reading back the just-created document).

---

## 2. Key BAPIs by Domain

### MM — Materials Management

| BAPI | Description | S/4HANA alternative |
|---|---|---|
| `BAPI_PO_CREATE1` | Create purchase order | OData V2 `API_PURCHASEORDER_PROCESS_SRV` POST |
| `BAPI_PO_CHANGE` | Change PO header/items | OData V2 PATCH |
| `BAPI_PO_GETDETAIL` | Read PO details | OData V2 GET with $expand |
| `BAPI_PO_RELEASE` | Release (approve) PO | OData action `ReleaseApprovalRequest` |
| `BAPI_MATERIAL_STOCK_REQ_LIST` | Read stock quantities | OData V2 `API_MATERIAL_STOCK_SRV` |
| `BAPI_RESERVATION_CREATE1` | Create stock reservation | No standard OData equivalent |
| `BAPI_GOODSMVT_CREATE` | Post goods movement | OData V2 `API_MATERIAL_DOCUMENT_SRV` |
| `BAPI_INCOMINGINVOICE_CREATE` | Create vendor (LIV) invoice | OData V2 `API_SUPPLIERINVOICE_PROCESS_SRV` |
| `BAPI_REQUISITION_CREATE` | Create purchase requisition | OData V2 `API_PURCHASEREQ_PROCESS_SRV` |

### SD — Sales and Distribution

| BAPI | Description | S/4HANA alternative |
|---|---|---|
| `BAPI_SALESORDER_CREATEFROMDAT2` | Create sales order | OData V2 `API_SALES_ORDER_SRV` POST |
| `BAPI_SALESORDER_CHANGE` | Change sales order | OData V2 PATCH |
| `BAPI_SALESORDER_GETLIST` | List sales orders | OData V2 GET |
| `BAPI_SALESORDER_GETSTATUS` | Get sales order status | OData V2 GET with status fields |
| `BAPI_DELIVERY_SAVEREPLICA` | Create outbound delivery | OData V2 `API_OUTBOUND_DELIVERY_SRV` |
| `BAPI_BILLINGDOC_CREATEMULTIPLE` | Create billing document | OData V2 `API_BILLING_DOCUMENT_SRV` |

### FI — Financial Accounting

| BAPI | Description | S/4HANA alternative |
|---|---|---|
| `BAPI_ACC_DOCUMENT_POST` | Post accounting document | No standard OData equivalent for generic posting |
| `BAPI_ACC_GL_POSTING_GET_DETAIL` | Read GL document details | OData V2 `API_OPLACCTGDOCITEMCUBE_SRV` (read-only) |
| `BAPI_GL_GETGLACCCURRENTBALANCE` | Read GL account balance | OData V2 `API_GLACCOUNTBALANCE_SRV` |
| `BAPI_ACC_INVOICE_RECEIPT_POST` | Post invoice receipt (MIRO) | OData V2 `API_SUPPLIERINVOICE_PROCESS_SRV` |
| `BAPI_OUTGOING_PAYMENT_CREATE` | Create outgoing payment | Requires FI Accounts Payable config |
| `BAPI_TRANSACTION_COMMIT` | Commit LUW | Required after all write BAPIs |
| `BAPI_TRANSACTION_ROLLBACK` | Rollback LUW | Use in error handling after write BAPIs |

### CO — Controlling

| BAPI | Description |
|---|---|
| `BAPI_COSTCENTER_GETDETAIL` | Read cost center master data |
| `BAPI_INTERNALORDER_GETDETAIL` | Read internal order details |
| `BAPI_ACTIVITYPRICE_GET` | Read activity price for cost center/activity type |

---

## 3. RAP — RESTful Application Programming

### What is RAP

RAP (RESTful Application Programming) is the modern SAP programming model introduced with S/4HANA 1809. It replaces the classic CRUD+Search programming model for OData services.

RAP services:
- Are exposed natively as **OData V4** services
- Are built on CDS (Core Data Services) views
- Follow strict conventions for entity relationships, actions, and functions
- Support optimistic locking (ETag), delta tokens, and deep operations natively

### SRVD_A2X suffix explained

When you see a service URL like:
```
/sap/opu/odata4/sap/api_purchaseorder/srvd_a2x/sap/purchaseorder/0001/
```

The `srvd_a2x` part means:
- **SRVD**: Service Definition (the CDS annotation that exposes the service)
- **A2X**: "Application-to-X" = generic external consumer scenario (as opposed to A2A = application-to-application UI scenario)

This distinguishes API-oriented services (A2X) from Fiori UI services (A2A), even if they serve the same underlying data model.

### How OData V4 services are exposed in S/4HANA

1. Developer creates a CDS view annotated with `@OData.publish: true` or creates a Service Definition object (SRVD)
2. Runs transaction `SOAMANAGER` or uses ADT (Eclipse) to activate the service
3. Service appears in `/IWFND/MAINT_SERVICE` or can be browsed at:
   ```
   https://host:port/sap/opu/odata4/
   ```

### RAP action imports

OData V4 services support "Actions" and "Functions" — equivalent to V2 Function Imports:

```bash
# V2 Function Import example
POST /sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/ReleaseApprovalRequest?...

# V4 Action (Bound action on entity)
POST /sap/opu/odata4/sap/api_purchaseorder/srvd_a2x/sap/purchaseorder/0001/\
PurchaseOrder('4500012345')/com.sap.gateway.srvd_a2x.api_purchaseorder.v0001.Release
```

---

## 4. Decision Matrix: BAPI vs OData V2 vs OData V4/RAP

| Criterion | BAPI via JCo | OData V2 | OData V4 / RAP |
|---|---|---|---|
| **ECC 6.0** | Best choice | Not available (standard) | Not available |
| **S/4HANA On-Prem 1909–2022** | Works; use OData if available | Recommended for standard objects | Partially available |
| **S/4HANA On-Prem 2023+** | Works; some BAPIs deprecated | Some APIs deprecated (SAP Note 3502308) | Expanding; preferred for new APIs |
| **S/4HANA Cloud Public** | Not available externally | Limited | Primary and only method |
| **Consumer language** | Java/JVM (JCo); other languages via proxy (see `rfc-jco.md §9`) | Any HTTP client | Any HTTP client |
| **Complexity** | Medium (JCo setup + X-structures) | Low (REST + JSON) | Low (REST + JSON, cleaner) |
| **Bulk/batch operations** | Efficient | $batch (limited) | $batch JSON format |
| **FI document posting** | Required (no OData alternative) | N/A | N/A |
| **Standard API availability** | Always (BAPI exists for most objects) | Check api.sap.com | Check api.sap.com (newer services) |
| **Long-term roadmap** | Legacy (still supported) | Being replaced by V4 | SAP's strategic direction |
| **Error details** | RETURN table (detailed) | `innererror` in JSON | `error` in JSON |

### Quick selection flowchart

```
Is the SAP system ECC 6.0?
  YES → BAPI via JCo

Is the SAP system S/4HANA Cloud Public Edition?
  YES → OData V4 / RAP only

Is the SAP system S/4HANA On-Premise?
  Does a standard OData V2 or V4 API exist for this operation?
    YES → Use OData (prefer V4 if available in your release)
    NO → Use BAPI via JCo

Is FI document posting required (GL, vendor invoice)?
  YES → BAPI_ACC_DOCUMENT_POST via JCo (regardless of version)
```

---

## 5. Custom BAPI Wrapper Pattern

When no standard BAPI or OData API exists for your business requirement, the standard SAP pattern is to create a **custom RFC-enabled function module** wrapping your ABAP business logic.

This pattern is called "Custom BAPI Wrapper" and follows BAPI conventions:

### ABAP function module template

```abap
FUNCTION Z_CREATE_CUSTOM_OBJECT
  IMPORTING
    VALUE(IV_COMPANY_CODE) TYPE BUKRS
    VALUE(IV_REFERENCE)    TYPE XBLNR
    IS_HEADER              TYPE ZS_CUSTOM_HEADER
  EXPORTING
    EV_DOCUMENT_NUMBER     TYPE BELNR_D
  TABLES
    IT_LINE_ITEMS          STRUCTURE ZS_CUSTOM_ITEM
    ET_RETURN              STRUCTURE BAPIRET2
  EXCEPTIONS
    INPUT_ERROR            = 1
    SYSTEM_ERROR           = 2
    OTHERS                 = 3.

  "--- Input validation ---
  IF IV_COMPANY_CODE IS INITIAL.
    APPEND INITIAL LINE TO ET_RETURN ASSIGNING FIELD-SYMBOL(<ls_return>).
    <ls_return>-TYPE    = 'E'.
    <ls_return>-ID      = 'ZZ'.
    <ls_return>-NUMBER  = '001'.
    <ls_return>-MESSAGE = 'Company code is required'.
    RETURN.
  ENDIF.

  "--- Business logic here ---
  " ... call SAP standard function modules ...

  "--- Return success ---
  APPEND INITIAL LINE TO ET_RETURN ASSIGNING <ls_return>.
  <ls_return>-TYPE    = 'S'.
  <ls_return>-MESSAGE = TEXT-001.  "Document & created successfully"

ENDFUNCTION.
```

### Key requirements for a custom BAPI wrapper

1. **Remote-Enabled**: In `SE37`, set "Remote-enabled module" = `RFC` on the Attributes tab
2. **Pass-by-value for imports**: All `IMPORTING` parameters must be `VALUE(...)` to prevent pass-by-reference across RFC boundary
3. **RETURN table**: Use `BAPIRET2` structure for the return table (matches standard BAPI convention)
4. **No COMMIT WORK in BAPI**: Never call `COMMIT WORK` inside the function module. The caller must call `BAPI_TRANSACTION_COMMIT` explicitly.
5. **Flat structures**: RFC cannot pass internal tables with nested types or references. Keep all types flat (elementary fields only)
6. **Unicode-compatible**: Ensure no character set issues for cross-system calls

### Calling from Java

```java
JCoFunction customBapi = dest.getRepository().getFunction("Z_CREATE_CUSTOM_OBJECT");

customBapi.getImportParameterList().setValue("IV_COMPANY_CODE", "1000");
customBapi.getImportParameterList().setValue("IV_REFERENCE",    "EXT-REF-001");

JCoStructure header = customBapi.getImportParameterList().getStructure("IS_HEADER");
header.setValue("FIELD1", "value1");
header.setValue("FIELD2", "value2");

JCoTable lineItems = customBapi.getTableParameterList().getTable("IT_LINE_ITEMS");
lineItems.appendRow();
lineItems.setValue("ITEM_NO",  "0001");
lineItems.setValue("MATERIAL", "MAT001");
lineItems.setValue("QUANTITY", new java.math.BigDecimal("5"));

customBapi.execute(dest);

// Always commit
JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
commit.getImportParameterList().setValue("WAIT", "X");
commit.execute(dest);

String docNumber = customBapi.getExportParameterList().getString("EV_DOCUMENT_NUMBER");
```

---

## 6. BAPI Browser

Transaction `BAPI` in SAP provides a graphical browser of all registered Business Objects and their methods (BAPIs).

**Navigation:**
1. Transaction `BAPI`
2. Expand the Business Object Repository tree on the left
3. Navigate by: Cross-Application Components / Accounting / Logistics / etc.
4. Select a business object (e.g., `PurchaseOrder`)
5. Expand Methods → select a BAPI (e.g., `CreateFromData1`)
6. Click **Detail** to see all parameters, tables, and documentation

**Alternative**: Transaction `SE37` → enter BAPI name → `F8` to test/execute interactively in development systems.
