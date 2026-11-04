# Dynamic REST2RFC Gateway Reference

## Table of Contents

1. [Overview](#1-overview)
2. [When to Use It](#2-when-to-use-it)
3. [Prerequisites and SAP-Side Setup](#3-prerequisites-and-sap-side-setup)
4. [HTTP and JSON Contract](#4-http-and-json-contract)
5. [Transaction Boundaries](#5-transaction-boundaries)
6. [Security and Operations](#6-security-and-operations)
7. [Known Limitations](#7-known-limitations)
8. [Metadata Helper](#8-metadata-helper)
9. [Public Project References](#9-public-project-references)

---

## 1. Overview

[SAP REST2RFC Gateway](https://github.com/shrek-abaper/sap-rest2rfc-gateway) is a community-developed, pure-ABAP gateway that exposes registered RFC-enabled function modules and BAPIs as synchronous HTTP/JSON endpoints. Its dynamic route reads the target function's real interface metadata and binds JSON fields to RFC parameters at runtime.

```text
External system (any HTTP client)
        │ HTTPS + JSON
        ▼
SICF /sap/bc/rest2rfc
        │
        ▼
Registered and active function in ZTIF_GENERAL_CON
        │
        ▼
Dynamic metadata binding → RFC-enabled function module or BAPI
```

The gateway runs inside SAP. External consumers need no JCo, SAP NW RFC SDK, or other SAP client library, and no separate Java integration middleware is required. After the one-time gateway deployment, exposing another existing function normally requires configuration rather than a new per-interface ABAP mapping or a change to the target function.

This is **RPC-style JSON over HTTP**, not OData or resource-oriented REST. It is also not an SAP standard API. The initial gateway classes, DDIC objects, configuration, and SICF setup are still SAP-side work.

This reference covers only the **dynamic reflection-based REST2RFC route**.

## 2. When to Use It

| Situation | Recommendation |
|---|---|
| ECC or S/4HANA On-Premise has an existing RFC/BAPI but no suitable standard OData API | Good candidate |
| Python, Node.js, Go, .NET, or low-code consumers need JSON without an SAP SDK | Good candidate |
| Many existing functions need one consistent HTTP entry point without per-interface mapping code | Good candidate |
| A released standard OData V2/V4 API covers the requirement | Prefer the standard OData API |
| No custom ABAP components may be installed | Use SOAP over HTTP RFC or an external JCo-based option instead |
| S/4HANA Cloud Public Edition | Do not use this gateway; use released APIs and Communication Arrangements |
| IDoc, tRFC/qRFC, or SAP-initiated callbacks are required | Use the appropriate IDoc/ALE or JCo pattern instead |

### Compare the RFC/BAPI transport options

| Dimension | Dynamic REST2RFC | SOAP over HTTP RFC | Java JCo |
|---|---|---|---|
| External payload | JSON | SOAP/XML | JCo API, not HTTP by itself |
| External SAP library | None | None | JCo JAR + native library |
| Gateway location | Inside SAP | SAP standard ICF endpoint | External Java application |
| Additional SAP components | Gateway classes, tables, and SICF node | No gateway installation; activate standard ICF service | None for outbound calls |
| Per-interface exposure | Register and activate the function | Address the RFC-FM through SOAP | Implement Java calls/mappings |
| Typical fit | Reuse existing RFC/BAPIs through JSON with minimal per-interface ABAP work | No custom gateway allowed; XML is acceptable | Java estates, connection pooling, or RFC-specific capabilities |

## 3. Prerequisites and SAP-Side Setup

1. **Check platform prerequisites.** The project recommends `SAP_BASIS >= 7.40`. Dynamic JSON parsing depends on `/UI2/CL_JSON`, supplied with the `SAP_UI` add-on rather than `SAP_BASIS`; verify that it exists in the target system.
2. **Deploy the dynamic gateway components.** This includes `ZCL_REST2RFC_HANDLE`, `ZCL_REST2RFC_BIND`, and the required configuration/log objects. Follow the public project documentation and validate the objects in a development system first.
3. **Configure the ICF entry point.** Attach `ZCL_REST2RFC_HANDLE` to the `/sap/bc/rest2rfc` SICF node and enable HTTPS according to the system's network and security standards.
4. **Register each allowed function.** Add a row to `ZTIF_GENERAL_CON`:

   | Field | Purpose | Read-only PO example |
   |---|---|---|
   | `IFCODE` | Unique interface configuration key | `PO_GETDETAIL` |
   | `TASKFM` | Exact target function module name | `BAPI_PO_GETDETAIL1` |
   | `ACTFLG` | Must be `X` to allow calls | `X` |
   | `LOGFLG` | Enables raw request/response logging | Set according to log policy |
   | `COMMITMODE` | Declares transaction ownership | `N` |

   The URL selects `TASKFM`, but the function is callable only when its configuration row exists and is active. Unregistered and inactive functions return HTTP 404.
5. **Validate authorization and transaction semantics.** The configuration row is an allowlist, not a business authorization check. Confirm the target function's authorization behavior and choose `COMMITMODE` deliberately before exposing it.

## 4. HTTP and JSON Contract

### Endpoint

```text
POST /sap/bc/rest2rfc?RFC={TASKFM}
Content-Type: application/json
```

Only POST is supported; other methods return HTTP 405. Use uppercase RFC parameter and field names in requests.

The dynamic binder uses `RFC_GET_FUNCTION_INTERFACE_P` to read the function interface. JSON keys at the top level map to RFC parameter names; structures map to nested JSON objects and table rows map to arrays of objects. The target function does not need a fixed `REQUEST`/`RESPONSE` signature.

A successful response is one JSON object assembled from the function's `EXPORTING`, `CHANGING`, and `TABLES` output parameters. Payload validation errors use structured error JSON with codes such as `UNKNOWN_PARAM`, `MISSING_PARAM`, and `TYPE_MISMATCH`.

### Read-only example: `BAPI_PO_GETDETAIL1`

Use `COMMITMODE = N` for this read-only call. The example requests the purchase-order header and items:

```bash
export REST2RFC_BASE_URL="https://sap-dev.example.com:44300"
export REST2RFC_CLIENT="100"
export REST2RFC_USER="RFCUSER"
export REST2RFC_PASSWORD="your-password"

curl --request POST \
  --user "${REST2RFC_USER}:${REST2RFC_PASSWORD}" \
  --header "Content-Type: application/json" \
  --data '{"PURCHASEORDER":"4500000123","ITEMS":"X"}' \
  "${REST2RFC_BASE_URL}/sap/bc/rest2rfc?RFC=BAPI_PO_GETDETAIL1&sap-client=${REST2RFC_CLIENT}"
```

Python equivalent:

```python
import os

import requests

response = requests.post(
    f"{os.environ['REST2RFC_BASE_URL'].rstrip('/')}/sap/bc/rest2rfc",
    params={
        "RFC": "BAPI_PO_GETDETAIL1",
        "sap-client": os.environ["REST2RFC_CLIENT"],
    },
    auth=(os.environ["REST2RFC_USER"], os.environ["REST2RFC_PASSWORD"]),
    json={"PURCHASEORDER": "4500000123", "ITEMS": "X"},
    timeout=30,
)
response.raise_for_status()
result = response.json()
```

These examples illustrate the documented contract; adapt host, authentication, fields, and TLS settings to the target system. Do not treat an HTTP 2xx response alone as proof of business success when the function returns a `RETURN` parameter.

## 5. Transaction Boundaries

`ZTIF_GENERAL_CON-COMMITMODE` determines who owns the SAP LUW:

| Value | Owner and behavior | Typical use |
|---|---|---|
| blank / `N` | The gateway does not interpret `RETURN`, commit, or roll back | Read-only functions |
| `G` | The gateway checks `RETURN`, then calls `BAPI_TRANSACTION_ROLLBACK` on business errors or `BAPI_TRANSACTION_COMMIT` with `WAIT = 'X'` on success | Standard write BAPIs with conventional `RETURN` output |
| `F` | The target function owns its commit; the gateway does not intervene | Functions with explicitly implemented transaction handling |

For write BAPIs, verify that `G` matches the actual function contract before activation. The caller must still inspect returned business messages. In `N` mode, the gateway does not turn a `RETURN` error into a rollback or an HTTP error. In `F` mode, do not add a second commit in the caller.

Do not infer idempotency from transaction management. A timeout after a write can leave the client uncertain about the outcome; reconcile using an external business key or document number before retrying. See `best-practices.md`.

## 6. Security and Operations

- **Keep the allowlist narrow.** Register only functions intended for HTTP exposure and activate them only after review.
- **Enforce business authorization.** The gateway delegates business-level authorization to the exposed function. Add an authorization-enforcing wrapper when the original function does not enforce the required checks; such cases require additional SAP-side development.
- **Use HTTPS and a least-privilege technical user.** Restrict network access to intended consumers and never expose the endpoint directly to the public internet without an appropriate enterprise security layer.
- **Protect raw payload logs.** `LOGFLG` writes inbound/outbound payloads and status information to `ZTIF_GENERAL_LOG`. Restrict access and define retention, redaction, and handling for financial, personal, credential, or other sensitive data.
- **Return safe errors.** Do not expose credentials, connection strings, internal hostnames, or sensitive payloads in response messages.
- **Test writes in a non-production system.** Verify `RETURN` handling, rollback, commit visibility, and retry behavior before release.

## 7. Known Limitations

The dynamic `/UI2/CL_JSON=>GENERATE` binding has documented trade-offs:

- Empty objects `{}` and empty arrays `[]` cannot be distinguished; both are treated as empty values.
- JSON scalar types degrade to strings, losing the original number/boolean/null distinction. Use strings for SAP values such as dates, NUMC fields, and identifiers with leading zeros.
- JSON keys are converted to uppercase, so error paths do not preserve the original key casing.
- Duplicate JSON keys are silently merged; clients must not send duplicates.
- Binary, `RAW`, and `XSTRING` fields have no implicit dynamic conversion and return `NOT_SUPPORTED`.

Also verify the `/UI2/CL_JSON` dependency on older ECC systems. S/4HANA Cloud Private Edition requires confirmation that the necessary custom ABAP and ICF deployment model is permitted; Cloud Public Edition is out of scope.

## 8. Metadata Helper

The project includes `rest2rfc_meta.py`, which uses the dynamic gateway to inspect an RFC/BAPI parameter tree and generate structure notes, request/response JSON skeletons, and interface documentation. It requires pre-registered metadata functions such as `SYS_META`; follow the public dynamic-route README for setup and usage.

Use generated skeletons as development aids, then validate mandatory fields, business authorization, and transaction behavior against the target SAP system.

## 9. Public Project References

- Project: https://github.com/shrek-abaper/sap-rest2rfc-gateway
- Dynamic route contract and limitations: https://github.com/shrek-abaper/sap-rest2rfc-gateway/blob/main/src/rest_rfc_dynamic/README.md

The public project documentation is the source of truth for installation objects, configuration fields, helper prerequisites, and version-specific behavior.
