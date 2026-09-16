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

Core dependencies (`click`, `requests`, `urllib3`) are installed automatically on first run.
Keystore backends are optional: `pip install keyring` for desktop OS vaults,
`pip install cryptography` for the encrypted-file fallback (WSL2 needs neither —
it uses Windows DPAPI directly). See [Credential storage](#credential-storage-keystore).

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

Connection details are stored per environment profile in
`~/.sap-adt-cli/config.json` (non-secret fields only), while **passwords are
stored in the operating system keystore** — never as plain text. Multiple SAP
systems (DEV/QAS/PRD) are supported as named profiles — see
[Credential storage](#credential-storage-keystore) and
[Multiple SAP environments](#multiple-sap-environments-profiles).

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

# 2. Configure credentials (interactive wizard — password is not echoed and is
#    saved to the OS keystore; add more systems later with: configure --profile qas / prd)
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

Credential lookup order is:

1. Process environment variables
2. `skills/sap-adt-cli/.env`
3. The selected profile in `~/.sap-adt-cli/config.json` (non-secret fields)
   and its password in the OS keystore — see [Credential storage](#credential-storage-keystore)

### Multiple SAP environments (profiles)

Each SAP system is stored as a named profile in `~/.sap-adt-cli/config.json`
(non-secret fields; the password goes to the keystore). The first `configure`
run creates a profile called `default`; an old single-connection config is
migrated automatically:

```bash
CLI="python3 skills/sap-adt-cli/scripts/sap_adt_cli.py"

# Add environments (each saved profile becomes the active one)
$CLI configure --profile dev --url "https://sap-dev:8000" --username DEV --client 100
$CLI credentials set dev                       # then store the password (hidden prompt)
SAP_PASSWORD="..." $CLI configure --profile prd --url "https://sap-prd:8000" --username PRD --client 200
                                               # ^ SAP_PASSWORD is moved into the keystore, not left in config.json

# List environments; * marks the active profile
$CLI profile list

# Persistent switch
$CLI profile use dev

# One-off override: global --profile (before the command) or SAP_PROFILE env var
$CLI --profile prd get-program SAPMV45A
SAP_PROFILE=qas $CLI status

# Remove an environment (the active profile cannot be removed)
$CLI profile remove qas
```

Profile selection order: `--profile` > `SAP_PROFILE` > the active profile set by
`profile use`. Note the write/transport capability switches are **global** — they
apply to every profile, including production.

> A complete set of `SAP_URL/USERNAME/PASSWORD/CLIENT` environment variables (or a
> SKILL-local `.env`) overrides all profiles. Run `status` to see which source is
> actually used.

### SKILL-local `.env` (recommended for per-skill isolation)

```bash
cp skills/sap-adt-cli/.env.example skills/sap-adt-cli/.env
# edit skills/sap-adt-cli/.env and fill SAP_URL, SAP_USERNAME, SAP_PASSWORD, SAP_CLIENT
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py status
```

Never commit the real `.env` file.

### Interactive wizard

```bash
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure
```

Connection fields are saved as a profile (the wizard asks for a profile name) in
`~/.sap-adt-cli/config.json` (`0600`); the password goes to the selected
keystore. Re-running the wizard for an existing profile and leaving the
password blank keeps the stored password.

### Credential storage (keystore)

Passwords are stored **only** through pluggable keystore backends, selected by
real capability probing rather than by operating system. Priority order:

| # | Backend | Environment | Setup needed | One-time configuration |
|---|---------|-------------|--------------|------------------------|
| 1 | `env` | containers / CI / any | none | `export SAP_ADT_<PROFILE>_PASSWORD=...` (read-only) |
| 2 | `keyring` | native Windows, macOS, Linux desktop | `pip install keyring` (Credential Manager / Keychain / Secret Service) | none |
| 3 | `dpapi` | **WSL2** | none — uses Windows DPAPI via `powershell.exe` interop | none |
| 4 | `pass` | headless Linux with GPG | [`pass`](https://www.passwordstore.org/) initialized (`pass init`) | none |
| 5 | `file` | last-resort fallback, all platforms | `pip install cryptography` | a master passphrase (prompted, or `SAP_ADT_MASTER_PASSPHRASE`) |

There is deliberately no `credentials export` command. Diagnose the active
backend with:

```bash
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py credentials doctor
# force a specific backend (fail-closed: an unavailable choice errors out)
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py --keystore file credentials status
```

Manage stored passwords:

```bash
CLI="python3 skills/sap-adt-cli/scripts/sap_adt_cli.py"
$CLI credentials set dev          # prompts with hidden input + confirmation
$CLI credentials status           # configured / not configured per profile — never prints secrets
$CLI credentials forget dev       # purge from all writable backends
```

> **Keystore-bound secrets are not portable.** DPAPI blobs are tied to the
> Windows account and Keychain entries to the macOS login; copying
> `secrets.json`/the config to another machine or user cannot decrypt them.
> Re-running `credentials set` on the new machine is expected behavior, not a bug.
>
> **Migration from older versions:** a config that still contains plaintext
> passwords is migrated automatically on first run — the passwords move into
> the selected keystore, the fields are stripped from `config.json` (no backup
> copy is created), and you are advised to change those passwords on the SAP
> side because they previously sat on disk unencrypted.

### Environment variables

Useful for CI/CD pipelines or one-off sessions. The complete-connection
variables take precedence over both the SKILL-local `.env` and saved profiles.

```bash
export SAP_URL=https://my-sap.example.com:8000
export SAP_USERNAME=MYUSER
export SAP_PASSWORD=secret          # complete-connection override; prefer over the --password flag
export SAP_CLIENT=100
export SAP_PROFILE=dev              # optional: select a profile (ignored when SAP_URL..SAP_CLIENT are all set)
export SAP_LANGUAGE=EN              # optional, default: EN
export SAP_VERIFY_SSL=0             # optional: set 0 for self-signed certificates
export SAP_ALLOW_WRITE=0            # optional: set 1 to enable write-source/activate
export SAP_ALLOW_TRANSPORT=0        # optional: set 1 to enable create/release transport

# Per-profile password for the 'env' keystore (profile 'dev' -> variable SAP_ADT_DEV_PASSWORD)
export SAP_ADT_DEV_PASSWORD=secret
# Master passphrase for the 'file' keystore in non-interactive runs
export SAP_ADT_MASTER_PASSPHRASE=...
```

### Capability flags (default: disabled)

Two optional flags unlock write and transport capabilities.
**Enable only when needed — they are GLOBAL and apply to every profile, including
production.** Check `status` (which shows the active profile and both switches)
before write operations.

```bash
# Enable interactively (answer 'y' to the write/transport prompts)
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure --profile dev

# Enable non-interactively
SAP_PASSWORD="secret" python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure --profile dev \
  --url "https://sap-dev.example.com:44300" \
  --username "DEVELOPER" \
  --client "400" \
  --allow-write \
  --no-allow-transport
```

| Flag | Config field (global, all profiles) | Default | Commands unlocked |
|------|-------------|---------|-------------------|
| `--allow-write` | `allow_write` | false | `write-source`, `activate` |
| `--allow-transport` | `allow_transport` | false | `create-transport`, `release-transport` |

**Confirmation policy**: even when flags are enabled, every write/create/release
operation shows a change preview and requires explicit `[y/N]` confirmation.
The confirmation applies to the current operation only — it is discarded immediately
after use and must be repeated for each subsequent operation.

### Non-interactive flags (agent / automation workflows)

```bash
# Pass password via environment variable to avoid shell history exposure.
# configure stores it in the keystore; it does not remain in config.json.
SAP_PASSWORD="secret" python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure --profile dev \
  --url      "https://my-sap.example.com:8000" \
  --username "MYUSER" \
  --client   "100"
```

At runtime, CI can instead provide the password per profile via
`SAP_ADT_<PROFILE>_PASSWORD` (read-only `env` backend), or use
`--keystore file` together with `SAP_ADT_MASTER_PASSPHRASE`.

---

## Commands

| Command | Description |
|---------|-------------|
| `configure [--profile NAME]` | Save credentials for one environment profile (wizard or flags) |
| `profile list` | List all configured environments (`*` = active) |
| `profile use <NAME>` | Persistently switch the active environment |
| `profile remove <NAME>` | Delete an environment (active profile is protected) and purge its password |
| `credentials set <NAME>` | Store a profile password in the keystore (hidden prompt) |
| `credentials forget <NAME>` | Purge a profile password from writable keystores |
| `credentials status` | Show configured/not-configured per profile (never prints passwords) |
| `credentials doctor` | Diagnose backends, selected backend, files and entries |
| `status` | Show active profile and current connection configuration |
| `--profile NAME <command>` | Global option: one-off profile override for a single command |
| `--keystore <env\|keyring\|dpapi\|pass\|file> <command>` | Global option: force the credential backend (fail-closed if unavailable) |
| `-v, --verbose` | Verbose logging (secrets are always redacted) |
| `get-program <NAME>` | ABAP program / report source code |
| `get-class <NAME>` | ABAP class source code |
| `get-function-group <NAME>` | Function group top-include source code |
| `get-function <NAME> --group <FG>` | Function module source code |
| `get-include <NAME>` | ABAP include source code |
| `get-interface <NAME>` | ABAP interface source code |
| `get-table <NAME>` | DDIC table fields — `fields` envelope (DDL on S/4) |
| `get-structure <NAME>` | DDIC structure fields — `fields` envelope |
| `get-type-info <NAME>` | Domain/data element — `scalar` envelope (`resolved_as`) |
| `get-type-group <NAME>` | ABAP type group (TYPE POOL) source |
| `get-cds-view <NAME>` | CDS View DDL source code |
| `get-package <NAME>` | Package objects — `objects` envelope |
| `get-transaction <NAME>` | Transaction properties — `scalar` envelope |
| `search-object <QUERY> [--max-results N]` | Object name search — `*` wildcard supported |
| `syntax-check <TYPE> <NAME> [--group <FG>]` | Syntax check — read-only, no confirmation; `--group` required when TYPE is `function` |
| `where-used <TYPE> <NAME> [--max-results N] [--group <FG>]` | Where-used list — `objects` envelope; `--group` required when TYPE is `function` |
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

## Output contract

All read commands emit the JSON envelope documented in **SKILL.md**
(`ok`/`format_version`/`command`/`object`/`kind`/`data`/`meta`); source
commands default to plain ABAP text and every kind defaults to JSON. Kinds:
`source`, `fields`, `objects`, `rows`, `records`, `findings`, `scalar`.
`-f/--format json|text|xml` (`SAP_ADT_FORMAT`) selects the format; `xml`
returns the raw ADT payload. Empty results are `ok:true,row_count:0,exit 0`.

Errors are JSON envelopes on **stderr** with exit tiers 1 (retryable),
2 (config/credentials), 3 (safety-policy refusal — no retry), 4 (not found);
`status`/`profile`/`credentials` remain human-readable text. See SKILL.md for
all 16 error codes.

---

## Error Reference

| Error | Cause | Fix |
|-------|-------|-----|
| `Not configured` | No credentials saved | Run `configure` |
| `Profile 'x' not found` | Unknown profile on `--profile` / `SAP_PROFILE` | Run `profile list` or `configure --profile x` |
| `is currently active` on remove | Active profile cannot be removed | `profile use <other>` first |
| `HTTP 401` | Wrong username or password | Re-run `configure` or `credentials set <profile>` |
| `no password ... in the keystore` | Profile has no stored password | `credentials set <profile>` (or `credentials doctor`) |
| `HTTP 403` | Missing `SAP_ADT_BASE` role | Ask Basis to assign authorization |
| `HTTP 404` | Object name not found | Try `search-object` to find the correct name |
| `HTTP 503` | `/sap/bc/adt` not active | Ask Basis to activate in `SICF` |
| SSL error | Self-signed certificate | Re-configure with `SAP_VERIFY_SSL=0` |

---

## Security Considerations

- **Passwords are never stored in plain text.** `~/.sap-adt-cli/config.json` keeps only
  non-secret connection fields (URL, username, client, language, TLS flags); the password
  lives in the OS keystore (DPAPI in WSL, Credential Manager, Keychain, Secret Service,
  GPG `pass`, or the passphrase-encrypted fallback file). Run `credentials doctor` to see
  which backend is active. Old plaintext configs are migrated automatically and stripped.
- DPAPI/Keychain-bound secrets **cannot be copied to another machine or user** — set them
  again after moving machines. Do not commit `secrets.json`, `secrets.enc` or any `.env`
  file; the config directory itself should stay on the native filesystem (WSL `/mnt/c`
  makes chmod ineffective — `credentials doctor` warns about this).
- Avoid passing passwords via `--password` — they appear in shell history and `ps` output.
  Prefer the interactive `configure`/`credentials set` prompts, `SAP_ADT_<PROFILE>_PASSWORD`
  or the `SAP_PASSWORD` environment variable.
- Log output (including `-v/--verbose`) and HTTP error tracebacks redact `Authorization`
  headers and password literals; there is no `credentials export` command by design.
- Write and transport commands require explicit capability flags (`allow_write`, `allow_transport`)
  plus per-operation `[y/N]` confirmation. Never enable on production systems.
- For shared or CI environments, use short-lived credentials and rotate them regularly.
- Optional dependencies stay optional: `pip install keyring` for desktop vaults,
  `pip install cryptography` for the encrypted-file fallback (the `[file]` extra).
  The core CLI remains dependency-light.

---

## Changelog

### v1.3.0 — Keystore credential storage

- **No more plaintext passwords**: profile passwords move to pluggable OS keystore backends
  (`env` → `keyring` → `dpapi` → `pass` → `file`); `config.json` keeps non-secret fields only
- **WSL2**: Windows DPAPI via `powershell.exe` interop, secret passed over stdin (never argv)
- **Automatic one-way migration** of existing plaintext configs on first run, with a
  password-rotation warning; idempotent and creates no backup copies
- **New commands**: `credentials set|forget|status|doctor`; new global options `--keystore`, `-v/--verbose`
- **Leak hardening**: masked credential/config reprs, redacting log filter, sanitized
  HTTP errors (no Authorization header in tracebacks), per-process decryption cache
- Plaintext `keyrings.alt` (incl. PlaintextKeyring) and chainer backends are rejected
  as insecure

### v1.2.0 — Multi-environment profiles

- **Multiple SAP environments in one config**: `~/.sap-adt-cli/config.json` now stores named profiles (`dev`, `qas`, `prd`, ...); old single-connection configs are migrated automatically to a `default` profile
- **New commands**: `configure --profile NAME`, `profile list`, `profile use NAME` (persistent switch), `profile remove NAME`
- **One-off profile override**: global `--profile NAME` option (before the command name) or `SAP_PROFILE` env var; selection order is `--profile` > `SAP_PROFILE` > active profile
- **Capability flags are global**: `allow_write` / `allow_transport` now apply to every profile — check `status` before write operations
- **Wizard UX**: prompts for a profile name; re-editing a profile with a blank password keeps the stored password
- `.env` / `SAP_*` environment variables remain a single-environment override layer that wins over all profiles

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

## License

[MIT](../../LICENSE)
