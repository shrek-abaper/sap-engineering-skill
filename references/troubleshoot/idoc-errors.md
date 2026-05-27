# IDoc Error Troubleshooting

## Table of Contents

1. [Status 51 — Error in Application](#status-51--error-in-application)
2. [Status 64 — IDoc Ready to Transfer (Not Sent)](#status-64--idoc-ready-to-transfer-not-sent)
3. [Status 02 — Error Passing Data to Port](#status-02--error-passing-data-to-port)
4. [Partner Profile Not Found](#partner-profile-not-found)
5. [Segment Unknown](#segment-unknown)
6. [IDoc Monitoring Quick Reference](#idoc-monitoring-quick-reference)

---

## Status 51 — Error in Application

### Symptom

IDoc received by SAP (status moved to `30` = ready for processing) but then switched to `51` (error in application).

This is the most common inbound IDoc error. It means SAP accepted the IDoc but the application function module that processes it returned an error.

### How to find the root cause

**Step 1: Find the IDoc in WE02**
1. Transaction `WE02`
2. Filter by status `51`
3. Double-click the IDoc
4. Look at the **Status Records** section at the bottom
5. The error message in the status record often says the cause (e.g., "Material not found", "Vendor account not found")

**Step 2: Check the application log in SLG1**
1. Transaction `SLG1`
2. Enter the date and time of the IDoc creation
3. Object: depends on the message type — common objects:
   - `BASISEXPORT` for general IDoc errors
   - `/SCWM/EWM` for warehouse management
   - `ME` for purchasing-related IDocs
4. Execute → find matching entry → expand for details

**Step 3: Reprocess after fixing (BD87)**

Once the root cause is fixed:
1. Transaction `BD87`
2. Filter by status `51` and date range
3. Select the stuck IDoc(s)
4. Click **Process** (Execute)

### Common status 51 root causes

| Error text in status record | Root cause | Fix |
|---|---|---|
| "Vendor/supplier account 'XXXX' not found" | Partner number in control record doesn't match SAP vendor master | Create vendor in XK01 or correct RCVPRN in partner profile |
| "Material 'XXXX' not found in plant '1000'" | Material doesn't exist in the receiving plant | Extend material to plant in MM01 or correct material number in IDoc |
| "Delivery date in the past" | EDAP01 delivery date is earlier than today | Correct the delivery date before reprocessing |
| "No purchasing info record" | INFO record (purchasing info record) doesn't exist for vendor/material combination | Create purchasing info record in ME11 |
| "Partner profile not found" → then goes to 51 | Wrong partner type in WE20 | Correct partner type in WE20 |
| "Function module &1 not found" | Process code references non-existent FM | Check WE42 → assign correct function module |
| "Company code '1000' not authorized" | Authorization object `F_BKPF_BUK` missing | Add company code authorization to the posting user |

---

## Status 64 — IDoc Ready to Transfer (Not Sent)

### Symptom

Outbound IDoc created (status `01`) but stuck at status `64` (ready to transfer, not sent). No transmission occurred.

### Root causes

| Root cause | Check | Fix |
|---|---|---|
| tRFC destination not configured | `SM59` → find RFC destination named in WE21 port | Create RFC destination in SM59 |
| RFC destination unavailable/down | `SM59` → select destination → click "Connection Test" | Fix network issue; check SMICM for HTTP destinations |
| Outbound dispatch job not scheduled | `SE38` → check `RSEIDOCA` (IDoc dispatch) | Schedule RSEOUT00 periodically (every minute in prod) |
| Port definition missing | `WE21` → check port named in WE20 partner profile | Create port in WE21 |
| tRFC queue stuck | `SM58` → check stuck entries | SM58 → select → Execute to retry; if repeating, fix root cause first |
| Partner profile output mode = 4 (no immediate dispatch) | `WE20` → outbound parameter → output mode | Change to output mode 1 (immediate) for real-time dispatch |

### Check tRFC queue (SM58)

1. Transaction `SM58`
2. Look for function calls with status "Error" or repeatedly failing
3. Select a call → click **Display** to see the error detail
4. If it's a connectivity issue: fix SM59 destination first, then select all and **Execute** to retry

### Schedule dispatch job

If IDocs sit in status `64` and you need them dispatched immediately:

```
Transaction SE38 → Program RSEOUT00 → Execute
```

Or schedule it as a background job:
1. Transaction `SM36` → Define job `IDOC_DISPATCH`
2. Step: RSEOUT00 with parameters (message type, partner, etc.)
3. Schedule: every 1 minute

---

## Status 02 — Error Passing Data to Port

### Symptom

Outbound IDoc fails at status `02` immediately after creation — never reaches the port.

### Root causes

| Root cause | Check | Fix |
|---|---|---|
| Port does not exist | `WE21` → check port name from partner profile | Create port in WE21 |
| Port type mismatch | `WE21` → verify port type matches what is configured in WE20 | Align port type (tRFC, File, Internet) |
| RFC destination in port is wrong | `WE21` → open port → check RFC destination name | Point to valid RFC destination in SM59 |
| File port: directory not writable | `WE21` → File port → check directory path | Ensure SAP app server has write access to directory |
| File port: directory doesn't exist | Same | Create directory; grant permissions |
| XML conversion error | IDoc has invalid characters (non-Unicode in Unicode system) | Sanitize IDoc data; check character set |

---

## Partner Profile Not Found

### Symptom

IDoc received but immediately gets status `56` (IDoc with errors) or `51` with message:
```
No matching entry found in partner profiles for partner SUPPLIER001 / LI / ORDRSP
```

### Root causes and fixes

**Case 1: Partner number mismatch**

The partner number in the IDoc's EDI_DC40 control record (`RCVPRN` for inbound or `SNDPRN` for outbound) doesn't match any entry in WE20.

Fix:
- `WE20` → check if `SUPPLIER001` exists with partner type `LI`
- If not: create it with the correct number
- If it exists with a different number: either fix the number in WE20 or correct the IDoc partner number

**Case 2: Partner type mismatch**

The IDoc has `RCVPRT = LS` (logical system) but WE20 has the partner under type `LI` (vendor).

Fix: In `WE20`, verify the partner type matches what the sender uses.  
Common partner types:
- `LI` — Vendor (for external supplier IDocs)
- `KU` — Customer (for external customer IDocs)
- `LS` — Logical system (for SAP-to-SAP ALE)

**Case 3: Message type not configured under the partner**

The partner exists in WE20 but the specific message type (e.g., `ORDRSP`) is not listed under Inbound Parameters.

Fix:
1. `WE20` → open partner
2. Scroll to "Inbound parameters" section
3. Click "+" to add new entry:
   - Message type: `ORDRSP`
   - IDoc basic type: `ORDERS05`
   - Process code: `ORDE`

**Case 4: Wrong port for outbound**

The outbound partner profile references a port that doesn't exist in WE21.

Fix: `WE21` → create the port with the name referenced in WE20.

---

## Segment Unknown

### Symptom

IDoc received and rejected with status `56`:
```
Segment E1EDP99 unknown in basic type ORDERS05
```

Or:
```
IDoc type ZORDERS05E not found
```

### Root causes

**Root cause 1: Segment from IDoc extension not registered**

The sender is using an enhanced IDoc type (e.g., `ORDERS05E` — a customer enhancement) that adds custom segments. The receiving SAP system doesn't have this IDoc extension installed.

Fix:
1. SAP Basis must create matching IDoc extension in `WE30`
2. Assign it to the IDoc basic type `ORDERS05`
3. The extension adds the same segments the sender is using

**Root cause 2: Completely wrong IDoc type in control record**

The control record `IDOCTYP` field references a type that doesn't exist at all.

Fix:
- `WE30` → verify the IDoc type
- Correct the `IDOCTYP` in the partner profile or in the sender system

**Root cause 3: Version mismatch**

Sender is on S/4HANA using a newer ORDERS06 type; receiver is on ECC using ORDERS05.

Fix:
- Map segments in PI/PO (message mapping)
- Or use the common subset in ORDERS05

---

## IDoc Monitoring Quick Reference

| Transaction | Purpose | When to use |
|---|---|---|
| `WE02` | View all IDocs (inbound + outbound), filter by status/type/date | General IDoc monitoring |
| `WE05` | View inbound IDocs only | Inbound problem investigation |
| `WE19` | Create and process test IDoc | Development/testing |
| `WE20` | Partner profile maintenance | Setup and configuration |
| `WE21` | Port maintenance | Setup and configuration |
| `WE30` | IDoc type/extension viewer | Check segment definitions |
| `BD87` | Inbound IDoc reprocessing | After fixing status 51 errors |
| `BD53` | Inbound IDoc summary | Overview of inbound processing |
| `SM58` | tRFC error monitor | Status 64 / transmission failures |
| `SM59` | RFC destination maintenance | Fix RFC connectivity for ports |
| `SLG1` | Application log | Detailed errors for status 51 |
| `SE37` → `IDOC_OUTPUT_ORDERS` | Test function module directly | Debug outbound IDoc generation |
| `MIGO` | Goods movement (verify GR from IDoc) | After IDoc 53 — verify SAP doc created |
| `ME23N` | Display PO (verify PO created/changed) | After ORDERS IDoc 53 |

### IDoc status decision tree

```
IDoc is stuck at:

Status 30 (Ready for inbound processing)?
  → No processing job running → Schedule RBDAPP01 or process via BD87
  → Processing is running but always fails → Check process code in WE42

Status 51 (Application error)?
  → WE02 → IDoc → Status records → read error message
  → SLG1 → check application log for detailed error
  → Fix root cause → BD87 → reprocess

Status 56 (IDoc with errors)?
  → Segment unknown → WE30 → check IDoc extension
  → Partner profile issue → WE20 → verify setup
  → Syntax error in SDATA → IDoc data format problem in sender

Status 64 (Ready to transfer, not sent)?
  → SM58 → check tRFC queue for errors
  → WE21 → check port configuration
  → SM59 → test RFC destination connectivity

Status 02 (Error passing data to port)?
  → WE21 → check port exists and is correctly configured
  → SM59 → check RFC destination for the port
```
