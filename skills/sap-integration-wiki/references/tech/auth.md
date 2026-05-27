# SAP Authentication Reference

## Table of Contents

1. [Basic Auth Setup Checklist](#1-basic-auth-setup-checklist)
2. [OAuth2 on S/4HANA On-Premise](#2-oauth2-on-s4hana-on-premise)
3. [OAuth2 on S/4HANA Cloud Public Edition](#3-oauth2-on-s4hana-cloud-public-edition)
4. [SSL/TLS Configuration](#4-ssltls-configuration)
5. [SAP BTP Connectivity](#5-sap-btp-connectivity)
6. [Quick Diagnosis Checklist](#6-quick-diagnosis-checklist)

---

## 1. Basic Auth Setup Checklist

Basic Authentication uses HTTP Basic (username:password in Base64) on every request. Simple but credentials transmitted with every call.

### SAP user requirements

| Requirement | Detail |
|---|---|
| **User type** | Communication user (`S`) — not dialog user (`A`). Dialog users have password change policies that break automation. |
| **Password policy** | Ensure the user's password does not expire. Set in `SU01` → Logon Data → Valid Through |
| **User not locked** | Check `SU01` → select user → verify "User is not locked" status |
| **Required roles** | See below — varies by operation |

### Role requirements by operation

| Operation | Required Authorization Object | Role Example |
|---|---|---|
| OData read (GET) | `S_SERVICE` with `SRV_NAME` = service name and `SRV_TYPE = 'HT'` | `SAP_BC_WEBSERVICE_CONSUMER` |
| OData write (POST/PATCH) | `S_SERVICE` (read) + business object authorization | `SAP_MM_PUR_PURCHASEORDER` |
| RFC/BAPI call | `S_RFC` with `RFC_TYPE = 'FUGR'` and `RFC_NAME = function_group` | `SAP_BC_BASIS_RFC` |
| IDoc posting (inbound) | `S_IDOCCTRL` with authorization for partner/message type | Custom role |

### ICF node activation

OData services only respond if the Internet Communication Framework node is active.

**Transaction: `SICF`**

1. Open `SICF`
2. Navigate path: `sap` → `opu` → `odata` → `sap` → `<SERVICE_NAME>`
3. If the service appears greyed out (inactive), right-click → **Activate Service**
4. To activate the parent node for all OData services: `sap/opu/odata` → Activate recursively

**Testing ICF activation:**

```bash
# Should return 200 OK (possibly redirects) if ICF node is active
curl -I "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/"
# Returns 404 if ICF node is inactive
```

### Testing Basic Auth with curl

```bash
# Test connection and authentication (GET metadata — no write required)
curl -v -u "USERNAME:PASSWORD" \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/\$metadata" \
  -H "Accept: application/xml"

# Expected: HTTP 200 with XML metadata
# HTTP 401: Wrong credentials or locked user
# HTTP 403: User authenticated but missing S_SERVICE authorization
# HTTP 404: Service not activated (SICF issue)
```

---

## 2. OAuth2 on S/4HANA On-Premise

SAP supports OAuth 2.0 for OData service access on S/4HANA On-Premise. The supported grants are:
- **Client Credentials** — server-to-server, no user interaction
- **SAML Bearer Assertion** — with identity federation (complex setup)
- **Authorization Code** — browser-based flows (for Fiori apps)

### Prerequisites

- S/4HANA On-Premise 1709+ (OAuth2 server built-in)
- SAP Basis must enable OAuth in `SOAUTH2`

### Step-by-step: Client Credentials flow

**Step 1: Create OAuth2 Client (transaction SOAUTH2)**

1. Transaction `SOAUTH2`
2. Click "Create OAuth 2.0 Client"
3. Fill in:
   - **OAuth 2.0 Client ID**: e.g., `INTEGRATION_CLIENT`
   - **Description**: e.g., `External integration client`
   - **Client Secret**: set and store securely
   - **Redirect URI**: not needed for client credentials
   - **Allowed Grant Types**: check `Client Credentials`
4. Under **Scope**, add the required scopes:
   - For OData: `OA2_CLIENT_CREDENTIALS` (basic scope for API access)
   - For specific services: add service-specific scopes if configured
5. Assign to user: the OAuth client acts as the user; ensure the underlying user has proper roles

**Step 2: Get token endpoint URL**

```
https://<host>:<port>/sap/bc/sec/oauth2/token
```

**Step 3: Request access token**

```bash
curl -X POST \
  "https://s4hana.example.com:44300/sap/bc/sec/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials\
&client_id=INTEGRATION_CLIENT\
&client_secret=YOUR_SECRET\
&scope=OA2_CLIENT_CREDENTIALS"

# Response:
# {
#   "access_token": "eyJhbGciOiJ...",
#   "token_type": "Bearer",
#   "expires_in": 3600,
#   "scope": "OA2_CLIENT_CREDENTIALS"
# }
```

**Step 4: Use token in OData calls**

```bash
ACCESS_TOKEN="eyJhbGciOiJ..."

# CSRF token fetch using Bearer token
curl -u "" \  # No Basic Auth
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CSRF-Token: Fetch" \
  -H "Accept: application/json" \
  -c /tmp/sap-cookies.txt \
  -D /tmp/sap-headers.txt \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/"

CSRF_TOKEN=$(grep -i "x-csrf-token" /tmp/sap-headers.txt | awk '{print $2}' | tr -d '\r')

# POST with Bearer token + CSRF
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Content-Type: application/json" \
  -b /tmp/sap-cookies.txt \
  -X POST \
  "https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder" \
  -d @po-create.json
```

**Activating the OAuth ICF node:**

Transaction `SICF` → navigate to `/sap/bc/sec/oauth2` → ensure it is active.

---

## 3. OAuth2 on S/4HANA Cloud Public Edition

In Cloud Public Edition, OAuth2 is the **only supported authentication method** for external API access. Basic Auth is not available.

### Communication Arrangements

Cloud Public uses "Communication Arrangements" to define inbound/outbound connectivity:

1. **Create Communication System** (transaction `SPRO` → SAP NetWeaver → Communication → Communication Systems):
   - System ID: e.g., `EXTERNAL_INTEGRATION`
   - Host name / URL of external system

2. **Create Communication User** (transaction `SU01` or communication user maintenance app):
   - User type: Communication User
   - Assign required roles/authorizations

3. **Create Communication Arrangement** (Fiori app: "Communication Arrangements"):
   - Select Communication Scenario (e.g., `SAP_COM_0109` for purchase order)
   - Assign communication system
   - Note the **service URL** and **client credentials** generated

4. **Retrieve credentials**:
   - OAuth Client ID and Client Secret are in the communication arrangement
   - Token URL: `https://<tenant>.s4hana.cloud/sap/bc/sec/oauth2/token`

### Token request (Cloud Public Edition)

```bash
curl -X POST \
  "https://mytenant.s4hana.cloud/sap/bc/sec/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials\
&client_id=<CLIENT_ID_FROM_COMM_ARRANGEMENT>\
&client_secret=<SECRET_FROM_COMM_ARRANGEMENT>"
```

**Python example with token caching:**

```python
import requests
import time

class SAPCloudAuth:
    def __init__(self, token_url, client_id, client_secret):
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None
        self._token_expires_at = 0

    def get_token(self):
        # Return cached token if not expired (with 60s buffer)
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        response = requests.post(
            self.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        token_data = response.json()

        self._token = token_data["access_token"]
        self._token_expires_at = time.time() + token_data.get("expires_in", 3600)
        return self._token

    def get_headers(self):
        return {"Authorization": f"Bearer {self.get_token()}"}
```

---

## 4. SSL/TLS Configuration

### When SSL/TLS is required

- Always in production — SAP On-Premise default HTTPS port is `44300`
- S/4HANA Cloud always uses HTTPS
- JCo RFC over SNC (Secure Network Communications) for encrypted RFC

### Importing CA certificate into SAP Trust Store

When your SAP system needs to trust an external server's SSL certificate (e.g., calling an external REST API):

**Transaction: `STRUST`**

1. Open `STRUST`
2. Navigate to **SSL client SSL Client (Anonymous)** (for outbound calls from SAP)
3. Click **Change** (pencil icon)
4. Paste the CA certificate PEM content in the certificate input field at the bottom
5. Click **Add to Certificate List**
6. Click **Save**
7. Restart ICM: transaction `SMICM` → Administration → ICM → Restart → Soft

### Importing external server certificate for OData client calls

When your external application calls SAP using HTTPS, the SAP server certificate must be trusted by your client:

```bash
# Download SAP server's certificate
openssl s_client -connect s4hana.example.com:44300 -showcerts \
  </dev/null 2>/dev/null | openssl x509 -outform PEM > sap-server.pem

# Add to Java truststore
keytool -import -alias sap-server \
  -keystore $JAVA_HOME/lib/security/cacerts \
  -file sap-server.pem \
  -storepass changeit

# For Python (requests library) — pass CA bundle
import requests
response = requests.get(url, auth=auth, verify="/path/to/sap-server.pem")

# Or disable verification (NOT for production)
response = requests.get(url, auth=auth, verify=False)
```

### SNC for RFC (encrypted JCo connections)

For encrypted RFC connections, SAP supports SNC (Secure Network Communications):

```properties
# jcoDestination file with SNC
jco.client.host=sap-erp.example.com
jco.client.sysnr=00
jco.client.client=100
jco.client.user=RFCUSER
jco.client.passwd=password
jco.client.snc_mode=1                          # Enable SNC
jco.client.snc_partnername=p:CN=SAPID,O=Corp   # Partner SNC name from STRUST
jco.client.snc_lib=/path/to/sapcrypto.dll      # SNC library path
```

---

## 5. SAP BTP Connectivity

SAP Business Technology Platform (BTP) is SAP's cloud platform. It connects external (non-SAP) applications to on-premise SAP systems.

### Components

| Component | Purpose |
|---|---|
| **Connectivity Service** | Manages destinations (connection configurations) |
| **Cloud Connector** | Secure tunnel between BTP and on-premise SAP |
| **Destination Service** | Stores and serves connection parameters (URL, credentials, auth type) |
| **Principal Propagation** | Passes the BTP user's identity to the on-premise SAP system (SSO) |

### Cloud Connector setup

1. Download SAP Cloud Connector from SAP Support Portal
2. Install and start on a server in your on-premise network
3. Connect to BTP subaccount: enter subaccount host, user, password
4. In Cloud Connector admin UI: add an on-premise system → specify SAP host + port → define virtual host mapping
5. In BTP Destination Service: create a destination pointing to the virtual host

### Destination configuration in BTP

```json
{
  "Name": "SAP_ERP_PURCHASEORDER",
  "Type": "HTTP",
  "URL": "https://virtual-sap-host:44300",
  "Authentication": "BasicAuthentication",
  "ProxyType": "OnPremise",
  "User": "APIUSER",
  "Password": "...",
  "sap-client": "100",
  "HTML5.DynamicDestination": "true"
}
```

For OAuth2, change `Authentication` to `OAuth2ClientCredentials` and add token URL + client ID/secret.

---

## 6. Quick Diagnosis Checklist

When auth fails, work through this checklist in order:

```
Step 1: Can you reach the SAP server at all?
  curl -I https://s4hana.example.com:44300/
  ✓ HTTP 200/301/302 → Server reachable
  ✗ Connection refused / timeout → Network issue, firewall, SAP not running

Step 2: Is the ICF node active?
  curl -I https://s4hana.example.com:44300/sap/opu/odata/
  ✓ HTTP 200 → ICF active
  ✗ HTTP 404 → SICF: activate /sap/opu/odata node

Step 3: Are credentials correct?
  curl -v -u USERNAME:PASSWORD https://s4hana.example.com:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/
  ✓ HTTP 200 with XML metadata → Auth OK
  ✗ HTTP 401 with "UNAUTHORIZED" → Check SU01: user exists? password correct? user not locked?
  ✗ HTTP 401 with "LOCKED" → SU01: unlock the user

Step 4: Does the user have S_SERVICE authorization?
  After a 403 response: transaction SU53 (immediately after failed call) → shows missing auth object
  ✓ No missing auth → Auth OK for this call
  ✗ S_SERVICE missing → Assign role with S_SERVICE for your service name

Step 5: For CSRF errors (403 with "CSRF token validation failed"):
  ✓ Are you sending X-CSRF-Token header? → Yes: verify token not expired; re-fetch
  ✗ Missing header → Add X-CSRF-Token: <fetched token> + Cookie header

Step 6: For OAuth2 issues:
  Does token request return 400? → Check SOAUTH2: client exists? grant type enabled?
  Does token request return 401? → Wrong client_id or client_secret
  Does API call with token return 401? → Token expired? Wrong scope? Check SOAUTH2 scope config
  Does API call with token return 403? → User associated with OAuth client lacks S_SERVICE authorization
```

### SAP transactions for auth diagnosis

| Transaction | Purpose |
|---|---|
| `SU01` | User maintenance — check lock status, password, validity |
| `SU53` | Authorization check result — shows last failed auth object immediately after failure |
| `STAUTHTRACE` | Detailed authorization trace — enable, reproduce failure, review |
| `SICF` | ICF node activation status |
| `SOAUTH2` | OAuth2 client configuration |
| `STRUST` | SSL/TLS trust store — certificate management |
| `SMICM` | ICM monitor — restart ICM after certificate changes |
| `SM59` | RFC destinations — check connectivity for JCo/RFC |
