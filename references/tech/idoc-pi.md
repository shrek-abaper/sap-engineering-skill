# IDoc / SAP PI-PO Integration Reference

## Table of Contents

1. [When to Use IDoc](#1-when-to-use-idoc)
2. [IDoc Anatomy](#2-idoc-anatomy)
3. [Inbound IDoc Processing Setup](#3-inbound-idoc-processing-setup)
4. [Outbound IDoc Triggering](#4-outbound-idoc-triggering)
5. [IDoc Status Lifecycle](#5-idoc-status-lifecycle)
6. [SAP PI/PO Channel Types](#6-sap-pipo-channel-types)
7. [Monitoring IDocs](#7-monitoring-idocs)
8. [ORDERS05 Key Segments](#8-orders05-key-segments)
9. [Common Error Patterns](#9-common-error-patterns)

---

## 1. When to Use IDoc

| Scenario | Use IDoc |
|---|---|
| Asynchronous integration (fire-and-forget) | Yes |
| EDI with external partners (suppliers, customers) | Yes — IDoc is the native EDI format |
| Event-driven: SAP triggers notification on business event (PO creation, delivery) | Yes |
| ECC + S/4HANA On-Premise | Yes (fully supported in both) |
| S/4HANA Cloud Public | Limited (specific standard IDocs only; check SAP documentation) |
| Near-real-time synchronous call | No — use OData or RFC |
| Ad-hoc query (read-only, on-demand) | No — use OData GET |
| Large volume message exchange with external EDI system | Yes — most EDI VAN/translators speak IDoc natively |

**IDoc strengths over OData/RFC:**
- Built-in retry and monitoring (WE02, BD87)
- Status tracking throughout the process chain
- Native SAP audit trail
- Works with SAP PI/PO middleware for format translation
- Supports transformation to EDIFACT, X12, XML automatically via PI/PO

---

## 2. IDoc Anatomy

An IDoc (Intermediate Document) consists of three record types in a strict hierarchy:

### Control Record (EDI_DC40)

One per IDoc. Contains routing and metadata.

| Field | Description | Example |
|---|---|---|
| `TABNAM` | Control record type | `EDI_DC40` |
| `MANDT` | Client | `100` |
| `DOCNUM` | IDoc document number (16 digits) | `0000000000000001` |
| `DOCREL` | SAP release | `756` |
| `STATUS` | Current status code | `03` |
| `DIRECT` | Direction: 1=outbound, 2=inbound | `1` |
| `OUTMOD` | Output mode (1=immediate, 2=collect, 4=no output) | `1` |
| `EXPRSS` | Override partner profile if set | `` |
| `MESTYP` | Message type | `ORDERS` |
| `MESCOD` | Message code (optional) | `` |
| `MESFCT` | Message function (optional) | `` |
| `STD` | EDI standard (`UN`=EDIFACT, `AN`=ANSI) | `UN` |
| `STDVRS` | Standard version | `D96A` |
| `STDMES` | Standard message type | `ORDERS` |
| `SNDPOR` | Sending port | `SAPECC` |
| `SNDPRT` | Sending partner type | `LS` (logical system) |
| `SNDPFC` | Sending partner function | `` |
| `SNDPRN` | Sending partner number (logical system name) | `SAPECCP10` |
| `SNDSAD` | Sending partner address | `` |
| `SNDLAD` | Sending logical address | `` |
| `RCVPOR` | Receiving port | `PORTEDI01` |
| `RCVPRT` | Receiving partner type | `LI` (vendor) or `LS` |
| `RCVPFC` | Receiving partner function | `` |
| `RCVPRN` | Receiving partner number | `SUPPLIER001` |
| `RCVSAD` | Receiving partner address | `` |
| `RCVLAD` | Receiving logical address | `` |
| `CREDAT` | Creation date | `20260430` |
| `CRETIM` | Creation time | `143022` |
| `REFINT` | Reference interchange number | `` |
| `REFGRP` | Reference group number | `` |
| `REFMES` | Reference message number | `` |
| `ARCKEY` | Archive key | `` |
| `SERIAL` | Serialization field | `` |

### Data Records

Multiple data records, each carrying one IDoc segment.

| Field | Description |
|---|---|
| `SEGNAM` | Segment name (e.g., `E1EDK01`) |
| `MANDT` | Client |
| `DOCNUM` | IDoc document number |
| `SEGNUM` | Sequential segment number |
| `PSGNUM` | Parent segment number (0 for root) |
| `HLEVEL` | Hierarchy level (1 = direct child of control, 2 = grandchild) |
| `SDATA` | Segment data (fixed-length 1000 bytes) |

### Status Records

Multiple status records logging each step of IDoc processing.

| Field | Description |
|---|---|
| `DOCNUM` | IDoc number |
| `STATUS` | Status code |
| `LOGDAT` | Status set date |
| `LOGTIM` | Status set time |
| `REPID` | ABAP report that set this status |
| `STAPA1`–`STAPA4` | Status parameters |
| `STATXT` | Status text |

---

## 3. Inbound IDoc Processing Setup

Inbound IDocs arrive at SAP from external systems. SAP must know which function to call to process each incoming message type.

### Step 1: Define Port (WE21)

Transaction: `WE21`

Create an inbound port:
- **Port type**: `tRFC` (for SAP-to-SAP) or `File` (for file-based testing) or `Internet` (HTTP-based)
- **Port name**: e.g., `PARTNER_IN`
- For tRFC port: specify the RFC destination (SM59) that your integration middleware will use

### Step 2: Create Partner Profile (WE20)

Transaction: `WE20`

For each external partner sending IDocs to SAP:

1. Create partner with:
   - **Partner type**: `LI` (vendor/supplier), `KU` (customer), `LS` (logical system for SAP-to-SAP)
   - **Partner number**: vendor account number or logical system name

2. Under **Inbound parameters**, add entry:
   - Message type: e.g., `ORDRSP`
   - IDoc type: `ORDERS05`
   - Process code: `ORDE` (order response) — this code maps to the function module that processes the IDoc

3. Set processing:
   - **Processing by function module**: immediate processing
   - **Trigger immediately**: checked for real-time processing; unchecked for batch

### Step 3: Message Type Assignment (WE57)

Verify that the message type is linked to the IDoc basic type:
- Transaction `WE57` → check `ORDRSP` → `ORDERS05`

### Step 4: Test with WE19

Transaction `WE19` → create test IDoc → process manually to verify setup before going live.

---

## 4. Outbound IDoc Triggering

### Via Output Condition (standard SAP)

SAP triggers outbound IDocs via the output control mechanism (message determination).

**For Purchase Orders:**

1. Transaction `MN04` (Create Message Condition Records for Purchasing)
   - Message type: `NEU` (new PO output) or custom
   - Communication: `EDI`
   - Partner function: `LF` (vendor)

2. In the output type configuration (transaction `M706`):
   - Set medium to `6` (EDI)
   - Assign function module `IDOC_OUTPUT_ORDERS` as dispatch function

3. Partner Profile (WE20) — outbound parameters:
   - Partner type: `LI`
   - Partner number: vendor account
   - Message type: `ORDERS`
   - IDoc basic type: `ORDERS05`
   - Receiver port: points to your PI/PO system or EDI VAN

### Via Direct Program

For custom programs that need to trigger IDoc programmatically:

```abap
DATA: lv_mestyp TYPE edi_mestyp VALUE 'ORDERS',
      lv_idoctp TYPE edi_idoctp VALUE 'ORDERS05'.

CALL FUNCTION 'MASTER_IDOC_DISTRIBUTE'
  EXPORTING
    master_idoc_control = ls_control
  TABLES
    communication_idoc_control = lt_comm_ctrl
    master_idoc_data           = lt_idoc_data
  EXCEPTIONS
    error_in_idoc_compress     = 1
    OTHERS                     = 2.
```

---

## 5. IDoc Status Lifecycle

### Status codes reference

| Status | Direction | Description | Action |
|---|---|---|---|
| `01` | Outbound | IDoc created by application | Normal — waiting to be sent |
| `02` | Outbound | Error passing data to port | Check port config (WE21); check SM59 destination |
| `03` | Outbound | Data passed to port OK | Normal — handed off to middleware |
| `06` | Outbound | Translation error | Check ALE/EDI translation rules |
| `07` | Outbound | Error in packet dispatch | Check IDOC dispatch program (RSEOUT00) |
| `08` | Outbound | Syntax error in IDoc | IDoc data has invalid segment or field |
| `09` | Outbound | Dispatch OK, recipient acknowledged | Positive acknowledgement received |
| `12` | Outbound | Dispatch OK, dispatch confirmed | IDoc sent to partner system OK |
| `18` | Outbound | Triggering EDI subsystem OK | Sent to external EDI translator |
| `30` | Inbound | IDoc ready for inbound processing | Queued for processing |
| `51` | Inbound | **Error in application** | Most common inbound error — check application log (SLG1); business validation failed |
| `53` | Inbound | Application document posted | Success — document created in SAP |
| `56` | Inbound | IDoc with errors added | Parsing or segment error |
| `61` | Inbound | Processing despite syntax error | IDoc processed but had data issues |
| `64` | Outbound | IDoc ready to be transferred (not sent) | Check tRFC queue (SM58); check port (WE21) |
| `65` | Outbound | Error in transport/distribution | Network or RFC error to partner |
| `68` | Outbound | Error: no further processing | Terminated; check error in RETURN table |
| `70` | Both | Original of a resent IDoc | Previous IDoc superseded |
| `75` | Inbound | IDoc archived | Archiving status |

### Status flow for successful outbound IDoc (ORDERS)

```
01 (Created) → 03 (Passed to port) → 12 (Dispatch confirmed)
```

### Status flow for successful inbound IDoc (ORDRSP)

```
30 (Ready for processing) → 53 (Application document posted)
```

---

## 6. SAP PI/PO Channel Types

SAP Process Integration (PI) / Process Orchestration (PO) is SAP's middleware layer for cross-system integration. It supports the following adapter types:

### Adapter types

| Adapter | Protocol | Typical use case |
|---|---|---|
| **IDoc adapter** | tRFC/qRFC | IDoc from/to SAP systems; legacy SAP-to-SAP |
| **SOAP adapter** | HTTP/SOAP | Web service integration; WSDL-based partners |
| **REST adapter** | HTTP/REST | Modern JSON/XML API integration |
| **JDBC adapter** | JDBC | Direct database read/write (use carefully) |
| **File/FTP adapter** | File system / FTP | Batch file exchange; legacy EDI file drop |
| **JMS adapter** | JMS | Message queue (IBM MQ, ActiveMQ) integration |
| **Mail adapter** | SMTP/POP3 | Email-triggered integrations |
| **RFC adapter** | RFC/JCo | Direct BAPI/RFC call from PI/PO to ABAP |
| **XI/HTTP adapter** | HTTP(S) | Direct PI-to-PI or SAP-to-PI |

### When to use which adapter (PI/PO)

| Scenario | Adapter |
|---|---|
| SAP sends ORDERS IDoc to supplier EDI system | IDoc (source) → EDIFACT translator via JDBC/File |
| External REST service triggers SAP purchase order | REST (inbound) → IDoc (to SAP) |
| SAP triggers SOAP web service at bank | SOAP (target adapter) |
| Partner drops order XML file on SFTP | File/FTP (source) → IDoc (target) |
| Real-time inventory check from SAP ECC | RFC adapter (source) → REST (target) |

---

## 7. Monitoring IDocs

### Transaction WE02 — IDoc List

All IDocs, both inbound and outbound.

**Key filters:**
- Direction: `1` = outbound, `2` = inbound
- Message type: e.g., `ORDERS`, `ORDRSP`
- Status: e.g., `51` for errors
- Date range: creation date

From the list, double-click an IDoc to view:
- Control record (routing info)
- Data segments with field values
- Status records (processing history)

### Transaction WE05 — Inbound IDoc Display

Filtered view for inbound IDocs only. Same drill-down capability as WE02.

### Transaction SM58 — tRFC Error Monitor

Shows IDocs that failed during RFC/tRFC transport. Status `64` IDocs appear here.

Actions:
- Select stuck tRFC call → Execute → Retry manually
- Check RFC destination (SM59) if all calls fail

### Transaction BD87 — Inbound IDoc Reprocessing

For status `51` IDocs: select → click "Process" → triggers reprocessing after fixing the root cause.

### Transaction SLG1 — Application Log

When status `51` occurs, the detailed error reason is often in the application log.
- Object: typically `BASISEXPORT` or the function module name
- Sub-object: SAP-specific per message type
- Date/time matches the IDoc creation time

---

## 8. ORDERS05 Key Segments

ORDERS05 is the standard IDoc type for purchase orders. It is also used for sales orders in the SD module.

### Segment hierarchy

```
EDI_DC40 (Control)
└── E1EDK01 (Header)
    ├── E1EDK02 (Reference document numbers)
    ├── E1EDK03 (Date/deadline)
    ├── E1EDK04 (Currency, amounts)
    ├── E1EDK05 (Terms of payment)
    ├── E1EDK14 (Org data: purch.org, sales org)
    ├── E1EDK17 (Transport/delivery conditions)
    ├── E1EDKA1 (Partner: SOLD-TO, SHIP-TO, VENDOR)
    └── E1EDP01 (Item)
        ├── E1EDP02 (Item reference)
        ├── E1EDP04 (Delivery date/schedule)
        ├── E1EDP05 (Conditions/pricing per item)
        ├── E1EDP19 (Material identification)
        ├── E1EDP20 (Account assignment)
        └── E1EDPT1 (Item text)
```

### Key segment fields

**E1EDK01 (Header)**

| Field | Description | Example |
|---|---|---|
| `BSART` | Document type | `NB` (standard PO) |
| `BELNR` | Document number (PO number) | `4500012345` |
| `NTGEW` | Net weight | `10.000` |
| `BRGEW` | Gross weight | `11.500` |
| `GEWEI` | Weight unit | `KG` |

**E1EDP01 (Item)**

| Field | Description | Example |
|---|---|---|
| `POSEX` | Item number | `000010` |
| `ACTION` | Change indicator: `000`=new, `001`=change, `002`=delete | `000` |
| `PSTYP` | Item category | `0` (standard) |
| `MENGE` | Quantity | `10.000` |
| `MENEE` | Unit of measure | `EA` |
| `PREIS` | Price | `25.00` |
| `PEINH` | Price unit | `1` |
| `CURCY` | Currency | `USD` |

**E1EDP19 (Material identification)**

| Field | Description | Example |
|---|---|---|
| `QUALF` | Qualifier: `001`=buyer material, `002`=vendor material, `007`=EAN | `001` |
| `IDTNR` | Material/article number | `RAW-001` |
| `KTEXT` | Short description | `Raw material 001` |

---

## 9. Common Error Patterns

| Error | Status | Root cause | Fix |
|---|---|---|---|
| Partner profile not found | `51` / `56` | WE20 entry missing or wrong partner number/type | Create/correct entry in WE20 |
| Message type not assigned | `51` | Inbound parameter for message type missing in partner profile | Add message type under WE20 > Inbound params |
| Segment unknown | `56` | IDoc type mismatch; sender using extended IDoc type unknown to receiver | Check IDoc type in WE30; add missing segment extension |
| Port not configured | `02` / `64` | Port name in partner profile doesn't exist in WE21 | Create matching port in WE21 |
| RFC destination not found | `65` | SM59 destination referenced by port doesn't exist | Create RFC destination in SM59 |
| Function module for processing not found | `51` | Process code (WE41/WE42) references non-existent FM | Check process code in WE42; assign correct FM |
| Authorizations missing | `51` | SAP user posting the IDoc lacks required auth objects | Check SU53; assign required roles |
| IDoc stuck in status 30 | `30` | No process configured to pick it up; or processing program not scheduled | Schedule RBDAPP01 (inbound processing job) or check WE20 immediate flag |
