# Usage examples

`SAP_CLI="<skill_dir>/scripts/sap_adt_cli.py"`.

## Source code

```bash
python3 "$SAP_CLI" get-program SAPMV45A
python3 "$SAP_CLI" get-class ZCL_MY_CLASS
python3 "$SAP_CLI" get-function BAPI_SALESORDER_CREATEFROMDAT2 --group BAPI_SD_SALESORDER
python3 "$SAP_CLI" get-include MV45AFZZ
python3 "$SAP_CLI" get-interface ZIF_MY_INTERFACE
```

Source commands print plain ABAP by default; redirect byte-for-byte:

```bash
python3 "$SAP_CLI" get-class ZCL_FOO > zcl_foo.abap
cat updated.abap | python3 "$SAP_CLI" write-source class ZCL_FOO --file -
```

## Dictionary

```bash
python3 "$SAP_CLI" get-table VBAK
python3 "$SAP_CLI" get-structure VBAKKOM
python3 "$SAP_CLI" get-type-info MATNR
```

On S/4HANA `get-table`/`get-structure` are served as DDL. Built-in types
(`abap.char(18)`, `abap.dec(13,2)`) carry length/decimals; data-element
references have null length and are listed in `meta.unparsed_types`. Field
descriptions are not available from this response and the key is omitted.

## Discovery

```bash
python3 "$SAP_CLI" search-object "ZCL_*" --max-results 20
python3 "$SAP_CLI" get-package ZMYPACKAGE
python3 "$SAP_CLI" get-transaction VA01
python3 "$SAP_CLI" get-cds-view ZI_INVENTORY_POSITION
python3 "$SAP_CLI" get-type-group ICON
```

## Write & activate (allow_write + confirmation each time)

```bash
python3 "$SAP_CLI" write-source class ZCL_MY_CLASS --file /tmp/zcl.abap
python3 "$SAP_CLI" write-source class ZCL_MY_CLASS --file /tmp/zcl.abap --activate
python3 "$SAP_CLI" write-source class ZCL_MY_CLASS --file /tmp/z.abap --yes  # trusted automation only
python3 "$SAP_CLI" activate class ZCL_MY_CLASS
```

## Where-used (read-only)

```bash
python3 "$SAP_CLI" where-used class ZCL_PAYMENT_PROCESSOR --max-results 50
python3 "$SAP_CLI" where-used interface ZIF_MY_INTERFACE
# objects[] may carry usage_line/usage_uri when the response names a position
```

## Open SQL via Data Preview (read-only, SELECT only)

```bash
python3 "$SAP_CLI" run-sql "SELECT * FROM t001 UP TO 10 ROWS"
python3 "$SAP_CLI" run-sql "SELECT bukrs, butxt FROM t001 UP TO 200 ROWS"
```

## Transports (read / write)

```bash
python3 "$SAP_CLI" list-transports                      # read-only
python3 "$SAP_CLI" create-transport --package '$TMP' --description "Fix rounding issue" \
  --ref /sap/bc/adt/programs/programs/zfix_rounding/source/main   # allow_transport + confirm
python3 "$SAP_CLI" release-transport DEVK900001          # irreversible + confirm
```

## Workflows

```bash
# unknown class
python3 "$SAP_CLI" search-object "ZCL_ORDER*"
python3 "$SAP_CLI" get-class ZCL_ORDER_HANDLER

# package contents
python3 "$SAP_CLI" get-package ZMYPACKAGE

# BAPI signature
python3 "$SAP_CLI" get-function BAPI_SALESORDER_CREATEFROMDAT2 --group BAPI_SD_SALESORDER

# table structure + field type
python3 "$SAP_CLI" get-table VBAK
python3 "$SAP_CLI" get-type-info VBELN

# transaction package/application
python3 "$SAP_CLI" get-transaction VA01

# safe write: syntax-check locally, then write+activate (fresh confirmation)
python3 "$SAP_CLI" syntax-check class ZCL_MY_CLASS
python3 "$SAP_CLI" write-source class ZCL_MY_CLASS --file ./zcl.abap --activate

# data check without SE16N
python3 "$SAP_CLI" run-sql "SELECT COUNT(*) AS cnt FROM ekko WHERE bstyp = 'F'"

# two transports = two independent confirmations (package + object REF required)
python3 "$SAP_CLI" create-transport --package ZSPRINT12 --description "Sprint 12 invoice fix" \
  --ref /sap/bc/adt/oo/classes/zcl_invoice/source/main
python3 "$SAP_CLI" release-transport DEVK900042
```

## SAP-side prerequisites

- ADT services active: `SICF` → `/sap/bc/adt` → Activate.
- Base authorization: role `SAP_ADT_BASE` or `S_ADT_RES`, `S_RFC`.
- Write/activate: `allow_write: true` plus `S_DEVELOP` `ACTVT=02`.
- Transport create/release: `allow_transport: true` plus `S_CTS_ADMI` or
  equivalent. `list-transports` needs no flag.
- Data preview: `/sap/bc/adt/datapreview` active in SICF.
