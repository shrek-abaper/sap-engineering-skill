# SAP BTP Integration Suite & Cloud Integration

## Table of Contents
- [Overview: From PI/PO to BTP Integration Suite](#overview)
- [Key Components](#key-components)
- [SAP Cloud Connector](#sap-cloud-connector)
- [Integration Flow (iFlow) Basics](#integration-flow-iflow-basics)
- [Common Adapters](#common-adapters)
- [API Management](#api-management)
- [SAP Event Mesh (Asynchronous Messaging)](#sap-event-mesh)
- [S/4HANA Cloud: Communication Arrangements](#s4hana-cloud-communication-arrangements)
- [Migration from SAP PI/PO](#migration-from-sap-pipo)
- [Version Considerations](#version-considerations)
- [Common Pitfalls](#common-pitfalls)

---

## Overview

SAP BTP (Business Technology Platform) Integration Suite is SAP's modern middleware platform, replacing SAP Process Integration (PI) and Process Orchestration (PO) for new projects. If your integration connects to **S/4HANA Cloud** or uses SAP-managed infrastructure, you will almost certainly interact with BTP Integration Suite.

**When to use BTP Integration Suite:**
- New integrations targeting S/4HANA Cloud (Public or Private Edition)
- Replacing an aging SAP PI/PO landscape
- Need for API rate limiting, throttling, or developer portal (API Management)
- Event-driven / asynchronous patterns between cloud systems
- Connecting on-premise systems to cloud systems via Cloud Connector

**When to stay on SAP PI/PO (for now):**
- Existing on-premise-only integrations with ECC or S/4HANA On-Premise with no cloud involvement
- Legacy IDoc-heavy landscapes with complex mapping that would require full rewrites
- Organization has not yet migrated to BTP

> SAP has announced end of mainstream maintenance for SAP PO 7.5 in **2027**, with extended maintenance until 2030. New capabilities are only being added to BTP Integration Suite.

---

## Key Components

| Component | Purpose | On-Premise Equivalent |
|---|---|---|
| **Cloud Integration** | Integration flows (iFlows), message mapping, adapter framework | SAP Process Integration / PI |
| **API Management** | API gateway, rate limiting, developer portal, analytics | SAP API Management (was separate product) |
| **Event Mesh** | Asynchronous publish/subscribe messaging | SAP Process Orchestration queues |
| **Open Connectors** | Pre-built connectors for 200+ SaaS apps (Salesforce, ServiceNow) | Adapter SDK |
| **Integration Advisor** | B2B message mapping templates (EDIFACT, X12, TRADACOMS) | B2B Add-on for PI |
| **Cloud Connector** | Secure tunnel from BTP to on-premise systems | Proxy / SAP Router |

---

## SAP Cloud Connector

Cloud Connector creates a **reverse HTTPS tunnel** from on-premise to SAP BTP, allowing cloud iFlows to call on-premise systems without opening firewall ports.

### Setup Overview

1. Download Cloud Connector from [SAP Tools](https://tools.hana.ondemand.com/#cloud) (Java-based, runs on any OS)
2. Start: `./go.sh` (Linux) or `go.bat` (Windows)
3. Admin UI: `https://localhost:8443` — default user `Administrator`/`manage`
4. Connect to BTP subaccount: enter BTP Region URL, Subaccount ID, User/Password
5. Add a **System Mapping**: set Virtual Host (used in iFlow) → Real Host (your SAP system)
6. Add **Resources**: expose only the needed URL paths (e.g., `/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV`)

```
Virtual Host: s4hana-prod        Real Host: s4hana.internal.corp:443
Virtual Port: 443                Real Port: 443
Protocol: HTTPS                  Check Internal Hostname: enabled
```

> Security best practice: restrict resources to only the exact paths your iFlow needs. Never map `/` — it exposes everything.

### Using Cloud Connector in an iFlow

In your iFlow HTTP receiver adapter, set:
- **Address**: `https://s4hana-prod:443/sap/opu/odata/...`
- **Proxy Type**: `On-Premise`
- **Location ID**: your Cloud Connector's location ID (default: empty)
- **Authentication**: `BasicAuthentication` or `OAuth2ClientCredentials`

---

## Integration Flow (iFlow) Basics

An iFlow is a BPMN-2.0-like diagram that defines a message processing pipeline:

```
[Sender Adapter] → [Message Processing Steps] → [Receiver Adapter]
```

**Core processing steps:**

| Step Type | Description |
|---|---|
| Message Mapping | Transform source format (JSON/XML/IDoc) to target format |
| XSLT Mapping | XSLT 1.0/2.0/3.0 stylesheet transformation |
| Content Modifier | Add/change/delete message headers and body |
| Filter | Evaluate XPath/JSONPath condition to decide routing |
| Router | Route to different branches based on condition |
| Groovy Script | Custom Java/Groovy code for complex logic |
| Call (Subprocess) | Invoke a reusable local subprocess iFlow |
| Request-Reply | Synchronous HTTP call out to an external system |

### Minimal iFlow for OData inbound (receiving from external, posting to S/4HANA)

```
[HTTPS Sender] → [Content Modifier: set headers] → [Request-Reply: POST to S/4HANA OData] → [Response Transform] → [HTTPS Reply]
```

**HTTPS Sender adapter config** (your iFlow exposes an endpoint):
- **Address**: `/api/v1/purchase-orders` (relative path within your tenant)
- **CSRF Protected**: `false` for inbound (BTP handles auth separately)
- **Authorization**: `User Role` → map to BTP role `ESBMessaging.send`

**Request-Reply to S/4HANA via Cloud Connector:**
- **Address**: `https://s4hana-prod:443/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder`
- **Method**: `POST`
- **Proxy Type**: `On-Premise`
- **Authentication**: `BasicAuthentication`

---

## Common Adapters

### IDoc Adapter (S/4HANA On-Premise / Cloud)

Sends/receives IDocs between BTP and SAP systems. The IDoc adapter handles EDI_DC40 control record construction automatically.

**Sender (SAP → BTP)**:
- Configure SAP RFC destination pointing to BTP Integration Suite endpoint
- In S/4HANA: create partner profile (WE20) with port pointing to RFC destination

**Receiver (BTP → SAP)**:
- In iFlow receiver: select IDoc adapter, enter `SAP System ID` and `Client`
- Set `IDoc Type` and `Message Type`
- BTP posts to `/sap/bc/srt/idoc` (ICF node must be active in SAP)

### OData Adapter

Provides built-in support for OData V2/V4 operations including CSRF token management.

**Receiver adapter config:**
- **Address**: service root URL
- **Resource Path**: entity set path (e.g., `/A_PurchaseOrder`)
- **Operation**: `GET_ENTITY_SET`, `CREATE`, `UPDATE`, `DELETE`, `MERGE`
- **CSRF Token**: enable checkbox — adapter fetches and caches token automatically
- **x-sap-client**: add as header

### RFC Adapter (BTP to On-Premise via JCo)

Calls SAP BAPIs/Function Modules from BTP iFlows through Cloud Connector.

**Configuration:**
- **Connection**: select Cloud Connector system mapping
- **Function Module Name**: e.g., `BAPI_PO_CREATE1`
- **Parameters**: map iFlow message fields to BAPI import/table parameters using graphical mapper

---

## API Management

BTP API Management sits in front of your backend APIs (SAP or non-SAP) and adds:

- **Rate limiting**: `X requests per minute per consumer`
- **OAuth2/API Key authentication**: consumers authenticate to API Management, which proxies to backend
- **Analytics**: latency, error rates, call volumes per API/consumer
- **Developer Portal**: self-service API catalog for internal/external developers
- **Policies**: JSON-to-XML conversion, request validation, response caching

### Publishing a SAP OData API via API Management

1. **Discover API**: import from API Business Hub or manually enter metadata URL
2. **Create API Proxy**: set target to your Cloud Connector virtual host
3. **Assign Policy**: add `VerifyAPIKey` or `OAuthV2` policy for consumer auth
4. **Create Product**: bundle APIs into a product, set quota
5. **Publish to Developer Portal**: developers can self-subscribe and get API key

```
Consumer → API Management (OAuth2 + rate limit + analytics) → Cloud Connector → S/4HANA OData
```

---

## SAP Event Mesh

SAP Event Mesh provides a cloud-based message broker (similar to Apache Kafka or RabbitMQ) for asynchronous event-driven integration.

### Key Concepts

| Concept | Description |
|---|---|
| **Namespace** | Logical grouping, e.g., `default/sap.s4.beh.salesorder.v1/` |
| **Topic** | Event channel with specific type, e.g., `SalesOrder/Created/v1` |
| **Queue** | Durable subscription — messages persist until consumed |
| **Queue Subscription** | Binds a queue to a topic pattern |

### S/4HANA Business Events (Cloud Edition)

S/4HANA Cloud publishes **Business Events** to Event Mesh automatically when business objects change. Consumers subscribe to queues.

**Available event types** (subset):
- `sap.s4.beh.purchaseorder.v1.PurchaseOrder.Created.v1`
- `sap.s4.beh.salesorder.v1.SalesOrder.Changed.v1`
- `sap.s4.beh.businesspartner.v1.BusinessPartner.Created.v1`
- `sap.s4.beh.material.v1.Material.Changed.v1`

**Consuming events (Node.js):**
```javascript
const { MessagingService } = require("@sap/xb-msg-amqp-v100");

const client = new MessagingService({
  settings: {
    connection: [{
      host: "enterprise-messaging.cfapps.eu10.hana.ondemand.com",
      port: 5671,
      useTLS: true,
    }],
    credentials: {
      clientId: process.env.EM_CLIENT_ID,
      clientSecret: process.env.EM_CLIENT_SECRET,
      tokenEndpoint: process.env.EM_TOKEN_ENDPOINT,
    },
  },
});

client.connect();
client.incoming().subscribe("my-queue", (message) => {
  const event = JSON.parse(message.payload.toString());
  console.log("Event received:", event.type, event.data);
  message.done(); // Acknowledge message
});
```

**Consuming events (Python with AMQP):**
```python
import json, ssl, os
from proton.handlers import MessagingHandler
from proton.reactor import Container

class EventConsumer(MessagingHandler):
    def on_start(self, event):
        ssl_domain = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.container = event.container
        conn = event.container.connect(
            url=os.environ["EM_AMQP_URL"],
            user=os.environ["EM_CLIENT_ID"],
            password=os.environ["EM_CLIENT_SECRET"],
            ssl_domain=ssl_domain,
        )
        event.container.create_receiver(conn, "my-s4-queue")

    def on_message(self, event):
        payload = json.loads(event.message.body)
        print(f"Received: {payload['type']}")
        event.delivery.update(event.delivery.ACCEPTED)

Container(EventConsumer()).run()
```

---

## S/4HANA Cloud: Communication Arrangements

In S/4HANA Cloud (Public Edition), all external integrations are configured through **Communication Arrangements** — a declarative, admin-UI-driven approach replacing manual RFC destinations and ICF configuration.

### Setup Process

1. **Communication System**: define the external system (name, host, certificates)
2. **Communication User**: create a technical user for the arrangement (assigns OAuth2 or Basic Auth credentials)
3. **Communication Scenario**: SAP-delivered scenarios define which APIs are included (e.g., `SAP_COM_0008` for Purchase Order API)
4. **Communication Arrangement**: links Scenario + System + User; generates the service URL

### Finding the correct Communication Scenario

| Business Object | Communication Scenario ID |
|---|---|
| Purchase Order (OData V4) | `SAP_COM_0008` |
| Sales Order | `SAP_COM_0105` |
| Business Partner | `SAP_COM_0008` (BP is part of central APIs) |
| Product / Material | `SAP_COM_0009` |
| Finance / Journal Entries | `SAP_COM_0002` |
| Event Mesh (outbound events) | `SAP_COM_0092` |

```bash
# After setting up Communication Arrangement for SAP_COM_0008:
# The service URL will be in the format:
# https://<tenant>.s4hana.ondemand.com/sap/opu/odata4/sap/api_purchaseorder/srvd_a2x/sap/purchaseorder/0001/

# Authenticate with the Communication User credentials (Basic Auth or OAuth2 per arrangement config)
curl -u COMM_USER:comm_pass \
  "https://my-tenant.s4hana.ondemand.com/sap/opu/odata4/sap/api_purchaseorder/srvd_a2x/sap/purchaseorder/0001/PurchaseOrder?\$top=5"
```

---

## Migration from SAP PI/PO

### Migration Path

| PI/PO Object | BTP Integration Suite Equivalent |
|---|---|
| Integration Scenario | Integration Package |
| Integration Process (ccBPM) | iFlow with Send step + correlation |
| Message Mapping | Message Mapping (same XSLT/graphical mapping, importable) |
| Value Mapping | Value Mapping (same concept, stored in CPI tenant) |
| Business System | Communication System |
| Communication Channel | Adapter in iFlow sender/receiver |
| Receiver Determination | Router step in iFlow |
| Interface Determination | Subprocess iFlow |
| Alert / Monitoring | Operations view in BTP Integration Suite |

### Migration tooling

- **Migration Assessment Tool**: SAP-provided tool that analyzes your PI/PO system and estimates migration effort per integration object
- **SAP Integration Suite Migration**: automated wizard to convert some PI/PO objects to iFlows
- **Manual migration**: required for ccBPM processes, custom adapters, and complex multi-mapping scenarios

---

## Version Considerations

| Capability | SAP PI 7.3/7.4 (ECC era) | SAP PO 7.5 | BTP Integration Suite |
|---|---|---|---|
| IDoc integration | Full | Full | Full (IDoc adapter) |
| OData integration | Custom HTTP adapter | HTTP adapter | OData V2/V4 adapter (built-in) |
| RFC/BAPI integration | RFC adapter | RFC adapter | RFC adapter via Cloud Connector |
| SOAP/WSDL | Full | Full | SOAP adapter |
| REST/JSON | HTTP adapter | HTTP adapter | HTTP / OData adapter |
| Event-driven | Manual (no native broker) | Advanced Adapter Engine | Event Mesh (native) |
| S/4HANA Cloud APIs | Not supported | Not supported | Full support via Communication Arrangements |
| End of mainstream maintenance | Ended | 2027 | Actively developed |

---

## Common Pitfalls

1. **Cloud Connector resource scope**: Never map `/*` as the resource path. Always restrict to exact service paths. A misconfigured Cloud Connector can expose your entire SAP system to BTP tenants.

2. **CSRF token in OData adapter**: Unlike manual HTTP calls, the BTP OData adapter handles CSRF token fetch automatically when you enable the `CSRF Token` checkbox. Do NOT also manually add `X-CSRF-Token` headers — double-token logic will cause `403 Forbidden`.

3. **Event Mesh topic namespace**: S/4HANA Cloud event topics follow a strict namespace format `default/<namespace>/<event-type>`. Subscribing to the wrong namespace results in silently receiving no messages. Verify in the S/4HANA Communication Arrangement for Event Mesh (SAP_COM_0092) the exact topic names being published.

4. **Communication Arrangement vs. manual configuration**: In S/4HANA Cloud, you cannot manually configure RFC destinations or ICF nodes — it's all managed through Communication Arrangements. If you're copy-pasting configuration from an On-Premise guide, recognize that the setup process is fundamentally different.

5. **iFlow error handling**: Unlike PI/PO's adapter-level error handling, BTP Integration Suite errors must be handled explicitly with error sub-processes or `setProperty` steps. Uncaught exceptions result in the message being marked as `Failed` in monitoring without retries unless you configure a Dead Letter Queue.
