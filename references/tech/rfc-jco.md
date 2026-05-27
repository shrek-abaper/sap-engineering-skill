# RFC / JCo Integration Reference

## Table of Contents

1. [When to Use RFC/JCo](#1-when-to-use-rfcjco)
2. [JCo Dependency Setup](#2-jco-dependency-setup)
3. [Connection Properties Reference](#3-connection-properties-reference)
4. [Direct Connection vs Load Balancing](#4-direct-connection-vs-load-balancing)
5. [Connection Pool Configuration](#5-connection-pool-configuration)
6. [Calling a BAPI — Java Code Template](#6-calling-a-bapi--java-code-template)
7. [Reading the RETURN Table](#7-reading-the-return-table)
8. [Common JCo Exceptions](#8-common-jco-exceptions)
9. [Non-JVM Options (Python, .NET)](#9-non-jvm-options-python-net)
10. [RFC Destination Types](#10-rfc-destination-types)

---

## 1. When to Use RFC/JCo

| Scenario | Use RFC/JCo |
|---|---|
| SAP ECC 6.0 | Always (primary integration method; no standard OData) |
| S/4HANA On-Premise: no standard OData API for the use case | Yes |
| S/4HANA On-Premise: bulk/batch operations (1000+ records) | Yes (more efficient than OData $batch) |
| S/4HANA On-Premise: FI document posting | Yes (`BAPI_ACC_DOCUMENT_POST` — no OData equivalent) |
| S/4HANA Cloud Public Edition | **No** — RFC external access is restricted; use OData V4 |
| Java application already running in JVM | Yes (JCo is native JVM library) |
| Non-JVM client (Python, Node.js, .NET) | Use OData instead; or proxy via a Java JCo microservice |

---

## 2. JCo Dependency Setup

### Important note

**SAP JCo is NOT available on Maven Central or public npm registries.** You must download it from the SAP Support Portal.

**Download URL**: https://support.sap.com/en/product/connectors/jco.html  
(Requires SAP S-User login)

The download is platform-specific (Linux x64, Windows x64, macOS). Download the correct version.

### Maven (after downloading JCo JAR locally)

```xml
<!-- pom.xml -->
<!-- Install JCo JAR to local Maven repository first: -->
<!-- mvn install:install-file -Dfile=sapjco3.jar \
     -DgroupId=com.sap.conn.jco -DartifactId=sapjco3 \
     -Dversion=3.1.9 -Dpackaging=jar -->

<dependency>
    <groupId>com.sap.conn.jco</groupId>
    <artifactId>sapjco3</artifactId>
    <version>3.1.9</version>
    <scope>system</scope>
    <systemPath>${project.basedir}/lib/sapjco3.jar</systemPath>
</dependency>
```

### Gradle

```groovy
// build.gradle
dependencies {
    implementation files('lib/sapjco3.jar')
}
```

### Native library (libsapjco3)

JCo requires a native shared library in addition to the JAR:
- **Linux**: `libsapjco3.so` → place in `/usr/lib/` or set `LD_LIBRARY_PATH`
- **Windows**: `sapjco3.dll` → place in `%WINDIR%\system32` or application directory
- **macOS**: `libsapjco3.jnilib` → place in `/usr/local/lib` or set `DYLD_LIBRARY_PATH`

If the native library is not found, JCo throws:
```
java.lang.UnsatisfiedLinkError: no sapjco3 in java.library.path
```

Fix: Set `java.library.path` JVM argument:
```bash
java -Djava.library.path=/path/to/jco/native -jar myapp.jar
```

### Required JCo version

- JCo 3.0.x: Supports SAP Kernel 720/721+
- JCo 3.1.x: Recommended for S/4HANA; supports Unicode and non-Unicode
- Always use the same JCo version as your SAP kernel version supports (check SAP Note 2786093)

---

## 3. Connection Properties Reference

JCo connections are configured via `.jcoDestination` properties files or programmatically.

### Direct connection properties

| Property | Description | Example | Required |
|---|---|---|---|
| `jco.client.host` | SAP application server hostname or IP | `sap-erp.example.com` | Yes |
| `jco.client.sysnr` | System number (2 digits) | `00` | Yes |
| `jco.client.client` | SAP client (3 digits) | `100` | Yes |
| `jco.client.user` | SAP logon user | `RFCUSER` | Yes |
| `jco.client.passwd` | SAP logon password | `password` | Yes |
| `jco.client.lang` | Logon language | `EN` | Recommended |
| `jco.client.ashost` | Alternative to `jco.client.host` | `sap-erp.example.com` | One of host/ashost |

### Load balancing properties

| Property | Description | Example | Required |
|---|---|---|---|
| `jco.client.mshost` | Message server hostname | `sap-ms.example.com` | Yes (LB mode) |
| `jco.client.r3name` | SAP System ID (SID) | `PRD` | Yes (LB mode) |
| `jco.client.group` | Logon group (from SMLG) | `PUBLIC` | Yes (LB mode) |
| `jco.client.client` | SAP client | `100` | Yes |
| `jco.client.user` | SAP user | `RFCUSER` | Yes |
| `jco.client.passwd` | SAP password | `password` | Yes |
| `jco.client.lang` | Language | `EN` | Recommended |
| `jco.client.msserv` | Message server port | `3600` | If non-standard |

### SSL properties (for encrypted RFC connections)

| Property | Description | Example |
|---|---|---|
| `jco.client.ssl` | Enable SSL/TLS | `1` |
| `jco.client.ssl_client_keystore` | Path to JKS keystore | `/path/to/client.jks` |
| `jco.client.ssl_client_keystorepwd` | Keystore password | `keystorepass` |
| `jco.client.ssl_partner_commonname` | Expected server CN | `sap-erp.example.com` |

### Pool properties

| Property | Description | Default |
|---|---|---|
| `jco.destination.pool_capacity` | Max idle connections | `1` |
| `jco.destination.peak_limit` | Max total connections | `10` |
| `jco.destination.expiration_time` | Idle connection expiry (ms) | `60000` |
| `jco.destination.expiration_check_period` | Cleanup interval (ms) | `60000` |

---

## 4. Direct Connection vs Load Balancing

### Direct connection

Use when: Development/test environments, single application server, known host.

```properties
# SAP_ERP.jcoDestination
jco.client.host=sap-erp.example.com
jco.client.sysnr=00
jco.client.client=100
jco.client.user=RFCUSER
jco.client.passwd=password
jco.client.lang=EN
jco.destination.pool_capacity=5
jco.destination.peak_limit=20
```

### Load balancing

Use when: Production systems, high availability required, multiple application servers.

```properties
# SAP_ERP_LB.jcoDestination
jco.client.mshost=sap-ms.example.com
jco.client.msserv=3600
jco.client.r3name=PRD
jco.client.group=PUBLIC
jco.client.client=100
jco.client.user=RFCUSER
jco.client.passwd=password
jco.client.lang=EN
jco.destination.pool_capacity=5
jco.destination.peak_limit=20
```

**Note**: For load balancing, the message server port `3600` (or `3600 + instance_nr` if non-standard) must be accessible from your integration server. Check with SAP Basis.

### Registering destination programmatically

```java
import com.sap.conn.jco.ext.*;

public class SAPDestinationDataProvider implements DestinationDataProvider {
    private final Properties props;

    public SAPDestinationDataProvider(Properties props) {
        this.props = props;
    }

    @Override
    public Properties getDestinationProperties(String destinationName) {
        if ("SAP_ERP".equals(destinationName)) {
            return props;
        }
        throw new DestinationDataEventListener.InvalidDestinationDataException(
            "Unknown destination: " + destinationName
        );
    }

    @Override
    public boolean supportsEvents() { return false; }

    @Override
    public void setDestinationDataEventListener(DestinationDataEventListener listener) {}
}

// Registration
Properties props = new Properties();
props.setProperty(DestinationDataProvider.JCO_ASHOST, "sap-erp.example.com");
props.setProperty(DestinationDataProvider.JCO_SYSNR,  "00");
props.setProperty(DestinationDataProvider.JCO_CLIENT, "100");
props.setProperty(DestinationDataProvider.JCO_USER,   "RFCUSER");
props.setProperty(DestinationDataProvider.JCO_PASSWD, "password");
props.setProperty(DestinationDataProvider.JCO_LANG,   "EN");
props.setProperty(DestinationDataProvider.JCO_POOL_CAPACITY, "5");
props.setProperty(DestinationDataProvider.JCO_PEAK_LIMIT,    "10");

Environment.registerDestinationDataProvider(new SAPDestinationDataProvider(props));
```

---

## 5. Connection Pool Configuration

JCo maintains a connection pool per destination. Pool configuration is critical for performance under load.

```properties
# Recommended production settings
jco.destination.pool_capacity=10    # Max idle connections kept in pool
jco.destination.peak_limit=50       # Max concurrent connections (hard limit)
jco.destination.expiration_time=60000        # Idle conn expires after 60 seconds
jco.destination.expiration_check_period=60000 # Check for expired every 60 seconds
jco.destination.max_get_client_time=30000    # Timeout waiting for a connection (ms)
```

**Sizing rule**: `peak_limit` should not exceed the SAP work process count for type `DIA` (dialog) on your target server. Check transaction `SM50` to see available work processes.

---

## 6. Calling a BAPI — Java Code Template

This is the canonical Java pattern for any BAPI call:

```java
import com.sap.conn.jco.*;

public class BAPITemplate {

    public static void callBAPI(String destinationName) throws JCoException {
        // 1. Get connection from pool
        JCoDestination dest = JCoDestinationManager.getDestination(destinationName);

        // 2. Get function metadata (cached after first call)
        JCoFunction bapi = dest.getRepository().getFunction("BAPI_PO_CREATE1");
        if (bapi == null) {
            throw new RuntimeException("BAPI_PO_CREATE1 not found in SAP repository");
        }

        // 3. Set import parameters (scalar)
        JCoParameterList imports = bapi.getImportParameterList();
        imports.setValue("SOME_PARAM", "value");

        // 4. Set import structure parameters
        JCoStructure header = imports.getStructure("POHEADER");
        header.setValue("DOC_TYPE",   "NB");
        header.setValue("PURCH_ORG",  "1000");
        header.setValue("PUR_GROUP",  "001");
        header.setValue("COMP_CODE",  "1000");
        header.setValue("VENDOR",     "1000001");
        header.setValue("DOC_DATE",   "20260430");
        header.setValue("CURRENCY",   "USD");

        // 5. Set X-structure (field change flags) — required for most BAPIs
        JCoStructure headerX = imports.getStructure("POHEADERX");
        headerX.setValue("DOC_TYPE",  "X");
        headerX.setValue("PURCH_ORG", "X");
        headerX.setValue("PUR_GROUP", "X");
        headerX.setValue("COMP_CODE", "X");
        headerX.setValue("VENDOR",    "X");
        headerX.setValue("DOC_DATE",  "X");
        headerX.setValue("CURRENCY",  "X");

        // 6. Set table parameters
        JCoTable poItem  = bapi.getTableParameterList().getTable("POITEM");
        JCoTable poItemX = bapi.getTableParameterList().getTable("POITEMX");

        poItem.appendRow();
        poItem.setValue("PO_ITEM",   "00010");
        poItem.setValue("PLANT",     "1000");
        poItem.setValue("MATERIAL",  "RAW-001");
        poItem.setValue("QUANTITY",  new java.math.BigDecimal("10"));
        poItem.setValue("NET_PRICE", new java.math.BigDecimal("25.00"));
        poItem.setValue("PRICE_UNIT", 1);

        poItemX.appendRow();
        poItemX.setValue("PO_ITEM",   "00010");
        poItemX.setValue("PLANT",     "X");
        poItemX.setValue("MATERIAL",  "X");
        poItemX.setValue("QUANTITY",  "X");
        poItemX.setValue("NET_PRICE", "X");
        poItemX.setValue("PRICE_UNIT","X");

        // 7. Execute the BAPI
        bapi.execute(dest);

        // 8. MANDATORY: ALWAYS commit after write BAPIs
        //    Write BAPIs do NOT auto-commit. Without this, changes are rolled back.
        JCoFunction commit = dest.getRepository().getFunction("BAPI_TRANSACTION_COMMIT");
        commit.getImportParameterList().setValue("WAIT", "X");  // "X" = synchronous commit
        commit.execute(dest);

        // 9. Read export parameters
        JCoParameterList exports = bapi.getExportParameterList();
        String poNumber = exports.getString("EXPPURCHASEORDER");
        System.out.println("PO Number: " + poNumber);

        // 10. Read tables (structure or table results)
        JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
        for (int i = 0; i < returnTable.getNumRows(); i++) {
            returnTable.setRow(i);
            System.out.printf("[%s] %s%n",
                returnTable.getString("TYPE"),
                returnTable.getString("MESSAGE")
            );
        }
    }
}
```

---

## 7. Reading the RETURN Table

The `RETURN` table is the universal error/status output for all BAPIs. **Never skip RETURN table validation** — a successful BAPI execution (`bapi.execute()` not throwing) does NOT mean the business operation succeeded.

### RETURN table fields

| Field | Description |
|---|---|
| `TYPE` | Message type: `S` (Success), `I` (Info), `W` (Warning), `E` (Error), `A` (Abort) |
| `ID` | Message class (e.g., `M8`, `F5`) |
| `NUMBER` | Message number within class |
| `MESSAGE` | Human-readable message text |
| `LOG_NO` | Application log number (check SLG1) |
| `LOG_MSG_NO` | Message number in application log |
| `MESSAGE_V1` to `MESSAGE_V4` | Message variables (fill into the message text) |
| `FIELD` | Field name that caused the error |
| `SYSTEM` | Source system |

### Correct RETURN processing

```java
JCoTable returnTable = bapi.getTableParameterList().getTable("RETURN");
boolean hasError = false;
StringBuilder errorMessages = new StringBuilder();

for (int i = 0; i < returnTable.getNumRows(); i++) {
    returnTable.setRow(i);
    String type = returnTable.getString("TYPE");
    String message = returnTable.getString("MESSAGE");
    String field = returnTable.getString("FIELD");

    switch (type) {
        case "E":
        case "A":
            hasError = true;
            errorMessages.append("[ERROR] ").append(message);
            if (!field.isEmpty()) errorMessages.append(" (field: ").append(field).append(")");
            errorMessages.append("\n");
            break;
        case "W":
            System.out.println("[WARN] " + message);
            break;
        case "S":
        case "I":
            System.out.println("[INFO] " + message);
            break;
    }
}

if (hasError) {
    // ROLLBACK if needed (for read-only or already-committed failures)
    JCoFunction rollback = dest.getRepository().getFunction("BAPI_TRANSACTION_ROLLBACK");
    rollback.execute(dest);
    throw new RuntimeException("BAPI failed:\n" + errorMessages);
}
```

---

## 8. Common JCo Exceptions

| JCoException Code | Root Cause | Fix |
|---|---|---|
| `101` | Destination not configured | Check `.jcoDestination` file path and name |
| `102` | Logon failed (wrong credentials) | Verify user/password in SAP; check user lock (SU01) |
| `103` | Communication failure | Check host/port reachability; firewall; SAP services running |
| `104` | Connection refused | SAP instance not running; wrong system number; port blocked |
| `109` | Connection closed by remote host | SAP timed out the connection; increase SAP session timeout; check ICM |
| `111` | RFC function not found in repository | Function module name typo, or remote-enabled flag not set in SAP |
| `122` | Data conversion error | Type mismatch (e.g., passing String where BigDecimal required) |
| `131` | Table function not found | Missing table parameter; check BAPI metadata |
| `206` | `JCoContext` not set correctly | Use `JCoContext.begin(dest)` / `end()` for stateful calls |

### Handling JCoException

```java
try {
    JCoDestination dest = JCoDestinationManager.getDestination("SAP_ERP");
    JCoFunction bapi = dest.getRepository().getFunction("BAPI_PO_CREATE1");
    bapi.execute(dest);
} catch (JCoException e) {
    System.err.println("JCo error code: " + e.getGroup()); // 0-7 = JCO error groups
    System.err.println("JCo error key: " + e.getKey());
    System.err.println("JCo message: " + e.getMessage());
    e.printStackTrace();
}
```

---

## 9. Non-JVM Options (Python, .NET)

### Preferred: Use OData Instead

For non-JVM runtimes (Python, Node.js, .NET, Go), the **recommended integration path is OData**, not RFC/JCo. SAP JCo is a Java native library — it cannot be called directly from Python or Node.js. Any RFC call from a non-JVM runtime must either go through a compatibility layer or a proxy service.

**Why OData is preferred for non-JVM**:
- Standard HTTP/JSON — no native library dependencies
- Works with any HTTP client (requests, axios, HttpClient, etc.)
- Supported on S/4HANA On-Premise and Cloud
- No platform-specific binary dependencies

**When OData is not available** (ECC 6.0, or use cases with no standard OData service):

### Option A: Java JCo Microservice Proxy (Recommended for ECC)

Deploy a lightweight Java service that exposes a REST/gRPC API and calls SAP via JCo internally. Non-JVM applications call the microservice over HTTP.

```
Python / Node.js / .NET
        │
        │  REST or gRPC (internal network)
        ▼
Java JCo Microservice
  ├── POST /api/bapi/vendor-invoice   → BAPI_ACC_DOCUMENT_POST
  ├── GET  /api/open-items/ap         → BAPI_AP_ACC_GETOPENITEMS
  └── POST /api/goods-receipt         → BAPI_GOODSMVT_CREATE
        │
        │  JCo TCP (port 33xx)
        ▼
SAP ECC / S/4HANA Application Server
```

This pattern:
- Keeps all SAP-specific logic in one place (Java service)
- Non-JVM clients stay clean — no SAP SDK dependencies
- JCo connection pool is managed centrally
- Enables independent scaling and versioning of the SAP integration layer

### Option B: SAP .NET Connector (NCo) — for .NET Only

For .NET applications, SAP provides **SAP .NET Connector 3.0 (NCo)**, which is the actively maintained equivalent of JCo for the .NET runtime. It wraps the SAP NW RFC SDK and provides a similar programming model.

- **Download**: https://support.sap.com/en/product/connectors/msnet.html (requires SAP S-User)
- **Supports**: .NET Framework 4.x and .NET 6+
- **Programming model**: similar to JCo — `RfcDestinationManager`, `IRfcFunction`, `IRfcTable`

### Option C: pyrfc — Python (⚠️ Maintenance Risk)

[pyrfc](https://github.com/SAP/PyRFC) provides Python bindings for RFC via the **SAP NW RFC SDK** (a C library — `libsapnwrfc.so` on Linux). It does **not** wrap the JCo JAR; it is a separate binding to a separate C library.

```bash
# Requires SAP NW RFC SDK (C library) — NOT the JCo JAR
# Download from: https://support.sap.com → SAP NW RFC SDK
export SAPNWRFC_HOME=/path/to/nwrfcsdk

pip install pyrfc
```

**⚠️ Before using pyrfc, be aware**:
- Release cadence is irregular (community-maintained open source)
- Python 3.12+ compatibility issues have been reported in some environments
- The SAP NW RFC SDK binary must match the OS and SAP release (separate download from JCo)
- For production systems, the Java JCo microservice pattern (Option A above) is more operationally predictable

**Technical note**: pyrfc wraps `libsapnwrfc.so` (SAP NW RFC SDK, a C library). This is architecturally distinct from SAP JCo, which is a pure Java library (`sapjco3.jar` + `libsapjco3.so`). Both ultimately communicate with the SAP application server over the RFC protocol, but they use different SDK stacks.

---

## 10. RFC Destination Types

| Type | Code | Description | Use case |
|---|---|---|---|
| ABAP connection | `3` | ABAP-to-ABAP RFC call | SAP-to-SAP integration, ALE/IDoc |
| TCP/IP connection | `T` | External program/Java connection | JCo from external server |
| HTTP connection | `H` | HTTP-based RFC call | RESTful scenarios |
| Internal | `I` | Within same ABAP system | Test destinations |
| SNA LU6.2 | `L` | Legacy mainframe | Rare; legacy systems |

**For JCo**: Your SAP administrator must create a Type `T` (TCP/IP) RFC destination in transaction `SM59` pointing to your integration server (if using registered RFC server mode). For outbound calls (your app calling SAP), no destination registration in SM59 is needed — you configure the SAP host in your `.jcoDestination` file.
