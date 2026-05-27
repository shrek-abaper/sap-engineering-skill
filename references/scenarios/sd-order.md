# SD: Sales Order Integration

## Table of Contents

1. [Scenario Overview](#scenario-overview)
2. [Create Sales Order via OData (Deep Insert)](#1-create-sales-order-via-odata-deep-insert)
3. [Read Sales Order Status and Schedule Lines](#2-read-sales-order-status-and-schedule-lines)
4. [Change Sales Order Item](#3-change-sales-order-item)
5. [Send Order Confirmation Outbound (IDoc ORDACK/ORDRSP)](#4-send-order-confirmation-outbound)
6. [Common Pitfalls](#5-common-pitfalls)

---

## Scenario Overview

| Sub-scenario | S/4HANA On-Prem recommendation | ECC 6.0 recommendation |
|---|---|---|
| Create sales order from external system | OData V2 `API_SALES_ORDER_SRV` POST with deep insert | `BAPI_SALESORDER_CREATEFROMDAT2` via JCo |
| Read order status and schedule lines | OData GET with `$expand=to_Item/to_ScheduleLine` | RFC `BAPI_SALESORDER_GETLIST` + `BAPI_SALESORDER_GETSTATUS` |
| Change item quantity or delivery date | OData PATCH on `A_SalesOrderItem` | `BAPI_SALESORDER_CHANGE` via JCo |
| Send order confirmation outbound | Outbound IDoc `ORDACK` (SAP internal) or `ORDRSP` via PI/PO | Same |

---

## 1. Create Sales Order via OData (Deep Insert)

### API Details

- **Service**: `API_SALES_ORDER_SRV`
- **Entity set**: `A_SalesOrder`
- **SAP API Hub**: https://api.sap.com/api/API_SALES_ORDER_SRV
- **S/4HANA On-Prem**: Available from 1709 onward

### Required SAP setup

1. Activate `API_SALES_ORDER_SRV` in `/IWFND/MAINT_SERVICE`
2. User requires role `SAP_BC_SALES_ORDER_DISPLAY` + authorization for `V_VBAK_AAR` (sales area authorization)
3. For write operations: authorization object `V_VBAK_VKO` with `Activity 01`

### Minimal required fields

**Header (A_SalesOrder):**

| Field | Description | Example |
|---|---|---|
| `SalesOrderType` | SO document type | `"OR"` (standard), `"TA"` (if custom) |
| `SalesOrganization` | Sales org | `"1000"` |
| `DistributionChannel` | Distribution channel | `"10"` |
| `OrganizationDivision` | Division | `"00"` |
| `SoldToParty` | Customer account | `"C0001"` |
| `PurchaseOrderByCustomer` | Customer PO reference | `"CUS-PO-2026-001"` |
| `RequestedDeliveryDate` | Requested delivery | `"/Date(1748563200000)/"` |

**Item (via deep insert to_Item):**

| Field | Description | Example |
|---|---|---|
| `SalesOrderItem` | 6-digit item number | `"000010"` |
| `Material` | Material number | `"FG-001"` |
| `RequestedQuantity` | Order quantity | `"5"` |
| `RequestedQuantityUnit` | UoM | `"EA"` |

### curl example with deep insert

```bash
# Step 1: Fetch CSRF token
curl -s -u "APIUSER:password" \
  -H "X-CSRF-Token: Fetch" \
  -H "Accept: application/json" \
  -c /tmp/sap-sd-cookies.txt \
  -D /tmp/sap-sd-headers.txt \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_SALES_ORDER_SRV/" \
  > /dev/null

CSRF_TOKEN=$(grep -i "x-csrf-token" /tmp/sap-sd-headers.txt | awk '{print $2}' | tr -d '\r')

# Step 2: Create sales order with items and schedule lines
curl -s -u "APIUSER:password" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -b /tmp/sap-sd-cookies.txt \
  -X POST \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_SALES_ORDER_SRV/A_SalesOrder" \
  -d '{
    "SalesOrderType": "OR",
    "SalesOrganization": "1000",
    "DistributionChannel": "10",
    "OrganizationDivision": "00",
    "SoldToParty": "C0001",
    "PurchaseOrderByCustomer": "CUS-PO-2026-001",
    "RequestedDeliveryDate": "/Date(1748563200000)/",
    "to_Item": {
      "results": [
        {
          "SalesOrderItem": "000010",
          "Material": "FG-001",
          "RequestedQuantity": "5",
          "RequestedQuantityUnit": "EA",
          "ItemGrossWeight": "10.000",
          "ItemWeightUnit": "KG",
          "to_ScheduleLine": {
            "results": [
              {
                "ScheduleLine": "0001",
                "RequestedDeliveryDate": "/Date(1748563200000)/",
                "ScheduleLineOrderQuantity": "5"
              }
            ]
          }
        }
      ]
    }
  }'
```

### Response fields to capture

```json
{
  "d": {
    "SalesOrder": "0000012345",
    "SalesOrderType": "OR",
    "SalesOrganization": "1000",
    "SoldToParty": "C0001",
    "OverallSDProcessStatus": "A",
    "TotalNetAmount": "125.00",
    "TransactionCurrency": "USD"
  }
}
```

Key status: `OverallSDProcessStatus`:
- `A` = Open
- `B` = In process
- `C` = Completed
- `D` = Rejected

**SAP verification**: Transaction `VA03` → enter SO number → verify header and items.

---

### ECC 6.0: BAPI_SALESORDER_CREATEFROMDAT2 via JCo

```java
JCoFunction bapi = dest.getRepository().getFunction("BAPI_SALESORDER_CREATEFROMDAT2");

// Header data
JCoStructure header = bapi.getImportParameterList().getStructure("ORDER_HEADER_IN");
header.setValue("DOC_TYPE",    "OR");
header.setValue("SALES_ORG",   "1000");
header.setValue("DISTR_CHAN",  "10");
header.setValue("DIVISION",    "00");
header.setValue("PURCH_DATE",  "20260530");
header.setValue("PRICE_DATE",  "20260530");

// Partners table (mandatory: AG = sold-to, WE = ship-to)
JCoTable partners = bapi.getTableParameterList().getTable("ORDER_PARTNERS");
partners.appendRow();
partners.setValue("PARTN_ROLE", "AG");  // Sold-to
partners.setValue("PARTN_NUMB", "C0001");

partners.appendRow();
partners.setValue("PARTN_ROLE", "WE");  // Ship-to
partners.setValue("PARTN_NUMB", "C0001");  // Same as sold-to if no separate ship-to

// Items table
JCoTable items = bapi.getTableParameterList().getTable("ORDER_ITEMS_IN");
items.appendRow();
items.setValue("ITM_NUMBER", "000010");
items.setValue("MATERIAL",   "FG-001");
items.setValue("PLANT",      "1000");
items.setValue("TARGET_QU",  "EA");
items.setValue("REQ_QTY",    new java.math.BigDecimal("5"));

// Schedule lines
JCoTable schedules = bapi.getTableParameterList().getTable("ORDER_SCHEDULES_IN");
schedules.appendRow();
schedules.setValue("ITM_NUMBER",  "000010");
schedules.setValue("SCHED_LINE",  "0001");
schedules.setValue("REQ_QTY",     new java.math.BigDecimal("5"));
schedules.setValue("REQ_DATE",    "20260530");

bapi.execute(dest);

// Commit required
JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
commit.getImportParameterList().setValue("WAIT", "X");
commit.execute(dest);

String soNumber = bapi.getExportParameterList().getString("SALESDOCUMENT");
System.out.println("Sales order created: " + soNumber);
```

---

## 2. Read Sales Order Status and Schedule Lines

### OData GET with deep expand

```bash
# Read SO header + items + schedule lines + delivery status
curl -u "APIUSER:password" \
  -H "Accept: application/json" \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_SALES_ORDER_SRV/\
A_SalesOrder('0000012345')?\
\$expand=to_Item,to_Item/to_ScheduleLine\
&\$select=SalesOrder,SoldToParty,OverallSDProcessStatus,\
to_Item/SalesOrderItem,to_Item/Material,to_Item/RequestedQuantity,\
to_Item/SDProcessStatus,\
to_Item/to_ScheduleLine/ScheduleLine,to_Item/to_ScheduleLine/ScheduleLineOrderQuantity,\
to_Item/to_ScheduleLine/ScheduleLineDeliveryDate,\
to_Item/to_ScheduleLine/DeliveredQtyInOrderQtyUnit\
&\$format=json"
```

**Key status fields:**

| Field | Entity | Values |
|---|---|---|
| `OverallSDProcessStatus` | Header | `A`=Open, `B`=In process, `C`=Completed |
| `SDProcessStatus` | Item | `A`=Open, `B`=Partial, `C`=Completed, `D`=Rejected |
| `DeliveredQtyInOrderQtyUnit` | Schedule line | Quantity actually delivered |
| `InvoiceAmount` | Item | Amount invoiced |

**SAP verification**: Transaction `VA03` → item detail → delivery status.

---

## 3. Change Sales Order Item

### OData PATCH on A_SalesOrderItem

```bash
# Fetch CSRF token first (see section 1)

# Update item quantity and price
curl -s -u "APIUSER:password" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -b /tmp/sap-sd-cookies.txt \
  -X PATCH \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_SALES_ORDER_SRV/\
A_SalesOrderItem(SalesOrder='0000012345',SalesOrderItem='000010')" \
  -d '{
    "RequestedQuantity": "8",
    "RequestedQuantityUnit": "EA"
  }'

# Also update the corresponding schedule line
curl -s -u "APIUSER:password" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -b /tmp/sap-sd-cookies.txt \
  -X PATCH \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_SALES_ORDER_SRV/\
A_SalesOrderScheduleLine(SalesOrder='0000012345',SalesOrderItem='000010',ScheduleLine='0001')" \
  -d '{
    "ScheduleLineOrderQuantity": "8"
  }'
```

**Note**: For price changes, update via `A_SalesOrderItemPr` (pricing condition entity), not via the item directly. Price conditions in SAP are maintained separately.

---

## 4. Send Order Confirmation Outbound

### IDoc ORDACK (internal SAP output)

SAP automatically triggers an output message (type `BA00` or configurable) when a SO is created/changed.  
This output can be configured to generate an IDoc for delivery to the customer's system.

**Setup (both ECC and S/4HANA):**

1. **Output Condition (VV11/VV12)**: Create output condition record in the sales output schema.
   - Message type: `BA00` (order confirmation) or `ORDRSP` (EDI response)
   - Communication method: `EDI`
   - Partner function: `AG` (sold-to)
2. **Partner Profile (WE20)**:
   - Partner type: `KU` (customer)
   - IDoc type: `ORDERS05`
   - Message type: `ORDRSP`
3. **Output processing**: Run `VF31` for collective output or set to immediate dispatch.

### Monitoring

- **Transaction VF03**: View output messages for a specific SO → check dispatch status
- **Transaction WE02**: IDoc monitor → filter by direction `Outbound`, message `ORDRSP`

### Key ORDRSP segments for order confirmation

| Segment | Content |
|---|---|
| `E1EDK01` | Header (order type, document date) |
| `E1EDK02` | Reference document (customer PO number) |
| `E1EDP01` | Item (item number, confirmed quantity) |
| `E1EDP04` | Schedule line (delivery date, confirmed quantity) |
| `E1EDKT1` | Text (confirmation message) |

---

## 5. Common Pitfalls

1. **Missing partner role in BAPI call (ECC)**: `BAPI_SALESORDER_CREATEFROMDAT2` requires at minimum `AG` (sold-to) in the `ORDER_PARTNERS` table. If omitted, the error is cryptic: `Customer master has not been maintained`. Always supply both `AG` and `WE`.

2. **RequestedDeliveryDate in past (OData)**: SAP validates delivery dates against plant calendar and shipping point lead time. If date is in the past or before the material availability date, the order is created but with a different confirmed date. Read back `ConfirmedDeliveryDate` from the schedule line to get the actual commitment.

3. **CSRF token scope**: The CSRF token fetched from `API_SALES_ORDER_SRV` is **not reusable** for `API_PURCHASEORDER_PROCESS_SRV`. Each service requires its own token fetch from its own base URL.

4. **Deep insert item numbering**: Item numbers in deep insert must be exactly 6 digits zero-padded (`"000010"`, `"000020"`). Using `"10"` or `"10010"` causes validation failure.

5. **Net price missing (S/4HANA OData)**: If the material has a price condition record in SAP, the price is determined automatically. If not, `TotalNetAmount` will be 0. For external pricing, pass `ManualInvoiceMaintenanceIsActive: "X"` and supply price conditions via `to_Item/to_PricingElement`.
