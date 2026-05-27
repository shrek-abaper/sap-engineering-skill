# SAP Integration Best Practices

## Table of Contents
- [Connection Management](#connection-management)
- [Authentication & Secrets](#authentication--secrets)
- [Error Handling](#error-handling)
- [Idempotency & Duplicate Prevention](#idempotency--duplicate-prevention)
- [Retry Logic](#retry-logic)
- [Performance & Throughput](#performance--throughput)
- [Observability & Monitoring](#observability--monitoring)
- [Testing Strategy](#testing-strategy)
- [Versioning & Compatibility](#versioning--compatibility)
- [Security Hardening Checklist](#security-hardening-checklist)

---

## Connection Management

### JCo Connection Pools

Never create a new JCo connection per request — it opens a new TCP+SAP logon dialog each time (300–1000 ms overhead). Always use `JCoDestinationManager` with a pool.

```java
// WRONG: Creates a new connection for every call
JCoDestination dest = new JCoManagedConnectionFactory(...).createConnection();
dest.getRepository().getFunction("BAPI_PO_CREATE1").execute(dest);
dest.getClient().close(); // This is not how JCo works — there's no such close

// CORRECT: Pool is managed by the destination manager
JCoDestination dest = JCoDestinationManager.getDestination("SAP_ERP");
// JCo transparently checks out a pooled connection
JCoFunction fn = dest.getRepository().getFunction("BAPI_PO_CREATE1");
fn.execute(dest);
// Connection automatically returns to pool after execute()
```

**Recommended pool settings for production:**

| Parameter | Value | Rationale |
|---|---|---|
| `jco.destination.pool_capacity` | 5–10 | Matches typical concurrent thread count |
| `jco.destination.peak_limit` | 20–30 | Overflow headroom during load spikes |
| `jco.destination.expiration_time` | 600000 (10 min) | Avoid idle timeout from SAP side |
| `jco.destination.max_get_client_time` | 30000 (30 s) | Fail fast on pool exhaustion |

### HTTP Session Reuse (OData)

SAP OData issues a session cookie on the CSRF token fetch. Reuse the same HTTP session across multiple write requests to avoid repeatedly fetching a new CSRF token.

```python
import requests

class SAPSession:
    def __init__(self, base_url, user, password, client):
        self.session = requests.Session()
        self.session.auth = (user, password)
        self.session.headers.update({"x-sap-client": client, "Accept": "application/json"})
        self.base_url = base_url
        self._csrf_token = None

    def _ensure_csrf(self):
        if not self._csrf_token:
            resp = self.session.get(
                self.base_url,
                headers={"X-CSRF-Token": "Fetch"},
            )
            resp.raise_for_status()
            self._csrf_token = resp.headers["X-CSRF-Token"]

    def post(self, path, payload):
        self._ensure_csrf()
        resp = self.session.post(
            f"{self.base_url}{path}",
            json=payload,
            headers={"X-CSRF-Token": self._csrf_token, "Content-Type": "application/json"},
        )
        if resp.status_code == 403:
            # Token may have expired — refetch once
            self._csrf_token = None
            self._ensure_csrf()
            resp = self.session.post(
                f"{self.base_url}{path}",
                json=payload,
                headers={"X-CSRF-Token": self._csrf_token, "Content-Type": "application/json"},
            )
        resp.raise_for_status()
        return resp.json()
```

---

## Authentication & Secrets

### Never Hard-Code Credentials

```java
// WRONG — hard-coded credentials
Properties props = new Properties();
props.setProperty(DestinationDataProvider.JCO_USER,   "RFCUSER");
props.setProperty(DestinationDataProvider.JCO_PASSWD, "SuperSecret123");  // ← never do this

// CORRECT — read from environment variables
Properties props = new Properties();
props.setProperty(DestinationDataProvider.JCO_ASHOST, System.getenv("SAP_HOST"));
props.setProperty(DestinationDataProvider.JCO_SYSNR,  System.getenv("SAP_SYSNR"));
props.setProperty(DestinationDataProvider.JCO_CLIENT, System.getenv("SAP_CLIENT"));
props.setProperty(DestinationDataProvider.JCO_USER,   System.getenv("SAP_USER"));
props.setProperty(DestinationDataProvider.JCO_PASSWD, System.getenv("SAP_PASSWORD"));
```

**Secrets management hierarchy (prefer higher in list):**

| Approach | When to Use |
|---|---|
| Cloud secrets manager (AWS Secrets Manager, Azure Key Vault, HashiCorp Vault) | Production on cloud |
| Kubernetes Secrets + mounted volume | Production on Kubernetes |
| Environment variables from CI/CD pipeline | CI/CD and containers |
| `.env` file (excluded from git) | Local development only |
| Hardcoded in source | **Never** |

### OAuth2 Token Caching

Do NOT request a new token for every API call. Cache the token and refresh before expiry.

```java
import java.time.Instant;

public class OAuthTokenCache {
    private String cachedToken;
    private Instant expiresAt;
    private final long BUFFER_SECONDS = 60; // refresh 60s before expiry

    public synchronized String getToken() {
        if (cachedToken == null || Instant.now().isAfter(expiresAt.minusSeconds(BUFFER_SECONDS))) {
            TokenResponse resp = fetchNewToken(); // POST to token endpoint
            this.cachedToken = resp.accessToken;
            this.expiresAt = Instant.now().plusSeconds(resp.expiresIn);
        }
        return cachedToken;
    }
}
```

### Principle of Least Privilege

Create dedicated technical users in SAP for each integration interface:

| User | Authorizations |
|---|---|
| `RFC_PO_READ` | `S_RFC` (read), `M_BEST_BSA` (PO display) |
| `RFC_PO_CREATE` | `S_RFC` (execute), `M_BEST_BSA` (PO create), `F_BKPF_BUK` (FI posting) |
| `ODATA_MM` | `Z_ODATA_MM` (custom OData role), `S_SERVICE` (OData ICF nodes) |

Never give an integration user SAP_ALL or developer authorizations. Use `SU53` after a failed call to identify the exact missing authorization object.

---

## Error Handling

### BAPI RETURN Table — Always Check All Rows

```java
JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
List<String> errors = new ArrayList<>();
List<String> warnings = new ArrayList<>();

for (int i = 0; i < returnTable.getNumRows(); i++) {
    returnTable.setRow(i);
    String type = returnTable.getString("TYPE");
    String msg = String.format("[%s/%s] %s",
        returnTable.getString("ID"),      // Message class
        returnTable.getString("NUMBER"),   // Message number
        returnTable.getString("MESSAGE")   // Resolved text
    );
    if ("E".equals(type) || "A".equals(type)) errors.add(msg);
    else if ("W".equals(type)) warnings.add(msg);
}

if (!errors.isEmpty()) {
    // ALWAYS rollback on BAPI errors before throwing
    JCoFunction rollback = dest.getRepository().getFunction("BAPI_TRANSACTION_ROLLBACK");
    rollback.execute(dest);
    throw new SAPIntegrationException("BAPI failed: " + String.join("; ", errors));
}
if (!warnings.isEmpty()) {
    log.warn("BAPI warnings: {}", warnings);
}
// Only commit when no errors
JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
commit.getImportParameterList().setValue("WAIT", "X");
commit.execute(dest);
```

### OData Error Response Parsing

SAP OData error responses have a specific structure. Always parse `innererror` for the full message:

```python
def parse_sap_odata_error(response):
    try:
        body = response.json()
        error = body.get("error", {})
        code = error.get("code", "UNKNOWN")
        message = error.get("message", {}).get("value", str(response.text))
        innererror = error.get("innererror", {})
        details = innererror.get("errordetails", [])
        detail_msgs = [d.get("message", "") for d in details if d.get("severity") == "error"]
        full_msg = message
        if detail_msgs:
            full_msg += " | Details: " + "; ".join(detail_msgs)
        return f"SAP OData Error {response.status_code} [{code}]: {full_msg}"
    except Exception:
        return f"SAP HTTP Error {response.status_code}: {response.text[:500]}"

# Usage:
resp = session.post(url, json=payload)
if not resp.ok:
    raise RuntimeError(parse_sap_odata_error(resp))
```

### Error Classification

Classify errors before deciding whether to retry:

| Error Class | Examples | Action |
|---|---|---|
| **Transient** | 503, 429, network timeout, lock conflict (`ENQUEUE_E_LOCK`) | Retry with backoff |
| **Client error** | 400 (bad payload), 404 (key not found), BAPI field validation failure | Fix the request, do not retry |
| **Auth error** | 401 (credentials), 403 CSRF token | Refresh credentials/token, retry once |
| **SAP system error** | `ABAP Runtime Error`, database lock timeout, short dump | Alert, do not retry automatically |

---

## Idempotency & Duplicate Prevention

SAP does not natively enforce idempotency on BAPI or OData calls. Two identical POST requests will create two purchase orders. You must implement duplicate detection externally.

### Pattern 1: External Key Mapping Table

Store a mapping of your system's business keys to SAP document numbers:

```sql
CREATE TABLE sap_doc_map (
    external_key     VARCHAR(100) PRIMARY KEY,  -- e.g., "ERPOrder-2026-001"
    sap_doc_number   VARCHAR(20) NOT NULL,
    sap_doc_type     VARCHAR(20) NOT NULL,       -- 'PO', 'SO', 'FI_DOC'
    created_at       TIMESTAMP DEFAULT NOW(),
    status           VARCHAR(20) DEFAULT 'created'
);
```

Before creating a document in SAP, check if `external_key` already exists. If it does, return the existing SAP number without calling SAP again.

### Pattern 2: SAP Reference Field

Many SAP BAPIs accept a reference/external number field. Use your system's unique ID:

```java
// BAPI_PO_CREATE1 — POHEADER.YOUR_REFERENCE
header.setValue("YOUR_REFERENCE", "EXTERNAL-ORDER-2026-001");

// BAPI_ACC_DOCUMENT_POST — DOCUMENTHEADER.OBJ_KEY
documentHeader.setValue("OBJ_KEY", "MY-SYSTEM-VOUCHER-789");
```

Then use `BAPI_PO_GETDETAIL` or OData `$filter=YourReference eq 'EXTERNAL-ORDER-2026-001'` to check for duplicates before creating.

### Pattern 3: Batch Number / Supplier Reference (STO)

For `API_PURCHASEORDER_PROCESS_SRV`, the field `SupplierRespSalesPersonName` on the PO header is often used as an external reference marker in custom scenarios (as in the `sap-sto-create` skill). This is not standard SAP practice but is a common workaround when no standard reference field fits.

---

## Retry Logic

### Exponential Backoff with Jitter

```python
import time, random, logging

def call_with_retry(fn, max_attempts=5, base_delay=1.0, max_delay=60.0):
    attempt = 0
    while attempt < max_attempts:
        try:
            return fn()
        except TransientSAPError as e:
            attempt += 1
            if attempt == max_attempts:
                raise
            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
            logging.warning(f"Transient error (attempt {attempt}/{max_attempts}): {e}. Retrying in {delay:.1f}s")
            time.sleep(delay)

# Usage
result = call_with_retry(lambda: create_purchase_order(payload))
```

### SAP-specific Transient Conditions

| Condition | Indicator | Action |
|---|---|---|
| DB lock / enqueue | JCoException code `JCO_ERROR_SYSTEM_FAILURE` + "ENQUEUE_E_LOCK" | Retry after 2–5 s |
| HTTP 503 from SAP Gateway | HTTP 503 | Retry after 10–30 s |
| CSRF token expired (403) | HTTP 403 + "CSRF token validation failed" | Refetch token, retry once |
| SAP work process shortage | HTTP 503 or timeout | Retry with longer backoff |
| Rate limiting (Cloud) | HTTP 429 | Respect `Retry-After` header |

---

## Performance & Throughput

### OData $batch for Bulk Operations

Instead of 1000 individual POST requests, use a single `$batch` request:

```http
POST /sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/$batch
Content-Type: multipart/mixed; boundary=batch_001
X-CSRF-Token: <token>

--batch_001
Content-Type: multipart/mixed; boundary=changeset_001

--changeset_001
Content-Type: application/http
Content-Transfer-Encoding: binary

POST A_PurchaseOrderItem HTTP/1.1
Content-Type: application/json

{"PurchaseOrder":"4500000001","PurchaseOrderItem":"00020",...}

--changeset_001--
--batch_001--
```

SAP OData `$batch` limits:
- Maximum 100 operations per `$batch` request (SAP default; configurable)
- All operations in a `changeset` are atomic — one failure rolls back all
- Operations in separate `changeset` blocks are independent

### RFC Parallel Processing

For large bulk loads via BAPI, use parallel RFC calls:

```java
// JCo supports parallel execution via JCoAbapFunction.setDestination + executeInBackground
// For true parallelism, use Java thread pool + separate JCo connections from pool
ExecutorService pool = Executors.newFixedThreadPool(5);
List<Future<String>> futures = new ArrayList<>();

for (MaterialRecord record : records) {
    futures.add(pool.submit(() -> createMaterial(record)));
}

for (Future<String> future : futures) {
    try {
        future.get(30, TimeUnit.SECONDS);
    } catch (ExecutionException e) {
        log.error("Material creation failed", e.getCause());
    }
}
pool.shutdown();
```

### Pagination for Large Result Sets

SAP OData V2 returns a maximum of 1000 rows by default. Always paginate:

```python
def get_all_materials(session, base_url, filter_expr=""):
    url = f"{base_url}/A_Product"
    params = {"$top": 500, "$skiptoken": None}
    if filter_expr:
        params["$filter"] = filter_expr

    results = []
    while url:
        resp = session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()["d"]
        results.extend(data.get("results", []))

        # SAP V2 paging: look for __next in response
        next_link = data.get("__next")
        url = next_link if next_link else None
        params = {}  # params are embedded in __next URL

    return results
```

---

## Observability & Monitoring

### Correlation IDs

Attach a unique correlation ID to every request chain. Pass it as a custom HTTP header that flows through all systems:

```python
import uuid

CORRELATION_HEADER = "X-Correlation-ID"

def create_purchase_order(payload, correlation_id=None):
    corr_id = correlation_id or str(uuid.uuid4())
    session.headers.update({CORRELATION_HEADER: corr_id})
    # Include in your application logs too
    log.info("Creating PO", extra={"correlation_id": corr_id, "payload_summary": payload.get("Supplier")})
    resp = session.post(url, json=payload)
    log.info("PO created", extra={"correlation_id": corr_id, "sap_doc": resp.json()["d"]["PurchaseOrder"]})
    return resp.json()
```

SAP does not natively propagate your correlation ID through its internal processing, but having it in your logs and in SAP's `SY-MSGNO` / transaction trace (SM50, ST05) allows you to correlate the timestamps.

### Structured Logging

```json
{
  "timestamp": "2026-05-01T14:30:00.000Z",
  "level": "INFO",
  "service": "po-integration",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "sap_system": "PRD",
  "operation": "BAPI_PO_CREATE1",
  "duration_ms": 423,
  "sap_doc_number": "4500012345",
  "supplier": "0000100005",
  "plant": "1000"
}
```

### Key Metrics to Track

| Metric | Alert Threshold |
|---|---|
| BAPI call latency (p95) | > 5 seconds |
| OData error rate (4xx/5xx) | > 2% over 5 minutes |
| JCo pool wait time | > 10 seconds |
| Failed message queue depth | > 100 messages |
| Token refresh failures | Any |
| SAP system availability (health probe) | Any failure |

---

## Testing Strategy

### Unit Testing with Mocked SAP Responses

Do not connect to a live SAP system in unit tests. Mock the SAP response:

```python
# pytest with unittest.mock
from unittest.mock import patch, MagicMock

def test_create_po_success():
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {
        "d": {"PurchaseOrder": "4500099999", "PurchasingOrganization": "1000"}
    }

    with patch("requests.Session.post", return_value=mock_response):
        result = create_purchase_order({
            "CompanyCode": "1000",
            "Supplier": "0000100005",
            ...
        })
    assert result["PurchaseOrder"] == "4500099999"

def test_create_po_handles_400_error():
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 400
    mock_response.json.return_value = {
        "error": {
            "code": "MM/873",
            "message": {"value": "Vendor not found"},
            "innererror": {"errordetails": []}
        }
    }
    with patch("requests.Session.post", return_value=mock_response):
        with pytest.raises(RuntimeError, match="Vendor not found"):
            create_purchase_order({"Supplier": "INVALID", ...})
```

### Integration Testing Against SAP Sandbox

Use a dedicated sandbox or DEV client for integration tests. Key practices:
- Create test data with a recognizable prefix (e.g., `TEST-PO-` + timestamp)
- Clean up test documents after the test run (set deletion indicator)
- Never run integration tests against PRD — even "read-only" tests generate audit logs

### Contract Testing

Define the expected SAP API contract (request/response schema) in OpenAPI or JSON Schema:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "PO Create Request",
  "required": ["CompanyCode", "PurchasingOrganization", "Supplier"],
  "properties": {
    "CompanyCode": { "type": "string", "minLength": 4, "maxLength": 4 },
    "PurchasingOrganization": { "type": "string", "maxLength": 4 },
    "Supplier": { "type": "string", "maxLength": 10 }
  }
}
```

Validate your payload against this schema before sending to SAP to catch client-side errors early.

---

## Versioning & Compatibility

### API Version Pinning

Avoid using the latest SAP API version blindly. Pin to a specific version and test upgrades explicitly:

```bash
# OData V4: version is in the URL
# Pin to a specific release path
/sap/opu/odata4/sap/api_purchaseorder/srvd_a2x/sap/purchaseorder/0001/

# When SAP releases a new version (0002), test in sandbox before switching
```

### Graceful Degradation

When calling S/4HANA and you do not know the exact release:

```python
def get_product(material, plant):
    # Try OData V2 first (available S/4HANA 1709+)
    try:
        return get_product_odata(material, plant)
    except HTTPError as e:
        if e.response.status_code in (404, 503):
            # Fallback to BAPI for older systems or unavailable service
            return get_product_bapi(material, plant)
        raise
```

### Handling SAP Release Notes

Subscribe to SAP release notes for the APIs you use:
- **SAP API Business Hub**: each API has a "What's New" tab and deprecation notices
- **SAP Note search**: search for your API name + "deprecation" or "successor" on `support.sap.com`
- **SAP Community blogs**: the "SAP S/4HANA" and "SAP BTP" spaces publish breaking changes
- **SAP Help Portal changelog**: `help.sap.com` has version-specific documentation

---

## Security Hardening Checklist

### Network
- [ ] HTTPS only — never HTTP for production
- [ ] Validate SAP server certificate (don't use `verify=False` in production)
- [ ] Cloud Connector resources restricted to exact paths, not `/*`
- [ ] SAP firewall rule: only allow inbound RFC (port 33xx) from known IP ranges
- [ ] No SAP system directly internet-facing — use reverse proxy or API Management

### Credentials
- [ ] Integration users are type "S" (Service/System) — not dialog users
- [ ] Passwords stored in secrets manager, not in source code or config files
- [ ] OAuth2 client secrets rotated at least annually
- [ ] Separate users per integration interface (principle of least privilege)
- [ ] User account lockout policy doesn't apply to RFC users (avoid false lockouts from concurrent calls)

### Authorization
- [ ] Only necessary authorization objects assigned (use `SU53` + `STAUTHTRACE` to audit)
- [ ] No `SAP_ALL` or `SAP_NEW` for integration users
- [ ] ICF nodes activated for only the required OData services
- [ ] RFC function modules in authorization group `ZCUST` or specific group (not `*`)

### Application
- [ ] All inputs validated before sending to SAP (length, type, enum values)
- [ ] SAP error messages sanitized before returning to external callers (don't leak internal details)
- [ ] Audit log for all write operations (who called what, when, with what data)
- [ ] Rate limiting on your integration layer to protect SAP from traffic spikes
- [ ] Correlation IDs in all log entries for traceability
