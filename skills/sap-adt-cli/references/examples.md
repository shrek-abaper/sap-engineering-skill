# Usage examples

All examples use the installed `sap-adt` command (see `setup.md` for install
channels). The legacy `scripts/sap_adt_cli.py` shim accepts the same
arguments during the compat window.

## Source code

```bash
sap-adt get-program SAPMV45A
sap-adt get-class ZCL_MY_CLASS
sap-adt get-function BAPI_SALESORDER_CREATEFROMDAT2 --group BAPI_SD_SALESORDER
sap-adt get-include MV45AFZZ
sap-adt get-interface ZIF_MY_INTERFACE
```

Source commands print plain ABAP by default; redirect byte-for-byte:

```bash
sap-adt get-class ZCL_FOO > zcl_foo.abap
cat updated.abap | sap-adt write-source class ZCL_FOO --file -
```

## Dictionary

```bash
sap-adt get-table VBAK
sap-adt get-structure VBAKKOM
sap-adt get-type-info MATNR
```

On S/4HANA `get-table`/`get-structure` are served as DDL. Built-in types
(`abap.char(18)`, `abap.dec(13,2)`) carry length/decimals; data-element
references have null length and are listed in `meta.unparsed_types`. Field
descriptions are not available from this response and the key is omitted.

## Discovery

```bash
sap-adt search-object "ZCL_*" --max-results 20
sap-adt get-package ZMYPACKAGE
sap-adt get-transaction VA01
sap-adt get-cds-view ZI_INVENTORY_POSITION
sap-adt get-type-group ICON
```

## Write & activate (allow_write + confirmation each time)

```bash
sap-adt write-source class ZCL_MY_CLASS --file /tmp/zcl.abap
sap-adt write-source class ZCL_MY_CLASS --file /tmp/zcl.abap --activate
sap-adt write-source class ZCL_MY_CLASS --file /tmp/z.abap --yes  # trusted automation only
sap-adt activate class ZCL_MY_CLASS
```

## Where-used (read-only)

```bash
sap-adt where-used class ZCL_PAYMENT_PROCESSOR --max-results 50
sap-adt where-used interface ZIF_MY_INTERFACE
# objects[] may carry usage_line/usage_uri when the response names a position
```

## Open SQL via Data Preview (read-only, SELECT only)

```bash
sap-adt run-sql "SELECT * FROM t001 UP TO 10 ROWS"
sap-adt run-sql "SELECT bukrs, butxt FROM t001 UP TO 200 ROWS"
```

## Transports (read / write)

```bash
sap-adt list-transports                      # read-only
sap-adt create-transport --package '$TMP' --description "Fix rounding issue" \
  --ref /sap/bc/adt/programs/programs/zfix_rounding/source/main   # allow_transport + confirm
sap-adt release-transport DEVK900001          # irreversible + confirm
```

## Workflows

```bash
# unknown class
sap-adt search-object "ZCL_ORDER*"
sap-adt get-class ZCL_ORDER_HANDLER

# package contents
sap-adt get-package ZMYPACKAGE

# BAPI signature
sap-adt get-function BAPI_SALESORDER_CREATEFROMDAT2 --group BAPI_SD_SALESORDER

# table structure + field type
sap-adt get-table VBAK
sap-adt get-type-info VBELN

# transaction package/application
sap-adt get-transaction VA01

# safe write: syntax-check locally, then write+activate (fresh confirmation)
sap-adt syntax-check class ZCL_MY_CLASS
sap-adt write-source class ZCL_MY_CLASS --file ./zcl.abap --activate

# data check without SE16N
sap-adt run-sql "SELECT COUNT(*) AS cnt FROM ekko WHERE bstyp = 'F'"

# two transports = two independent confirmations (package + object REF required)
sap-adt create-transport --package ZSPRINT12 --description "Sprint 12 invoice fix" \
  --ref /sap/bc/adt/oo/classes/zcl_invoice/source/main
sap-adt release-transport DEVK900042
```

## SAP-side prerequisites

- ADT services active: `SICF` → `/sap/bc/adt` → Activate.
- Base authorization: role `SAP_ADT_BASE` or `S_ADT_RES`, `S_RFC`.
- Write/activate: `allow_write: true` plus `S_DEVELOP` `ACTVT=02`.
- Transport create/release: `allow_transport: true` plus `S_CTS_ADMI` or
  equivalent. `list-transports` needs no flag.
- Data preview: `/sap/bc/adt/datapreview` active in SICF.
