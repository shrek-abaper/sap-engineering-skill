# FI-AA: Fixed Asset Accounting Integration

## Table of Contents

1. [Scenario Overview](#scenario-overview)
2. [Read Asset List via BAPI](#1-read-asset-list-via-bapi)
3. [Read Asset Detail via BAPI](#2-read-asset-detail-via-bapi)
4. [Post Asset Acquisition](#3-post-asset-acquisition)
5. [Post Asset Retirement (Write-Off)](#4-post-asset-retirement-write-off)
6. [Post Asset Transfer (Intracompany)](#5-post-asset-transfer-intracompany)
7. [OData V4 for S/4HANA Cloud](#6-odata-v4-for-s4hana-cloud)
8. [Depreciation Run Integration](#7-depreciation-run-integration)
9. [Common Pitfalls](#8-common-pitfalls)

---

## Scenario Overview

| Sub-scenario | S/4HANA On-Prem recommendation | ECC 6.0 recommendation |
|---|---|---|
| Read asset list with book values | JCo `BAPI_FIXEDASSET_GETLIST` | Same |
| Read single asset master + values | JCo `BAPI_FIXEDASSET_GETDETAIL` | Same |
| Post external asset acquisition | JCo `BAPI_ASSET_ACQUISITION_CHECK` → `BAPI_ASSET_ACQUISITION_POST` | Same |
| Write off / retire asset | JCo `BAPI_ASSET_RETIREMENT_CHECK` → `BAPI_ASSET_RETIREMENT_POST` | Same |
| Intracompany asset transfer | JCo `BAPI_ASSET_TRANSFER_CHECK` → `BAPI_ASSET_TRANSFER_POST` | Same |
| Read asset master (S/4HANA Cloud) | OData V4 `CE_FIXEDASSET_0001` | N/A |
| Post acquisition (S/4HANA Cloud) | OData V4 `OP_FIXEDASSETACQUISITION_0001` | N/A |
| Post retirement (S/4HANA Cloud) | OData V4 `OP_FIXEDASSETRETIREMENT_0001` | N/A |

**Key architectural note**: On-Premise and ECC FI-AA write operations exclusively use JCo BAPIs. There is no standard OData V2 write service for asset posting in On-Premise deployments. S/4HANA Cloud Public Edition provides OData V4 services under Communication Arrangement `SAP_COM_0510`. The check-then-post pattern (always call `_CHECK` before `_POST`) is mandatory for all asset write BAPIs.

---

## 1. Read Asset List via BAPI

### BAPI_FIXEDASSET_GETLIST

Returns a list of fixed assets for a company code with current book values as of a given evaluation date.

**Import parameters**:

| Parameter | Type | Description | Required |
|---|---|---|---|
| `COMPANYCODE` | CHAR(4) | SAP company code | Yes |
| `EVALUATIONDATE` | DATE(8) | Valuation date (YYYYMMDD) | Yes |
| `DEPRECIATIONAREA` | NUMC(2) | Depreciation area (e.g., `01`=book depreciation) | Yes |
| `MAXENTRIES` | INT4 | Max rows to return; `0` = no limit | No |
| `ASSETCLASS` | CHAR(8) | Filter by asset class (optional) | No |
| `COSTCENTER` | CHAR(10) | Filter by cost center (optional) | No |

**Export tables**:

| Table | Type | Description |
|---|---|---|
| `GENERALDATA` | `BAPI1022_FEGLG004` | Asset master header: number, description, class, capitalization date |
| `DEPRECIATIONAREAVALS` | `BAPI1022_FEGLG005` | Book values per depreciation area |
| `RETURN` | `BAPIRET2` | Standard return messages |

**Key fields in `DEPRECIATIONAREAVALS`** (`BAPI1022_VALUES`):

| Field | Description |
|---|---|
| `DEPR_CURR_YEAR` | Depreciation posted in current fiscal year |
| `ACCUM_DEPR` | Accumulated depreciation (total life-to-date) |
| `CURRENT_APC` | Acquisition and Production Cost (gross book value) |
| `NET_BOOK_VAL` | Net book value = `CURRENT_APC` - `ACCUM_DEPR` |
| `ORDINARY_DEP` | Planned ordinary depreciation for the fiscal year |

```java
public static List<Map<String, Object>> getAssetList(
        JCoDestination dest, String companyCode, String evalDate, String deprArea)
        throws JCoException {

    JCoFunction fn = dest.getRepository().getFunction("BAPI_FIXEDASSET_GETLIST");
    JCoParameterList imp = fn.getImportParameterList();
    imp.setValue("COMPANYCODE",      companyCode);
    imp.setValue("EVALUATIONDATE",   evalDate);    // YYYYMMDD
    imp.setValue("DEPRECIATIONAREA", deprArea);    // e.g. "01" = book depreciation
    imp.setValue("MAXENTRIES",       0);           // 0 = no limit
    fn.execute(dest);

    // Check RETURN table for hard errors
    JCoTable ret = fn.getTableParameterList().getTable("RETURN");
    for (int i = 0; i < ret.getNumRows(); i++) {
        ret.setRow(i);
        String type = ret.getString("TYPE");
        if ("E".equals(type) || "A".equals(type)) {
            throw new RuntimeException("BAPI error: " + ret.getString("MESSAGE"));
        }
    }

    // Index DEPRECIATIONAREAVALS by "ASSET|SUBNUMBER" composite key
    JCoTable depVals = fn.getTableParameterList().getTable("DEPRECIATIONAREAVALS");
    Map<String, Map<String, String>> depMap = new HashMap<>();
    for (int i = 0; i < depVals.getNumRows(); i++) {
        depVals.setRow(i);
        String key = depVals.getString("ASSET") + "|" + depVals.getString("SUBNUMBER");
        Map<String, String> depRow = new HashMap<>();
        depRow.put("CURRENT_APC",    depVals.getString("CURRENT_APC"));
        depRow.put("ACCUM_DEPR",     depVals.getString("ACCUM_DEPR"));
        depRow.put("NET_BOOK_VAL",   depVals.getString("NET_BOOK_VAL"));
        depRow.put("DEPR_CURR_YEAR", depVals.getString("DEPR_CURR_YEAR"));
        depMap.put(key, depRow);
    }

    List<Map<String, Object>> assets = new ArrayList<>();
    JCoTable generalData = fn.getTableParameterList().getTable("GENERALDATA");
    for (int i = 0; i < generalData.getNumRows(); i++) {
        generalData.setRow(i);
        String assetNo = generalData.getString("ASSET");
        String subNo   = generalData.getString("SUBNUMBER");
        Map<String, String> dep = depMap.getOrDefault(assetNo + "|" + subNo, new HashMap<>());

        Map<String, Object> row = new LinkedHashMap<>();
        row.put("asset_number",        assetNo);
        row.put("subnumber",           subNo);
        row.put("description",         generalData.getString("DESCRIPT"));
        row.put("asset_class",         generalData.getString("ASSET_CLASS"));
        row.put("cost_center",         generalData.getString("COSTCENTER"));
        row.put("capitalization_date", generalData.getString("CAPITALDATE"));
        row.put("current_apc",         parseDouble(dep.get("CURRENT_APC")));
        row.put("accum_depr",          parseDouble(dep.get("ACCUM_DEPR")));
        row.put("net_book_value",      parseDouble(dep.get("NET_BOOK_VAL")));
        row.put("depr_curr_year",      parseDouble(dep.get("DEPR_CURR_YEAR")));
        assets.add(row);
    }
    return assets;
}

private static double parseDouble(String s) {
    if (s == null || s.isBlank()) return 0.0;
    try { return Double.parseDouble(s.trim()); } catch (NumberFormatException e) { return 0.0; }
}
```

---

## 2. Read Asset Detail via BAPI

### BAPI_FIXEDASSET_GETDETAIL

Returns complete master data and book values for a single asset (including all depreciation areas).

**Import parameters**:

| Parameter | Type | Description |
|---|---|---|
| `COMPANYCODE` | CHAR(4) | Company code |
| `ASSETMAINO` | CHAR(12) | Main asset number (zero-padded to 12 chars, e.g., `"000000123456"`) |
| `ASSETSUBNO` | CHAR(4) | Asset sub-number (usually `"0000"` for main asset) |
| `EVALUATIONDATE` | DATE(8) | Valuation date |
| `DEPRECIATIONAREA` | NUMC(2) | Depreciation area filter (leave blank for all areas) |

> **Gotcha**: `ASSETMAINO` must be exactly 12 characters, zero-padded from the left. Passing `"12345"` will return `ASSET_NOT_FOUND`. Always format with `str(asset_no).zfill(12)`.

**Export structures** (key):

| Export | Type | Key fields |
|---|---|---|
| `GENERALDATA` | `BAPI1022_FEGLG001` | `ASSET`, `DESCRIPT`, `ASSET_CLASS`, `COSTCENTER`, `PLANT`, `WBSELEMENT`, `CAPITALDATE`, `DEACTIVDATE` |
| `TIMEDEPENDENTDATA` | `BAPI1022_FEGLG002` | `COSTCENTER`, `PROFIT_CTR`, `PLANT` (time-dependent fields) |
| `DEPRECIATIONDATA` | `BAPI1022_FEGLG003` | `DEPRAREA`, `DEPRKEY`, `ULIFE_YRS`, `ULIFE_PER`, `DEPR_START` — useful life and key |
| `DEPRECIATIONAREAVALS` | `BAPI1022_FEGLG005` | See fields above |

```java
public static Map<String, Object> getAssetDetail(
        JCoDestination dest, String companyCode, String assetNo,
        String subNumber, String evalDate)
        throws JCoException {

    // ASSETMAINO must be exactly 12 chars, zero-padded from the left
    String assetPadded = String.format("%12s", assetNo).replace(' ', '0');
    String subPadded   = String.format("%4s",  subNumber).replace(' ', '0');

    JCoFunction fn = dest.getRepository().getFunction("BAPI_FIXEDASSET_GETDETAIL");
    JCoParameterList imp = fn.getImportParameterList();
    imp.setValue("COMPANYCODE",    companyCode);
    imp.setValue("ASSETMAINO",     assetPadded);
    imp.setValue("ASSETSUBNO",     subPadded);
    imp.setValue("EVALUATIONDATE", evalDate);   // YYYYMMDD
    fn.execute(dest);

    JCoTable ret = fn.getTableParameterList().getTable("RETURN");
    for (int i = 0; i < ret.getNumRows(); i++) {
        ret.setRow(i);
        String type = ret.getString("TYPE");
        if ("E".equals(type) || "A".equals(type)) {
            throw new RuntimeException(ret.getString("MESSAGE"));
        }
    }

    JCoStructure general  = fn.getExportParameterList().getStructure("GENERALDATA");
    JCoTable depAreas     = fn.getTableParameterList().getTable("DEPRECIATIONAREAVALS");

    List<Map<String, Object>> depList = new ArrayList<>();
    for (int i = 0; i < depAreas.getNumRows(); i++) {
        depAreas.setRow(i);
        Map<String, Object> area = new LinkedHashMap<>();
        area.put("area",           depAreas.getString("DEPRAREA"));
        area.put("current_apc",    parseDouble(depAreas.getString("CURRENT_APC")));
        area.put("accum_depr",     parseDouble(depAreas.getString("ACCUM_DEPR")));
        area.put("net_book_value", parseDouble(depAreas.getString("NET_BOOK_VAL")));
        depList.add(area);
    }

    Map<String, Object> result = new LinkedHashMap<>();
    result.put("asset",               general.getString("ASSET"));
    result.put("description",         general.getString("DESCRIPT"));
    result.put("asset_class",         general.getString("ASSET_CLASS"));
    result.put("cost_center",         general.getString("COSTCENTER"));
    result.put("plant",               general.getString("PLANT"));
    result.put("capitalization_date", general.getString("CAPITALDATE"));
    result.put("deactivation_date",   general.getString("DEACTIVDATE"));
    result.put("depreciation_areas",  depList);
    return result;
}
```

---

## 3. Post Asset Acquisition

Asset acquisition records the purchase or capitalization of a new fixed asset.

### Transaction types for acquisition

| Type | Description |
|---|---|
| `100` | External acquisition with vendor (MM invoice linked) |
| `110` | Acquisition with automatic offsetting entry (no vendor) |
| `120` | In-house acquisition (self-constructed) |

### Mandatory: always call CHECK before POST

```
BAPI_ASSET_ACQUISITION_CHECK  →  inspect RETURN for errors  →  BAPI_ASSET_ACQUISITION_POST  →  BAPI_TRANSACTION_COMMIT WAIT="X"
```

Never skip the `_CHECK` step. If `_CHECK` returns `TYPE = 'E'`, do not call `_POST`.

### Key import structures for BAPI_ASSET_ACQUISITION_POST

**`DOCUMENTHEADER`** (`BAPI1092_DOC_HDR1`):

| Field | Description | Example |
|---|---|---|
| `ASSET_VALUE_DATE` | Asset value date (YYYYMMDD) | `"20260501"` |
| `POSTING_DATE` | FI posting date | `"20260501"` |
| `DOC_DATE` | Document date (invoice date) | `"20260430"` |
| `COMP_CODE` | Company code | `"1000"` |
| `PSTNG_DATE` | Alias for posting date (some releases) | same as above |
| `REF_DOC_NO` | External reference number (e.g., invoice number) | `"INV-2026-001"` |
| `HEADER_TXT` | Document header text | `"PC purchase Q2"` |

**`ACQUISITIONDATA`** (`BAPI1092_ACQUISITIONDATA`):

| Field | Description | Example |
|---|---|---|
| `ASSET` | Main asset number (12-char zero-padded) | `"000000123456"` |
| `SUB_NUMBER` | Sub-number | `"0000"` |
| `TRANSACTION_TYPE` | Asset transaction type | `"100"` |
| `AMOUNT` | Acquisition amount (always positive) | `"50000.00"` |
| `CURRENCY` | Transaction currency | `"CNY"` |
| `QUANTITY` | Quantity (for quantity-tracked assets) | `"1"` |
| `BASE_UOM` | Base unit of measure | `"EA"` |

```java
public static Map<String, String> postAssetAcquisition(
        JCoDestination dest, String companyCode, String assetNo,
        double amount, String currency, String postingDate,
        String refDocNo, String headerText, boolean dryRun)
        throws JCoException {

    String assetPadded = String.format("%12s", assetNo).replace(' ', '0');

    // Step 1: CHECK
    JCoFunction checkFn = dest.getRepository().getFunction("BAPI_ASSET_ACQUISITION_CHECK");
    setAcquisitionParams(checkFn, companyCode, assetPadded, amount, currency,
                         postingDate, refDocNo, headerText);
    checkFn.execute(dest);

    JCoTable checkRet = checkFn.getTableParameterList().getTable("RETURN");
    for (int i = 0; i < checkRet.getNumRows(); i++) {
        checkRet.setRow(i);
        String type = checkRet.getString("TYPE");
        if ("E".equals(type) || "A".equals(type)) {
            throw new RuntimeException("CHECK failed: " + checkRet.getString("MESSAGE"));
        }
    }
    if (dryRun) {
        return Map.of("dry_run", "true", "status", "CHECK_PASSED");
    }

    // Step 2: POST
    JCoFunction postFn = dest.getRepository().getFunction("BAPI_ASSET_ACQUISITION_POST");
    setAcquisitionParams(postFn, companyCode, assetPadded, amount, currency,
                         postingDate, refDocNo, headerText);
    postFn.execute(dest);

    JCoTable postRet = postFn.getTableParameterList().getTable("RETURN");
    for (int i = 0; i < postRet.getNumRows(); i++) {
        postRet.setRow(i);
        String type = postRet.getString("TYPE");
        if ("E".equals(type) || "A".equals(type)) {
            dest.getRepository().getFunction("BAPI_TRANSACTION_ROLLBACK").execute(dest);
            throw new RuntimeException("POST failed: " + postRet.getString("MESSAGE"));
        }
    }

    // Step 3: COMMIT — mandatory
    JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
    commit.getImportParameterList().setValue("WAIT", "X");
    commit.execute(dest);

    JCoStructure docRef = postFn.getExportParameterList().getStructure("DOCUMENTREFERENCE");
    return Map.of(
        "success",      "true",
        "company_code", docRef.getString("COMP_CODE"),
        "fiscal_year",  docRef.getString("FISC_YEAR"),
        "document_no",  docRef.getString("DOC_NO")
    );
}

private static void setAcquisitionParams(JCoFunction fn, String companyCode,
        String assetPadded, double amount, String currency,
        String postingDate, String refDocNo, String headerText) throws JCoException {

    JCoStructure docHdr = fn.getImportParameterList().getStructure("DOCUMENTHEADER");
    docHdr.setValue("ASSET_VALUE_DATE", postingDate);
    docHdr.setValue("POSTING_DATE",     postingDate);
    docHdr.setValue("DOC_DATE",         postingDate);
    docHdr.setValue("COMP_CODE",        companyCode);
    docHdr.setValue("REF_DOC_NO",       refDocNo.length() > 16 ? refDocNo.substring(0, 16) : refDocNo);
    docHdr.setValue("HEADER_TXT",       headerText.length() > 25 ? headerText.substring(0, 25) : headerText);

    JCoStructure acqData = fn.getImportParameterList().getStructure("ACQUISITIONDATA");
    acqData.setValue("ASSET",            assetPadded);
    acqData.setValue("SUB_NUMBER",       "0000");
    acqData.setValue("TRANSACTION_TYPE", "100");   // external acquisition
    acqData.setValue("AMOUNT",           String.valueOf(amount));
    acqData.setValue("CURRENCY",         currency);
}
```

**`DOCUMENTREFERENCE`** export structure:

| Field | Description |
|---|---|
| `COMP_CODE` | Company code |
| `FISC_YEAR` | Fiscal year |
| `DOC_NO` | FI document number |
| `ASSET_VALUE_DATE` | Asset value date used |

---

## 4. Post Asset Retirement (Write-Off)

Asset retirement records the removal of a fixed asset from the books — either by sale or write-off.

### Transaction types for retirement

| Type | Description |
|---|---|
| `210` | Retirement without revenue (write-off / scrapping) |
| `250` | Retirement with revenue (sale) |
| `260` | Retirement of a portion of an asset |

### Key import structures for BAPI_ASSET_RETIREMENT_POST

**`RETIREMENTDATA`** (`BAPI1092_RETIREMENTDATA`):

| Field | Description | Example |
|---|---|---|
| `ASSET` | Main asset number (zero-padded 12) | `"000000123456"` |
| `SUB_NUMBER` | Sub-number | `"0000"` |
| `TRANSACTION_TYPE` | Retirement type | `"210"` |
| `AMOUNT` | Amount to retire (for partial retirement; 0=full) | `"0"` |
| `QUANTITY` | Quantity to retire (for quantity-tracked assets) | `"0"` |
| `CURRENCY` | Currency | `"CNY"` |

```java
public static Map<String, String> postAssetRetirement(
        JCoDestination dest, String companyCode, String assetNo,
        String postingDate, String refDocNo,
        double amount, String currency, String transactionType)
        throws JCoException {

    String assetPadded = String.format("%12s", assetNo).replace(' ', '0');

    // Step 1: CHECK
    JCoFunction checkFn = dest.getRepository().getFunction("BAPI_ASSET_RETIREMENT_CHECK");
    setRetirementParams(checkFn, companyCode, assetPadded, postingDate, refDocNo,
                        amount, currency, transactionType);
    checkFn.execute(dest);

    JCoTable checkRet = checkFn.getTableParameterList().getTable("RETURN");
    for (int i = 0; i < checkRet.getNumRows(); i++) {
        checkRet.setRow(i);
        String type = checkRet.getString("TYPE");
        if ("E".equals(type) || "A".equals(type)) {
            throw new RuntimeException("CHECK failed: " + checkRet.getString("MESSAGE"));
        }
    }

    // Step 2: POST
    JCoFunction postFn = dest.getRepository().getFunction("BAPI_ASSET_RETIREMENT_POST");
    setRetirementParams(postFn, companyCode, assetPadded, postingDate, refDocNo,
                        amount, currency, transactionType);
    postFn.execute(dest);

    JCoTable postRet = postFn.getTableParameterList().getTable("RETURN");
    for (int i = 0; i < postRet.getNumRows(); i++) {
        postRet.setRow(i);
        String type = postRet.getString("TYPE");
        if ("E".equals(type) || "A".equals(type)) {
            dest.getRepository().getFunction("BAPI_TRANSACTION_ROLLBACK").execute(dest);
            throw new RuntimeException(postRet.getString("MESSAGE"));
        }
    }

    // Step 3: COMMIT — mandatory
    JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
    commit.getImportParameterList().setValue("WAIT", "X");
    commit.execute(dest);

    JCoStructure docRef = postFn.getExportParameterList().getStructure("DOCUMENTREFERENCE");
    return Map.of(
        "success",     "true",
        "document_no", docRef.getString("DOC_NO"),
        "fiscal_year", docRef.getString("FISC_YEAR")
    );
}

private static void setRetirementParams(JCoFunction fn, String companyCode,
        String assetPadded, String postingDate, String refDocNo,
        double amount, String currency, String transactionType) throws JCoException {

    JCoStructure docHdr = fn.getImportParameterList().getStructure("DOCUMENTHEADER");
    docHdr.setValue("ASSET_VALUE_DATE", postingDate);
    docHdr.setValue("POSTING_DATE",     postingDate);
    docHdr.setValue("DOC_DATE",         postingDate);
    docHdr.setValue("COMP_CODE",        companyCode);
    docHdr.setValue("REF_DOC_NO",       refDocNo.length() > 16 ? refDocNo.substring(0, 16) : refDocNo);

    JCoStructure retData = fn.getImportParameterList().getStructure("RETIREMENTDATA");
    retData.setValue("ASSET",            assetPadded);
    retData.setValue("SUB_NUMBER",       "0000");
    retData.setValue("TRANSACTION_TYPE", transactionType);
    retData.setValue("AMOUNT",           String.valueOf(amount));  // 0 = full remaining NBV
    retData.setValue("QUANTITY",         "0");
    retData.setValue("CURRENCY",         currency);
}
```

---

## 5. Post Asset Transfer (Intracompany)

Asset transfer moves an asset from one cost center, plant, or asset class to another within the same company code.

### Transaction type

| Type | Description |
|---|---|
| `300` | Intracompany transfer (same company code) |
| `320` | Intercompany transfer (different company codes — requires additional BAPI sequence) |

### Key import structures for BAPI_ASSET_TRANSFER_POST

**`TRANSFERDATA`** (`BAPI1092_TRANSFERDATA`):

| Field | Description |
|---|---|
| `SENDING_ASSET` | Source asset number (12-char zero-padded) |
| `SENDING_SUB_NUMBER` | Source sub-number |
| `RECEIVING_ASSET` | Target asset number (must exist in SAP) |
| `RECEIVING_SUB_NUMBER` | Target sub-number |
| `TRANSACTION_TYPE` | `"300"` for intracompany |
| `AMOUNT` | Amount to transfer (0 = full transfer) |
| `CURRENCY` | Currency |

```java
public static Map<String, String> postAssetTransfer(
        JCoDestination dest, String companyCode,
        String fromAsset, String toAsset,
        String postingDate, String refDocNo,
        double amount, String currency)
        throws JCoException {

    String fromPadded = String.format("%12s", fromAsset).replace(' ', '0');
    String toPadded   = String.format("%12s", toAsset).replace(' ', '0');

    // Step 1: CHECK
    JCoFunction checkFn = dest.getRepository().getFunction("BAPI_ASSET_TRANSFER_CHECK");
    setTransferParams(checkFn, companyCode, fromPadded, toPadded,
                      postingDate, refDocNo, amount, currency);
    checkFn.execute(dest);

    JCoTable checkRet = checkFn.getTableParameterList().getTable("RETURN");
    for (int i = 0; i < checkRet.getNumRows(); i++) {
        checkRet.setRow(i);
        String type = checkRet.getString("TYPE");
        if ("E".equals(type) || "A".equals(type)) {
            throw new RuntimeException("CHECK failed: " + checkRet.getString("MESSAGE"));
        }
    }

    // Step 2: POST
    JCoFunction postFn = dest.getRepository().getFunction("BAPI_ASSET_TRANSFER_POST");
    setTransferParams(postFn, companyCode, fromPadded, toPadded,
                      postingDate, refDocNo, amount, currency);
    postFn.execute(dest);

    JCoTable postRet = postFn.getTableParameterList().getTable("RETURN");
    for (int i = 0; i < postRet.getNumRows(); i++) {
        postRet.setRow(i);
        String type = postRet.getString("TYPE");
        if ("E".equals(type) || "A".equals(type)) {
            dest.getRepository().getFunction("BAPI_TRANSACTION_ROLLBACK").execute(dest);
            throw new RuntimeException(postRet.getString("MESSAGE"));
        }
    }

    // Step 3: COMMIT — mandatory
    JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
    commit.getImportParameterList().setValue("WAIT", "X");
    commit.execute(dest);

    JCoStructure docRef = postFn.getExportParameterList().getStructure("DOCUMENTREFERENCE");
    return Map.of(
        "success",     "true",
        "document_no", docRef.getString("DOC_NO"),
        "fiscal_year", docRef.getString("FISC_YEAR")
    );
}

private static void setTransferParams(JCoFunction fn, String companyCode,
        String fromPadded, String toPadded, String postingDate,
        String refDocNo, double amount, String currency) throws JCoException {

    JCoStructure docHdr = fn.getImportParameterList().getStructure("DOCUMENTHEADER");
    docHdr.setValue("ASSET_VALUE_DATE", postingDate);
    docHdr.setValue("POSTING_DATE",     postingDate);
    docHdr.setValue("DOC_DATE",         postingDate);
    docHdr.setValue("COMP_CODE",        companyCode);
    docHdr.setValue("REF_DOC_NO",       refDocNo.length() > 16 ? refDocNo.substring(0, 16) : refDocNo);

    JCoStructure tfData = fn.getImportParameterList().getStructure("TRANSFERDATA");
    tfData.setValue("SENDING_ASSET",        fromPadded);
    tfData.setValue("SENDING_SUB_NUMBER",   "0000");
    tfData.setValue("RECEIVING_ASSET",      toPadded);
    tfData.setValue("RECEIVING_SUB_NUMBER", "0000");
    tfData.setValue("TRANSACTION_TYPE",     "300");   // intracompany transfer
    tfData.setValue("AMOUNT",               String.valueOf(amount));  // 0 = full transfer
    tfData.setValue("CURRENCY",             currency);
}
```

---

## 6. OData V4 for S/4HANA Cloud

S/4HANA Cloud Public Edition exposes fixed asset operations as OData V4 services. These are the recommended approach for cloud deployments and are not available in On-Premise systems (verify service availability per release).

**Communication Arrangement**: `SAP_COM_0510` — Fixed Assets Integration

### Read asset master: CE_FIXEDASSET_0001

```bash
# List all active assets in company code 1710
curl -u "s4cloud_user:password" \
  -H "Accept: application/json" \
  "https://my-tenant.s4hana.cloud.sap/sap/opu/odata4/sap/ce_fixedasset_0001/srvd/sap/fixedasset/0001/FixedAsset?\
\$filter=CompanyCode eq '1710' and IsMarkedForDeletion eq false\
&\$select=CompanyCode,MasterFixedAsset,FixedAsset,FixedAssetDescription,\
AssetClass,CostCenter,PlantSection,CapitalizationDate\
&\$top=100"
```

**Key entity fields**:

| Field | Description |
|---|---|
| `MasterFixedAsset` | Main asset number |
| `FixedAsset` | Sub-number |
| `FixedAssetDescription` | Description |
| `AssetClass` | Asset class code |
| `CostCenter` | Cost center assignment |
| `CapitalizationDate` | Date asset was capitalized |
| `PlannedAcqnAndProdCosts` | Planned APC (acquisition cost) |
| `AccumulatedDepreciation` | Accumulated depreciation |
| `NetBookValue` | Net book value |

### Post acquisition: OP_FIXEDASSETACQUISITION_0001

```bash
# Fetch CSRF token
TOKEN=$(curl -s -u "s4user:password" \
  -H "x-csrf-token: fetch" -I \
  "https://my-tenant.s4hana.cloud.sap/sap/opu/odata4/sap/op_fixedassetacquisition_0001/srvd/sap/fixedassetacquisition/0001/" \
  | grep -i "x-csrf-token:" | awk '{print $2}' | tr -d '\r')

# Post acquisition
curl -u "s4user:password" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "x-csrf-token: $TOKEN" \
  "https://my-tenant.s4hana.cloud.sap/sap/opu/odata4/sap/op_fixedassetacquisition_0001/srvd/sap/fixedassetacquisition/0001/FixedAssetAcquisition" \
  -d '{
    "CompanyCode": "1710",
    "MasterFixedAsset": "100001",
    "FixedAsset": "0",
    "DocumentDate": "2026-05-01",
    "PostingDate": "2026-05-01",
    "AssetValueDate": "2026-05-01",
    "TransactionType": "100",
    "AmountInTransactionCurrency": "50000.00",
    "TransactionCurrency": "USD",
    "DocumentReferenceID": "INV-2026-001",
    "DocumentHeaderText": "Server rack purchase"
  }'
```

### Post retirement: OP_FIXEDASSETRETIREMENT_0001

```bash
curl -u "s4user:password" -X POST \
  -H "Content-Type: application/json" \
  -H "x-csrf-token: $TOKEN" \
  "https://my-tenant.s4hana.cloud.sap/sap/opu/odata4/sap/op_fixedassetretirement_0001/srvd/sap/fixedassetretirement/0001/FixedAssetRetirement" \
  -d '{
    "CompanyCode": "1710",
    "MasterFixedAsset": "100001",
    "FixedAsset": "0",
    "DocumentDate": "2026-05-31",
    "PostingDate": "2026-05-31",
    "AssetValueDate": "2026-05-31",
    "TransactionType": "210",
    "AmountInTransactionCurrency": "0",
    "TransactionCurrency": "USD",
    "DocumentReferenceID": "SCRAP-001"
  }'
```

> **Note**: `AmountInTransactionCurrency: "0"` with transaction type `210` retires the full remaining net book value. To do a partial retirement, specify the exact amount.

### Revaluation: OP_FIXEDASSETREVALUATION_0001

Used for upward revaluation of asset values (common in IFRS reporting):

```bash
curl -u "s4user:password" -X POST \
  -H "Content-Type: application/json" \
  -H "x-csrf-token: $TOKEN" \
  "https://my-tenant.s4hana.cloud.sap/sap/opu/odata4/sap/op_fixedassetrevaluation_0001/srvd/sap/fixedassetrevaluation/0001/FixedAssetRevaluation" \
  -d '{
    "CompanyCode": "1710",
    "MasterFixedAsset": "100001",
    "FixedAsset": "0",
    "PostingDate": "2026-12-31",
    "AssetValueDate": "2026-12-31",
    "TransactionType": "700",
    "AmountInTransactionCurrency": "5000.00",
    "TransactionCurrency": "USD",
    "DocumentHeaderText": "Year-end revaluation"
  }'
```

---

## 7. Depreciation Run Integration

External systems (FSSC, reporting tools) typically read depreciation data rather than trigger runs. Depreciation posting runs are executed in SAP via transaction `AFAB` or `RAPOST2000`.

### Read posted depreciation amounts via OData

```bash
# Posted depreciation line items via journal entry API
curl -u "APIUSER:password" \
  -H "Accept: application/json" \
  -H "x-sap-client: 100" \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_JOURNALENTRYITEMBASIC_SRV/\
A_JournalEntryItemBasic?\
\$filter=CompanyCode eq '1000' \
and FiscalYear eq '2026' \
and GLAccount eq '160010'\
&\$select=CompanyCode,FiscalYear,AccountingDocument,DocumentItemText,\
PostingDate,AmountInCompanyCodeCurrency,CompanyCodeCurrency,\
CostCenter,ProfitCenter,Segment\
&\$orderby=PostingDate asc"
```

> Replace `GLAccount eq '160010'` with your accumulated depreciation account. Asset accounts typically reside in account range 1xxxxx for Chinese GAAP (CAS) or IFRS implementations.

### Key BAPI for depreciation forecast: BAPI_FIXEDASSET_GETLIST with future date

Setting `EVALUATIONDATE` to a future date returns projected book values including planned depreciation, useful for FSSC forecasting:

```python
# Get projected book value at year-end
from datetime import date
projected = get_asset_list(conn, "1000", date(2026, 12, 31), depr_area="01")
```

---

## 8. Common Pitfalls

### 1. ASSETMAINO not zero-padded
**Symptom**: `BAPI_FIXEDASSET_GETDETAIL` returns `ASSET_NOT_FOUND` despite valid asset number.  
**Cause**: `ASSETMAINO` is a 12-character field; passing `"12345"` is interpreted as asset `"12345       "` (right-padded), not `"000000012345"`.  
**Fix**: Always `str(asset_no).zfill(12)`.

### 2. Forgetting BAPI_TRANSACTION_COMMIT after POST
**Symptom**: No FI document created; no error returned either.  
**Cause**: Without `BAPI_TRANSACTION_COMMIT WAIT="X"`, SAP holds the LUW (Logical Unit of Work) open. The posting is silently discarded when the JCo connection closes.  
**Fix**: Always call `BAPI_TRANSACTION_COMMIT` with `WAIT="X"` immediately after each successful `_POST`. If `_POST` returns errors, call `BAPI_TRANSACTION_ROLLBACK` instead.

### 3. Calling POST without CHECK
**Symptom**: Inconsistent results — `_POST` sometimes succeeds on invalid data, sometimes raises a hard ABAP dump.  
**Cause**: BAPIs do less validation in `_POST` than in `_CHECK`. Skipping `_CHECK` bypasses the full validation layer.  
**Fix**: Always call `_CHECK` first and halt if any `TYPE = 'E'` message is present.

### 4. Fiscal period closed
**Symptom**: `BAPI_ASSET_ACQUISITION_POST` returns `Message AA318: Posting period XX/YYYY is not open`.  
**Cause**: FI-AA posting periods (transaction `OAAQ`) are separate from general FI posting periods (`OB52`). Both must be open.  
**Fix**: Coordinate with the SAP basis/finance team to open the FI-AA posting period, or shift the `POSTING_DATE` to an open period.

### 5. Asset already fully depreciated
**Symptom**: Retirement POST returns `AA390: Asset … has already been fully retired`.  
**Cause**: Asset net book value is already zero; SAP will not allow a second full retirement.  
**Fix**: Query current NBV using `BAPI_FIXEDASSET_GETDETAIL` before attempting retirement. Skip if NBV = 0.

### 6. Transaction type not allowed for asset class
**Symptom**: `_CHECK` returns `AA632: Transaction type … not allowed for asset class …`.  
**Cause**: Asset class configuration in SAP restricts which transaction types are permitted.  
**Fix**: Verify the asset class configuration in transaction `AAOT` or consult the FI-AA configuration team to add the required transaction type to the asset class.

### 7. S/4HANA Cloud OData V4 service not activated
**Symptom**: HTTP 404 when calling `CE_FIXEDASSET_0001`.  
**Cause**: Communication Arrangement `SAP_COM_0510` not created, or the communication user lacks the Fixed Assets role.  
**Fix**: In SAP S/4HANA Cloud admin cockpit, create Communication Arrangement `SAP_COM_0510`, assign a Communication User with role `SAP_BR_FIXED_ASSETS_ACCOUNTANT`, and note the generated service URL.

### 8. Amount sign for partial retirement
**Symptom**: Partial retirement using `AMOUNT` results in wrong posting (too much or wrong direction).  
**Cause**: `AMOUNT` in `RETIREMENTDATA` must be a **positive** value representing how much of the APC to retire. It is not signed.  
**Fix**: Pass a positive amount, e.g., `"10000.00"` to retire CNY 10,000 of the asset's acquisition cost. SAP automatically calculates the proportional accumulated depreciation.
