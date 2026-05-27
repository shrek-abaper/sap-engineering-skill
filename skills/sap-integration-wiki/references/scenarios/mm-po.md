# MM: Purchase Order Integration

## Table of Contents

1. [Scenario Overview](#scenario-overview)
2. [Create PO from External System](#1-create-po-from-external-system)
3. [Read PO Status and Line Items](#2-read-po-status-and-line-items)
4. [Update PO Quantity or Price](#3-update-po-quantity-or-price)
5. [Receive PO Acknowledgement from Supplier (Inbound IDoc ORDRSP)](#4-receive-po-acknowledgement-from-supplier)
6. [Send PO to Supplier System (Outbound IDoc ORDERS)](#5-send-po-to-supplier-system)
7. [Technology Recommendation Summary](#technology-recommendation-summary)

---

## Scenario Overview

| Sub-scenario | S/4HANA On-Prem recommendation | ECC 6.0 recommendation |
|---|---|---|
| Create PO from external system | OData V2 `API_PURCHASEORDER_PROCESS_SRV` POST | `BAPI_PO_CREATE1` via JCo |
| Read PO status / line items | OData GET with `$expand=to_PurchaseOrderItem` | RFC `BAPI_PO_GETDETAIL` via JCo |
| Update PO quantity or price | OData PATCH on `A_PurchaseOrderItem` + `A_PurchaseOrderScheduleLine` | `BAPI_PO_CHANGE` via JCo |
| Receive PO acknowledgement from supplier | Inbound IDoc `ORDRSP` via PI/PO | Same |
| Send PO to supplier system | Outbound IDoc `ORDERS` via PI/PO | Same |

---

## 1. Create PO from External System

### S/4HANA On-Premise: OData V2

**API**: `API_PURCHASEORDER_PROCESS_SRV`  
**Entity set**: `A_PurchaseOrder`  
**Method**: POST  
**SAP Note**: 3502308 documents deprecation timeline; V4 successor `API_PURCHASEORDER` is available in newer releases.

**Minimal required fields:**

| Field | Type | Description | Example |
|---|---|---|---|
| `CompanyCode` | String | FI company code | `"1000"` |
| `PurchasingOrganization` | String | Purchasing org | `"1000"` |
| `PurchasingGroup` | String | Buyer group | `"001"` |
| `Supplier` | String | Vendor account number | `"1000001"` |
| `DocumentCurrency` | String | ISO currency code | `"USD"` |
| `PurchaseOrderDate` | DateTime | Header date (OData V2 `/Date(...)` format) | `"/Date(1716768000000)/"` |

For line items (deep insert via `to_PurchaseOrderItem`):

| Field | Description | Example |
|---|---|---|
| `PurchaseOrderItem` | 5-digit item number | `"00010"` |
| `Plant` | Receiving plant | `"1000"` |
| `Material` | Material number | `"RAW-001"` |
| `OrderQuantity` | Quantity | `"10"` |
| `NetPriceAmount` | Unit price | `"25.00"` |
| `NetPriceCurrency` | Price currency | `"USD"` |
| `PurchaseOrderItemCategory` | Item category (blank = standard) | `"0"` |
| `AccountAssignmentCategory` | Account assignment (blank, K=cost center, F=order) | `""` |

**curl example (create PO with one item):**

```bash
# Step 1: Fetch CSRF token
TOKEN_RESPONSE=$(curl -s -u "APIUSER:password" \
  -H "X-CSRF-Token: Fetch" \
  -H "Accept: application/json" \
  -c /tmp/sap-cookies.txt \
  -D /tmp/sap-headers.txt \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/")

CSRF_TOKEN=$(grep -i "x-csrf-token" /tmp/sap-headers.txt | awk '{print $2}' | tr -d '\r')

# Step 2: Create PO with deep insert
curl -s -u "APIUSER:password" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -b /tmp/sap-cookies.txt \
  -X POST \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder" \
  -d @assets/payloads/po-create.json
```

**SAP verification**: Transaction `ME23N` → enter PO number from response → verify header/item data.

---

### ECC 6.0: BAPI_PO_CREATE1 via JCo

**BAPI**: `BAPI_PO_CREATE1`  
**Required import structures**: `POHEADER`, `POHEADERX` (X = change flag indicators)  
**Tables**: `POITEM`, `POITEMX`, `POSCHEDULE`, `POSCHEDULEX`, `POACCOUNT`, `POACCOUNTX`, `RETURN`

**Minimal required fields in POHEADER:**

| Field | Description | Example |
|---|---|---|
| `DOC_TYPE` | PO document type | `"NB"` (standard), `"ZNB"` (custom) |
| `PURCH_ORG` | Purchasing organization | `"1000"` |
| `PUR_GROUP` | Purchasing group | `"001"` |
| `COMP_CODE` | Company code | `"1000"` |
| `VENDOR` | Vendor number | `"1000001"` |
| `DOC_DATE` | Document date | `"20260430"` |
| `CURRENCY` | Currency | `"USD"` |

**Java JCo stub:**

```java
import com.sap.conn.jco.*;

public class CreatePurchaseOrder {
    public static String createPO(String destinationName) throws JCoException {
        JCoDestination dest = JCoDestinationManager.getDestination(destinationName);
        JCoFunction bapi = dest.getRepository().getFunction("BAPI_PO_CREATE1");

        // --- POHEADER ---
        JCoStructure poHeader = bapi.getImportParameterList().getStructure("POHEADER");
        poHeader.setValue("DOC_TYPE",   "NB");
        poHeader.setValue("PURCH_ORG",  "1000");
        poHeader.setValue("PUR_GROUP",  "001");
        poHeader.setValue("COMP_CODE",  "1000");
        poHeader.setValue("VENDOR",     "1000001");
        poHeader.setValue("DOC_DATE",   "20260430");
        poHeader.setValue("CURRENCY",   "USD");

        // POHEADERX — X structure signals which fields to update
        JCoStructure poHeaderX = bapi.getImportParameterList().getStructure("POHEADERX");
        poHeaderX.setValue("DOC_TYPE",  "X");
        poHeaderX.setValue("PURCH_ORG", "X");
        poHeaderX.setValue("PUR_GROUP", "X");
        poHeaderX.setValue("COMP_CODE", "X");
        poHeaderX.setValue("VENDOR",    "X");
        poHeaderX.setValue("DOC_DATE",  "X");
        poHeaderX.setValue("CURRENCY",  "X");

        // --- POITEM (line items table) ---
        JCoTable poItem  = bapi.getTableParameterList().getTable("POITEM");
        JCoTable poItemX = bapi.getTableParameterList().getTable("POITEMX");

        poItem.appendRow();
        poItem.setValue("PO_ITEM",   "00010");
        poItem.setValue("PLANT",     "1000");
        poItem.setValue("MATERIAL",  "RAW-001");
        poItem.setValue("QUANTITY",  new java.math.BigDecimal("10"));
        poItem.setValue("NET_PRICE", new java.math.BigDecimal("25.00"));
        poItem.setValue("PRICE_UNIT", 1);

        poItemX.appendRow();
        poItemX.setValue("PO_ITEM",   "00010");
        poItemX.setValue("PLANT",     "X");
        poItemX.setValue("MATERIAL",  "X");
        poItemX.setValue("QUANTITY",  "X");
        poItemX.setValue("NET_PRICE", "X");
        poItemX.setValue("PRICE_UNIT","X");

        // --- POSCHEDULE (delivery schedule) ---
        JCoTable poSchedule  = bapi.getTableParameterList().getTable("POSCHEDULE");
        JCoTable poScheduleX = bapi.getTableParameterList().getTable("POSCHEDULEX");

        poSchedule.appendRow();
        poSchedule.setValue("PO_ITEM",     "00010");
        poSchedule.setValue("SCHED_LINE",  "0001");
        poSchedule.setValue("DEL_DATCAT_EXT", "D");  // Date category
        poSchedule.setValue("DELIVERY_DATE", "20260530");
        poSchedule.setValue("QUANTITY",    new java.math.BigDecimal("10"));

        poScheduleX.appendRow();
        poScheduleX.setValue("PO_ITEM",       "00010");
        poScheduleX.setValue("SCHED_LINE",    "0001");
        poScheduleX.setValue("DEL_DATCAT_EXT","X");
        poScheduleX.setValue("DELIVERY_DATE", "X");
        poScheduleX.setValue("QUANTITY",      "X");

        // --- Execute BAPI ---
        bapi.execute(dest);

        // --- ALWAYS commit after write BAPI ---
        JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
        commit.getImportParameterList().setValue("WAIT", "X");
        commit.execute(dest);

        // --- Check RETURN table ---
        JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
        String poNumber = bapi.getExportParameterList().getString("EXPPURCHASEORDER");
        for (int i = 0; i < returnTable.getNumRows(); i++) {
            returnTable.setRow(i);
            String msgType = returnTable.getString("TYPE");
            String msgText = returnTable.getString("MESSAGE");
            if ("E".equals(msgType) || "A".equals(msgType)) {
                throw new RuntimeException("BAPI error: " + msgText);
            }
            System.out.println("[" + msgType + "] " + msgText);
        }
        return poNumber;
    }
}
```

**SAP verification**: Transaction `ME23N` → enter PO number → verify.

---

## 2. Read PO Status and Line Items

### S/4HANA On-Premise: OData GET with $expand

**API**: `API_PURCHASEORDER_PROCESS_SRV`  
**Entity**: `A_PurchaseOrder('4500012345')`

```bash
# Read PO header + items + schedule lines in one call
curl -u "APIUSER:password" \
  -H "Accept: application/json" \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/\
A_PurchaseOrder('4500012345')?\
\$expand=to_PurchaseOrderItem,to_PurchaseOrderItem/to_PurchaseOrderScheduleLine\
&\$select=PurchaseOrder,CompanyCode,Supplier,PurchaseOrderDate,\
to_PurchaseOrderItem/PurchaseOrderItem,to_PurchaseOrderItem/Material,\
to_PurchaseOrderItem/OrderQuantity,to_PurchaseOrderItem/NetPriceAmount,\
to_PurchaseOrderItem/PurchasingDocumentDeletionCode"
```

**Key status fields:**

| Field | Entity | Meaning |
|---|---|---|
| `PurchaseOrderLifeCycleStatus` | Header | `N` = not yet delivered, `P` = partially delivered, `C` = closed |
| `PurchasingDocumentDeletionCode` | Item | `L` = logically deleted |
| `ScheduleLineDeliveryDate` | Schedule line | Requested delivery date |
| `QuantityInDeliveryNote` | Item | GR-confirmed quantity |

**SAP verification**: `ME23N` → display PO → verify item status codes match.

---

### ECC 6.0: BAPI_PO_GETDETAIL via JCo

```java
JCoFunction bapi = dest.getRepository().getFunction("BAPI_PO_GETDETAIL");
bapi.getImportParameterList().setValue("PURCHASEORDER", "4500012345");
// Flag which details to retrieve:
bapi.getImportParameterList().setValue("ITEMS",    "X");
bapi.getImportParameterList().setValue("SCHEDULE", "X");
bapi.getImportParameterList().setValue("ACCOUNT",  "X");
bapi.execute(dest);

JCoTable items = bapi.getTableParameterList().getTable("POITEM");
for (int i = 0; i < items.getNumRows(); i++) {
    items.setRow(i);
    System.out.println("Item: " + items.getString("PO_ITEM")
        + " Material: " + items.getString("MATERIAL")
        + " Qty: " + items.getDouble("QUANTITY")
        + " Delivered: " + items.getDouble("DELIV_QTY"));
}
```

---

## 3. Update PO Quantity or Price

### S/4HANA On-Premise: OData PATCH

**Important**: You must PATCH both `A_PurchaseOrderItem` AND `A_PurchaseOrderScheduleLine` when changing quantity. The header entity is read-only for most fields.

```bash
# First fetch CSRF token (as shown in section 1)

# PATCH item quantity
curl -s -u "APIUSER:password" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -b /tmp/sap-cookies.txt \
  -X PATCH \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/\
A_PurchaseOrderItem(PurchaseOrder='4500012345',PurchaseOrderItem='00010')" \
  -d '{"OrderQuantity": "15", "OrderQuantityUnit": "EA"}'

# PATCH schedule line quantity (must match item quantity)
curl -s -u "APIUSER:password" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -b /tmp/sap-cookies.txt \
  -X PATCH \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/\
A_PurchaseOrderScheduleLine(PurchaseOrder='4500012345',PurchaseOrderItem='00010',ScheduleLine='0001')" \
  -d '{"ScheduleLineOrderQuantity": "15"}'
```

**Common pitfall**: `PurchasingCompletenessStatus` is read-only; attempting to PATCH it returns 400. Always update quantities at the item and schedule line level.

**SAP verification**: `ME23N` → item detail → verify `OrderQuantity` changed.

---

### ECC 6.0: BAPI_PO_CHANGE via JCo

```java
JCoFunction bapi = dest.getRepository().getFunction("BAPI_PO_CHANGE");
bapi.getImportParameterList().setValue("PURCHASEORDER", "4500012345");

JCoTable poItem  = bapi.getTableParameterList().getTable("POITEM");
JCoTable poItemX = bapi.getTableParameterList().getTable("POITEMX");

poItem.appendRow();
poItem.setValue("PO_ITEM",  "00010");
poItem.setValue("QUANTITY", new java.math.BigDecimal("15"));

poItemX.appendRow();
poItemX.setValue("PO_ITEM",  "00010");
poItemX.setValue("QUANTITY", "X");  // Mark field as changed

bapi.execute(dest);

// ALWAYS commit
JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
commit.getImportParameterList().setValue("WAIT", "X");
commit.execute(dest);
```

---

## 4. Receive PO Acknowledgement from Supplier

**IDoc Message Type**: `ORDRSP` (Order Response)  
**IDoc Type**: `ORDERS05`  
**Direction**: Inbound to SAP  
**Channel**: SAP PI/PO IDoc adapter or direct tRFC posting

### Inbound processing setup (S/4HANA and ECC)

1. **Partner Profile (WE20)**: Create inbound partner profile for the supplier partner number.
   - Partner Type: `LI` (vendor)
   - Message Type: `ORDRSP`
   - Process Code: `ORDE` (standard order response process)
2. **Port (WE21)**: Define the port used by your PI/PO or integration middleware.
3. **Message Type Assignment**: Assign `ORDRSP` to `ORDERS05` IDoc type in WE57.

### Verification

- **WE02**: View all received IDocs, filter by message type `ORDRSP`
- **WE05**: Inbound IDoc display — check processing status
- **ME23N**: Open PO → check "Confirmations" tab for supplier confirmation records

### Typical ORDRSP segments

| Segment | Content |
|---|---|
| `E1EDK01` | Header (order date, partner info) |
| `E1EDP01` | Item line (line number, confirmed quantity) |
| `E1EDP04` | Delivery date per item |
| `E1EDK14` | Purchasing organization qualifier |

---

## 5. Send PO to Supplier System

**IDoc Message Type**: `ORDERS`  
**IDoc Type**: `ORDERS05`  
**Direction**: Outbound from SAP  
**Trigger**: Output condition record in ME → message type `NEU` triggers IDoc output

### Outbound setup

1. **Output Condition (MN04)**: Create output condition record for message type `NEU` in the purchasing output schema (e.g., `RMBEF1`).
   - Set communication channel: `EDI`
   - Partner function: `LF` (vendor)
2. **Partner Profile (WE20)**: Create outbound partner profile.
   - Message Type: `ORDERS`
   - IDoc Type: `ORDERS05`
   - Output Mode: `4` (collect IDocs) or `1` (transfer immediately)
3. **Port (WE21)**: Define tRFC port pointing to PI/PO or direct EDIFACT translator.

### Monitoring outbound IDocs

- **WE02**: Filter by direction `Outbound`, message type `ORDERS`
- **BD87**: For stuck IDocs — reprocess manually

### Key ORDERS05 segments for PO

| Segment | Content |
|---|---|
| `E1EDK01` | Header (document type, document date) |
| `E1EDK14` | Org data (purchasing org, company code) |
| `E1EDP01` | Item (item number, quantity, unit) |
| `E1EDP19` | Material identification (material number, supplier material number) |
| `E1EDP26` | Pricing condition per item |
| `E1EDS01` | Summary / trailer |

See `assets/payloads/idoc-orders05.xml` for a complete example.

---

## Technology Recommendation Summary

```
Is your SAP system ECC 6.0?
  YES → Use JCo + BAPI_PO_CREATE1 / BAPI_PO_CHANGE / BAPI_PO_GETDETAIL
  NO (S/4HANA) → Is it On-Premise?
    YES → Use OData V2 API_PURCHASEORDER_PROCESS_SRV
          (Check SAP Note 3502308 for your release's deprecation status)
    NO (Cloud Public) → Use OData V4 API_PURCHASEORDER or RAP service
                        (RFC/JCo not available externally)

Is the integration async with an external supplier/partner?
  YES → Use IDoc ORDERS (outbound) / ORDRSP (inbound) via PI/PO
```

**Common pitfalls across all methods:**
1. **Commit missing (BAPI)**: Forgetting `BAPI_TRANSACTION_COMMIT` → PO created but immediately rolled back. Always add it.
2. **CSRF token not refreshed (OData)**: CSRF tokens expire with the session. If you get 403 after a period of inactivity, re-fetch the token.
3. **Schedule line out of sync (OData PATCH)**: Patching only `A_PurchaseOrderItem` quantity without patching `A_PurchaseOrderScheduleLine` leaves the delivery schedule inconsistent and may trigger SAP validation errors downstream.
