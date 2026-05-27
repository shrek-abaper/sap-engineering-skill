# OData Error Troubleshooting

For each error: symptom → root cause → fix steps → SAP transaction to check.

## Table of Contents

1. [400 Bad Request](#400-bad-request)
2. [401 Unauthorized](#401-unauthorized)
3. [403 Forbidden — Authorization Object Missing](#403-forbidden--authorization-object-missing)
4. [403 CSRF Token Validation Failed](#403-csrf-token-validation-failed)
5. [404 Not Found](#404-not-found)
6. [500 Internal Server Error](#500-internal-server-error)
7. [Deep Insert Rejection](#deep-insert-rejection)
8. [PurchasingCompletenessStatus is Read-Only](#purchasingcompletenessstatus-is-read-only)
9. [Reading SAP OData Error Responses](#reading-sap-odata-error-responses)

---

## 400 Bad Request

### Symptom

```json
{
  "error": {
    "code": "005056A509B11EE1B9A8FEC11C21578E",
    "message": {
      "lang": "en",
      "value": "Invalid value '0' for property 'OrderQuantity' of type 'Edm.Decimal'"
    },
    "innererror": {
      "application": {
        "component_id": "MM-PUR-PO-OD",
        "service_namespace": "/SAP/",
        "service_id": "API_PURCHASEORDER_PROCESS_SRV",
        "service_version": "0001"
      },
      "transactionid": "A23C90F8...",
      "errordetails": [
        {
          "code": "CX_SY_CONVERSION_NO_NUMBER",
          "message": "Cannot convert '0' to number",
          "propertyref": "OrderQuantity",
          "severity": "error"
        }
      ]
    }
  }
}
```

### Common root causes and fixes

| Sub-symptom | Root cause | Fix |
|---|---|---|
| "Invalid value" or "Cannot convert" | Wrong data type (e.g., string `"0"` vs decimal `0`) | Check OData `$metadata` for correct Edm type; send numbers as strings in OData V2 JSON |
| "Mandatory field missing" | Required field not provided | Check `$metadata` for `Nullable="false"` fields; add the field |
| "$filter syntax error" | Invalid OData filter expression | See filter syntax in `references/tech/odata.md#5`; avoid `in`, `not`, `contains` in V2 |
| "Navigation property not found" | Wrong navigation property name for deep insert | Check `$metadata` for exact `NavigationProperty Name=` value |
| "Key field value cannot be changed" | Attempting to PATCH a key field | Key fields are immutable after entity creation |
| "Entity already exists" | POST to create a document that already exists | Use PATCH for update; verify idempotency logic |

**SAP transaction to check**: `ST22` (ABAP runtime errors / short dumps) if the 400 seems like an unexpected crash.

---

## 401 Unauthorized

### Symptom

```
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Basic realm="SAP NetWeaver Application Server"
```

```json
{
  "error": {
    "code": "401",
    "message": { "value": "Unauthorized" }
  }
}
```

### Root causes

| Root cause | How to identify | Fix |
|---|---|---|
| Wrong username | Log in to SAP GUI with same credentials | Correct the username |
| Wrong password | Log in to SAP GUI | Correct the password |
| User locked (too many failed attempts) | Check `SU01` → user → "Login data" → locked indicator | Unlock in `SU01` or contact SAP admin |
| User type is Dialog, requires password change | Dialog user with expired password | Use Communication user type (S) with non-expiring password; or reset password |
| Wrong SAP client in URL | URL has no `sap-client=` param or wrong value | Add `?sap-client=100` query parameter to the URL |
| Basic Auth header malformed | `curl -v` shows outgoing Authorization header | Ensure header is `Basic <base64(user:pass)>` — no extra characters |

### Diagnosis

```bash
# Test authentication with minimal request
curl -v -u "USERNAME:PASSWORD" \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/\$metadata"

# If locked, response will contain:
# <message>Password logon no longer possible - too many failed attempts</message>
```

**SAP transaction to check**: `SU01` → enter username → verify account is not locked and password is valid.

---

## 403 Forbidden — Authorization Object Missing

### Symptom

```
HTTP/1.1 403 Forbidden
```

```json
{
  "error": {
    "code": "HTTP_STATUS_CODE_403",
    "message": { "value": "Forbidden" }
  }
}
```

### Root causes

| Root cause | How to identify | Fix |
|---|---|---|
| `S_SERVICE` authorization missing | Run `SU53` immediately after failure in same session | Add role containing `S_SERVICE` with `SRV_NAME = API_PURCHASEORDER_PROCESS_SRV` and `SRV_TYPE = HT` |
| ICF node inactive | `SICF`: check node status | Activate ICF node |
| Business data authorization missing | `SU53` or `STAUTHTRACE` | Add required authorization object (e.g., `M_BEST_BSA` for PO) |
| Missing activity authorization | `SU53` shows correct object but wrong activity | Add Activity `01` (Create) or `02` (Change) or `03` (Display) as needed |

### Step-by-step diagnosis

1. Make the failing API call from your client
2. **Immediately** open SAP GUI and run transaction `SU53`
3. `SU53` displays the last failed authorization check for the current session
4. The display shows exactly which authorization object was checked, which values were required, and which the user has
5. Share the `SU53` output with your SAP Basis/security team to add the missing authorization

**SAP transaction**: `SU53` (most useful), `STAUTHTRACE` (for detailed trace across multiple calls).

---

## 403 CSRF Token Validation Failed

### Symptom

```
HTTP/1.1 403 Forbidden
X-CSRF-Token: Required
```

```json
{
  "error": {
    "code": "005056A509B11EE1B9A8FEC11C21578E",
    "message": { "value": "CSRF token validation failed" }
  }
}
```

### Root causes and fixes

| Root cause | Symptom | Fix |
|---|---|---|
| No CSRF token fetched | First POST without prior GET | Perform GET to service root with `X-CSRF-Token: Fetch` header first |
| Token not sent in request | POST has no `X-CSRF-Token` header | Add header `X-CSRF-Token: <fetched_token>` to POST request |
| Session cookie not sent | POST sent without cookies | Send the session cookie received during token fetch (`-b cookies.txt` in curl) |
| Token expired (session timeout) | Works at start, fails after 30 min inactivity | Re-fetch token; use session pooling to keep sessions alive |
| Wrong token (different service) | Token from service A used with service B | Fetch token from each service's own root URL |
| Token fetched with GET on wrong URL | Fetched from metadata, not service root | Fetch from service root: `.../API_PURCHASEORDER_PROCESS_SRV/` not `.../\$metadata` |

### Correct token fetch

```bash
# CORRECT: Fetch from service root (ends with /)
curl -H "X-CSRF-Token: Fetch" \
  "https://host:port/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/"

# INCORRECT: Fetching from metadata endpoint
curl -H "X-CSRF-Token: Fetch" \
  "https://host:port/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/\$metadata"
# ↑ This often returns a token but the session is read-only
```

**SAP transaction**: No direct SAP transaction — this is a client-side configuration issue. Check ICM trace via `SMICM` if you need to see server-side token validation logs.

---

## 404 Not Found

### Symptom

```
HTTP/1.1 404 Not Found
```

### Root causes

| Root cause | Fix |
|---|---|
| Service not activated in `/IWFND/MAINT_SERVICE` | Activate service — see `references/tech/odata.md#2` |
| Wrong service name in URL | Check exact service technical name in `/IWFND/MAINT_SERVICE` |
| Wrong system alias | In `/IWFND/MAINT_SERVICE`, verify system alias points to correct backend |
| ICF node inactive | `SICF`: activate node at `/sap/opu/odata/sap/<SERVICE_NAME>` |
| Entity set name wrong | Check `$metadata` — entity set names are case-sensitive |
| Key value format wrong | String keys need quotes: `A_PurchaseOrder('4500012345')` not `A_PurchaseOrder(4500012345)` |

### Diagnosis

```bash
# Step 1: Check service metadata (if this returns 404, service is not activated)
curl -u user:pass "https://host:port/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/\$metadata"

# Step 2: Check service list
curl -u user:pass "https://host:port/sap/opu/odata/sap/" | grep -i purchaseorder
```

**SAP transaction**: `/IWFND/MAINT_SERVICE` to verify service activation; `SICF` to verify ICF node.

---

## 500 Internal Server Error

### Symptom

```
HTTP/1.1 500 Internal Server Error
```

```json
{
  "error": {
    "code": "005056A509B11EE1B9A8FEC11C21578E",
    "message": { "value": "An error occurred" },
    "innererror": {
      "transactionid": "A23C90F8D2CC...",
      "errordetails": []
    }
  }
}
```

### Root causes

| Root cause | How to identify | Fix |
|---|---|---|
| ABAP runtime error (short dump) | Transaction `ST22` on SAP system | Fix the underlying ABAP error; share dump with SAP support |
| Missing configuration (customizing) | `innererror` may hint at missing config | Check SAP IMG for relevant area; raise with SAP Basis |
| Insufficient SAP work processes | Concurrent requests all 500 | Check `SM50` for work process saturation; scale up or reduce concurrency |
| Network timeout on backend RFC call | 500 with timeout message | Check SM59 RFC destination timeouts; increase as needed |

### Key diagnostic information to collect

When reporting a 500 error:
1. The `transactionid` from `innererror` — this maps to an ICM log entry in `SMICM`
2. `ST22` dump: transaction → enter date/time → find matching dump → capture full details
3. ICM trace: `SMICM` → Goto → Trace File → find entry matching the transaction ID

**SAP transaction**: `ST22` (ABAP short dumps), `SMICM` (HTTP trace), `SM50` (work processes).

---

## Deep Insert Rejection

### Symptom

```
HTTP/1.1 400 Bad Request
"message": "Deep insert failed: navigation property 'to_PurchaseOrderItm' not found"
```

or

```
"message": "Entity set 'A_PurchaseOrderItem' key field 'PurchaseOrder' must not be provided"
```

### Common mistakes

| Mistake | Fix |
|---|---|
| Wrong navigation property name (`to_PurchaseOrderItm` vs `to_PurchaseOrderItem`) | Check `$metadata` for exact `NavigationProperty Name=` value |
| Providing parent key in child entity during deep insert | Do NOT set `PurchaseOrder` in child items — SAP assigns it automatically |
| Using `to_Item` instead of `to_PurchaseOrderItem` | Use the exact name from `$metadata` |
| Nesting too deep (4+ levels) | SAP limits deep insert depth — flatten to separate POST calls |
| Child entity missing mandatory fields | Check which child fields are `Nullable="false"` in `$metadata` |
| Using array `[]` instead of `{"results": [...]}` | OData V2 requires `{"results": [...]}` wrapper for collections |

### Quick check: Verify navigation property names

```bash
# Get metadata and search for navigation properties
curl -u user:pass \
  "https://host:port/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/\$metadata" \
  | grep -i "NavigationProperty"
```

---

## PurchasingCompletenessStatus is Read-Only

### Symptom

```
HTTP/1.1 400 Bad Request
"message": "Property 'PurchasingCompletenessStatus' cannot be modified"
```

### Explanation

`PurchasingCompletenessStatus` is a computed/derived field in `A_PurchaseOrder`. SAP calculates it based on:
- Whether all PO items have delivery completeness indicators set
- Whether all schedule lines have delivery dates

It cannot be directly patched.

### Fix

To change the completeness status:
1. PATCH the individual `A_PurchaseOrderItem` entity with `IsDeliveryCompleted: "X"` (for each item)
2. Or: PATCH `A_PurchaseOrderScheduleLine` with `IsDeliveryCompleted: "X"`

```bash
curl -X PATCH \
  -H "X-CSRF-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -b /tmp/cookies.txt \
  "https://host:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/\
A_PurchaseOrderItem(PurchaseOrder='4500012345',PurchaseOrderItem='00010')" \
  -d '{"IsDeliveryCompleted": "X"}'
```

---

## Reading SAP OData Error Responses

SAP OData errors always follow this structure (V2):

```json
{
  "error": {
    "code": "<UUID>",
    "message": {
      "lang": "en",
      "value": "<human-readable message>"
    },
    "innererror": {
      "application": {
        "component_id": "<SAP component>",
        "service_namespace": "/SAP/",
        "service_id": "<service name>",
        "service_version": "0001"
      },
      "transactionid": "<hex string for ICM log lookup>",
      "timestamp": "20260430143022",
      "errordetails": [
        {
          "code": "<error code>",
          "message": "<detail message>",
          "propertyref": "<field that caused error>",
          "severity": "error",
          "target": ""
        }
      ]
    }
  }
}
```

**Key fields to log and share with SAP support:**
- `transactionid` — maps to ICM access log entry
- `component_id` — tells you the SAP development component responsible
- `errordetails[].code` — the specific ABAP message class + number (e.g., `M8_007`)
- `errordetails[].propertyref` — which field triggered the error
