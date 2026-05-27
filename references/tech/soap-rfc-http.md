# SOAP over HTTP RFC Reference

## Table of Contents

1. [When to Use SOAP over HTTP](#1-when-to-use-soap-over-http)
2. [SOAP over HTTP vs Java JCo](#2-soap-over-http-vs-java-jco)
3. [Prerequisites and SAP-Side Configuration](#3-prerequisites-and-sap-side-configuration)
4. [Authentication](#4-authentication)
5. [Request Format](#5-request-format)
6. [XML Payload Examples](#6-xml-payload-examples)
7. [Code Examples](#7-code-examples)
8. [Response Parsing](#8-response-parsing)
9. [Known Limitations](#9-known-limitations)

---

## 1. When to Use SOAP over HTTP

SAP exposes a standard SOAP endpoint at `/sap/bc/soap/rfc` that allows any HTTP client to call RFC-enabled function modules without installing any SAP-proprietary client library. The transport is standard HTTPS; the payload is a SOAP envelope. No JVM, no JCo JAR, no native library is required.

| Scenario | Use SOAP over HTTP |
|---|---|
| Non-JVM runtime (Python, Node.js, Go, etc.) and no standard OData API | Yes — zero library overhead |
| AI agent or LLM tool calling SAP for low-frequency reads | Yes — minimal footprint |
| Cloud or containerized workload with HTTPS-only egress | Yes — port 443 / 8001 only |
| Rapid prototyping or CLI tooling that needs to call a specific BAPI | Yes — only an HTTP client needed |
| ECC 6.0 and no suitable OData service exists | Yes — same as JCo without the JVM |
| Java application already using JCo | No — stay with JCo |
| High-concurrency or batch workload (1 000+ calls/minute) | No — no connection pool; use JCo |
| Sending or receiving IDocs | No — not supported |
| Transactional RFC (tRFC / qRFC) | No — not supported |
| SAP-initiated callback to your system | No — outbound only |

**Supported systems**: SAP ECC 6.0+ (NW 7.0+), S/4HANA On-Premise (all releases). **Not available** for S/4HANA Cloud Public Edition (no direct RFC external access).

---

## 2. SOAP over HTTP vs Java JCo

| Dimension | SOAP over HTTP | Java JCo |
|---|---|---|
| Protocol | Standard HTTP/HTTPS | SAP proprietary RFC protocol (port 33xx) |
| Client dependency | Any HTTP library (`requests`, `axios`, etc.) | JVM + SAP JCo JAR (closed-source, SAP Support Portal download) |
| Language support | Any language | Java only |
| Performance | ~1/3 of JCo (XML serialization overhead) | Best (binary protocol) |
| Connection pooling | None — new HTTP connection per call | Built-in connection pool |
| Firewall traversal | ✅ HTTPS 443 / 8001 — enterprise-friendly | ⚠️ Requires opening SAP RFC port 33xx |
| Bidirectional | ❌ Outbound only (external → SAP) | ✅ SAP can call back to Java |
| IDoc support | ❌ Not supported | ✅ Supported |
| tRFC / qRFC | ❌ Not supported | ✅ Supported |
| Load balancing | ❌ Single application server only | ✅ Message Server auto-routing |
| Monitoring | No standard tooling (HTTP response only) | SM58 / SM59 standard monitoring |
| SAP certification | ❌ Not an officially recommended integration path | ✅ SAP-certified integration method |
| Deployment complexity | Minimal — zero extra installation | High — JVM + native library + classpath |

---

## 3. Prerequisites and SAP-Side Configuration

### Activate the ICF service (transaction SICF)

The `/sap/bc/soap/rfc` ICF node must be active before any SOAP call will succeed.

**Step-by-step:**

1. Open transaction `SICF`
2. Navigate to: `default_host → sap → bc → soap → rfc`
3. Right-click the `rfc` node → **Activate Service**
4. Confirm the activation dialog

If the node is not active, SAP returns HTTP 404 or HTTP 403 for all requests to this endpoint.

### Required authorization for the calling user

The SAP user whose credentials are used for Basic Auth must have the following authorization:

| Authorization Object | Field | Value |
|---|---|---|
| `S_RFC` | `RFC_TYPE` | `FUGR` |
| `S_RFC` | `RFC_NAME` | Name of the function group containing the RFC-FM (e.g., `ME_API` for PO BAPIs) |
| `S_RFC` | `ACTVT` | `16` (Execute) |

Ask the SAP Basis / Security team to assign `S_RFC` for the relevant function groups. For a test user, the profile `S_RFC_ALL` grants unrestricted RFC access (do not use in production).

---

## 4. Authentication

- **HTTP Basic Auth** — pass `Authorization: Basic {base64(user:password)}` on every request
- **Always use HTTPS** to prevent credentials from being transmitted in cleartext
- **CSRF token** — required for all write operations (BAPIs that create or modify data):

```
Step 1 — Fetch token:
  GET https://{host}:{port}/sap/bc/adt/discovery
  Headers:
    Authorization: Basic {base64(user:password)}
    x-csrf-token: Fetch

  Response header:
    x-csrf-token: {TOKEN_VALUE}

Step 2 — Include token in SOAP POST:
  Headers:
    x-csrf-token: {TOKEN_VALUE}
    Content-Type: text/xml; charset=utf-8
    SOAPAction: {FM_NAME}
    Authorization: Basic {base64(user:password)}
```

Read-only RFC function modules (those that do not commit data) typically do not require a CSRF token. If in doubt, fetch one regardless — the overhead is a single GET request.

---

## 5. Request Format

### URL

```
POST https://{SAP_HOST}:{SAP_PORT}/sap/bc/soap/rfc?sap-client={SAP_CLIENT}
```

Common SAP ports:
- HTTP: `8000` (or `80xx` where `xx` = instance number)
- HTTPS: `44300` (or `443xx`)

### Required headers

| Header | Value |
|---|---|
| `Content-Type` | `text/xml; charset=utf-8` |
| `SOAPAction` | The RFC function module name, e.g., `BAPI_PO_GETDETAIL1` |
| `Authorization` | `Basic {base64(SAP_USER:SAP_PASSWORD)}` |
| `x-csrf-token` | Token fetched in advance (write operations only) |

### SOAP envelope structure

```xml
<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:urn="urn:sap-com:document:sap:rfc:functions">
  <soapenv:Body>
    <urn:{FM_NAME}>
      <!-- Import / Tables parameters here -->
    </urn:{FM_NAME}>
  </soapenv:Body>
</soapenv:Envelope>
```

**Namespace** (`urn:sap-com:document:sap:rfc:functions`) must be exact — SAP rejects requests with a different namespace.

### Parameter encoding rules

| Parameter kind | XML encoding |
|---|---|
| Scalar Import parameter | Direct child element: `<PARAM_NAME>value</PARAM_NAME>` |
| Structure Import parameter | Wrapper element containing field elements: `<STRUCT_NAME><FIELD>value</FIELD></STRUCT_NAME>` |
| Table parameter (each row) | `<TABLE_NAME><item><FIELD>value</FIELD></item></TABLE_NAME>` |
| Omitted / empty parameter | Simply omit the element — SAP uses the default |

---

## 6. XML Payload Examples

### Example A — Scalar Import parameters only

Calling `RFC_PING` (no parameters):

```xml
<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:urn="urn:sap-com:document:sap:rfc:functions">
  <soapenv:Body>
    <urn:RFC_PING/>
  </soapenv:Body>
</soapenv:Envelope>
```

Calling `BAPI_PO_GETDETAIL1` with scalar parameters:

```xml
<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:urn="urn:sap-com:document:sap:rfc:functions">
  <soapenv:Body>
    <urn:BAPI_PO_GETDETAIL1>
      <PURCHASEORDER>4500000123</PURCHASEORDER>
      <ITEMS>X</ITEMS>
      <ACCOUNT>X</ACCOUNT>
    </urn:BAPI_PO_GETDETAIL1>
  </soapenv:Body>
</soapenv:Envelope>
```

### Example B — Table (TABLES) parameter

Calling `RFC_READ_TABLE` with a FIELDS table parameter:

```xml
<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:urn="urn:sap-com:document:sap:rfc:functions">
  <soapenv:Body>
    <urn:RFC_READ_TABLE>
      <QUERY_TABLE>T001</QUERY_TABLE>
      <ROWCOUNT>3</ROWCOUNT>
      <FIELDS>
        <item><FIELDNAME>BUKRS</FIELDNAME></item>
        <item><FIELDNAME>BUTXT</FIELDNAME></item>
      </FIELDS>
    </urn:RFC_READ_TABLE>
  </soapenv:Body>
</soapenv:Envelope>
```

### Example C — Mixed scalar and table parameters

Calling `BAPI_GOODSMVT_CREATE` (goods movement) with a header structure and items table:

```xml
<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:urn="urn:sap-com:document:sap:rfc:functions">
  <soapenv:Body>
    <urn:BAPI_GOODSMVT_CREATE>
      <!-- Scalar: movement type code -->
      <GOODSMVT_CODE>
        <GM_CODE>04</GM_CODE>
      </GOODSMVT_CODE>
      <!-- Structure: document header -->
      <GOODSMVT_HEADER>
        <PSTNG_DATE>20260501</PSTNG_DATE>
        <DOC_DATE>20260501</DOC_DATE>
        <REF_DOC_NO>EXT-REF-001</REF_DOC_NO>
      </GOODSMVT_HEADER>
      <!-- Table: line items -->
      <GOODSMVT_ITEM>
        <item>
          <MATERIAL>RAW-001</MATERIAL>
          <PLANT>1000</PLANT>
          <STGE_LOC>0001</STGE_LOC>
          <MOVE_TYPE>261</MOVE_TYPE>
          <ENTRY_QNT>10</ENTRY_QNT>
          <ORDERID>000001234567</ORDERID>
        </item>
      </GOODSMVT_ITEM>
    </urn:BAPI_GOODSMVT_CREATE>
  </soapenv:Body>
</soapenv:Envelope>
```

---

## 7. Code Examples

### Python (`requests`) — Query purchase order via `BAPI_PO_GETDETAIL1`

```python
import base64
import requests
import xml.etree.ElementTree as ET

SAP_HOST     = "s4hana.example.com"
SAP_PORT     = "44300"
SAP_CLIENT   = "100"
SAP_USER     = "RFC_USER"
SAP_PASSWORD = "Passw0rd!"

BASE_URL = f"https://{SAP_HOST}:{SAP_PORT}"
SOAP_URL = f"{BASE_URL}/sap/bc/soap/rfc?sap-client={SAP_CLIENT}"

credentials = base64.b64encode(f"{SAP_USER}:{SAP_PASSWORD}".encode()).decode()
auth_header = f"Basic {credentials}"

SOAP_BODY = """<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:urn="urn:sap-com:document:sap:rfc:functions">
  <soapenv:Body>
    <urn:BAPI_PO_GETDETAIL1>
      <PURCHASEORDER>{po_number}</PURCHASEORDER>
      <ITEMS>X</ITEMS>
    </urn:BAPI_PO_GETDETAIL1>
  </soapenv:Body>
</soapenv:Envelope>"""


def get_po_detail(po_number: str) -> dict:
    payload = SOAP_BODY.format(po_number=po_number)

    response = requests.post(
        SOAP_URL,
        data=payload.encode("utf-8"),
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction":   "BAPI_PO_GETDETAIL1",
            "Authorization": auth_header,
        },
        verify=True,  # set to path of CA bundle if using self-signed cert
        timeout=30,
    )
    response.raise_for_status()

    # Parse response
    ns = {"urn": "urn:sap-com:document:sap:rfc:functions"}
    root = ET.fromstring(response.text)
    body = root.find(".//urn:BAPI_PO_GETDETAIL1.Response", ns)

    header = body.find("POHEADER", ns)
    return {
        "vendor":       header.findtext("VENDOR",    default=""),
        "doc_type":     header.findtext("DOC_TYPE",  default=""),
        "purch_org":    header.findtext("PURCH_ORG", default=""),
        "currency":     header.findtext("CURRENCY",  default=""),
        "doc_date":     header.findtext("DOC_DATE",  default=""),
    }


if __name__ == "__main__":
    result = get_po_detail("4500000123")
    print(result)
```

### curl — Query `T001` table via `RFC_READ_TABLE`

```bash
SAP_HOST="s4hana.example.com"
SAP_PORT="44300"
SAP_CLIENT="100"
SAP_USER="RFC_USER"
SAP_PASSWORD="Passw0rd!"

curl -s \
  -u "${SAP_USER}:${SAP_PASSWORD}" \
  -H "Content-Type: text/xml; charset=utf-8" \
  -H "SOAPAction: RFC_READ_TABLE" \
  --data '<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:urn="urn:sap-com:document:sap:rfc:functions">
  <soapenv:Body>
    <urn:RFC_READ_TABLE>
      <QUERY_TABLE>T001</QUERY_TABLE>
      <ROWCOUNT>3</ROWCOUNT>
      <FIELDS>
        <item><FIELDNAME>BUKRS</FIELDNAME></item>
        <item><FIELDNAME>BUTXT</FIELDNAME></item>
      </FIELDS>
    </urn:RFC_READ_TABLE>
  </soapenv:Body>
</soapenv:Envelope>' \
  "https://${SAP_HOST}:${SAP_PORT}/sap/bc/soap/rfc?sap-client=${SAP_CLIENT}"
```

### JavaScript (Node.js, `axios`) — Query material details via `BAPI_MATERIAL_GET_DETAIL`

```javascript
const axios = require('axios');
const { XMLParser } = require('fast-xml-parser');

const SAP_HOST     = 's4hana.example.com';
const SAP_PORT     = '44300';
const SAP_CLIENT   = '100';
const SAP_USER     = 'RFC_USER';
const SAP_PASSWORD = 'Passw0rd!';

const SOAP_URL = `https://${SAP_HOST}:${SAP_PORT}/sap/bc/soap/rfc?sap-client=${SAP_CLIENT}`;
const AUTH     = Buffer.from(`${SAP_USER}:${SAP_PASSWORD}`).toString('base64');

async function getMaterialDetail(materialNumber) {
  const soapBody = `<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:urn="urn:sap-com:document:sap:rfc:functions">
  <soapenv:Body>
    <urn:BAPI_MATERIAL_GET_DETAIL>
      <MATERIAL>${materialNumber}</MATERIAL>
    </urn:BAPI_MATERIAL_GET_DETAIL>
  </soapenv:Body>
</soapenv:Envelope>`;

  const response = await axios.post(SOAP_URL, soapBody, {
    headers: {
      'Content-Type': 'text/xml; charset=utf-8',
      'SOAPAction':   'BAPI_MATERIAL_GET_DETAIL',
      'Authorization': `Basic ${AUTH}`,
    },
    timeout: 30000,
  });

  const parser = new XMLParser({ ignoreAttributes: false });
  const parsed = parser.parse(response.data);

  // Navigate to the response element
  const envelope = parsed['soapenv:Envelope'] || parsed['Envelope'];
  const body     = envelope['soapenv:Body']   || envelope['Body'];
  const rfcResp  = body['BAPI_MATERIAL_GET_DETAIL.Response'];
  const genData  = rfcResp['MATERIAL_GENERAL_DATA'];

  return {
    materialDesc: genData['MATL_DESC'],
    baseUnit:     genData['BASE_UOM'],
    materialType: genData['MATL_TYPE'],
    division:     genData['DIVISION'],
  };
}

getMaterialDetail('RAW-001')
  .then(console.log)
  .catch(console.error);
```

---

## 8. Response Parsing

### SOAP response structure

SAP wraps the RFC output in a standard SOAP envelope. The response element name follows the pattern `{FM_NAME}.Response`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <urn:BAPI_PO_GETDETAIL1.Response
        xmlns:urn="urn:sap-com:document:sap:rfc:functions">
      <!-- Export scalar parameters -->
      <POHEADER>
        <DOC_TYPE>NB</DOC_TYPE>
        <VENDOR>1000001</VENDOR>
        <PURCH_ORG>1000</PURCH_ORG>
        <CURRENCY>USD</CURRENCY>
      </POHEADER>
      <!-- Export table parameters -->
      <POITEM>
        <item>
          <PO_ITEM>00010</PO_ITEM>
          <MATERIAL>RAW-001</MATERIAL>
          <QUANTITY>10.000</QUANTITY>
        </item>
        <item>
          <PO_ITEM>00020</PO_ITEM>
          <MATERIAL>RAW-002</MATERIAL>
          <QUANTITY>5.000</QUANTITY>
        </item>
      </POITEM>
      <!-- Standard BAPI return table -->
      <RETURN>
        <item>
          <TYPE>S</TYPE>
          <ID>M8</ID>
          <NUMBER>162</NUMBER>
          <MESSAGE>Purchase order 4500000123 read successfully</MESSAGE>
        </item>
      </RETURN>
    </urn:BAPI_PO_GETDETAIL1.Response>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>
```

### Namespace handling

The response uses `urn:sap-com:document:sap:rfc:functions` on the response element. When using namespace-aware parsers (Python `xml.etree.ElementTree`, Java `javax.xml.parsers`), prefix all element lookups:

```python
ns = {"urn": "urn:sap-com:document:sap:rfc:functions"}
response_node = root.find(".//urn:BAPI_PO_GETDETAIL1.Response", ns)
```

### Extracting scalar return fields

```python
# Scalar field from a structure
vendor = response_node.find("POHEADER/VENDOR").text

# Scalar field directly on the response element
po_number = response_node.findtext("EXPPURCHASEORDER", default="")
```

### Iterating table return rows

```python
for item in response_node.findall("POITEM/item"):
    po_item   = item.findtext("PO_ITEM",   default="")
    material  = item.findtext("MATERIAL",  default="")
    quantity  = item.findtext("QUANTITY",  default="")
    print(po_item, material, quantity)
```

### Error handling — two layers

SOAP/RFC errors fall into two distinct categories. **Always check both.**

| Layer | Indicator | Meaning |
|---|---|---|
| **SOAP Fault** | HTTP 500 + `<faultcode>` in body | Protocol-level error: malformed XML, unknown FM name, ICF node inactive, auth failure |
| **Business error** | HTTP 200 + `RETURN` table with `TYPE=E` or `TYPE=A` | The RFC executed but the business operation failed |

```python
# Layer 1: HTTP / SOAP Fault
response.raise_for_status()   # raises on 4xx / 5xx

# Check for SOAP Fault in body (SAP may return 500 with a Fault element)
if "<faultcode>" in response.text:
    raise RuntimeError(f"SOAP Fault: {response.text}")

# Layer 2: BAPI RETURN table
for item in response_node.findall("RETURN/item"):
    msg_type = item.findtext("TYPE", default="")
    message  = item.findtext("MESSAGE", default="")
    if msg_type in ("E", "A"):
        raise RuntimeError(f"BAPI error [{msg_type}]: {message}")
```

---

## 9. Known Limitations

- **No IDoc support** — IDoc send/receive requires JCo or SAP PI/PO. The SOAP/RFC endpoint handles function modules only.
- **No tRFC or qRFC** — Transactional and queued RFC patterns are not exposed via this endpoint. All calls are synchronous sRFC semantics.
- **No connection pooling** — Each call opens and closes an HTTP connection. Under high concurrency (hundreds of calls per minute), latency increases and SAP work processes can become a bottleneck. Use JCo for sustained high-throughput workloads.
- **Outbound only** — SAP cannot initiate a call to the HTTP client. For SAP-initiated callbacks, use JCo in server mode or IDoc/ALE.
- **Single application server** — There is no equivalent of JCo's message-server-based load balancing. Target a specific application server host. If that host is unavailable, the call fails.
- **No standard monitoring transaction** — Calls do not appear in SM58 (tRFC monitor) or SM59 (destination monitor). Troubleshoot using ICM traces (transaction `SMICM`) and HTTP access logs.
- **Requires NW 7.0+** — ECC 6.0 and all S/4HANA On-Premise releases qualify. Older NW 6.x systems may not have the `/sap/bc/soap/rfc` endpoint available.
