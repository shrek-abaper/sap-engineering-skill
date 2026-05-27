# SAP Integration Wiki

> A skill that turns any AI assistant into a SAP integration specialist.
> Built for developers who need to connect external systems to SAP — without reading 10,000 pages of SAP documentation.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![SAP Versions](https://img.shields.io/badge/SAP-ECC%20%7C%20S%2F4HANA%20%7C%20Cloud-blue.svg)](references/troubleshoot/version-diff.md)

[English](README.md) | [中文](README.zh-CN.md)

---

## What Is This?

`sap-integration-wiki` is a **composable skill** — a structured knowledge base following the standard skill specification (`SKILL.md`). Once installed into your AI agent framework, any AI assistant can load the right reference documents and provide precise, actionable answers backed by real SAP API documentation.

**Without this skill**, an AI assistant gives generic, often-wrong answers about SAP:
> "You can use the SAP RFC API to create a purchase order."

**With this skill**, the AI gives production-ready guidance:
> "For S/4HANA On-Premise, use OData V2 `API_PURCHASEORDER_PROCESS_SRV` with a deep insert POST to create the PO header + items in one request. Here's the exact payload structure with account assignment, and here's the CSRF token flow you need to implement first..."

---

## Covered Scenarios

### Business Scenarios

| Domain | Scenarios |
|---|---|
| **MM — Purchasing** | Create PO, read PO status, update quantity/price, supplier EDI acknowledgement |
| **MM — Inventory** | Query stock by plant/storage location, post goods issue/receipt, create reservation |
| **SD — Sales** | Create sales order, track delivery status, read billing documents |
| **FI — Finance** | Post GL document, read FI documents, account determination |
| **FI — AR / AP** | Query open items, payment terms, supplier invoice create, AP/AR posting, down payments, document parking |
| **FI — Asset Accounting** | Read asset register, post acquisition / retirement / write-off / transfer, OData V4 for S/4HANA Cloud |
| **FI — FSSC** | Financial Shared Service Center: Kingdee↔SAP patterns (Direct API / BTP-mediated / CFIN), API catalog, master data mapping |
| **Master Data** | Material master read/create, Business Partner (Customer/Vendor), Cost Center |
| **PP — Production** | Production orders, BOM read, goods movements (261/101), order confirmation, MRP |

### Integration Technologies

| Technology | Coverage |
|---|---|
| **OData V2 / V4** | CSRF flow, `$expand`/`$filter`/`$batch`, deep insert, error parsing |
| **RFC / SAP JCo** | Connection pool, BAPI call pattern, RETURN table parsing, load balancing |
| **SOAP over HTTP RFC** | Call any RFC-FM via HTTPS without JCo — Python/Node/curl examples, CSRF flow, response parsing |
| **IDoc / PI-PO** | Control record, key segments, status lifecycle, monitoring transactions |
| **BAPI & RAP** | When to use which, key BAPIs by domain, RAP OData V4 services |
| **Authentication** | Basic Auth, OAuth2 (on-premise SOAUTH2 + Cloud), SSL/TLS, ICF activation |
| **BTP Integration Suite** | iFlow, Cloud Connector, API Management, Event Mesh, Communication Arrangements |
| **Best Practices** | Idempotency, retry logic, connection management, security hardening, monitoring |

---

## Installation

This skill follows the standard skill specification with `SKILL.md` metadata. Installation steps vary by your AI agent framework:

### Example: Claude Code

```bash
# Symlink into Claude Code skills directory
ln -s /path/to/sap-integration-wiki ~/.agents/skills/sap-integration-wiki
```

### Example: OpenAI Custom Instructions / System Prompt

Add this to your agent context:

```
When answering SAP integration questions, load the knowledge base from:
- /path/to/sap-integration-wiki/SKILL.md (routing logic)
- /path/to/sap-integration-wiki/references/scenarios/*.md (business scenarios)
- /path/to/sap-integration-wiki/references/tech/*.md (technical guides)
- /path/to/sap-integration-wiki/references/troubleshoot/*.md (error solutions)
```

### Example: LangChain / RAG Integration

```python
from langchain.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader

loader = DirectoryLoader(
    '/path/to/sap-integration-wiki',
    glob='**/*.md',
    loader_cls=UnstructuredMarkdownLoader,
    loader_kwargs={'mode': 'elements'}
)

documents = loader.load()
# Then build your vector store or retrieval chain
```

### Verification

The skill should load automatically via `SKILL.md` metadata. Update your agent's skill scan paths to include this directory.

---

## Quick Start

Once installed, ask your AI assistant about SAP integration:

**Example prompts (language-agnostic):**

```
How do I create a purchase order in SAP S/4HANA from Python?
```

```
I'm getting HTTP 403 CSRF token validation failed from SAP OData. What's wrong?
```

```
What's the difference between using BAPI_PO_CREATE1 and the OData API for ECC?
```

```
How do I read stock levels from SAP in real time?
```

The skill automatically:
1. Identifies your SAP version and integration scenario
2. Loads the relevant reference documents from `references/`
3. Provides working code examples in your language (Java, Python, curl, etc.)
4. Flags common pitfalls specific to your situation

**Unusual requirement**: "The skill loads automatically for all AI assistants — just asking works."

---

## Directory Structure

```
sap-integration-wiki/
├── SKILL.md                          ← AI routing logic and decision tree
├── README.md                         ← This file (English)
├── README.zh-CN.md                   ← Chinese version
├── CONTRIBUTING.md                   ← Contribution guide
│
├── references/
│   ├── scenarios/                    ← What to do (business-oriented)
│   │   ├── mm-po.md                  Purchase Order integration
│   │   ├── mm-stock.md               Inventory/Stock integration
│   │   ├── sd-order.md               Sales Order integration
│   │   ├── fi-doc.md                 Financial Document integration (GL posting)
│   │   ├── fi-ar-ap.md               AR/AP open items, invoices, payments
│   │   ├── fi-asset.md               Fixed Asset accounting (acquisition, retirement, transfer)
│   │   ├── fi-fssc.md                Financial Shared Service Center (Kingdee↔SAP, CFIN)
│   │   ├── master-data.md            Material Master, Business Partner
│   │   └── pp-production.md          Production Orders, BOM, Goods Movements, MRP
│   │
│   ├── tech/                         ← How to do it (technology-oriented)
│   │   ├── odata.md                  OData V2/V4 protocol guide
│   │   ├── rfc-jco.md                RFC/JCo connection and BAPI guide
│   │   ├── soap-rfc-http.md          SOAP over HTTP RFC — no JCo required
│   │   ├── idoc-pi.md                IDoc and SAP PI/PO guide
│   │   ├── bapi-rap.md               BAPI vs RAP decision guide
│   │   ├── auth.md                   Authentication setup guide
│   │   ├── btp-cloud-integration.md  BTP Integration Suite guide
│   │   └── best-practices.md         Security, retry, monitoring, testing
│   │
│   └── troubleshoot/                 ← Fix it
│       ├── odata-errors.md           HTTP 4xx/5xx error solutions
│       ├── auth-errors.md            Auth and CSRF error solutions
│       ├── idoc-errors.md            IDoc stuck / status 51 solutions
│       └── version-diff.md           ECC vs S/4HANA behavior differences
│
├── scripts/                          ← Runnable tools
│   ├── gen-odata-postman.js          Generate Postman collection for any OData service
│   ├── gen-jco-config.py             Generate JCo .jcoDestination config file
│   └── gen-idoc-template.py          Generate IDoc XML skeleton
│
└── assets/                           ← Example payloads and config templates
    ├── payloads/
    │   ├── po-create.json            OData V2 PO deep-insert POST body
    │   ├── po-update.json            OData V2 PO item PATCH body
    │   └── idoc-orders05.xml         ORDERS05 IDoc XML example
    └── configs/
        ├── oauth-template.json       OAuth2 config for S/4HANA On-Premise
        └── jco-props.template        JCo connection properties reference
```

---

## Using the Scripts

### Generate Postman Collection

Creates a ready-to-import Postman collection for any SAP OData V2 service:

```bash
cd scripts
node gen-odata-postman.js \
  --service API_PURCHASEORDER_PROCESS_SRV \
  --host s4hana.example.com \
  --client 100 \
  --output po-collection.json
```

### Generate JCo Config

Creates a `.jcoDestination` properties file with all options documented:

```bash
python3 gen-jco-config.py \
  --name SAP_PRD \
  --host s4hana.example.com \
  --sysnr 00 \
  --client 100 \
  --user RFC_USER \
  --output SAP_PRD.jcoDestination
```

### Generate IDoc XML Skeleton

Creates a skeleton IDoc XML for a given message type:

```bash
python3 gen-idoc-template.py \
  --msgtype ORDERS \
  --idoctype ORDERS05 \
  --sender-partner SAP_PROD \
  --receiver-partner EXT_SUPPLIER_001 \
  --output orders05-skeleton.xml
```

---

## SAP Versions Supported

| SAP Version | OData | RFC/BAPI | IDoc | BTP |
|---|---|---|---|---|
| ECC 6.0 | Custom only | Full | Full | Via Cloud Connector |
| S/4HANA On-Prem 1909–2022 | OData V2 (standard APIs) | Full | Full | Via Cloud Connector |
| S/4HANA On-Prem 2023+ | OData V2 + V4 (partial) | Full | Full | Via Cloud Connector |
| S/4HANA Cloud Public Edition | OData V4 primary | Not available externally | Limited | Native |
| S/4HANA Cloud Private Edition | OData V2/V4 | Via RFC but restricted | Via BTP | Native |

---

## Contributing

We welcome contributions from SAP integration professionals worldwide. There are many ways to help:

- **Add a new scenario** — missing HR, WM/EWM, PM, QM, or other modules
- **Improve existing content** — fix errors, add examples, clarify explanations
- **Add code snippets** — examples in .NET, Go, JavaScript, Ruby, etc.
- **Report issues** — wrong API names, outdated information, broken examples
- **Translate content** — we currently have English and Chinese; other languages welcome

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgements

Content is based on publicly available SAP documentation from:
- [SAP Business Accelerator Hub](https://api.sap.com)
- [SAP Help Portal](https://help.sap.com)
- [SAP Community](https://community.sap.com)
- Real-world SAP integration project experience

---

## Disclaimer

This is a community project and is not affiliated with, endorsed by, or officially supported by SAP SE. SAP, S/4HANA, ECC, BTP, and related product names are trademarks of SAP SE. Always verify API behavior against the official SAP documentation for your specific release and system configuration.
