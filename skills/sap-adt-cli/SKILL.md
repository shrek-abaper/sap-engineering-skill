---
name: sap-adt-cli
description: "Read and write ABAP source code and metadata from SAP systems via the ADT REST API.
  Use when the user asks to read, view, analyze, modify, write, or activate ABAP programs,
  classes, function modules, function groups, interfaces, includes, CDS views, DDIC tables,
  structures, data elements, domains, type groups, transactions, or packages.
  Also handles: syntax checking, where-used analysis, Open SQL data preview,
  transport request management (list, create, release), and searching for ABAP objects by name.
  Write and transport operations require explicit capability flags enabled in config,
  AND require user confirmation for every individual operation — confirmation is one-time
  and never reused across operations in the same session.
  On first use, guides the user through SAP credential setup interactively."
---

# SAP ADT CLI Skill

Read ABAP source code and metadata from SAP via `scripts/sap_adt_cli.py`.

## CLI Location

The CLI is `scripts/sap_adt_cli.py` inside this skill's directory.
Resolve the skill directory at runtime using the skill tool's path, then build the CLI path:

```bash
SKILL_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]:-$0}")")"
SAP_CLI="$SKILL_DIR/scripts/sap_adt_cli.py"
python3 "$SAP_CLI" <command> [args]
```

If you already know the absolute path to the skill directory (e.g. from the skill loader), use it directly:

```bash
# Linux / macOS — skill installed via clone + symlink
SAP_CLI="$HOME/.agents/skills/sap-adt-cli/scripts/sap_adt_cli.py"
python3 "$SAP_CLI" <command> [args]
```

```powershell
# Windows — skill installed via setup-opencode-abap-cli.bat (Junction)
$SAP_CLI = "$env:USERPROFILE\.agents\skills\sap-adt-cli\scripts\sap_adt_cli.py"
python "$SAP_CLI" <command> [args]
```

First run auto-installs `click`, `requests`, and `urllib3`. All source code output goes to stdout. Errors go to stderr with exit code 1.

## CRITICAL: Credential Check Before First Command

**Always run this before the first ABAP query in a session:**

```bash
python3 "$SAP_CLI" status
```

### Credentials configured → proceed

Output example:
```
Profile:         dev
URL:             https://my-sap-dev.example.com:8000
Username:        DEVELOPER
Client:          100
Language:        EN
SSL:             verify
Write mode:      DISABLED (global)
Transport write: DISABLED (global)
Config source:   /home/user/.sap-adt-cli/config.json (profile 'dev')
```

Multiple SAP environments (DEV/QAS/PRD) are stored as **profiles**. If the user
mentions a specific environment, check `profile list` and select it:

```bash
python3 "$SAP_CLI" profile list          # shows all profiles, * = active
python3 "$SAP_CLI" profile use prd       # persistent switch
python3 "$SAP_CLI" --profile qas status  # one-off override (global option, BEFORE the command)
```

See [Multiple SAP Environments (Profiles)](#multiple-sap-environments-profiles) below.

### Credentials NOT configured → collect and save non-interactively

You will see:
```
Not configured. Run: python3 sap_adt_cli.py configure
```

Or any ABAP command will print to stderr:
```
SAP credentials not configured.
...
```

**Collect all credentials in a SINGLE `question` tool call** — pass all fields as one array.
Do NOT ask one field at a time; multiple sequential calls create separate UI tabs that can
cause earlier answers to be overwritten before all values are saved.

Fields to ask (all at once):

```
1. SAP System URL   — e.g. https://my-sap.example.com:8000  (include port)
2. SAP Username     — dialog user, e.g. DEVELOPER
3. SAP Password     — SAP logon password
4. SAP Client       — 3-digit number, e.g. 100
5. Skip SSL check?  — yes/no  (yes = self-signed / internal systems, no = production with valid cert)
```

If the user works with multiple SAP systems, also ask for a short environment
name (e.g. `dev`, `qas`, `prd`) and pass it as `--profile NAME`. On the first
ever setup, omitting `--profile` creates and activates a profile named `default`.

**After receiving all answers from the single question call, save the non-secret
fields with one configure command, then store the password in the keystore:**

```bash
python3 "$SAP_CLI" configure --profile dev \
  --url      "https://my-sap-dev.example.com:8000" \
  --username "DEVELOPER" \
  --client   "100" \
  --language "EN"
  # add --no-verify-ssl if user said yes to skipping SSL
python3 "$SAP_CLI" credentials set dev   # hidden prompt; or use the env var below
```

Pass the password via environment variable to avoid shell history exposure
(it is moved into the keystore by `configure` and does not remain in config.json):

```bash
SAP_PASSWORD="mysecret" python3 "$SAP_CLI" configure --profile dev \
  --url "https://my-sap-dev.example.com:8000" \
  --username "DEVELOPER" \
  --client "100"
```

Then verify:

```bash
python3 "$SAP_CLI" status
```

Connection fields are saved as a profile in `~/.sap-adt-cli/config.json`
(permissions 0600); the **password is stored only in the operating system
keystore** (`credentials doctor` shows which backend is active), never as plain
text in the config. An old single-connection or plaintext-password config is
migrated automatically to a profile named `default`, with the password moved
into the keystore.

**To enable write or transport capabilities** (these flags are **GLOBAL** — they
apply to every profile, so a write-enabled setup can also write to PRD; confirm
the active profile before write operations):

```bash
# Interactive — answer prompts for write/transport flags
python3 "$SAP_CLI" configure --profile dev

# Non-interactive — pass flags explicitly
SAP_PASSWORD="mysecret" python3 "$SAP_CLI" configure --profile dev \
  --url "https://sap-dev.example.com:44300" \
  --username "DEVELOPER" \
  --client "400" \
  --allow-write \
  --no-allow-transport
```

| Flag | Default | Controls |
|------|---------|---------|
| `--allow-write` / `--no-allow-write` | disabled | `write-source`, `activate` |
| `--allow-transport` / `--no-allow-transport` | disabled | `create-transport`, `release-transport` |

> **One-time confirmation rule (CRITICAL for agent workflows):**
> Even when capability flags are enabled, every write/create/release operation
> requires an interactive change preview and explicit `[y/N]` confirmation.
> This confirmation applies to the **current operation only** and is immediately
> discarded after use — it is NEVER stored, cached, or reused.
> In the same conversation, if the user asks for another write/create/release
> operation, confirmation must be obtained again from scratch.
> Use `--yes` only when the caller has explicit out-of-band authorization
> (e.g. a trusted CI pipeline). Never pass `--yes` on behalf of the user
> based on a previous confirmation in the same conversation.

> **Security note:** profile passwords are stored in the OS keystore, not in the
> config file. Backend priority is `env` (`SAP_ADT_<PROFILE>_PASSWORD`) →
> `keyring` (Credential Manager / Keychain / Secret Service) → `dpapi` (WSL2) →
> `pass` (GPG) → `file` (scrypt+Fernet fallback with a master passphrase).
> Inform users: stored passwords are **not portable across machines** (DPAPI /
> Keychain binding) — re-run `credentials set <profile>` after moving machines.
> There is no export command, and `-v/--verbose` output and error tracebacks
> stay redacted. Commands: `credentials set|forget|status|doctor`; global
> `--keystore <name>` forces a backend fail-closed.

**Alternative A — SKILL-local `.env`** (recommended for per-skill isolation):

```bash
cp "$(dirname "$SAP_CLI")/../.env.example" "$(dirname "$SAP_CLI")/../.env"
# edit .env and fill SAP_URL, SAP_USERNAME, SAP_PASSWORD, SAP_CLIENT
python3 "$SAP_CLI" status
```

**Alternative B — env vars per invocation** (no file written, useful for one-off sessions):

```bash
SAP_URL="https://..." SAP_USERNAME="USER" SAP_PASSWORD="pass" SAP_CLIENT="100" python3 "$SAP_CLI" status
```

Credential precedence is: process env vars > SKILL-local `.env` > selected profile in
`~/.sap-adt-cli/config.json`. When the four `SAP_*` connection variables are all
present they override profiles entirely (single-environment override layer); the
optional `SAP_PROFILE` variable only selects which profile is used otherwise.
Capability flags map to `SAP_ALLOW_WRITE` and `SAP_ALLOW_TRANSPORT`; keep both `0`
unless the user explicitly authorizes write or transport operations.

---

## Multiple SAP Environments (Profiles)

Profiles store one connection (URL/username/client/language/SSL) per SAP
system in `config.json`; the per-profile password lives in the keystore.
Write/transport capability switches are **global**, not per profile.

```bash
# Configure environments (each becomes the active profile when saved)
python3 "$SAP_CLI" configure --profile dev --url "https://sap-dev..." --username ... --client 100
SAP_PASSWORD="..." python3 "$SAP_CLI" configure --profile prd --url "https://sap-prd..." --username ... --client 200

# See every environment; * marks the active one
python3 "$SAP_CLI" profile list

# Persistent switch (remembered in config.json)
python3 "$SAP_CLI" profile use prd

# One-off switch for a single command (global option goes BEFORE the command name)
python3 "$SAP_CLI" --profile dev get-program SAPMV45A
SAP_PROFILE=qas python3 "$SAP_CLI" get-program SAPMV45A

# Remove an environment (the active profile cannot be removed)
python3 "$SAP_CLI" profile remove qas
```

Profile selection order (highest first): `--profile` flag > `SAP_PROFILE` env var
> `active_profile` in config.json (set by `profile use`). When exactly one profile
exists it is used even if `active_profile` is unset.

**Agent rules:**

- When the user names an environment ("在 QAS 看一下 / check in PRD"), run
  `profile list` first if unsure, then either `profile use NAME` (whole session in
  one system) or prefix individual commands with `--profile NAME`.
- Show the target profile in your response before/after write operations — the
  capability flags are global, so a write-enabled session pointed at PRD is
  dangerous. When in doubt, run `status` and read the `Profile:` line.
- Editing a profile with the wizard and leaving the password blank keeps the
  previously stored password.
- `.env` / `SAP_*` environment variables override profiles completely; if
  `status` shows `Config source: ... environment ...`, profile switching has no
  effect until the override is removed.

---

## Commands Quick Reference

| Command | Usage | Description |
|---------|-------|-------------|
| `configure` | `configure [--profile NAME]` | Interactive wizard (or flags) for one environment profile |
| `profile list` | `profile list` | List all SAP environments (`*` = active) |
| `profile use` | `profile use <NAME>` | Persistently switch the active environment |
| `profile remove` | `profile remove <NAME>` | Delete an environment (active one is protected) |
| `status` | `status` | Show active profile + connection config |
| _global option_ | `--profile NAME <command>` | One-off profile override, placed **before** the command name |
| `get-program` | `get-program <NAME>` | ABAP program (report) source code |
| `get-class` | `get-class <NAME>` | ABAP class source code |
| `get-function-group` | `get-function-group <NAME>` | Function group top-include source |
| `get-function` | `get-function <NAME> --group <FG>` | Function module source code |
| `get-include` | `get-include <NAME>` | ABAP include source code |
| `get-interface` | `get-interface <NAME>` | ABAP interface source code |
| `get-table` | `get-table <NAME>` | DDIC table field definitions |
| `get-structure` | `get-structure <NAME>` | DDIC structure definition |
| `get-type-info` | `get-type-info <NAME>` | Domain or data element (tries domain first) |
| `get-package` | `get-package <NAME>` | Package object list → JSON array |
| `get-transaction` | `get-transaction <NAME>` | Transaction properties/package info |
| `search-object` | `search-object <QUERY> [--max-results N]` | Quick object search (`*` wildcard) |
| `syntax-check` | `syntax-check <TYPE> <NAME> [--group <FG>]` | ABAP syntax check — no system change |
| `get-cds-view` | `get-cds-view <NAME>` | CDS View DDL source code |
| `get-type-group` | `get-type-group <NAME>` | ABAP type group (TYPE POOL) source |
| `write-source` | `write-source <TYPE> <NAME> --file <PATH>` | Write source code *(allow_write + confirm each time)* |
| `activate` | `activate <TYPE> <NAME>` | Activate ABAP object *(allow_write + confirm each time)* |
| `where-used` | `where-used <TYPE> <NAME> [--max-results N]` | Where-used list → JSON array |
| `run-sql`           | `run-sql "<SQL>" [--max-rows N]`               | Open SQL SELECT → JSON; DML statements are blocked      |
| `list-transports` | `list-transports [--user U] [--status D\|R]` | List transport requests → JSON |
| `create-transport` | `create-transport --description "<DESC>"` | Create transport request *(allow_transport + confirm each time)* |
| `release-transport` | `release-transport <TRKORR> [--yes]` | Release transport — irreversible *(allow_transport + confirm each time)* |

---

## Usage Examples

```bash
SAP_CLI="<skill_dir>/scripts/sap_adt_cli.py"

# Source code
python3 "$SAP_CLI" get-program SAPMV45A
python3 "$SAP_CLI" get-class ZCL_MY_CLASS
python3 "$SAP_CLI" get-function BAPI_SALESORDER_CREATEFROMDAT2 --group BAPI_SD_SALESORDER
python3 "$SAP_CLI" get-include MV45AFZZ
python3 "$SAP_CLI" get-interface ZIF_MY_INTERFACE

# Dictionary
python3 "$SAP_CLI" get-table VBAK
python3 "$SAP_CLI" get-structure VBAKKOM
python3 "$SAP_CLI" get-type-info MATNR

# Discovery
python3 "$SAP_CLI" search-object "ZCL_*" --max-results 20
python3 "$SAP_CLI" get-package ZMYPACKAGE
python3 "$SAP_CLI" get-transaction VA01

# CDS View & Type Group (read-only)
python3 "$SAP_CLI" get-cds-view ZI_INVENTORY_POSITION
python3 "$SAP_CLI" get-type-group ICON

# Write & activate (requires allow_write + confirmation each time)
python3 "$SAP_CLI" write-source class ZCL_MY_CLASS --file /tmp/zcl.abap
python3 "$SAP_CLI" write-source class ZCL_MY_CLASS --file /tmp/zcl.abap --activate
cat updated.abap | python3 "$SAP_CLI" write-source class ZCL_MY_CLASS --file -
python3 "$SAP_CLI" write-source class ZCL_MY_CLASS --file /tmp/zcl.abap --yes  # skip confirm (trusted automation only)
python3 "$SAP_CLI" activate class ZCL_MY_CLASS

# Where-used (read-only)
python3 "$SAP_CLI" where-used class ZCL_PAYMENT_PROCESSOR --max-results 50
python3 "$SAP_CLI" where-used interface ZIF_MY_INTERFACE

# Open SQL via Data Preview (read-only)
python3 "$SAP_CLI" run-sql "SELECT * FROM t001 UP TO 10 ROWS"
python3 "$SAP_CLI" run-sql "SELECT bukrs, butxt FROM t001 WHERE spras = 'EN'" --max-rows 200

# Multi-environment profiles
python3 "$SAP_CLI" profile list                           # show environments, * = active
python3 "$SAP_CLI" profile use qas                        # switch persistently
python3 "$SAP_CLI" --profile prd status                   # one-off override (before command)
SAP_PROFILE=dev python3 "$SAP_CLI" get-program SAPMV45A   # one-off override (env var)

# Transport management
python3 "$SAP_CLI" list-transports                        # read-only — no flag needed
python3 "$SAP_CLI" list-transports --user SHREK --status D
python3 "$SAP_CLI" create-transport --description "Fix rounding issue"   # allow_transport + confirm
python3 "$SAP_CLI" release-transport DEVK900001           # allow_transport + confirm (irreversible warning)
python3 "$SAP_CLI" release-transport DEVK900001 --yes     # skip confirm (trusted automation only)
```

---

## Key Behaviors & Gotchas

- **Object names**: SAP names are case-insensitive but always use **UPPERCASE** for reliability (e.g. `VBAK`, `ZCL_MY_CLASS`, not `vbak`)
- **Source output**: `get-program`, `get-class`, `get-function`, etc. return raw ABAP source text
- **XML output**: `get-table`, `get-structure`, `get-type-info`, `get-transaction`, `search-object` return raw XML from ADT — parse it or read it as-is
- **JSON output**: `get-package` is the only command that returns a parsed JSON array
- **`get-type-info` fallback**: tries domain first; if not found, falls back to data element
- **SSL**: for internal SAP systems with self-signed certs, configure with SSL disabled (`SAP_VERIFY_SSL=0` or answer "n" in wizard)
- **Session reuse**: the HTTP session is reused within a single script invocation; each `python3 "$SAP_CLI" ...` call starts fresh
- **Credentials precedence**: complete-connection env vars (`SAP_URL/USERNAME/PASSWORD/CLIENT`, process env > SKILL-local `.env`) override profiles entirely; otherwise non-secret fields come from the selected profile in `~/.sap-adt-cli/config.json` and the password from the keystore, where `SAP_ADT_<PROFILE>_PASSWORD` (`env` backend) wins over other backends; profile picks `--profile` > `SAP_PROFILE` > `active_profile`
- **Profiles vs. env override**: a complete set of `SAP_URL/USERNAME/PASSWORD/CLIENT` in env or `.env` bypasses all profiles; `status` shows the source it used — switching profiles has no effect while that override exists
- **Keystore management**: `credentials status` (configured/not-configured per profile, never the secret), `credentials doctor` (active backend, file modes, entries), `credentials set/forget`; run `doctor` when a user reports credential problems before debugging ADT calls
- **Global capability flags**: `allow_write` / `allow_transport` are global, not per profile; check `Profile:` and the switches in `status` before any write to a production-like system
- **Capability flags — config layer**: `write-source` and `activate` require `allow_write: true`;
  `create-transport` and `release-transport` require `allow_transport: true`.
  Run `configure` to enable. `list-transports` is read-only and has no flag requirement.
- **One-time confirmation — execution layer**: every write/create/release operation
  shows a change preview and requires `[y/N]` confirmation before executing.
  This confirmation is **scoped to the current operation only** — it is immediately
  discarded after use and never cached or reused within the same session.
  The next write/create/release in the same session requires a fresh confirmation.
- **Agent rule — never reuse confirmation**: when operating as an AI agent,
  do not infer that a previous confirmation covers subsequent operations.
  Every invocation of a write-capable command is independent.
  Pass `--yes` only with explicit user instruction for that specific call.
- **`write-source` lock protocol**: flow is lock → PUT → unlock; unlock runs in
  `finally` so objects are never left locked after an error.
- **`release-transport` is irreversible**: once released, a transport cannot be
  recalled. The confirmation preview explicitly calls this out.
- **`run-sql` Open SQL only**: uses ADT Data Preview; accepts SAP Open SQL syntax
  (e.g. `UP TO N ROWS`), not Native SQL or JDBC-style syntax.
- **`run-sql` DML blocked**: statements starting with `INSERT`, `UPDATE`, `DELETE`,
  `MODIFY`, or `TRUNCATE` are unconditionally rejected in this version.
  Only `SELECT` statements are permitted. Detection is by first keyword,
  case-insensitive — `SELECT` containing write keywords in values is safe.
- **`where-used` empty result**: returns `[]` — not an error (exit 0).
- **`get-cds-view` name**: use the CDS entity name (e.g. `ZI_INVENTORY_POSITION`),
  not the underlying database table name.
- **`syntax-check` with function**: requires `--group <FG>` (same as `get-function`).

---

## Output Format

| Command | Output Format |
|---------|---------------|
| Source code commands (`get-program`, `get-class`, `get-function`, `get-include`, `get-interface`, `get-cds-view`, `get-type-group`) | Plain text ABAP source |
| `get-table`, `get-structure`, `get-type-info`, `get-transaction`, `search-object` | Raw XML |
| `get-package`, `where-used`, `list-transports`, `run-sql` | JSON array |
| `syntax-check` | Plain text messages (`[ERROR]`, `[WARNING]`, `[INFO]` prefixed); `"Syntax OK"` if clean |
| `status` | Plain text key-value pairs |

---

## Error Handling

| Error Output | Cause | Action |
|--------------|-------|--------|
| `Not configured` | No saved credentials | Guide user through `configure` |
| `Profile 'x' not found` | `--profile`/`SAP_PROFILE` names an unknown profile | Run `profile list`, or `configure --profile x` to create it |
| `is currently active` on remove | Tried to remove the active profile | `profile use <other>` first, then remove |
| `HTTP 401` | Wrong username/password | Ask user to re-run `configure` or `credentials set <profile>` |
| `no password ... in the keystore` | Profile has no stored password | Run `credentials set <profile>` or `credentials doctor` |
| `HTTP 403` | Missing ADT authorization | User needs `SAP_ADT_BASE` role or equivalent |
| `HTTP 404` | Object name not found | Try `search-object` to find the correct name |
| `HTTP 503` | ADT service not active | SAP Basis must activate `/sap/bc/adt` in transaction SICF |
| SSL error | Certificate issue | Re-configure with `SAP_VERIFY_SSL=0` |

---

## Workflows

**Read an unknown class:**
```bash
python3 "$SAP_CLI" search-object "ZCL_ORDER*"
python3 "$SAP_CLI" get-class ZCL_ORDER_HANDLER
```

**Explore a package:**
```bash
python3 "$SAP_CLI" get-package ZMYPACKAGE
# → JSON list of all objects; pick the ones you need
python3 "$SAP_CLI" get-program ZMYREPORT
python3 "$SAP_CLI" get-class ZCL_MYCLASS
```

**Look up a BAPI signature:**
```bash
python3 "$SAP_CLI" get-function BAPI_SALESORDER_CREATEFROMDAT2 --group BAPI_SD_SALESORDER
```

**Understand a table structure:**
```bash
python3 "$SAP_CLI" get-table VBAK
python3 "$SAP_CLI" get-type-info VBELN   # look up field type
```

**Find a transaction's package/application:**
```bash
python3 "$SAP_CLI" get-transaction VA01
```

---

**Safe write workflow — syntax-check before writing:**
```bash
python3 "$SAP_CLI" syntax-check class ZCL_MY_CLASS
# → fix any errors locally, then:
python3 "$SAP_CLI" write-source class ZCL_MY_CLASS --file ./zcl_my_class.abap --activate
# → preview shown, confirmation required; confirmation discarded after use
```

**Find all usages of an interface:**
```bash
python3 "$SAP_CLI" where-used interface ZIF_MY_INTERFACE --max-results 100
# → JSON list of all implementing/using objects
```

**Quick data check without SE16N:**
```bash
python3 "$SAP_CLI" run-sql "SELECT COUNT(*) AS CNT FROM ekko WHERE bstyp = 'F'"
```

**Create and release a transport (two separate confirmations):**
```bash
python3 "$SAP_CLI" create-transport --description "Sprint 12 — invoice fix"
# → preview shown, confirmation #1 required → Created transport: DEVK900042
python3 "$SAP_CLI" list-transports --status D
# → JSON list (read-only, no confirmation)
python3 "$SAP_CLI" release-transport DEVK900042
# → irreversible-warning preview shown, confirmation #2 required (fresh, not reused)
```

---

## SAP Prerequisites

- ADT services active: transaction `SICF` → path `/sap/bc/adt` → Activate
- User authorization: role `SAP_ADT_BASE` or objects `S_ADT_RES`, `S_RFC`
- **Write & activate** (`write-source`, `activate`): requires `allow_write: true` in config.
  SAP user additionally needs `S_DEVELOP` with `ACTVT=02` on relevant object types.
- **Transport management** (`create/release-transport`): requires `allow_transport: true` in config.
  SAP user needs `S_CTS_ADMI` or equivalent transport authorization.
  `list-transports` is read-only and needs no additional flag.
- **Data Preview** (`run-sql`): requires `/sap/bc/adt/datapreview` active in transaction SICF.
