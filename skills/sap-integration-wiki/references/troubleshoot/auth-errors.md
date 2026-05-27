# Authentication Error Troubleshooting

## Table of Contents

1. [Test Basic Auth with curl Before Writing Code](#1-test-basic-auth-with-curl-before-writing-code)
2. [Checking User Lock Status (SU01)](#2-checking-user-lock-status-su01)
3. [Checking ICF Node Status (SICF)](#3-checking-icf-node-status-sicf)
4. [Authorization Trace (SU53 and STAUTHTRACE)](#4-authorization-trace-su53-and-stauthtrace)
5. [OAuth Token Endpoint Issues (SOAUTH2)](#5-oauth-token-endpoint-issues-soauth2)
6. [CSRF Token Debugging](#6-csrf-token-debugging)
7. [Quick Reference: Error Codes and Meanings](#7-quick-reference-error-codes-and-meanings)

---

## 1. Test Basic Auth with curl Before Writing Code

Always test authentication with a raw curl command before implementing in your application. This isolates application bugs from SAP configuration issues.

### Minimal connectivity test

```bash
# Test 1: Can you reach the server?
curl -I "https://s4hana.example.com:44300/"
# Expected: HTTP 200 or 301 (redirect) — server is reachable
# Got: Connection refused → SAP is not running or port is blocked
# Got: SSL handshake error → Certificate issue (see SSL section in auth.md)

# Test 2: Does Basic Auth succeed?
curl -v -u "USERNAME:PASSWORD" \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/\$metadata" \
  -H "Accept: application/json"

# Expected: HTTP 200 with OData metadata XML
# Got: HTTP 401 → Authentication failed (wrong user/pass or user locked)
# Got: HTTP 403 → Authenticated but not authorized (missing S_SERVICE)
# Got: HTTP 404 → Service not activated (SICF issue)

# Test 3: Verify CSRF token fetch
curl -v -u "USERNAME:PASSWORD" \
  -H "X-CSRF-Token: Fetch" \
  -c /tmp/test-cookies.txt \
  -D /tmp/test-headers.txt \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/"

# Look for in response headers:
# x-csrf-token: <40-character token>
# set-cookie: sap-usercontext=...; SAP_SESSIONID_...=...

# Extract and verify token is non-empty
grep -i "x-csrf-token" /tmp/test-headers.txt
```

### SSL certificate issues

```bash
# If you get SSL errors like "certificate verify failed"
# First: check the SAP certificate chain
openssl s_client -connect s4hana.example.com:44300 -showcerts

# Then: trust the certificate (add to curl's CA bundle or bypass for testing only)
curl --cacert /path/to/sap-ca.pem -u user:pass "https://..."

# TESTING ONLY (never in production):
curl -k -u user:pass "https://..."  # -k = --insecure, skips cert verification
```

### Test a write operation (POST)

```bash
# Full write test sequence
# Step 1: Fetch token
curl -s -u "USERNAME:PASSWORD" \
  -H "X-CSRF-Token: Fetch" \
  -c /tmp/c.txt -D /tmp/h.txt \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/" > /dev/null

TOKEN=$(grep -i "x-csrf-token" /tmp/h.txt | head -1 | awk '{print $2}' | tr -d '\r')
echo "Token: [$TOKEN]"

# Step 2: POST test (use a minimal payload)
curl -v -u "USERNAME:PASSWORD" \
  -H "X-CSRF-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -b /tmp/c.txt \
  -X POST \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder" \
  -d '{"CompanyCode":"1000","PurchasingOrganization":"1000"}'
# This will likely return 400 (missing fields) but that's fine — it means auth worked!
# HTTP 401/403 here means auth or authorization is still the problem
```

---

## 2. Checking User Lock Status (SU01)

### Transaction: SU01

1. Open SAP GUI → Transaction `SU01`
2. Enter the username in the "User" field
3. Click the magnifying glass or press Enter
4. Navigate to the **"Logon Data"** tab

### Lock indicators

| Indicator | Meaning | Resolution |
|---|---|---|
| "User is locked (administrator)" | Admin manually locked | Click "Unlock" button in SU01 |
| "User is locked (too many failed logon attempts)" | Password attempts exceeded threshold | Click "Unlock" button; consider increasing `login/fails_to_user_lock` parameter |
| "Password is initial" | User never set password | Set a permanent password |
| "Password expired" | Valid period elapsed | Extend validity in SU01 → Logon Data → "Valid Through" field |
| "User type: Dialog" | Should be Communication type | Change to "Communication" (S) type; dialog users require interactive password changes |

### Setting a non-expiring communication user

1. `SU01` → User → Change (Ctrl+F5)
2. Logon Data tab:
   - **User Type**: `S` (Communication)
   - **Valid Through**: set to far future date (e.g., 12/31/9999) or leave blank
3. Password tab:
   - Set a strong password
   - Ensure "Password is initial" is NOT checked

### Checking without SAP GUI (if you have RFC access)

```java
// JCo: Check user status
JCoFunction fn = dest.getRepository().getFunction("BAPI_USER_GET_DETAIL");
fn.getImportParameterList().setValue("USERNAME", "USERNAME_TO_CHECK");
fn.execute(dest);
JCoStructure logonData = fn.getExportParameterList().getStructure("LOGONDATA");
System.out.println("User type: "      + logonData.getString("USTYP"));
System.out.println("Valid through: "  + logonData.getString("GLTGB"));
// Check ISLOCKED structure for wrong-logon locks
JCoStructure isLocked = fn.getExportParameterList().getStructure("ISLOCKED");
System.out.println("Wrong logon lock: " + isLocked.getString("WRNG_LOGON"));
```

---

## 3. Checking ICF Node Status (SICF)

### Transaction: SICF

The Internet Communication Framework node must be active for any HTTP-based SAP service.

### Finding and activating a node

1. Open `SICF`
2. Click **Execute** (F8) to load the service tree
3. Navigate the tree:
   - For OData V2: `default_host → sap → opu → odata → sap → <SERVICE_NAME>`
   - For OAuth2: `default_host → sap → bc → sec → oauth2`
4. If the service appears **grey/inactive**:
   - Right-click the node → **Activate Service**
   - Confirm in the popup dialog
5. For activating all OData services at once:
   - Right-click `default_host → sap → opu → odata` → **Activate Service** (applies recursively)

### Programmatic check (if you can run ABAP)

```abap
DATA lv_active TYPE abap_bool.
CALL METHOD cl_http_server=>if_http_server~is_icf_node_active
  EXPORTING path = '/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV'
  RECEIVING result = lv_active.
IF lv_active IS INITIAL.
  MESSAGE 'ICF node is inactive' TYPE 'E'.
ENDIF.
```

---

## 4. Authorization Trace (SU53 and STAUTHTRACE)

### Transaction SU53 — Quick Authorization Check

SU53 shows the last failed authorization check for the **current SAP session**.

**How to use:**
1. Make the failing API call from your application (or reproduce in browser/Postman)
2. **Immediately** open SAP GUI with the same user and run `SU53`
3. SU53 displays:
   - Which authorization object was checked
   - What values were required
   - What values the user currently has
4. Share this output with SAP security team to add missing authorization

**Example SU53 output for missing OData service authorization:**
```
Authorization check failed for object S_SERVICE
  SRV_NAME: API_PURCHASEORDER_PROCESS_SRV
  SRV_TYPE: HT
User has: (nothing)
```

**Fix**: Add role with `S_SERVICE` authorization for the specific service.

### Transaction STAUTHTRACE — Detailed Authorization Trace

For complex authorization issues where multiple objects are checked:

1. `STAUTHTRACE` → Enable trace for user `USERNAME`
2. Reproduce the failing API call
3. `STAUTHTRACE` → Display trace
4. Analyze all authorization checks (success and failure)
5. Disable trace when done

---

## 5. OAuth Token Endpoint Issues (SOAUTH2)

### Transaction: SOAUTH2

### Token endpoint returning 400

```json
{
  "error": "invalid_client",
  "error_description": "Client authentication failed"
}
```

**Diagnosis checklist:**
1. `SOAUTH2` → Find your client → verify Client ID matches exactly what you're sending
2. Verify Client Secret is correctly copied (no trailing spaces)
3. Verify grant type `Client Credentials` is checked
4. Verify the OAuth ICF node is active: `SICF` → `sap/bc/sec/oauth2`

### Token endpoint returning 401

```json
{
  "error": "unauthorized_client",
  "error_description": "Unauthorized"
}
```

**Diagnosis checklist:**
1. The OAuth client is configured but the underlying user is locked → `SU01` to unlock
2. The OAuth client has no valid scope assigned → `SOAUTH2` → add scope
3. ICM session timeout configured too low → extend in ICM profile parameters

### Token endpoint returning 404

- ICF node `/sap/bc/sec/oauth2` is inactive → `SICF` → activate

### Token works but API returns 401

The access token is valid but the underlying user (associated with the OAuth client) lacks OData service authorization:
1. Identify which SAP user is associated with the OAuth2 client in `SOAUTH2`
2. Open that user in `SU01` and verify required roles are assigned
3. Use `SU53` (logged in as that user) after a failed API call to see missing auth objects

---

## 6. CSRF Token Debugging

### Verify the token was fetched

```bash
# Run with -v to see all request/response headers
curl -v -u user:pass \
  -H "X-CSRF-Token: Fetch" \
  "https://host:port/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/"

# In the verbose output, look for response headers containing:
# < x-csrf-token: abcdef1234567890abcdef1234567890abcdef12
# < set-cookie: sap-usercontext=sap-client=100&sap-user=APIUSER; ...
# < set-cookie: SAP_SESSIONID_PRD_100=...; HttpOnly; ...
```

### Verify token is sent correctly

```bash
# Confirm outgoing POST has both required headers
curl -v -u user:pass \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Cookie: $SAP_COOKIES" \
  -H "Content-Type: application/json" \
  -X POST \
  "https://host:port/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder" \
  -d '...'

# In verbose output, look for:
# > X-CSRF-Token: abcdef1234...  (token being sent)
# > Cookie: SAP_SESSIONID_PRD_100=...  (session cookie sent)
```

### Token length check

SAP CSRF tokens are typically 40 hex characters. If your extracted token is empty, the fetch failed:

```bash
TOKEN=$(grep -i "x-csrf-token" /tmp/headers.txt | awk '{print $2}' | tr -d '\r')
echo "Token length: ${#TOKEN}"
# Should be 40. If 0, the fetch failed.
```

---

## 7. Quick Reference: Error Codes and Meanings

| HTTP Code | SAP response body clue | Likely cause | First action |
|---|---|---|---|
| `401` | "Password logon no longer possible" | User locked | SU01 → unlock |
| `401` | "Logon failed" | Wrong credentials | Verify credentials in SAP GUI |
| `401` | (empty body) | Basic Auth header malformed | Check base64 encoding of user:pass |
| `403` | "Forbidden" | Missing S_SERVICE authorization | SU53 → add missing auth to role |
| `403` | "CSRF token validation failed" | Token missing or expired | Re-fetch CSRF token; send Cookie header |
| `404` | (short HTML page) | ICF node inactive | SICF → activate service node |
| `404` | `{"error": {"code": "404"}}` | Service not in /IWFND/MAINT_SERVICE | Activate service in /IWFND/MAINT_SERVICE |
| `500` | "transactionid" in innererror | ABAP dump | ST22 → find dump → fix or escalate |
| `503` | "Service unavailable" | SAP instance not running | SM51 (servers), SM50 (work processes) |
