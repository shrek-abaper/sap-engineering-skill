# SAP ADT Connectivity Reference

> `sap-transport-gate` v1.1.0 — Online Transport Mode: credential setup, authentication, TR extraction

This file enables the **Online Transport Mode** of the SKILL. The `tr_collector.py` script (in `scripts/`) implements everything described here.

---

## 1. Prerequisites

Python 3.8+ and the following packages (auto-installed on first run):

```
requests>=2.31.0
click>=8.1.0
urllib3>=2.0.0
```

---

## 2. Credential Configuration

Credentials are resolved in priority order (highest first):

| Priority | Source | When to Use |
|---|---|---|
| 1 | Process environment variables | CI pipelines, one-off runs, secrets managers |
| 2 | `.env` file in the SKILL directory | Per-skill isolated config; works from any CWD |
| 3 | `~/.sap-transport-gate/config.json` | Shared local config; set once via `configure` command |

### Option A — SKILL-local `.env` file (recommended for reuse)

Copy `.env.example` to `.env` inside the skill root and fill in your values:

```bash
cp .env.example .env
# edit .env
```

```ini
# <skill-dir>/.env
SAP_URL=https://your-sap-system.example.com:8000
SAP_USERNAME=YOUR_USERNAME
SAP_PASSWORD=YOUR_PASSWORD
SAP_CLIENT=100
SAP_LANGUAGE=EN          # optional, default: EN
SAP_VERIFY_SSL=1         # optional: 0 to disable SSL verification
```

The script resolves `.env` relative to its own location (`scripts/lib/config.py` → 3 levels up → skill root), so it is found correctly regardless of the working directory when the script is invoked.

### Option B — Environment Variables (CI / headless use)

```bash
export SAP_URL="https://my-sap.example.com:8000"
export SAP_USERNAME="ABAPDEV"
export SAP_PASSWORD="MyPassword"
export SAP_CLIENT="100"
export SAP_LANGUAGE="EN"          # optional, default: EN
export SAP_VERIFY_SSL="1"         # optional, set to 0 to disable SSL verification
```

### Option C — Interactive Setup (persistent config file)

```bash
python3 scripts/tr_collector.py configure
```

Stores credentials in `~/.sap-transport-gate/config.json` (mode 600, never committed).

### Credential Priority

Process environment variables override `.env`, which overrides `config.json`. A value present in a lower-priority source is only used when all higher-priority sources are absent or incomplete.

---

## 3. SAP ADT Authentication Flow

The `tr_collector.py` script uses SAP's standard ADT Basic Auth + CSRF token protocol:

```
1. GET /sap/bc/adt/
   Headers:  Authorization: Basic <base64(username:password)>
             X-SAP-Client: <client>
             x-csrf-token: fetch

   Response: Set-Cookie (session cookies)
             x-csrf-token: <TOKEN>

2. All subsequent requests reuse:
   - The session (cookies included)
   - x-csrf-token header for POST/PUT requests
   - Basic Auth on every request
```

On 403 with CSRF error: token is re-fetched automatically and the request is retried once.

SSL verification can be disabled via `SAP_VERIFY_SSL=0` (not recommended for production).

---

## 4. TR Object List Endpoint

```
GET {SAP_URL}/sap/bc/adt/cts/transports/{TR_ID}/objects
Headers:
  Authorization: Basic <credentials>
  X-SAP-Client: <client>
  Accept: application/vnd.sap.cts.transport.objects+xml

Response: XML containing transport object entries
```

Each object entry has these key attributes:

| Field | Meaning | Example |
|---|---|---|
| `PGMID` | Program ID | `R3TR` (repository), `LIMU` (partial) |
| `OBJECT` | Object type code | `PROG`, `CLAS`, `FUGR`, `DTEL`, `TABL`, `DDLS` |
| `OBJ_NAME` | Object name | `ZMYPROGRAM`, `ZCL_MY_CLASS` |
| `LOCKFLAG` | Lock state | `X` = locked, empty = unlocked |
| `ACTIVITY` | Change type | `M` = modified, `D` = deleted, `I` = inserted |

---

## 5. Source Code Fetch Endpoints

The script dispatches to the correct endpoint based on `OBJECT` type:

| Object Type | Endpoint |
|---|---|
| `PROG` (report/program) | `GET /sap/bc/adt/programs/programs/{NAME}/source/main` |
| `CLAS` (global class) | `GET /sap/bc/adt/oo/classes/{NAME}/source/main` |
| `INTF` (interface) | `GET /sap/bc/adt/oo/interfaces/{NAME}/source/main` |
| `FUGR` (function group) | `GET /sap/bc/adt/functions/groups/{NAME}/source/main` |
| `FUNC` (function module) | `GET /sap/bc/adt/functions/groups/{GROUP}/fmodules/{NAME}/source/main` |
| `CINC` (class include) | `GET /sap/bc/adt/programs/includes/{NAME}/source/main` |
| `REPS` (program include) | `GET /sap/bc/adt/programs/includes/{NAME}/source/main` |
| `DOMA` (domain) | `GET /sap/bc/adt/ddic/domains/{NAME}/source/main` |
| `DTEL` (data element) | `GET /sap/bc/adt/ddic/dataelements/{NAME}` |
| `TABL` (table/structure) | `GET /sap/bc/adt/ddic/tables/{NAME}/source/main` |
| `STRU` (structure) | `GET /sap/bc/adt/ddic/structures/{NAME}/source/main` |
| `DDLS` (CDS view) | `GET /sap/bc/adt/ddic/ddl/sources/{NAME}/source/main` |

For object types without a source endpoint (e.g., `DEVC`, `SICF`, `SMIM`, `NROB`), the script records the object in the manifest but marks `source_fetched: false`.

---

## 6. Review Package Output Format

The `collect` command produces a structured output directory:

```
<output_dir>/
├── manifest.json         ← TR metadata + object list + fetch status
└── sources/
    ├── PROG_ZMYREPORT.abap
    ├── CLAS_ZCL_MY_CLASS.abap
    ├── FUGR_ZFUGR_EXAMPLE.abap
    └── ...
```

### `manifest.json` Schema

```json
{
  "meta": {
    "tr_id": "DEVK900123",
    "sap_url": "https://my-sap.example.com:8000",
    "sap_client": "100",
    "collected_at": "2026-05-26T12:00:00Z",
    "collector_version": "1.0.0"
  },
  "objects": [
    {
      "pgmid": "R3TR",
      "object_type": "PROG",
      "object_name": "ZMYREPORT",
      "lockflag": "",
      "activity": "M",
      "source_fetched": true,
      "source_file": "sources/PROG_ZMYREPORT.abap",
      "fetch_error": null
    }
  ],
  "summary": {
    "total_objects": 5,
    "sources_fetched": 4,
    "fetch_errors": 1
  }
}
```

---

## 7. CLI Usage

### Configure credentials

```bash
python3 scripts/tr_collector.py configure
```

### Collect TR objects and source code

```bash
# Minimal usage — outputs to ./review_package/
python3 scripts/tr_collector.py collect DEVK900123

# With explicit output directory
python3 scripts/tr_collector.py collect DEVK900123 --output-dir ./reports/DEVK900123_package/

# Verbose mode (shows each object fetch)
python3 scripts/tr_collector.py collect DEVK900123 --verbose
```

### Check connection

```bash
python3 scripts/tr_collector.py ping
```

---

## 8. Handoff to AI Review

After collection, hand the output directory to the agent:

```
I have collected TR DEVK900123.
The Review Package is at: ./reports/DEVK900123_package/

Please load sap-transport-gate and perform a release gate review.
The manifest.json is at: ./reports/DEVK900123_package/manifest.json
Source files are in: ./reports/DEVK900123_package/sources/
```

The agent reads `manifest.json` as the TR Identity + Object List evidence, and reads individual source files from `sources/` as the Source Code evidence.

---

## 9. Troubleshooting

| Error | Likely Cause | Fix |
|---|---|---|
| `No CSRF token received` | SAP ADT not enabled or wrong URL | Verify `SAP_URL` points to the correct system/port |
| `HTTP 401 Unauthorized` | Wrong credentials | Re-run `configure` or check env vars |
| `HTTP 403 Forbidden` | User lacks ADT authorization | Request `S_ADT_RES` authorization |
| `HTTP 404 Not Found` | Object type not supported or object doesn't exist | Check `fetch_error` in manifest.json |
| `SSL certificate verify failed` | Self-signed cert | Set `SAP_VERIFY_SSL=0` (non-production only) |
| Empty object list | TR has no objects or TR ID not found | Verify TR ID and that user has visibility |

---

## 10. Security Notes

- Credentials in `~/.sap-transport-gate/config.json` are stored in **plain text** (mode 600). Protect accordingly.
- Never commit `.env` files or `config.json` to version control.
- The collector is **read-only**: it never modifies SAP objects, triggers transports, or writes to SAP.
- SSL verification should only be disabled in non-production environments.

---

## 11. Local File Fallback (When SAP Access Is Unavailable)

When SAP credentials are not configured, or when credential verification fails (HTTP 401, 403, connection refused, SSL error), the review can continue in **Offline Local Mode** using manually exported source files.

### Step 1: Get the Object List from SE01/SE09

1. Open SAP GUI
2. Go to transaction **SE01** (Workbench Organizer) or **SE09**
3. Enter the Transport Request ID (e.g., `DEVK900123`) → click **Display**
4. Expand the transport tree to see all objects
5. Note every object: **Program ID**, **Object Type**, **Object Name**

### Step 2: Export Source Code per Object Type

| Object Type | Transaction | Steps |
|---|---|---|
| `PROG` (Report / Program) | **SE38** | Enter program name → Source code tab → copy/download source |
| `CLAS` (Global Class) | **SE24** | Enter class name → click **Source-Based Display** to get full source |
| `INTF` (Interface) | **SE24** | Enter interface name → Source-Based Display |
| `FUGR` (Function Group) | **SE37** | Enter function module → Source code; repeat per function module in the group |
| `TABL` / `STRU` (Table / Structure) | **SE11** | Display definition; note fields and keys |
| `DTEL` (Data Element) | **SE11** | Display data element |
| `DDLS` (CDS View) | **SE11** or Eclipse ADT | Enter view name → Source |

For classes: the **Source-Based Display** button in SE24 shows the full class source as a single ABAP file (includes all methods). Use this instead of copying method by method.

### Step 3: Organize Files Locally

Create a directory structure matching the review package convention:

```
review_package/{TR_ID}/
├── object_list.txt          ← one line per object: PGMID  OBJECT_TYPE  OBJECT_NAME
└── sources/
    ├── PROG_ZMYREPORT.abap
    ├── CLAS_ZCL_MY_CLASS.abap
    ├── FUGR_ZFUGR_EXAMPLE.abap
    └── ...
```

**File naming**: `{OBJECT_TYPE}_{OBJECT_NAME}.abap`

**`object_list.txt` format** (tab-separated):
```
R3TR	PROG	ZMYREPORT
R3TR	CLAS	ZCL_MY_CLASS
R3TR	FUGR	ZFUGR_EXAMPLE
```

### Step 4: Hand Off to AI

Provide the directory path to the AI agent:

```
SAP connection failed. I have manually exported the TR objects.
Directory: ./review_package/DEVK900123/
Object list: ./review_package/DEVK900123/object_list.txt
Sources: ./review_package/DEVK900123/sources/

Please review as Offline Local Mode.
```

**Expected Evidence Level for manual export packages:**

| Exported Items | Evidence Level |
|---|---|
| Source files + object list + syntax check result + activation status | MEDIUM |
| Source files + object list only | MEDIUM (lower bound) |
| Source files only (no object list) | LOW |
