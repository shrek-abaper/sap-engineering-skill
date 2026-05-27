# Production Planning (PP) Integration Scenarios

## Table of Contents
- [Overview](#overview)
- [Read Bill of Materials (BOM)](#read-bill-of-materials-bom)
- [Read Work Centers and Routings](#read-work-centers-and-routings)
- [Production Orders](#production-orders)
- [Goods Movements for Production](#goods-movements-for-production)
- [Production Order Confirmation](#production-order-confirmation)
- [MRP and Requirements](#mrp-and-requirements)
- [Version Matrix](#version-matrix)
- [Common Pitfalls](#common-pitfalls)

---

## Overview

PP integration is typically required for manufacturing execution systems (MES), IoT/shopfloor data collection, scheduling tools, and quality systems that need to exchange data with SAP production processes.

**Key PP objects and their APIs:**

| Object | Read API | Write API |
|---|---|---|
| Bill of Materials (BOM) | `API_BILL_OF_MATERIAL_SRV` | JCo `CSAP_MAT_BOM_CREATE` / `CSAP_MAT_BOM_CHANGE` |
| Work Center | `API_WORK_CENTERS_SRV` | JCo `BAPI_WORK_CENTER_CREATE` |
| Routing / Recipe | `API_ROUTING_0001` (S/4) | JCo `BAPI_ROUTING_CREATE` |
| Production Order | `API_PP_ORDERS_SRV` | JCo `BAPI_PRODORD_CREATE` / `BAPI_PRODORD_CHANGE` |
| Goods Movement | — | JCo `BAPI_GOODSMVT_CREATE` |
| Order Confirmation | — | JCo `BAPI_PRODORDCONF_CREATE_TT` |

---

## Read Bill of Materials (BOM)

### OData: `API_BILL_OF_MATERIAL_SRV` (S/4HANA On-Prem)

**Service**: `API_BILL_OF_MATERIAL_SRV`
**Base URL**: `/sap/opu/odata/sap/API_BILL_OF_MATERIAL_SRV/`
**Key entity sets**:
- `MaterialBOMHeader` — BOM header (material, plant, BOM usage, alt BOM)
- `MaterialBOMItem` — BOM line items (component, quantity, unit)

```bash
# Read BOM header for a material in plant 1000, BOM usage 1 (Production)
curl -u APIUSER:pass \
  -H "Accept: application/json" \
  "https://s4hana.example.com:443/sap/opu/odata/sap/API_BILL_OF_MATERIAL_SRV/MaterialBOMHeader?\$filter=Material eq 'FINISHED-GOOD-001' and Plant eq '1000' and BOMUsage eq '1'&\$expand=to_BOMItem"
```

**BOM item key fields:**
- `BOMComponent` — child material number
- `ComponentQuantity` / `ComponentQuantityUnit` — quantity per parent
- `IsPhantomItem` — phantom assembly flag (don't order separately)
- `ItemCategory` — L=stock item, R=variable-size, T=text, N=non-stock
- `ValidityStartDate` / `ValidityEndDate` — engineering change validity

### JCo: `CSAP_MAT_BOM_READ` (all versions)

```java
JCoFunction bapi = dest.getRepository().getFunction("CSAP_MAT_BOM_READ");
bapi.getImportParameterList().setValue("MATERIAL", "FINISHED-GOOD-001");
bapi.getImportParameterList().setValue("PLANT", "1000");
bapi.getImportParameterList().setValue("BOM_USAGE", "1");   // 1 = Production
bapi.getImportParameterList().setValue("FL_EXPLODE", "X");  // explode multi-level
bapi.execute(dest);

JCoTable items = bapi.getTableParameterList().getTable("T_STPO");
for (int i = 0; i < items.getNumRows(); i++) {
    items.setRow(i);
    System.out.printf("Level %s  Component: %s  Qty: %s %s%n",
        items.getString("STLAL"),
        items.getString("IDNRK"),
        items.getString("MENGE"),
        items.getString("MEINS")
    );
}
```

---

## Read Work Centers and Routings

### Work Centers (`API_WORK_CENTERS_SRV`)

```bash
# Read all work centers in plant 1000
curl -u APIUSER:pass \
  "https://s4hana.example.com:443/sap/opu/odata/sap/API_WORK_CENTERS_SRV/WorkCenterCollection?\$filter=Plant eq '1000'&\$select=WorkCenter,WorkCenterName,WorkCenterTypeCode,CapacityCategoryCode"
```

### Routings (`API_ROUTING_0001`)

```bash
# Read routing for finished good in plant 1000
curl -u APIUSER:pass \
  "https://s4hana.example.com:443/sap/opu/odata/sap/API_ROUTING_0001/RoutingHeader?\$filter=Material eq 'FINISHED-GOOD-001' and Plant eq '1000'&\$expand=to_RoutingOperation"
```

Key operation fields: `OperationNumber`, `WorkCenter`, `SetupTime`, `OperatingTime`, `StandardValueUnit`.

---

## Production Orders

### Read Production Orders via OData (`API_PP_ORDERS_SRV`)

**Service**: `API_PP_ORDERS_SRV`
**Key entity sets**:
- `ManufacturingOrder` — order header
- `ManufacturingOrderComponent` — component (goods issue) requirements
- `ManufacturingOrderOperation` — operations to be performed

```bash
# Read all open production orders for plant 1000, material FINISHED-GOOD-001
curl -u APIUSER:pass \
  "https://s4hana.example.com:443/sap/opu/odata/sap/API_PP_ORDERS_SRV/ManufacturingOrder?\
\$filter=ProductionPlant eq '1000' and MfgOrderPlannedStartDate ge datetime'2026-01-01T00:00:00' and OrderIsReleasedForSched eq true\
&\$select=ManufacturingOrder,OrderType,Material,MfgOrderPlannedQuantity,MfgOrderConfirmedQuantity,MfgOrderActualStartDate\
&\$orderby=MfgOrderPlannedStartDate"
```

**Production order status decode:**

| Status Flag | Meaning |
|---|---|
| `CRTD` | Created, not released |
| `REL` | Released (can post goods movements) |
| `PCNF` | Partially confirmed |
| `CNF` | Fully confirmed |
| `TECO` | Technically completed |
| `CLSD` | Closed (accounting settled) |

### Create Production Order via JCo (`BAPI_PRODORD_CREATE`)

```java
JCoFunction bapi = dest.getRepository().getFunction("BAPI_PRODORD_CREATE");

JCoStructure header = bapi.getImportParameterList().getStructure("ORDER_HEADER_IN");
header.setValue("MATERIAL", "FINISHED-GOOD-001");
header.setValue("PLANT", "1000");
header.setValue("ORDER_TYPE", "PP01");       // PP01 = standard production order
header.setValue("QUANTITY", "100.0");
header.setValue("UNIT_OF_MEASURE", "EA");
header.setValue("SCHED_DATE_END", "20260530");  // YYYYMMDD

// Optional: routing override
JCoStructure routing = bapi.getImportParameterList().getStructure("ORDER_ROUTING");
// leave empty to use standard routing for material

bapi.execute(dest);

String orderNumber = bapi.getExportParameterList().getString("NUMBER");
System.out.println("Created production order: " + orderNumber);

// Check RETURN table
JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
for (int i = 0; i < returnTable.getNumRows(); i++) {
    returnTable.setRow(i);
    if ("E".equals(returnTable.getString("TYPE"))) {
        throw new RuntimeException("Create failed: " + returnTable.getString("MESSAGE"));
    }
}

// MANDATORY: commit
JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
commit.getImportParameterList().setValue("WAIT", "X");
commit.execute(dest);
```

### Release Production Order (`BAPI_PRODORD_CHANGE`)

A production order must be **released** before goods movements can be posted against it.

```java
JCoFunction bapi = dest.getRepository().getFunction("BAPI_PRODORD_CHANGE");
bapi.getImportParameterList().setValue("NUMBER", "000001000001");  // order number

JCoStructure statusChange = bapi.getImportParameterList().getStructure("ORDER_STATUS");
statusChange.setValue("I_REL", "X");  // I_REL = Release flag

bapi.execute(dest);
// Check RETURN and commit
```

---

## Goods Movements for Production

All production-related goods movements go through `BAPI_GOODSMVT_CREATE`. The movement type determines what happens:

| Movement Type | Description |
|---|---|
| `261` | Goods issue to production order (consume component stock) |
| `262` | Reversal of goods issue (put component back to stock) |
| `101` | Goods receipt for production order (produce finished goods) |
| `102` | Reversal of goods receipt |

### Post Goods Issue (mvt type 261) — Java

```java
JCoFunction bapi = dest.getRepository().getFunction("BAPI_GOODSMVT_CREATE");

// Header
JCoStructure header = bapi.getImportParameterList().getStructure("GOODSMVT_HEADER");
header.setValue("PSTNG_DATE", "20260530");    // Posting date YYYYMMDD
header.setValue("DOC_DATE", "20260530");
header.setValue("PR_UNAME", "RFC_USER");

// Items
JCoTable items = bapi.getTableParameterList().getTable("GOODSMVT_ITEM");
items.appendRow();
items.setValue("MOVE_TYPE", "261");         // Goods issue to production
items.setValue("MVT_IND", "F");            // F = order-related
items.setValue("ORDERID", "000001000001"); // Production order number
items.setValue("MATERIAL", "RAW-MAT-001");
items.setValue("PLANT", "1000");
items.setValue("STGE_LOC", "0001");         // Storage location
items.setValue("ENTRY_QNT", "5.0");         // Quantity
items.setValue("ENTRY_UOM", "KG");

bapi.execute(dest);

String materialDoc = bapi.getExportParameterList().getString("MATERIALDOCUMENT");
System.out.println("Material document: " + materialDoc);

// Check RETURN table — type "S" = success, "E" = error
JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
for (int i = 0; i < returnTable.getNumRows(); i++) {
    returnTable.setRow(i);
    if ("E".equals(returnTable.getString("TYPE"))) {
        JCoFunction rollback = dest.getRepository().getFunction("BAPI_TRANSACTION_ROLLBACK");
        rollback.execute(dest);
        throw new RuntimeException("Goods issue failed: " + returnTable.getString("MESSAGE"));
    }
}

// Commit ONLY if no errors
JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
commit.getImportParameterList().setValue("WAIT", "X");
commit.execute(dest);
```

### Goods Receipt for Production Order (mvt type 101) — Java

```java
JCoFunction bapi = dest.getRepository().getFunction("BAPI_GOODSMVT_CREATE");

// Header (import struct)
JCoStructure header = bapi.getImportParameterList().getStructure("GOODSMVT_HEADER");
header.setValue("PSTNG_DATE", "20260530");
header.setValue("DOC_DATE",   "20260530");
header.setValue("PR_UNAME",   "RFCUSER");

// Movement code (import struct, not a table)
JCoStructure code = bapi.getImportParameterList().getStructure("GOODSMVT_CODE");
code.setValue("GM_CODE", "02");   // 02 = GR for production order

// Items table
JCoTable items = bapi.getTableParameterList().getTable("GOODSMVT_ITEM");
items.appendRow();
items.setValue("MOVE_TYPE",  "101");              // GR for production order
items.setValue("MVT_IND",    "F");
items.setValue("ORDERID",    "000001000001");
items.setValue("MATERIAL",   "FINISHED-GOOD-001");
items.setValue("PLANT",      "1000");
items.setValue("STGE_LOC",   "0001");
items.setValue("ENTRY_QNT",  "100.0");
items.setValue("ENTRY_UOM",  "EA");

bapi.execute(dest);

// Check RETURN table for errors
JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
boolean hasError = false;
for (int i = 0; i < returnTable.getNumRows(); i++) {
    returnTable.setRow(i);
    String type = returnTable.getString("TYPE");
    if ("E".equals(type) || "A".equals(type)) {
        hasError = true;
        System.err.println("GR error: " + returnTable.getString("MESSAGE"));
    }
}
if (hasError) {
    dest.getRepository().getFunction("BAPI_TRANSACTION_ROLLBACK").execute(dest);
    throw new RuntimeException("Goods receipt failed — see errors above");
}

// Commit only after all error checks pass
JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
commit.getImportParameterList().setValue("WAIT", "X");
commit.execute(dest);

String matDoc = bapi.getExportParameterList().getString("MATERIALDOCUMENT");
System.out.println("Material document: " + matDoc);
```

---

## Production Order Confirmation

Confirmation reports actual quantities produced, time consumed, and scrapped.

### `BAPI_PRODORDCONF_CREATE_TT`

```java
JCoFunction bapi = dest.getRepository().getFunction("BAPI_PRODORDCONF_CREATE_TT");

JCoTable confirmations = bapi.getTableParameterList().getTable("TIMETICKETS");
confirmations.appendRow();
confirmations.setValue("ORDERID", "000001000001");
confirmations.setValue("OPERATION", "0010");           // Operation within order
confirmations.setValue("CONF_QTY", "50.0");            // Confirmed yield quantity
confirmations.setValue("SCRAP_QTY", "2.0");            // Scrap quantity
confirmations.setValue("CONF_UOM", "EA");
confirmations.setValue("EXEC_START_DATE", "20260530");
confirmations.setValue("EXEC_START_TIME", "080000");   // HHMMSS
confirmations.setValue("EXEC_FIN_DATE", "20260530");
confirmations.setValue("EXEC_FIN_TIME", "160000");
confirmations.setValue("WORK_CNTR", "WRKC-LINE-1");    // Actual work center used
// FINAL_CONF = "X" marks this as final confirmation (closes the operation)
confirmations.setValue("FINAL_CONF", "");              // empty = partial confirmation

bapi.execute(dest);

// RETURN is a table here too
JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
for (int i = 0; i < returnTable.getNumRows(); i++) {
    returnTable.setRow(i);
    if ("E".equals(returnTable.getString("TYPE"))) {
        throw new RuntimeException("Confirmation failed: " + returnTable.getString("MESSAGE"));
    }
}

JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
commit.getImportParameterList().setValue("WAIT", "X");
commit.execute(dest);
```

---

## MRP and Requirements

MRP (Material Requirements Planning) is largely an internal SAP process triggered by transaction `MD01`/`MD02`. External integration options are limited but include:

| Integration Point | Method |
|---|---|
| Create planned independent requirements (PIR) | JCo `BAPI_REQUIREMENTS_CREATE` |
| Read MRP elements (planned orders, open POs, stock) | JCo `BAPI_MATERIAL_MRPLIST_GETDATA` |
| Trigger MRP run for single material | JCo `BAPI_MATERIAL_SCHEDULE` (use cautiously — impacts live planning) |
| Read MD04 stock/requirements list | JCo `MD_STOCK_REQUIREMENTS_LIST_API` (function module, not BAPI) |

```python
# Read MRP requirements list for a material
result = conn.call(
    "BAPI_MATERIAL_MRPLIST_GETDATA",
    MATERIAL="RAW-MAT-001",
    PLANT="1000",
    MRP_AREA="1000",
)
for element in result["MRPELEMENTS"]:
    print(f"{element['DATE']}  {element['ELEMENT']}  {element['QUANTITY']} {element['UNIT']}")
```

---

## Version Matrix

| Scenario | ECC 6.0 | S/4HANA On-Prem | S/4HANA Cloud Public |
|---|---|---|---|
| Read BOM | `CSAP_MAT_BOM_READ` | `API_BILL_OF_MATERIAL_SRV` + `CSAP_MAT_BOM_READ` | `API_BILL_OF_MATERIAL_SRV` |
| Read Production Order | `BAPI_PRODORD_GET_DETAIL` | `API_PP_ORDERS_SRV` | `API_PP_ORDERS_SRV` |
| Create Production Order | `BAPI_PRODORD_CREATE` | `BAPI_PRODORD_CREATE` | Limited (use standard UI or BTP workflow) |
| Post Goods Movement | `BAPI_GOODSMVT_CREATE` | `BAPI_GOODSMVT_CREATE` | OData V4 API (check current availability) |
| Production Confirmation | `BAPI_PRODORDCONF_CREATE_TT` | `BAPI_PRODORDCONF_CREATE_TT` | `API_PROD_ORDER_CONFIRMATION_SRV` (OData) |
| MRP Read | `BAPI_MATERIAL_MRPLIST_GETDATA` | `BAPI_MATERIAL_MRPLIST_GETDATA` | Restricted |

---

## Common Pitfalls

1. **Order status gating**: Goods movements can only be posted against a **released** order (`REL` status). Attempting `BAPI_GOODSMVT_CREATE` against an unreleased order returns a hard error. Always check and release the order first.

2. **Goods movement code (`GM_CODE`) mismatch**: `BAPI_GOODSMVT_CREATE` requires a `GM_CODE` that matches the transaction context. Use `02` for GR for production order (movement 101/102), `01` for general goods receipt (e.g., PO-based), `04` for transfer posting. Wrong code causes silent misposting.

3. **BOM alternative and usage**: Each material may have multiple BOMs (different usage: 1=Production, 3=Universal, 5=Sales) and multiple alternatives (alt 1, alt 2...). If you omit `BOMUsage` in the filter, you will get all BOMs and must pick the right one. Production orders use `BOMUsage=1` by default.

4. **Confirmation finality**: Setting `FINAL_CONF = "X"` on a confirmation marks the operation as complete. This cannot easily be undone. Only set it when the operation is truly finished. Partial confirmations (no flag) can be made multiple times.

5. **BAPI_PRODORD_CREATE quantity unit**: The `UNIT_OF_MEASURE` in `BAPI_PRODORD_CREATE` must match the material's base unit of measure. Passing a different UoM without a conversion factor configured in the material master results in an error.

6. **Concurrent access locks**: SAP locks production orders during goods movements and confirmations. If two external systems try to post to the same order simultaneously, one will receive a lock error (`ENQUEUE_E_LOCK`). Implement retry logic with exponential backoff.
