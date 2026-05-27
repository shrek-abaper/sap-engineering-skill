# Master Data Integration Scenarios

## Table of Contents
- [Overview](#overview)
- [Material Master](#material-master)
- [Business Partner (Customer / Vendor)](#business-partner-customer--vendor)
- [Organizational Data (Cost Center, Profit Center, Plant)](#organizational-data)
- [Version Matrix](#version-matrix)
- [Common Pitfalls](#common-pitfalls)

---

## Overview

Master data integration is among the most common—and most dangerous—integration scenarios. Unlike transactional data (POs, invoices), master data changes can silently break downstream processes across the entire system. Always apply extra validation before write operations.

**Golden rules for master data integration:**
1. **Read first, write cautiously.** Most external systems only need to read master data. Confirm write is truly necessary.
2. **Never delete via API.** Use logical flags (deletion indicator, block indicators) instead.
3. **Changes are immediate and system-wide.** Unlike a PO line update, a material master change affects all plants and all pending documents referencing that material.
4. **Use a staging system.** Test master data changes in DEV/QAS before replicating to PRD.

---

## Material Master

### Sub-scenarios

| Sub-scenario | S/4HANA On-Prem Recommendation | ECC Recommendation |
|---|---|---|
| Read material attributes (description, UoM, weight) | OData V2 `API_PRODUCT_SRV` GET | JCo `BAPI_MATERIAL_GET_ALL` |
| Read classification / characteristics | OData V2 `API_CLFN_PRODUCT_SRV` | JCo `BAPI_OBJCL_READ` |
| Create material | JCo `BAPI_MATERIAL_SAVEDATA` (all versions) | Same |
| Extend material to a new plant | JCo `BAPI_MATERIAL_SAVEDATA` with plant org level | Same |
| Change material description or UoM | JCo `BAPI_MATERIAL_SAVEDATA` (CHANGENUMBER required in change mode) | Same |
| Set deletion indicator | JCo `BAPI_MATERIAL_SAVEDATA` with `CLIENTDATA.DEL_FLAG = 'X'` | Same |
| Replicate material master from MDM | IDoc `MATMAS05` via PI/PO | Same |

> **Why JCo for create/change?** There is no standard OData V2/V4 service for creating or updating Material Master as of S/4HANA 2023. `API_PRODUCT_SRV` is read-only. SAP roadmap indicates a writeable V4 Product API for future releases (check SAP API Business Hub for current status).

---

### Read Material via OData (`API_PRODUCT_SRV`)

**Service**: `API_PRODUCT_SRV`
**Base URL**: `/sap/opu/odata/sap/API_PRODUCT_SRV/`
**Key entity sets**:
- `A_Product` — general data (description, base UoM, weight, dimensions)
- `A_ProductPlant` — plant-level data (MRP type, procurement type, storage location)
- `A_ProductDescription` — multi-language descriptions
- `A_ProductSalesDelivery` — sales org/distribution channel data
- `A_ProductPlantMRPArea` — MRP area settings

**Read basic material data:**
```bash
# Get material header + plant data in one call
curl -u APIUSER:pass \
  -H "Accept: application/json" \
  "https://s4hana.example.com:443/sap/opu/odata/sap/API_PRODUCT_SRV/A_Product('MAT-CHAIR-001')?\$expand=to_Description,to_Plant"
```

**Read a material with plant extension:**
```python
import requests

session = requests.Session()
session.auth = ("APIUSER", "password")
session.headers.update({"Accept": "application/json", "x-sap-client": "100"})

BASE = "https://s4hana.example.com:443/sap/opu/odata/sap/API_PRODUCT_SRV"

resp = session.get(
    f"{BASE}/A_ProductPlant(Product='MAT-CHAIR-001',Plant='1000')",
    params={"$expand": "to_MRPArea,to_StorageLocation"}
)
resp.raise_for_status()
plant_data = resp.json()["d"]
print(f"MRP Type: {plant_data['MRPType']}, Lot Size: {plant_data['LotSizeIndependentRequirmt']}")
```

**Filter materials changed after a timestamp:**
```
GET /A_Product?$filter=LastChangeDateTime gt datetime'2026-01-01T00:00:00'
             &$select=Product,ProductDescription,BaseUnit,LastChangeDateTime
             &$orderby=LastChangeDateTime desc
```

---

### Create/Change Material via JCo (`BAPI_MATERIAL_SAVEDATA`)

**BAPI**: `BAPI_MATERIAL_SAVEDATA`
**Important**: BAPI_MATERIAL_SAVEDATA is both create and change — it upserts. Use flag table `CLIENTDATAX` / `PLANTDATAX` (the "X structures") to indicate which fields to update.

**Minimal Java example — create material:**
```java
JCoDestination dest = JCoDestinationManager.getDestination("SAP_ERP");
JCoFunction bapi = dest.getRepository().getFunction("BAPI_MATERIAL_SAVEDATA");

// Header data
JCoStructure header = bapi.getImportParameterList().getStructure("HEADDATA");
header.setValue("MATERIAL", "MAT-NEW-001");
header.setValue("IND_SECTOR", "M");     // M = Mechanical engineering
header.setValue("MATL_TYPE", "ROH");    // ROH = Raw material
header.setValue("BASIC_VIEW", "X");     // Create basic data view

// Client-level data
JCoStructure clientData = bapi.getImportParameterList().getStructure("CLIENTDATA");
clientData.setValue("MATL_DESC", "New Raw Material");
clientData.setValue("BASE_UOM", "KG");
clientData.setValue("MATL_GROUP", "A001");
clientData.setValue("GROSS_WEIGHT", "5.0");
clientData.setValue("UNIT_OF_WT", "KG");

// X-structure: must set a flag for every field you populate
JCoStructure clientDataX = bapi.getImportParameterList().getStructure("CLIENTDATAX");
clientDataX.setValue("MATL_DESC", "X");
clientDataX.setValue("BASE_UOM", "X");
clientDataX.setValue("MATL_GROUP", "X");
clientDataX.setValue("GROSS_WEIGHT", "X");
clientDataX.setValue("UNIT_OF_WT", "X");

// Plant data (extend to plant 1000)
JCoTable plantData = bapi.getTableParameterList().getTable("PLANTDATA");
JCoTable plantDataX = bapi.getTableParameterList().getTable("PLANTDATAX");

plantData.appendRow();
plantData.setValue("PLANT", "1000");
plantData.setValue("PUR_GROUP", "001");
plantData.setValue("MRP_TYPE", "PD");       // PD = MRP
plantData.setValue("LOT_SIZE", "EX");       // EX = exact lot size
plantData.setValue("PLANT_VIEW", "X");

plantDataX.appendRow();
plantDataX.setValue("PLANT", "1000");
plantDataX.setValue("PUR_GROUP", "X");
plantDataX.setValue("MRP_TYPE", "X");
plantDataX.setValue("LOT_SIZE", "X");
plantDataX.setValue("PLANT_VIEW", "X");

bapi.execute(dest);

// Parse RETURN table
JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
for (int i = 0; i < returnTable.getNumRows(); i++) {
    returnTable.setRow(i);
    String type = returnTable.getString("TYPE");
    String msg = returnTable.getString("MESSAGE");
    if ("E".equals(type) || "A".equals(type)) {
        throw new RuntimeException("BAPI_MATERIAL_SAVEDATA failed: " + msg);
    }
}

// MANDATORY: commit
JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
commit.getImportParameterList().setValue("WAIT", "X");
commit.execute(dest);
```

**Key X-structure rule**: For every field you set in `CLIENTDATA` or `PLANTDATA`, you MUST set the corresponding field in `CLIENTDATAX` or `PLANTDATAX` to `"X"`. Fields not flagged in the X-structure are ignored, even if populated.

---

### Replicate Material Master via IDoc (`MATMAS05`)

Use when: bulk initial load, MDM-to-SAP, or external PIM sending catalog updates.

**IDoc type**: `MATMAS05`
**Message type**: `MATMAS`
**Key segments**:
- `E1MARAM` — basic data (material number, type, unit of measure)
- `E1MAKTM` — descriptions (one segment per language)
- `E1MARCM` — plant data (one segment per plant)
- `E1MARDM` — storage location data
- `E1MVKEM` — sales data (sales org / distribution channel)

**Setup**: In SAP transaction `CMOD`, ensure user exit `MBCF0002` is not blocking inbound MATMAS. Configure inbound partner profile in `WE20` with message type `MATMAS`.

---

## Business Partner (Customer / Vendor)

> **Important S/4HANA change**: In S/4HANA, Customer and Vendor master data are unified into the **Business Partner (BP)** object. The old transactions `XD01` (create customer) and `XK01` (create vendor) still exist as thin wrappers but write to the BP model. Always use BP APIs for S/4HANA.

### Sub-scenarios

| Sub-scenario | S/4HANA On-Prem Recommendation | ECC Recommendation |
|---|---|---|
| Read customer/vendor data | OData V2 `API_BUSINESS_PARTNER` | JCo `BAPI_CUSTOMER_GETDETAIL2` / `BAPI_VENDOR_GETDETAIL` |
| Create new customer | OData V2 `API_BUSINESS_PARTNER` POST | JCo `BAPI_CUSTOMER_CREATEFROMDATA1` |
| Create new vendor/supplier | OData V2 `API_BUSINESS_PARTNER` POST + role `FLVN01` | JCo `BAPI_VENDOR_CREATE` (ECC) |
| Update address or payment terms | OData V2 PATCH on `A_BusinessPartner` | JCo `BAPI_CUSTOMER_CHANGE` / `BAPI_VENDOR_CHANGE` |
| Replicate BP from CRM/MDG | IDoc `DEBMAS07` (Customer) / `CREMAS05` (Vendor) | Same |
| Block/unblock a business partner | OData V2 PATCH `PostingBlock` / `CustomerIsBlockedForPosting` | JCo `BAPI_CUSTOMER_CHANGE` |

---

### Read Business Partner via OData (`API_BUSINESS_PARTNER`)

**Service**: `API_BUSINESS_PARTNER`
**Base URL**: `/sap/opu/odata/sap/API_BUSINESS_PARTNER/`
**Key entity sets**:
- `A_BusinessPartner` — general BP data (name, category: person/org/group)
- `A_BusinessPartnerAddress` — address per usage type (BILL-TO, SHIP-TO)
- `A_Customer` — customer-specific data (account group, customer classification)
- `A_CustomerSalesArea` — sales org / distribution channel / division assignment
- `A_Supplier` — supplier/vendor-specific data (account group, payment terms)
- `A_SupplierCompany` — company code-level vendor data
- `A_SupplierPurchasingOrg` — purchasing org-level vendor data

```bash
# Read a customer with sales area data
curl -u APIUSER:pass \
  -H "Accept: application/json" \
  "https://s4hana.example.com:443/sap/opu/odata/sap/API_BUSINESS_PARTNER/A_Customer('0000001000')?\$expand=to_CustomerSalesArea,to_CustomerCompany"

# Search vendors by payment terms
curl -u APIUSER:pass \
  -H "Accept: application/json" \
  "https://s4hana.example.com:443/sap/opu/odata/sap/API_BUSINESS_PARTNER/A_SupplierCompany?\$filter=PaymentTerms eq 'NT30'&\$select=Supplier,CompanyCode,PaymentTerms"
```

---

### Create Business Partner via OData (S/4HANA)

BP creation requires a POST to `A_BusinessPartner` followed by separate POSTs to role-specific entity sets to enable the partner as Customer or Supplier.

**Step 1 — Create BP (organization):**
```json
POST /A_BusinessPartner
{
  "BusinessPartnerCategory": "2",
  "BusinessPartnerGrouping": "BP01",
  "FirstName": "",
  "LastName": "",
  "OrganizationBPName1": "New Supplier GmbH",
  "SearchTerm1": "NEWSUPPLIER",
  "Language": "EN",
  "to_BusinessPartnerAddress": {
    "results": [{
      "AddressUsage": "",
      "StreetName": "Hauptstrasse 10",
      "CityName": "München",
      "PostalCode": "80331",
      "Country": "DE",
      "Language": "DE"
    }]
  }
}
```

**Step 2 — Assign supplier role (FLVN01) and company code data:**
```json
POST /A_Supplier
{
  "Supplier": "<BP-NUMBER-FROM-STEP-1>"
}

PATCH /A_SupplierCompany(Supplier='<BP-NUMBER>',CompanyCode='1000')
{
  "PaymentTerms": "0001",
  "ReconciliationAccount": "0000160000",
  "AutomaticPostingToClearingAccount": false
}
```

---

## Organizational Data

### Cost Center (`API_COSTCENTER_SRV`)

**Service**: `API_COSTCENTER_SRV` (S/4HANA, read-only)
**Entity set**: `CostCenterCollection`

```bash
# Read all active cost centers in controlling area 1000
curl -u APIUSER:pass \
  "https://s4hana.example.com:443/sap/opu/odata/sap/API_COSTCENTER_SRV/CostCenterCollection?\$filter=ControllingArea eq '1000' and ValidityEndDate gt datetime'2026-01-01T00:00:00'&\$select=CostCenter,CostCenterName,CostCenterCategory,ResponsiblePerson"
```

**Create/change cost centers (S/4HANA)**: Use RAP OData V4 service `API_COSTCENTER` if available for your release, or JCo `BAPI_COSTCENTER_CREATEMULTIPLE`.

```java
// ECC / S/4HANA: Create cost center via BAPI
JCoFunction bapi = dest.getRepository().getFunction("BAPI_COSTCENTER_CREATEMULTIPLE");
JCoTable costCenterTable = bapi.getTableParameterList().getTable("COSTCENTERLIST");
costCenterTable.appendRow();
costCenterTable.setValue("CONTROLLINGAREA", "1000");
costCenterTable.setValue("COSTCENTER", "9990001");
costCenterTable.setValue("VALID_FROM", "20260101");
costCenterTable.setValue("VALID_TO", "99991231");
costCenterTable.setValue("NAME", "Integration Test CC");
costCenterTable.setValue("DESCRIPT", "Created via external API");
costCenterTable.setValue("COSTCENTER_TYPE", "E"); // E = General Expenses
bapi.execute(dest);
// Always check RETURN table and call BAPI_TRANSACTION_COMMIT
```

### Profit Center

**Read**: `API_PROFIT_CTR_SRV` (S/4HANA) — entity set `ProfitCenterCollection`
**Create/Change**: `BAPI_PROFITCENTER_CREATEMULTIPLE`

### Plant / Storage Location

Plant structure is configuration data maintained via SPRO and not typically created via API. For read:
```
GET /sap/opu/odata/sap/API_ENTERPRISEPROJECTSUBNETWORK_SRV/PlantCollection
```
For simpler plant lookups, the `API_PRODUCT_SRV` entity `A_ProductPlant` provides the list of plants a material is extended to.

---

## Version Matrix

| Scenario | ECC 6.0 | S/4HANA On-Prem 1909–2023 | S/4HANA Cloud Public |
|---|---|---|---|
| Read Material | `BAPI_MATERIAL_GET_ALL` | `API_PRODUCT_SRV` (OData V2) | `API_PRODUCT_SRV` (OData V4 variant) |
| Create Material | `BAPI_MATERIAL_SAVEDATA` | `BAPI_MATERIAL_SAVEDATA` (no OData write API yet) | Limited (use S/4HANA Cloud APIs) |
| Read BP/Customer/Vendor | `BAPI_CUSTOMER_GETDETAIL2` / `BAPI_VENDOR_GETDETAIL` | `API_BUSINESS_PARTNER` | `API_BUSINESS_PARTNER` |
| Create BP | `BAPI_CUSTOMER_CREATEFROMDATA1` / `BAPI_VENDOR_CREATE` | `API_BUSINESS_PARTNER` POST | `API_BUSINESS_PARTNER` POST |
| Read Cost Center | `BAPI_COSTCENTER_GETDETAIL` | `API_COSTCENTER_SRV` | `API_COSTCENTER_SRV` |
| Replicate via IDoc | `MATMAS05`, `DEBMAS07`, `CREMAS05` | Same + can use OData batch | IDoc restricted |

---

## Common Pitfalls

1. **Business Partner number vs. Customer/Vendor number**: In S/4HANA, a BP may have a separate BP number (e.g., `1000000050`) and a customer number (e.g., `0000001000`). `API_BUSINESS_PARTNER` uses the BP number. Legacy `BAPI_CUSTOMER_*` BAPIs use the customer number. Map carefully.

2. **X-structure fields in `BAPI_MATERIAL_SAVEDATA`**: The most common error when creating materials is forgetting to set the corresponding `X` field. SAP silently ignores un-flagged fields instead of returning an error. Always pair every data field with its X counterpart.

3. **Change documents and authorization**: Material Master changes in S/4HANA 2020+ may require a change number (`ECM - Engineering Change Management`) depending on the plant's configuration. If you get error `M3 036 "Change is not allowed without change number"`, the material is under ECM control.

4. **BP role assignment timing**: When creating a new Business Partner via OData, the `A_BusinessPartner` POST and the role assignment POST (`A_Customer` or `A_Supplier`) must be separate calls — deep insert is not supported for role assignment. The BP number returned from the first call is used as the key for subsequent calls.

5. **Language-dependent descriptions**: Material descriptions (`A_ProductDescription`) and BP names are stored per language. If you read without specifying language, SAP returns the logon language. Always filter explicitly: `$filter=Language eq 'EN'`.
