# SAP Version Differences Reference

## Table of Contents

1. [Version Capability Matrix](#1-version-capability-matrix)
2. [API_PURCHASEORDER_PROCESS_SRV Deprecation Timeline](#2-api_purchaseorder_process_srv-deprecation-timeline)
3. [Migration Path: OData V2 → V4 for PO API](#3-migration-path-odata-v2--v4-for-po-api)
4. [S/4HANA Cloud Public vs On-Premise Differences](#4-s4hana-cloud-public-vs-on-premise-differences)
5. [Known V4 On-Premise Gaps (as of 2024)](#5-known-v4-on-premise-gaps-as-of-2024)
6. [Recommended Approach by Version and Scenario](#6-recommended-approach-by-version-and-scenario)

---

## 1. Version Capability Matrix

| Capability | ECC 6.0 | S/4HANA OP 1909–2022 | S/4HANA OP 2023+ | S/4HANA Cloud Public | S/4HANA Cloud Private |
|---|---|---|---|---|---|
| Standard OData V2 APIs | None | Full set | Full set (some deprecated per SAP Note 3502308) | Limited (V4 primary) | Similar to On-Prem |
| Standard OData V4 / RAP APIs | None | Partial (select services) | Expanding (see Note 3502308) | Primary API method | Expanding |
| RFC / JCo external access | Yes (primary) | Yes | Yes | **Restricted** — SAP-managed proxies only | Yes |
| IDoc (inbound/outbound) | Yes | Yes | Yes | Limited (scenario-specific) | Yes |
| BAPI via JCo | Yes (primary) | Yes | Yes (legacy supported) | **No** (not available externally) | Yes |
| Basic Auth (user/pass) | Yes | Yes | Yes | **No** (OAuth2 only) | Yes (with restrictions) |
| OAuth2 (On-Premise) | No | Yes (1709+) | Yes | N/A (managed by SAP) | Yes |
| SAP PI/PO integration | Yes | Yes | Yes | SAP Integration Suite (CPI) | Yes |
| SAP Business Connector | Legacy only | No | No | No | No |
| Custom ABAP development | Yes | Yes | Yes | In-App extensibility only | Yes |
| Direct database access | Possible (not recommended) | Possible (not recommended) | Not supported | Not available | Not recommended |
| ABAP RESTful App Programming (RAP) | No | From 1809 | Yes (primary for custom) | Yes | Yes |

---

## 2. API_PURCHASEORDER_PROCESS_SRV Deprecation Timeline

**SAP Note**: 3502308 — "Deprecation of OData V2 APIs for Purchase Order"

### What is being deprecated

`API_PURCHASEORDER_PROCESS_SRV` (OData V2) is being replaced by `API_PURCHASEORDER` (OData V4).

### Timeline

| Release | Status |
|---|---|
| S/4HANA OP 1909–2208 (up to 2022) | `API_PURCHASEORDER_PROCESS_SRV` V2 is the standard; V4 not yet available |
| S/4HANA OP 2308 (2023) | V4 `API_PURCHASEORDER` partially available; V2 still fully supported |
| S/4HANA OP 2408+ (2024+) | V2 marked as deprecated; V4 recommended for new implementations |
| S/4HANA Cloud Public 2402+ | V4 `API_PURCHASEORDER` is the primary; V2 may be removed in future releases |
| End of Life for V2 | Not yet announced as of 2024 — SAP has extended support; monitor SAP Note 3502308 |

### What this means for you

- **Existing integrations on V2**: Continue to work; SAP will not remove V2 abruptly. However, new features (e.g., new PO types, extended fields) are added to V4 only.
- **New integrations**: Use V4 if your SAP release supports it. If on pre-2308, use V2.
- **Check your release**: Transaction `SPAM` or `System → Status` → Application Server release field.

---

## 3. Migration Path: OData V2 → V4 for PO API

### Step 1: Verify V4 availability in your release

```bash
# Check if V4 PO API is available (will return 200 if activated)
curl -u user:pass \
  "https://s4hana.example.com:44300/sap/opu/odata4/sap/api_purchaseorder/srvd_a2x/sap/purchaseorder/0001/\$metadata"

# If 404: V4 not yet available in your S/4HANA release
# If 200: V4 available — check metadata for entity set names
```

### Step 2: Activate V4 service

Transaction `/IWFND/MAINT_SERVICE` → search for `API_PURCHASEORDER` → activate (same as V2 activation).

### Step 3: Key differences to adjust in your code

| Aspect | V2 | V4 | Change required |
|---|---|---|---|
| Date format | `/Date(1716768000000)/` | `2026-05-01T00:00:00Z` | Update date serialization |
| Entity set URL | `.../A_PurchaseOrder` | `.../PurchaseOrder` | Update base URL paths |
| Navigation property | `to_PurchaseOrderItem` | `_PurchaseOrderItem` (may vary) | Check V4 metadata |
| Response wrapper | `{"d": {...}}` | `{"@odata.context": ..., "value": [...]}` | Update response parsing |
| Count query | `$inlinecount=allpages` | `$count=true` | Update filter parameters |
| CSRF token | Required | Required | Same flow |
| Auth | Same | Same | No change |

### Step 4: Test migration

Run both V2 and V4 calls against your test system:

```bash
# V2 read PO header
curl -u user:pass \
  "https://host:44300/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder('4500012345')"

# V4 read PO header
curl -u user:pass \
  "https://host:44300/sap/opu/odata4/sap/api_purchaseorder/srvd_a2x/sap/purchaseorder/0001/PurchaseOrder('4500012345')"
```

Compare field names and response structures. Not all V2 fields have direct V4 equivalents — check V4 `$metadata` for exact field names.

---

## 4. S/4HANA Cloud Public vs On-Premise Differences

These differences most often surprise teams migrating from On-Premise:

| Area | S/4HANA On-Premise | S/4HANA Cloud Public |
|---|---|---|
| **Custom ABAP development** | Full ABAP stack — any development possible | In-App extensibility via Key User Extensions (KUT) and RAP only; no custom function modules |
| **Direct RFC/JCo from external** | Yes — open port 33XX | No — only through SAP BTP with SAP Event Mesh or API Management |
| **BAPI access from external** | Yes via JCo | No direct BAPI calls externally |
| **Database access (JDBC, direct)** | Possible (not recommended) | Not possible |
| **Custom OData services** | Can build with SEGW or RAP | In-App extensibility only; limited RAP |
| **Authentication** | Basic Auth, OAuth2, Kerberos/SPNEGO | OAuth2 only (no Basic Auth) |
| **System administration** | Customer-managed (SAP Basis team) | SAP-managed; limited admin access |
| **Upgrade schedule** | Customer-controlled | Quarterly (auto-upgrade) |
| **Transport management** | Customer transport landscape | Automated; no manual transports for standard customizing |
| **PI/PO middleware** | Customer-installed | SAP Integration Suite (Cloud Integration / CPI) |
| **Standard API coverage** | Full standard API set | Full standard API set (sometimes newer than On-Prem) |

### Implication: Cloud Public integration pattern

For S/4HANA Cloud Public Edition:
```
External System
    ↓ (OData V4 / OAuth2)
S/4HANA Cloud Public API
    OR
External System
    ↓
SAP BTP Integration Suite (SAP CPI)
    ↓ (API)
S/4HANA Cloud Public
```

Direct JCo/RFC connections from on-premise servers to SAP Cloud Public are **not supported**. All external access must go through the published OData APIs.

---

## 5. Known V4 On-Premise Gaps (as of 2024)

The following capabilities were either not yet available or had limitations in OData V4 On-Premise as of 2024. Check SAP Note 3502308 and the SAP API Business Hub for the latest status.

| Capability | V2 Status | V4 Status (2024) | Notes |
|---|---|---|---|
| Create PO with account assignment (cost center/order) | Available | Available (2308+) | Check `$metadata` for account assignment navigation |
| Service-Based PO (item category D) | Available | Partial | Some service entry sheet operations limited |
| Third-party PO (item category S) | Available | Partial | Check release notes for your version |
| PO with multiple account assignment | Available | Available (2308+) | Uses `DistributionFunction` field |
| PO outline agreements (contracts, scheduling agreements) | Separate API (`API_PURCHASECONTRACT_PROCESS_SRV`) | Separate V4 API (check api.sap.com) | Contract API has its own V4 successor |
| PO approval/release | Available via function import | Available as V4 Action (2308+) | Action name changed |
| Subcontracting PO (item category L) | Available | Limited | Subcontracting components not fully exposed |
| GR/GI posting via PO context | Via `API_MATERIAL_DOCUMENT_SRV` | Successor in V4 (check api.sap.com) | Goods movement has own API |

**Always verify** against your specific S/4HANA release by:
1. Checking `$metadata` for the V4 service on your system
2. Consulting SAP Note 3502308 for your release
3. Testing with a sample payload before full migration

---

## 6. Recommended Approach by Version and Scenario

### Decision guide

```
My SAP system is:

ECC 6.0 (any support pack)
  → Use: BAPI via JCo for all create/change operations
  → Use: RFC/JCo for read operations where no standard FM exists
  → Use: IDoc for async/EDI integration with external partners
  → Do NOT use OData (no standard SAP OData APIs in ECC)

S/4HANA On-Premise 1709–2208
  → Use: OData V2 for standard MM/SD/FI scenarios
  → Use: BAPI via JCo for FI posting and where no OData exists
  → Use: IDoc for async/EDI
  → V4 is not available in most of these releases

S/4HANA On-Premise 2308–2408
  → Use: OData V4 for NEW integrations where V4 API is available
  → Use: OData V2 for existing integrations (still supported)
  → Use: BAPI via JCo for FI posting
  → Check SAP Note 3502308 for which APIs have V4 successors

S/4HANA Cloud Public Edition
  → Use: OData V4 (primary and only external API method)
  → Use: OAuth2 (only supported auth; no Basic Auth)
  → Use: SAP Integration Suite (CPI) for middleware
  → Do NOT attempt JCo/RFC or Basic Auth

S/4HANA Cloud Private Edition
  → Similar to On-Premise but SAP-managed infrastructure
  → OData V2 + V4 both available
  → RFC/JCo possible (check with SAP account team for firewall rules)
  → Basic Auth possible but OAuth2 recommended
```

### Summary table

| Scenario | ECC | S/4 OP 1909–2022 | S/4 OP 2023+ | Cloud Public |
|---|---|---|---|---|
| Create PO | `BAPI_PO_CREATE1` | OData V2 | OData V4 | OData V4 |
| Read stock | `BAPI_MATERIAL_STOCK_REQ_LIST` | OData V2 `API_MATERIAL_STOCK_SRV` | OData V4 (if available) | OData V4 |
| Post FI document | `BAPI_ACC_DOCUMENT_POST` | Same (no OData for posting) | Same | OData V4 / BTP |
| Async supplier EDI | IDoc via PI/PO | Same | Same | IDoc via CPI |
| Authentication | Basic Auth | Basic Auth or OAuth2 | Basic Auth or OAuth2 | OAuth2 only |
