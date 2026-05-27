# MM: Inventory / Stock Integration

## Table of Contents

1. [Scenario Overview](#scenario-overview)
2. [Real-Time Stock Query via OData](#1-real-time-stock-query-via-odata)
3. [Batch Stock Query via RFC BAPI](#2-batch-stock-query-via-rfc-bapi)
4. [Stock Reservation via BAPI](#3-stock-reservation-via-bapi)
5. [Stock Type Reference](#4-stock-type-reference)
6. [Common Pitfalls](#5-common-pitfalls)

---

## Scenario Overview

| Sub-scenario | S/4HANA On-Prem recommendation | ECC 6.0 recommendation |
|---|---|---|
| Real-time stock check for a single material + plant | OData `API_MATERIAL_STOCK_SRV` | `BAPI_MATERIAL_STOCK_REQ_LIST` via JCo |
| Batch stock check (multiple materials) | OData `$batch` or loop | `BAPI_MATERIAL_STOCK_REQ_LIST` via JCo |
| Reserve stock for production/project | `BAPI_RESERVATION_CREATE1` via JCo | Same |
| Read warehouse (WM) stock | OData `API_WHSE_STOCK_SRV` (S/4 only) | RFC `L_FPLP_STOCK` or custom |

---

## 1. Real-Time Stock Query via OData

### API Details

- **Service**: `API_MATERIAL_STOCK_SRV`
- **Primary entity set**: `A_MatlStkInAcctMod`
- **SAP API Hub**: https://api.sap.com/api/API_MATERIAL_STOCK_SRV
- **Activation transaction**: `/IWFND/MAINT_SERVICE` on the SAP Gateway

### Required SAP setup

1. Activate service `API_MATERIAL_STOCK_SRV` in `/IWFND/MAINT_SERVICE`
2. Assign to system alias (usually the backend system)
3. Ensure user has authorization for `M_MSEG_BWA` (goods movement) and `M_MSEG_WMB` (plant)

### Query by Material + Plant

```bash
# Get all stock types for material RAW-001 at plant 1000
curl -u "APIUSER:password" \
  -H "Accept: application/json" \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV/\
A_MatlStkInAcctMod?\
\$filter=Material eq 'RAW-001' and Plant eq '1000'\
&\$select=Material,Plant,StorageLocation,MaterialBaseUnit,\
MatlWrhsStkQtyInMatlBaseUnit,QualityInspectionStockQuantity,\
BlockedStockQuantity,RestrictedUseStockQuantity\
&\$format=json"
```

### Example response

```json
{
  "d": {
    "results": [
      {
        "Material": "RAW-001",
        "Plant": "1000",
        "StorageLocation": "0001",
        "MaterialBaseUnit": "EA",
        "MatlWrhsStkQtyInMatlBaseUnit": "150",
        "QualityInspectionStockQuantity": "10",
        "BlockedStockQuantity": "5",
        "RestrictedUseStockQuantity": "0"
      }
    ]
  }
}
```

### Query by Storage Location

```bash
# Filter by specific storage location
curl -u "APIUSER:password" \
  -H "Accept: application/json" \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV/\
A_MatlStkInAcctMod?\
\$filter=Material eq 'RAW-001' and Plant eq '1000' and StorageLocation eq '0001'\
&\$format=json"
```

### SAP verification

Transaction `MMBE` (Stock Overview): enter material + plant → verify quantities match API response.

---

## 2. Batch Stock Query via RFC BAPI

### Use cases for RFC over OData

- ECC 6.0 (no standard OData)
- Checking stock for 100+ materials in one call (more efficient than OData $batch)
- Need to include special stock categories not exposed in `API_MATERIAL_STOCK_SRV`
- Java application already has JCo configured

### BAPI: BAPI_MATERIAL_STOCK_REQ_LIST

**Import parameters:**

| Parameter | Type | Description | Example |
|---|---|---|---|
| `PLANT` | String(4) | Plant code | `"1000"` |
| `MATERIAL` | String(40) | Material number | `"RAW-001"` |
| `UNIT` | String(3) | Unit of measure for output | `"EA"` |

**Export parameters / Tables:**

| Parameter | Description |
|---|---|
| `RETURN` | Error/status messages |
| `WAREHOUSENUMBERS` | WM warehouse numbers |

**Special stocks table (SPECIALSTOCKS):**

| Field | Description |
|---|---|
| `PLANT` | Plant |
| `STGE_LOC` | Storage location |
| `BATCH` | Batch number |
| `UNRESTRICTED` | Unrestricted stock quantity |
| `QUALINSPECT` | Quality inspection stock |
| `BLOCKED` | Blocked stock |
| `RESTRICTED` | Restricted-use stock |
| `TRANSIT` | Stock in transit |
| `RETURNS` | Returns stock |

**Java JCo example:**

```java
import com.sap.conn.jco.*;
import java.math.BigDecimal;

public class StockQuery {
    public static void getStock(JCoDestination dest, String material, String plant)
            throws JCoException {

        JCoFunction bapi = dest.getRepository().getFunction("BAPI_MATERIAL_STOCK_REQ_LIST");

        bapi.getImportParameterList().setValue("MATERIAL", material);
        bapi.getImportParameterList().setValue("PLANT",    plant);
        bapi.getImportParameterList().setValue("UNIT",     "");  // Use material base unit

        bapi.execute(dest);

        // Check RETURN for errors first
        JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
        for (int i = 0; i < returnTable.getNumRows(); i++) {
            returnTable.setRow(i);
            if ("E".equals(returnTable.getString("TYPE"))) {
                throw new RuntimeException("BAPI error: " + returnTable.getString("MESSAGE"));
            }
        }

        // Read stock quantities
        // Note: BAPI_MATERIAL_STOCK_REQ_LIST returns aggregate values in EXPORT parameters
        JCoStructure stockData = bapi.getExportParameterList().getStructure("STOCKREQDETAILS");
        // Alternative: check the SPECIALSTOCKS table for breakdown by storage location

        System.out.println("Unrestricted stock: " +
            bapi.getExportParameterList().getString("TOTALUNRESTRICTED"));
    }
}
```

---

## 3. Stock Reservation via BAPI

Reservations are used to earmark stock for production orders, maintenance orders, or projects.  
They do not physically move stock but reduce available-to-promise (ATP) quantities.

### BAPI: BAPI_RESERVATION_CREATE1

**Import parameters:**

| Parameter | Description | Example |
|---|---|---|
| `RESERVATIONDATE` | Requirement date | `"20260530"` |

**Table RESERVATIONITEMS** (mandatory fields):

| Field | Description | Example |
|---|---|---|
| `RES_ITEM` | Item number | `"0001"` |
| `MATERIAL` | Material number | `"RAW-001"` |
| `PLANT` | Plant | `"1000"` |
| `STGE_LOC` | Storage location | `"0001"` |
| `MOVE_TYPE` | Movement type | `"261"` (GI for order) or `"201"` (GI for cost center) |
| `ENTRY_QNT` | Quantity | `"10"` |
| `ENTRY_UOM` | Unit of measure | `"EA"` |
| `COSTCENTER` | Cost center (if move_type 201) | `"10001000"` |
| `G_L_ACCOUNT` | G/L account (if account assignment) | `"400000"` |

**Java example:**

```java
JCoFunction bapi = dest.getRepository().getFunction("BAPI_RESERVATION_CREATE1");
bapi.getImportParameterList().setValue("RESERVATIONDATE", "20260530");

JCoTable items = bapi.getTableParameterList().getTable("RESERVATIONITEMS");
items.appendRow();
items.setValue("RES_ITEM",   "0001");
items.setValue("MATERIAL",   "RAW-001");
items.setValue("PLANT",      "1000");
items.setValue("STGE_LOC",   "0001");
items.setValue("MOVE_TYPE",  "261");
items.setValue("ENTRY_QNT",  new java.math.BigDecimal("10"));
items.setValue("ENTRY_UOM",  "EA");

bapi.execute(dest);

// ALWAYS commit
JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
commit.getImportParameterList().setValue("WAIT", "X");
commit.execute(dest);

String reservationNumber = bapi.getExportParameterList().getString("RESERVATION");
System.out.println("Reservation created: " + reservationNumber);
```

**SAP verification**: Transaction `MB23` → enter reservation number → verify.

---

## 4. Stock Type Reference

Understanding stock categories is critical — the OData field names are not intuitive.

| Stock Category | OData Field (`A_MatlStkInAcctMod`) | BAPI Field | Description |
|---|---|---|---|
| Unrestricted use | `MatlWrhsStkQtyInMatlBaseUnit` | `TOTALUNRESTRICTED` | Available for use immediately |
| Quality inspection | `QualityInspectionStockQuantity` | `TOTALQUALINSPECT` | Awaiting QM release |
| Blocked | `BlockedStockQuantity` | `TOTALBLOCKED` | Blocked, not available |
| Restricted use | `RestrictedUseStockQuantity` | `RESTRICTED` | Restricted-use (batch-specific) |
| GR blocked | `GoodsReceiptBlockedStockQty` | `TOTALBLOCKED` | Received but not posted |
| Stock in transit | `TransferStockStorageLoc` | `TRANSIT` | In transit between plants |
| Returns | `ReturnsBlockedStockQuantity` | `RETURNS` | Returns from customer |

**Available-to-promise (ATP)** = Unrestricted − open reservations − open sales order requirements.  
For full ATP check, use `BAPI_MATERIAL_AVAILABILITY` (separate BAPI).

---

## 5. Common Pitfalls

1. **Stock not showing in OData but visible in MMBE**: The `API_MATERIAL_STOCK_SRV` aggregates by accounting document (movement type). If your storage location has never had a goods movement posted, the entity record may not exist. Use `$filter` by `Material` and `Plant` only (omit `StorageLocation`) to see aggregate first.

2. **Unrestricted stock is 0 but MMBE shows stock**: Verify the `MatlWrhsStkQtyInMatlBaseUnit` field — this is warehouse-managed stock. For MM-managed stock (without WM), use `MatlStkInAcctMod/...` navigation. The field name changed between releases.

3. **BAPI_MATERIAL_STOCK_REQ_LIST returns no data for batch-managed materials**: This BAPI requires `BATCH` parameter for batch-managed materials. Pass the specific batch number, or use a loop across batches retrieved from `MCHB` table (via RFC `RFC_READ_TABLE` or custom RFC).

4. **Reservations not reducing ATP**: If the reservation uses the wrong movement type or lacks a proper account assignment, SAP may save it but not consume ATP. Verify `MB23` shows the reservation has status `Active` (not `Final issue`).

5. **Authorization errors on OData stock query**: Users need `M_MSEG_BWA` (Activity `Display` = 03) plus plant authorization `M_MSEG_WMB`. Check via transaction `SU53` after a failed attempt.
