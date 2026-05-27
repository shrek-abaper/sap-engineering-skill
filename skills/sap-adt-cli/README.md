# sap-adt-cli

[English](README.md) | [中文](README.zh-CN.md)

A command-line tool and AI agent skill for reading **and writing** ABAP source code, metadata,
and transport requests from SAP systems via the [ADT (ABAP Development Tools) REST API](https://help.sap.com/docs/abap-cloud/abap-development-tools-user-guide/about-abap-development-tools).

Supports programs, classes, function modules, interfaces, includes, CDS views, DDIC objects,
packages, transactions, SQL queries, where-used analysis, syntax checks, and transport management —
all from the terminal or from within an AI agent workflow. Write and transport operations require
explicit capability flags and per-operation confirmation.

---

## Requirements

- Python 3.8+
- A SAP system (on-premise ECC / S/4HANA, or BTP ABAP) with ADT services activated
- A SAP dialog user with the `SAP_ADT_BASE` role (or equivalent)

Dependencies (`click`, `requests`, `urllib3`) are installed automatically on first run.

---

## Windows Quick Setup — AI Agent Integration

> **Example: [opencode](https://opencode.ai)** — a free, open-source AI agent — is used here as the reference setup.  
> `sap-adt-cli` is packaged as a standard Agent Skill (`SKILL.md`) and works with any agent framework that supports custom tools/skills.

`setup-opencode-abap-cli.bat` is a Windows one-click installer that wires up opencode and this skill end-to-end.

### What the script does

| Step | Action |
|------|--------|
| 1 | Checks Node.js ≥ v18, Python 3, and Git are installed (prints guided download links if any are missing) |
| 2 | Adds Node.js bin and npm global package paths to the user-level `PATH` |
| 3 | Installs `opencode-ai` globally via `npm install -g opencode-ai` |
| 4 | Clones this repository to `%USERPROFILE%\.agents\sap-engineering-skill` and creates a directory junction at `%USERPROFILE%\.agents\skills\sap-adt-cli` pointing to the `skills\sap-adt-cli` subfolder |
| 5 | Installs Python dependencies: `click`, `requests`, `urllib3` |

### Prerequisites

Install these before running the script:

- **[Node.js v18 LTS or later](https://nodejs.org)** — use default installer options (PATH is checked by default)
- **[Python 3.8+](https://www.python.org/downloads)** — check **"Add Python to PATH"** during setup
- **[Git for Windows](https://git-scm.com/download/win)** — use default installer options

### Run the installer

Download [`setup-opencode-abap-cli.bat`](../../setup-opencode-abap-cli.bat) and **double-click** it.  
The script prints colored status messages and will stop with instructions if any prerequisite is missing.

### Start analyzing SAP code with opencode

After the script completes:

```cmd
REM Open CMD: press Win+R, type cmd, press Enter
opencode
```

Inside opencode, connect to your preferred AI model provider:

```
/connect
```

Then start querying your SAP system directly in natural language:

```
Analyze class ZCL_PAYMENT_PROCESSOR for security vulnerabilities
```

```
Read program ZREPORT_UPLOAD and check for SQL injection risks,
missing authorization checks, and hardcoded credentials
```

```
Scan the package ZMYPAYMENT and list all objects with potential security issues
```

opencode automatically calls `sap-adt-cli` to fetch ABAP source code from your SAP system via ADT,
then passes it to the AI model for analysis — no copy-paste required.

### SAP credentials setup (first run)

On the first query, opencode will prompt you for SAP connection details:

```
SAP System URL    — e.g. https://my-sap.example.com:8000
SAP Username      — dialog user (e.g. DEVELOPER)
SAP Password      — SAP logon password
SAP Client        — 3-digit client number (e.g. 100)
Skip SSL check?   — yes for self-signed / internal certs
```

Credentials are saved to `~\.sap-adt-cli\config.json` and reused in all subsequent sessions.

### Compatible AI agents

opencode is one example. `sap-adt-cli` implements the standard Agent Skill interface (`SKILL.md`)
and integrates with any agent framework that supports custom tools or skills:

| Agent | Notes |
|-------|-------|
| [opencode](https://opencode.ai) | Free, open-source. Used in this example. Supports 30+ model providers. |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | Anthropic's official CLI agent — natively supports SKILL.md |
| [Cursor](https://cursor.sh) | AI-powered code editor; install via MCP tool adapter |
| Other agents | SKILL.md is natively supported by opencode and Claude Code; other frameworks may require adaptation |

> ⚠️ **Data compliance note:** ABAP source code may contain core business logic and sensitive data.  
> Before sending code to cloud-based AI services, confirm compliance with your organization's  
> data security policy. For sensitive environments, consider an internally-hosted model.

---

## Quickstart

```bash
# 1. Clone the repository
git clone https://github.com/shrek-abaper/sap-engineering-skill
cd sap-engineering-skill

# 2. Configure credentials (interactive wizard — password is not echoed)
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure

# 3. Verify the connection
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py status

# 4. Start reading ABAP objects
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py get-program SAPMV45A
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py get-class ZCL_MY_CLASS
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py get-function BAPI_SALESORDER_CREATEFROMDAT2 --group BAPI_SD_SALESORDER
```

---

## Configuration

### Interactive wizard (recommended)

```bash
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure
```

Credentials are saved to `~/.sap-adt-cli/config.json` with `0600` permissions.

> **Security note:** The config file stores credentials in plain text.
> Do not commit it to version control and restrict access to the file accordingly.

### Environment variables

Useful for CI/CD pipelines or one-off sessions. Environment variables take
precedence over the saved config file.

```bash
export SAP_URL=https://my-sap.example.com:8000
export SAP_USERNAME=MYUSER
export SAP_PASSWORD=secret          # prefer this over the --password flag
export SAP_CLIENT=100
export SAP_LANGUAGE=EN              # optional, default: EN
export SAP_VERIFY_SSL=0             # optional: set 0 for self-signed certificates
```

### Capability flags (default: disabled)

Two optional flags unlock write and transport capabilities.
**Enable only on development systems.**

```bash
# Enable interactively
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure
# → answer 'y' to the write/transport prompts

# Enable non-interactively
SAP_PASSWORD="secret" python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure \
  --url "https://sap-dev.example.com:44300" \
  --username "DEVELOPER" \
  --client "400" \
  --allow-write \
  --no-allow-transport
```

| Flag | Config field | Default | Commands unlocked |
|------|-------------|---------|-------------------|
| `--allow-write` | `allow_write` | false | `write-source`, `activate` |
| `--allow-transport` | `allow_transport` | false | `create-transport`, `release-transport` |

**Confirmation policy**: even when flags are enabled, every write/create/release
operation shows a change preview and requires explicit `[y/N]` confirmation.
The confirmation applies to the current operation only — it is discarded immediately
after use and must be repeated for each subsequent operation.

### Non-interactive flags (agent / automation workflows)

```bash
# Pass password via environment variable to avoid shell history exposure
SAP_PASSWORD="secret" python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure \
  --url      "https://my-sap.example.com:8000" \
  --username "MYUSER" \
  --client   "100"
```

---

## Commands

| Command | Description |
|---------|-------------|
| `configure` | Save connection credentials |
| `status` | Show current connection configuration |
| `get-program <NAME>` | ABAP program / report source code |
| `get-class <NAME>` | ABAP class source code |
| `get-function-group <NAME>` | Function group top-include source code |
| `get-function <NAME> --group <FG>` | Function module source code |
| `get-include <NAME>` | ABAP include source code |
| `get-interface <NAME>` | ABAP interface source code |
| `get-table <NAME>` | DDIC table field definitions (XML) |
| `get-structure <NAME>` | DDIC structure definition (XML) |
| `get-type-info <NAME>` | Domain or data element info (XML) |
| `get-type-group <NAME>` | ABAP type group (TYPE POOL) source |
| `get-cds-view <NAME>` | CDS View DDL source code |
| `get-package <NAME>` | Package object list (JSON) |
| `get-transaction <NAME>` | Transaction properties / package (XML) |
| `search-object <QUERY> [--max-results N]` | Object name search — `*` wildcard supported |
| `syntax-check <TYPE> <NAME> [--group <FG>]` | Syntax check — read-only, no confirmation; `--group` required when TYPE is `function` |
| `where-used <TYPE> <NAME> [--max-results N] [--group <FG>]` | Where-used list (JSON); `--group` required when TYPE is `function` |
| `run-sql "<SQL>" [--max-rows N]` | Open SQL SELECT → JSON *(DML statements blocked)*; default 100 rows, max 10 000 |
| `write-source <TYPE> <NAME> --file <PATH> [--activate] [--group <FG>] [--transport <TRKORR>]` | Write source code *(allow_write + confirm each time)*; `--activate` activates after writing; `--group` required when TYPE is `function`; `--transport` pins the transport request |
| `activate <TYPE> <NAME> [--group <FG>]` | Activate ABAP object *(allow_write + confirm each time)*; `--group` required when TYPE is `function` |
| `list-transports [--user U] [--status D\|R]` | List transport requests (JSON, read-only); default `--status D` (in development) |
| `create-transport --description "<DESC>" [--category Workbench\|Customizing]` | Create transport *(allow_transport + confirm each time)*; default category: `Workbench` |
| `release-transport <TRKORR> [--yes]` | Release transport — irreversible *(allow_transport + confirm each time)* |

Run any command with `--help` for full details.

---

## Examples

```bash
CLI="skills/sap-adt-cli/scripts/sap_adt_cli.py"

# Source code
python3 $CLI get-program SAPMV45A
python3 $CLI get-class ZCL_MY_CLASS
python3 $CLI get-function BAPI_SALESORDER_CREATEFROMDAT2 --group BAPI_SD_SALESORDER
python3 $CLI get-include MV45AFZZ
python3 $CLI get-interface ZIF_MY_INTERFACE

# Dictionary objects
python3 $CLI get-table VBAK
python3 $CLI get-structure VBAKKOM
python3 $CLI get-type-info MATNR
python3 $CLI get-type-group ICON

# Discovery
python3 $CLI search-object "ZCL_ORDER*" --max-results 20
python3 $CLI get-package ZMYPACKAGE
python3 $CLI get-transaction VA01
python3 $CLI get-cds-view ZI_INVENTORY_POSITION

# Analysis (read-only)
python3 $CLI syntax-check class ZCL_MY_CLASS
python3 $CLI where-used class ZCL_PAYMENT_PROCESSOR
python3 $CLI run-sql "SELECT * FROM t001 UP TO 5 ROWS"

# Write & activate (allow_write + confirm each time)
python3 $CLI write-source class ZCL_MY_CLASS --file /tmp/zcl.abap
python3 $CLI write-source class ZCL_MY_CLASS --file /tmp/zcl.abap --activate   # write + activate in one step
python3 $CLI activate class ZCL_MY_CLASS

# Transport management
python3 $CLI list-transports --status D                              # read-only
python3 $CLI create-transport --description "My feature"            # allow_transport + confirm
python3 $CLI release-transport DEVK900001                           # allow_transport + confirm
```

---

## SAP Prerequisites

### 1. Activate ADT services

In transaction `SICF`, activate the following service paths:

| Service path | Required for |
|---|---|
| `/sap/bc/adt` | All commands |
| `/sap/bc/adt/datapreview` | `run-sql` (Open SQL Data Preview) |

### 2. Assign user authorization

| Operations | Required authorization |
|---|---|
| All read commands | Role `SAP_ADT_BASE` — or manually: `S_ADT_RES` (ADT resource access) + `S_RFC` (ADT function groups) |
| `write-source`, `activate` | `S_DEVELOP` with `ACTVT=02` on the relevant object types |
| `create-transport`, `release-transport` | `S_CTS_ADMI` or equivalent transport authorization |
| `list-transports` | Covered by `SAP_ADT_BASE` — no additional authorization needed |

---

## Output Formats

| Commands | Output |
|----------|--------|
| Source code commands (`get-program`, `get-class`, `get-function-group`, `get-function`, `get-include`, `get-interface`, `get-cds-view`, `get-type-group`) | Plain text ABAP source |
| `get-table`, `get-structure`, `get-type-info`, `get-transaction`, `search-object` | Raw ADT XML |
| `get-package`, `where-used`, `list-transports`, `run-sql` | JSON array |
| `syntax-check` | Plain text messages (`[ERROR]`, `[WARNING]`, `[INFO]` prefixed); `"Syntax OK — no issues found."` if clean |
| `status` | Plain text key-value pairs |

All output is written to **stdout**. Errors are written to **stderr** with a non-zero exit code.

---

## Error Reference

| Error | Cause | Fix |
|-------|-------|-----|
| `Not configured` | No credentials saved | Run `configure` |
| `HTTP 401` | Wrong username or password | Re-run `configure` |
| `HTTP 403` | Missing `SAP_ADT_BASE` role | Ask Basis to assign authorization |
| `HTTP 404` | Object name not found | Try `search-object` to find the correct name |
| `HTTP 503` | `/sap/bc/adt` not active | Ask Basis to activate in `SICF` |
| SSL error | Self-signed certificate | Re-configure with `SAP_VERIFY_SSL=0` |

---

## Security Considerations

- Credentials are stored **in plain text** in `~/.sap-adt-cli/config.json` (permissions `0600`).
  This is consistent with common CLI tools (AWS CLI, Azure CLI). Restrict file access accordingly.
- Avoid passing passwords via `--password` — they appear in shell history and `ps` output.
  Prefer the interactive `configure` wizard or the `SAP_PASSWORD` environment variable.
- Write and transport commands require explicit capability flags (`allow_write`, `allow_transport`)
  plus per-operation `[y/N]` confirmation. Never enable on production systems.
- For shared or CI environments, use short-lived credentials and rotate them regularly.

---

## Changelog

### v1.1.1 — `run-sql` robustness improvements

- **GET → POST fallback**: `run-sql` now first attempts a `GET` request; if the server returns HTTP 405 (Method Not Allowed), it automatically retries as a `POST` with the SQL in the request body — improves compatibility with S/4HANA systems that require `POST` on the Data Preview endpoint
- **Correct XML parser**: `_parse_sql_result` now reads the proper ADT column structure (`<columns>/<metadata name="...">/<dataSet>/<data>`) instead of guessing child element names; the old heuristic is kept as a fallback for older SAP releases
- **Typed `Accept` header**: requests now negotiate `application/vnd.sap.adt.datapreview.table.v1+xml` for more reliable content handling

### v1.1.0 — Capability expansion & rename

- **10 new commands**: `syntax-check`, `get-cds-view`, `get-type-group`, `write-source`, `activate`, `where-used`, `run-sql`, `list-transports`, `create-transport`, `release-transport`
- **Dual-guard write protection**: capability flags (`allow_write` / `allow_transport`) must be enabled in config, AND each destructive operation requires explicit `[y/N]` confirmation at runtime
- **DML-safe SQL**: `run-sql` accepts only `SELECT` statements; `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `MODIFY`, `TRUNCATE` are blocked at the CLI layer regardless of system permissions
- **Renamed** from `sap-abap-cli` to `sap-adt-cli` to better reflect the ADT API scope
- **Config directory** migrated from `~/.sap-abap-cli/` to `~/.sap-adt-cli/`; automatic migration on first run if old config exists

### v1.0.0 — Initial release

- Read-only ADT skill: programs, classes, function modules, function groups, interfaces, includes, DDIC tables/structures/types, packages, transactions, object search

---

## Development Paradigm

This project was built using an AI-native, spec-driven development loop:

1. **Specification** — Requirements and implementation details were worked out through conversations with **Claude Sonnet 4.6**, which produced structured Markdown prompt files encoding the full spec (change scope, acceptance criteria, anti-patterns).
2. **Execution** — The prompt files were handed directly to an agentic coding stack — **[opencode](https://opencode.ai) + [Oh My OpenAgent](https://github.com/oh-my-opencode/oh-my-openagent)** running on a **GitHub Copilot Pro subscription** as the model backend — which planned, implemented, tested, and verified the changes autonomously.
3. **Review** — The human role was limited to deciding *what* to build, reviewing final outputs, and iterating on the spec when something fell short.

The result is a workflow where natural-language intent is refined with **Claude Sonnet 4.6** into precise executable specifications, which are then consumed end-to-end by an agent stack powered by a GitHub Copilot Pro subscription — closing the loop from idea to working code with minimal manual intervention.

> The author is a SAP consultant with over ten years of project experience and no software development background. This project grew from a practical daily need and became a personal experiment in how an AI-native workflow can reshape what domain experts are able to build — shared here in the hope it's useful to others on a similar path.

---

## License

[MIT](../../LICENSE)
