# OData Integration Reference

## Table of Contents

1. [When to Use OData](#1-when-to-use-odata)
2. [Activating an OData Service](#2-activating-an-odata-service)
3. [CSRF Token Flow](#3-csrf-token-flow)
4. [Deep Insert Pattern](#4-deep-insert-pattern)
5. [$filter / $expand / $select Syntax](#5-filter--expand--select-syntax)
6. [OData V2 vs V4 Differences](#6-odata-v2-vs-v4-differences)
7. [Service URL Patterns](#7-service-url-patterns)
8. [HTTP Client Examples](#8-http-client-examples)
9. [Known SAP OData Limitations](#9-known-sap-odata-limitations)

---

## 1. When to Use OData

| Condition | Use OData | Use RFC/JCo instead |
|---|---|---|
| S/4HANA On-Premise 1709+ | Yes | No (unless no standard API) |
| S/4HANA Cloud Public | Yes (V4 primary) | No (RFC unavailable externally) |
| ECC 6.0 | Avoid (no standard OData APIs) | Yes |
| HTTP-native client (Python, Node, .NET, low-code) | Yes | JCo requires native JVM |
| Real-time synchronous call | Yes | Yes (both work) |
| Bulk/batch operation (1000+ records) | Use `$batch` carefully | JCo often more efficient |
| Standard SAP business objects | Yes (check api.sap.com first) | If no standard API exists |

**Rule**: Always check [SAP API Business Hub](https://api.sap.com) first to find the standard OData service for your use case before building custom RFC calls.

---

## 2. Activating an OData Service

### Transaction: /IWFND/MAINT_SERVICE

This transaction runs on the **SAP Gateway** (front-end server). In embedded Gateway setups (S/4HANA), it runs on the application server itself.

**Step-by-step:**

1. Open `/IWFND/MAINT_SERVICE`
2. Click **"Add Service"**
3. In the **System Alias** field, enter your system alias (e.g., `LOCAL` for embedded, or the alias pointing to your backend)
4. In **Technical Service Name**, enter the service name (e.g., `API_PURCHASEORDER_PROCESS_SRV`)
5. Click **"Get Services"** to search
6. Select the service from the list
7. Click **"Add Selected Services"**
8. Confirm the namespace and package assignment dialog
9. Activate the service by selecting it and clicking the **ICF Node** button → ensure the node is active

### Verifying activation

```bash
# Test service metadata endpoint (should return 200 OK with XML/JSON)
curl -u "APIUSER:password" \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/\$metadata"
```

If you get `404 Not Found`, the service is not activated or the ICF node is inactive.  
Check ICF node: transaction `SICF` → navigate to `/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV` → right-click → **Activate service**.

### Required user roles for OData

| Role | Purpose |
|---|---|
| `SAP_BC_WEBSERVICE_CONSUMER` | Basic OData consumption |
| Business-specific role (e.g., `SAP_MM_PUR_PURCHASEORDER`) | Access to purchase order data |
| `S_SERVICE` authorization object | Grants access to specific OData service (check object with SU53) |

---

## 3. CSRF Token Flow

SAP OData requires CSRF (Cross-Site Request Forgery) token validation for all write operations (POST, PATCH, PUT, DELETE). Read operations (GET) do not require a token.

**Why SAP requires it**: Prevents replay attacks and cross-site request forgery on browser-based applications. Even for server-to-server calls, SAP enforces this.

### Step-by-step with curl

```bash
# ─────────────────────────────────────────────────────────────
# Step 1: GET request to fetch CSRF token
# - Header "X-CSRF-Token: Fetch" signals token request
# - Save cookies (-c flag) — session cookie is required for Step 2
# - Save headers (-D flag) to extract token
# ─────────────────────────────────────────────────────────────
curl -v -u "APIUSER:password" \
  -H "X-CSRF-Token: Fetch" \
  -H "Accept: application/json" \
  -c /tmp/sap-cookies.txt \
  -D /tmp/sap-headers.txt \
  -X GET \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/"

# Extract token from response headers
CSRF_TOKEN=$(grep -i "^x-csrf-token:" /tmp/sap-headers.txt | awk '{print $2}' | tr -d '\r\n')
echo "Token: $CSRF_TOKEN"

# ─────────────────────────────────────────────────────────────
# Step 2: POST with CSRF token and session cookies
# - Header "X-CSRF-Token: <token>" — use the fetched token
# - Cookies (-b flag) — pass the session cookie from Step 1
# ─────────────────────────────────────────────────────────────
curl -v -u "APIUSER:password" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -b /tmp/sap-cookies.txt \
  -X POST \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder" \
  -d @assets/payloads/po-create.json
```

### Python example (requests library)

```python
import requests
from requests.auth import HTTPBasicAuth

BASE_URL = "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV"
AUTH = HTTPBasicAuth("APIUSER", "password")

# Step 1: Fetch CSRF token (use a session to persist cookies automatically)
session = requests.Session()
session.auth = AUTH
session.verify = False  # Set to True in production with proper CA bundle

token_response = session.get(
    f"{BASE_URL}/",
    headers={"X-CSRF-Token": "Fetch", "Accept": "application/json"}
)
token_response.raise_for_status()
csrf_token = token_response.headers.get("x-csrf-token")
print(f"CSRF Token: {csrf_token}")

# Step 2: POST with token (session maintains cookies automatically)
import json
with open("assets/payloads/po-create.json") as f:
    payload = json.load(f)

create_response = session.post(
    f"{BASE_URL}/A_PurchaseOrder",
    headers={
        "X-CSRF-Token": csrf_token,
        "Content-Type": "application/json",
        "Accept": "application/json"
    },
    json=payload
)
create_response.raise_for_status()
result = create_response.json()
print(f"PO created: {result['d']['PurchaseOrder']}")
```

### Node.js example (axios)

```javascript
const axios = require('axios');
const fs = require('fs');

const BASE_URL = 'https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV';
const AUTH = { username: 'APIUSER', password: 'password' };

async function createPurchaseOrder(payload) {
    // Step 1: Fetch CSRF token
    const tokenRes = await axios.get(`${BASE_URL}/`, {
        auth: AUTH,
        headers: { 'X-CSRF-Token': 'Fetch', 'Accept': 'application/json' },
        withCredentials: true,
        httpsAgent: new (require('https').Agent)({ rejectUnauthorized: false }) // dev only
    });

    const csrfToken = tokenRes.headers['x-csrf-token'];
    const cookie = tokenRes.headers['set-cookie']?.join('; ') || '';

    // Step 2: POST with CSRF token and session cookie
    const createRes = await axios.post(`${BASE_URL}/A_PurchaseOrder`, payload, {
        auth: AUTH,
        headers: {
            'X-CSRF-Token': csrfToken,
            'Cookie': cookie,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    });

    return createRes.data.d;
}

// Usage
const payload = JSON.parse(fs.readFileSync('assets/payloads/po-create.json', 'utf8'));
createPurchaseOrder(payload).then(po => console.log('Created PO:', po.PurchaseOrder));
```

### Token expiry

CSRF tokens are tied to the user's SAP session. Sessions expire after the ICM session timeout (default: 1800 seconds = 30 minutes). If you get a `403 CSRF token validation failed` after a period of inactivity, re-fetch the token from the service root.

---

## 4. Deep Insert Pattern

Deep Insert allows creating a parent entity and its child entities in a single POST request. This is the recommended approach for creating complex objects like PO header + items + schedule lines.

### Structure

```json
{
  "ParentField1": "value",
  "ParentField2": "value",
  "to_ChildEntity": {
    "results": [
      {
        "ChildField1": "value",
        "ChildField2": "value",
        "to_GrandChildEntity": {
          "results": [
            {
              "GrandChildField1": "value"
            }
          ]
        }
      }
    ]
  }
}
```

### PO Deep Insert example (header + item + account assignment)

```json
{
  "CompanyCode": "1000",
  "PurchasingOrganization": "1000",
  "PurchasingGroup": "001",
  "Supplier": "1000001",
  "DocumentCurrency": "USD",
  "PurchaseOrderDate": "/Date(1746576000000)/",
  "to_PurchaseOrderItem": {
    "results": [
      {
        "PurchaseOrderItem": "00010",
        "Plant": "1000",
        "Material": "RAW-001",
        "OrderQuantity": "10",
        "NetPriceAmount": "25.00",
        "NetPriceCurrency": "USD",
        "PurchaseOrderItemCategory": "0",
        "AccountAssignmentCategory": "",
        "to_PurchaseOrderScheduleLine": {
          "results": [
            {
              "ScheduleLine": "0001",
              "ScheduleLineDeliveryDate": "/Date(1748563200000)/",
              "ScheduleLineOrderQuantity": "10"
            }
          ]
        }
      }
    ]
  }
}
```

**Important**: The navigation property name (e.g., `to_PurchaseOrderItem`) must match exactly the navigation property defined in the OData metadata. Check `$metadata` if unsure.

---

## 5. $filter / $expand / $select Syntax

### $filter

```bash
# Equality
$filter=CompanyCode eq '1000'

# Multiple conditions (AND)
$filter=CompanyCode eq '1000' and Supplier eq '1000001'

# Date comparison (OData V2 uses datetime literal)
$filter=PurchaseOrderDate ge datetime'2026-01-01T00:00:00'

# String contains (SAP OData V2 supports substringof, not contains)
$filter=substringof('RAW',Material) eq true

# In list (SAP OData V2 does NOT support 'in' operator — must use OR)
$filter=Plant eq '1000' or Plant eq '2000'
```

### $expand

```bash
# Expand one navigation property
$expand=to_PurchaseOrderItem

# Expand nested navigation properties (separate with /)
$expand=to_PurchaseOrderItem/to_PurchaseOrderScheduleLine

# Expand multiple properties (comma-separated)
$expand=to_PurchaseOrderItem,to_PurchaseOrderItem/to_PurchaseOrderScheduleLine,to_PurchaseOrderItem/to_AccountAssignment
```

### $select

```bash
# Select specific fields
$select=PurchaseOrder,CompanyCode,Supplier,PurchaseOrderDate

# Select fields from expanded entities
$select=PurchaseOrder,Supplier,to_PurchaseOrderItem/PurchaseOrderItem,to_PurchaseOrderItem/Material,to_PurchaseOrderItem/OrderQuantity
```

### $top and $skip (pagination)

```bash
# First 50 records
$top=50

# Records 51-100
$top=50&$skip=50

# SAP OData V2 also supports server-side paging via nextLink in response
```

---

## 6. OData V2 vs V4 Differences

| Aspect | OData V2 | OData V4 |
|---|---|---|
| Entity naming | PascalCase with `A_` prefix (e.g., `A_PurchaseOrder`) | Similar but may vary by service |
| Navigation properties | `to_Entity` prefix | `_Entity` or direct (varies) |
| Date format | `/Date(milliseconds)/` | ISO 8601: `2026-04-30T00:00:00Z` |
| Null value | `null` | `null` |
| Count | `$inlinecount=allpages` in response | `$count=true` in response |
| Batch requests | `$batch` with multipart/mixed | `$batch` with JSON format |
| Function imports | `FunctionImport` | `Action`, `Function` |
| Error format | `{"error":{"code":"...","message":{...},"innererror":{...}}}` | `{"error":{"code":"...","message":"..."}}` |
| Content-Type for POST | `application/json` or `application/atom+xml` | `application/json` only |
| `@odata.context` | Not present | Required in response |
| Service URL base | `/sap/opu/odata/sap/<SRV>/` | `/sap/opu/odata4/sap/<api>/srvd_a2x/sap/<entity>/0001/` |

### V4 date example

```json
// OData V2 — filter by date
$filter=PurchaseOrderDate ge datetime'2026-01-01T00:00:00'

// OData V4 — ISO 8601 format
$filter=PurchaseOrderDate ge 2026-01-01T00:00:00Z
```

---

## 7. Service URL Patterns

### OData V2 (most standard SAP APIs)

```
https://<host>:<port>/sap/opu/odata/sap/<SERVICE_NAME>/

Examples:
https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/
https://s4hana.example.com:44300/sap/opu/odata/sap/API_SALES_ORDER_SRV/
https://s4hana.example.com:44300/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV/
```

### OData V4 / RAP (S/4HANA 2020+ and Cloud)

```
https://<host>:<port>/sap/opu/odata4/sap/<api_name>/srvd_a2x/sap/<entity_set>/0001/

Examples:
https://s4hana.example.com:44300/sap/opu/odata4/sap/api_purchaseorder/srvd_a2x/sap/purchaseorder/0001/
```

### Metadata endpoint (always test this first)

```bash
# V2
curl -u user:pass "https://host:port/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/\$metadata"

# V4
curl -u user:pass "https://host:port/sap/opu/odata4/sap/api_purchaseorder/srvd_a2x/sap/purchaseorder/0001/\$metadata"
```

### Port conventions

| Protocol | Default Port | Notes |
|---|---|---|
| HTTP (development only) | 8000 | Never use in production |
| HTTPS | 44300 | Standard for AS ABAP |
| HTTPS (alternative) | 443 | Reverse proxy setups |
| Load balancer | Custom | Check with SAP Basis |

---

## 8. HTTP Client Examples

### Java (OkHttp)

```java
import okhttp3.*;

OkHttpClient client = new OkHttpClient();

// Step 1: Fetch CSRF token
Request tokenRequest = new Request.Builder()
    .url("https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/")
    .header("X-CSRF-Token", "Fetch")
    .header("Accept", "application/json")
    .header("Authorization", Credentials.basic("APIUSER", "password"))
    .build();

Response tokenResponse = client.newCall(tokenRequest).execute();
String csrfToken = tokenResponse.header("x-csrf-token");
String cookies = String.join("; ",
    tokenResponse.headers("set-cookie").stream()
        .map(c -> c.split(";")[0])
        .collect(java.util.stream.Collectors.toList())
);

// Step 2: POST
RequestBody body = RequestBody.create(
    MediaType.parse("application/json"),
    new String(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get("assets/payloads/po-create.json")))
);

Request createRequest = new Request.Builder()
    .url("https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder")
    .header("X-CSRF-Token", csrfToken)
    .header("Cookie", cookies)
    .header("Content-Type", "application/json")
    .header("Accept", "application/json")
    .header("Authorization", Credentials.basic("APIUSER", "password"))
    .post(body)
    .build();

Response createResponse = client.newCall(createRequest).execute();
System.out.println(createResponse.body().string());
```

---

## 9. Known SAP OData Limitations

| Limitation | Description | Workaround |
|---|---|---|
| No `not` operator in $filter | `$filter=not(...)` is unsupported | Use positive inverse logic |
| No `in` operator | `$filter=Plant in ('1000','2000')` fails | Use `or`: `Plant eq '1000' or Plant eq '2000'` |
| $expand depth limit | SAP limits expand depth, varies by service | Use separate GET calls for deeper navigation |
| Max response size | Default 10,000 entities; configurable in `/IWFND/MAINT_SERVICE` | Use `$top`/`$skip` pagination |
| `substringof` deprecated in V4 | V2 uses `substringof`, V4 uses `contains` | Adjust filter syntax per version |
| Batch limit | Max 1000 change sets per $batch | Break into multiple $batch requests |
| `PurchasingCompletenessStatus` is read-only | Cannot PATCH this field directly | Update at item/schedule line level |
| Deep insert nesting limit | 3 levels maximum in most standard services | Flatten to separate calls if deeper |
| Date format strict in V2 | Must use `/Date(ms)/` format; ISO fails | Always use OData V2 date format for V2 APIs |
| No async callbacks | OData is synchronous | Use IDoc or BAPI for event-driven scenarios |
