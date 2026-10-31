# sap-adt-cli

<!-- BEGIN GENERATED cli-setup -->
<!-- GENERATED from docs/installation/runtime-setup.md + compatibility.json by tools/sync_skill_runtime_docs.py — do not edit; run the tool to refresh -->

Online operations need the `sap-adt` CLI. Compatible CLI range: `>=1.5.0,<2.0.0`.
Install/readiness guide: [`references/setup.md`](references/setup.md).
<!-- END GENERATED cli-setup -->

[English](README.md) | [中文](README.zh-CN.md)

A command-line tool and AI agent skill for reading **and writing** ABAP source code, metadata,
and transport requests from SAP systems via the [ADT (ABAP Development Tools) REST API](https://help.sap.com/docs/abap-cloud/abap-development-tools-user-guide/about-abap-development-tools).

Supports programs, classes, function modules, interfaces, includes, CDS views, DDIC objects,
packages, transactions, SQL queries, where-used analysis, syntax checks, and transport management —
all from the terminal or from within an AI agent workflow. Write and transport operations require
explicit capability flags and per-operation confirmation.

CLI 1.6.0 adds **ADT diagnostic feeds, per-part object history,
version differences and transport object differences**.
Confirm command availability with `sap-adt --help`
and `sap-adt transport diff --help`. They are read-only and need no write flags.
See [diagnostics and change analysis](references/diagnostics-history.md) for
comparison baselines, evidence gaps and the real-system verification scope.
CLI 1.6.0 also adds explicit CLI updates: see [updating](references/updating.md).
The command never silently changes installation channels.

CLI 1.6.1 adds **Unit failure evidence, test-include source reads and dump
details**. The Skill connects these primitives into diagnosis, not automatic
repair. See [test failure diagnosis](references/test-failure-diagnosis.md).
An empty Unit result is not a pass; `--require-tests` makes it fail the gate.
Use the same commands with Python or an npm-installed native runtime.

CLI 1.6.2 makes **`write-source` a verified write**: baseline and upload
hash binding, in-lock baseline re-check, readback, guaranteed unlock and
optional activation with active-version readback. Each stage reports
`accepted` / `verified` / `failed` / `unknown`; unknown or partial outcomes
exit non-zero and are never retried or rolled back by writing old source.
`--yes` requires `--expect-baseline-sha256` and skips only the prompt.

---

## Requirements

- The `sap-adt` CLI, installed once (see [references/setup.md](references/setup.md)):
  - npm: `npm install -g "sap-adt-cli@^1.5.0"` (provides the `sap-adt` command) — Node.js ≥ 18, no Python. npx also works (`npx "sap-adt-cli@^1.5.0" install`) but keeps no PATH command, so prefix later calls with `npx "sap-adt-cli@^1.5.0"`
  - PyPI: `pip install "sap-adt-cli>=1.5.0,<2.0.0"` — Python ≥ 3.10
  - Linux portable archive from the release page (no Python/Node)
- A SAP system (on-premise ECC / S/4HANA, or BTP ABAP) with ADT services activated
- A SAP dialog user with the `SAP_ADT_BASE` role (or equivalent)

There is **no first-run auto-install** of dependencies. Core runtime dependencies are
`click`, `requests`, `urllib3`; keystore backends are optional: the `keyring` extra for
desktop OS vaults and the `file` extra (cryptography) for the encrypted-file fallback
(WSL2 needs neither — it uses Windows DPAPI directly). See
[Credential storage](#credential-storage-keystore).

---

## Using this skill with an AI agent

`sap-adt-cli` is a standard Agent Skill (`SKILL.md`) folder. Install the CLI from
the Requirements section, then load the skill with your agent:

| Agent | How to use it |
|-------|---------------|
| Claude Code | Install the plugin from the [repository](https://github.com/shrek-abaper/sap-engineering-skill) |
| Codex | Copy the complete skill folder into the directory Codex scans |
| WorkBuddy | Same folder copy |
| Other `SKILL.md` agents | Use the agent's own skill directory or import UI |

The agent drives the workflow; the `sap-adt` CLI performs the online ADT calls.
On Windows x64, CLI 1.5.3 or newer provides an npm runtime, portable ZIP
and unsigned desktop installer; Python ≥ 3.10 users can also use PyPI.
Copy the skill folder into your agent's skill directory separately.
See the [Windows guide](https://github.com/shrek-abaper/sap-engineering-skill/blob/main/docs/installation/windows.md)
for the verified silent-install scope and remaining GUI/PATH/elevation gaps.
CLI 1.6.0 adds experimental macOS 15+ npm/portable runtimes for Intel and
Apple Silicon, gated by native CI build/install checks. Personal Macs,
older macOS, Keychain, Gatekeeper/signing and live SAP on macOS remain
unverified; see [references/setup.md](references/setup.md).

> **Data compliance note:** ABAP source code may contain core business logic and sensitive data.
> Before sending code to cloud-based AI services, confirm compliance with your organization's
> data security policy. For sensitive environments, consider an internally-hosted model.

---

## Quickstart

```bash
# 1. Install the CLI once (pick one channel; details in references/setup.md)
pip install "sap-adt-cli>=1.5.0,<2.0.0"            # Python ≥ 3.10
# or: npm install -g "sap-adt-cli@^1.5.0" && sap-adt install   # Node.js ≥ 18, no Python
#     (npx: npx "sap-adt-cli@^1.5.0" install, then npx "sap-adt-cli@^1.5.0" <command>)

# 2. Configure credentials (interactive wizard — password is not echoed and is
#    saved to the OS keystore; add more systems later with: configure --profile qas / prd)
sap-adt configure

# 3. Verify the connection
sap-adt status

# 4. Start reading ABAP objects
sap-adt get-program SAPMV45A
sap-adt get-class ZCL_MY_CLASS
sap-adt get-function BAPI_SALESORDER_CREATEFROMDAT2 --group BAPI_SD_SALESORDER
```

---

## Configuration

Credential lookup order is:

1. Process environment variables
2. Dotenv file declared by `SAP_ADT_DOTENV`
3. The selected profile in `~/.sap-adt-cli/config.json` (non-secret fields)
   and its password in the OS keystore — see [Credential storage](#credential-storage-keystore)

### Multiple SAP environments (profiles)

Each SAP system is stored as a named profile in `~/.sap-adt-cli/config.json`
(non-secret fields; the password goes to the keystore). The first `configure`
run creates a profile called `default`; an old single-connection config is
migrated automatically:

```bash


# Add environments (each saved profile becomes the active one)
sap-adt configure --profile dev --url "https://sap-dev:8000" --username DEV --client 100
sap-adt credentials set dev                       # then store the password (hidden prompt)
SAP_PASSWORD="..." sap-adt configure --profile prd --url "https://sap-prd:8000" --username PRD --client 200
                                               # ^ SAP_PASSWORD is moved into the keystore, not left in config.json

# List environments; * marks the active profile
sap-adt profile list

# Persistent switch
sap-adt profile use dev

# One-off override: global --profile (before the command) or SAP_PROFILE env var
sap-adt --profile prd get-program SAPMV45A
SAP_PROFILE=qas sap-adt status

# Remove an environment (the active profile cannot be removed)
sap-adt profile remove qas
```

Profile selection order: `--profile` > `SAP_PROFILE` > the active profile set by
`profile use`. Note the write/transport capability switches are **global** — they
apply to every profile, including production.

> A complete set of `SAP_URL/USERNAME/PASSWORD/CLIENT` environment variables (or a
> dotenv file declared by `SAP_ADT_DOTENV`) overrides all profiles. Run `status`
> to see which source is actually used.

### Dotenv file (explicit path, per-environment override)

```bash
# create ~/.config/sap-adt.env from the template in references/setup.md
# edit it and fill SAP_URL, SAP_USERNAME, SAP_PASSWORD, SAP_CLIENT
export SAP_ADT_DOTENV="$HOME/.config/sap-adt.env"
sap-adt status
```

The CLI never scans the current directory or the skill folder for a `.env`;
only the file named by `SAP_ADT_DOTENV` is read. Never commit the real file.

### Interactive wizard

```bash
sap-adt configure
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
sap-adt credentials doctor
# force a specific backend (fail-closed: an unavailable choice errors out)
sap-adt --keystore file credentials status
```

Manage stored passwords:

```bash

sap-adt credentials set dev          # prompts with hidden input + confirmation
sap-adt credentials status           # configured / not configured per profile — never prints secrets
sap-adt credentials forget dev       # purge from all writable backends
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
variables take precedence over both the declared dotenv file (`SAP_ADT_DOTENV`) and saved profiles.

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
export SAP_ALLOW_DEBUG=0            # optional: separate debugger capability (CLI 1.6.1+)
export SAP_ENVIRONMENT=dev          # required explicitly for env-based debugging

# Per-profile password for the 'env' keystore (profile 'dev' -> variable SAP_ADT_DEV_PASSWORD)
export SAP_ADT_DEV_PASSWORD=secret
# Master passphrase for the 'file' keystore in non-interactive runs
export SAP_ADT_MASTER_PASSPHRASE=...
```

### Capability flags (default: disabled)

Separate flags unlock source writes, transport writes and debugger controls.
**Enable only the capability needed, on the intended profile.** Write/transport
have legacy global fallbacks; debug permission never does. `environment=prd`
hard-refuses all three. Check `status` for each effective flag and its source.

```bash
# Enable interactively (answer 'y' to the write/transport prompts)
sap-adt configure --profile dev

# Enable non-interactively
SAP_PASSWORD="secret" sap-adt configure --profile dev \
  --url "https://sap-dev.example.com:44300" \
  --username "DEVELOPER" \
  --client "400" \
  --allow-write \
  --no-allow-transport
```

| Flag | Config field (profile scope preferred) | Default | Commands unlocked |
|------|-------------|---------|-------------------|
| `--allow-write` | `allow_write` | false | `write-source`, `activate` |
| `--allow-transport` | `allow_transport` | false | `create-transport`, `release-transport` |
| `--allow-debug` (1.6.1+) | `allow_debug` (profile-only) | false | `debug serve/breakpoint/listen/attach/step/continue` |

For an existing, approved non-production profile:
`sap-adt configure --profile qas --allow-debug` preserves unspecified write/TLS
settings. `--no-allow-debug` disables new controls. Neither `allow_write=true`
nor a legacy global switch grants debugging. Complete env/dotenv connections
use `SAP_ALLOW_DEBUG=true` with explicit `SAP_ENVIRONMENT=dev|qas`.
This local flag does not replace SAP-side debug authorization.

**Confirmation policy**: even when flags are enabled, every write/create/release or debug control
operation shows a change preview and requires explicit `[y/N]` confirmation.
The confirmation applies to the current operation only — it is discarded immediately
after use and must be repeated for each subsequent operation.
Debugging is not a read-only sandbox: step/continue can let application code
write business data even with source writes disabled. Authorized stack/variable
reads and status/detach/cleanup do not need re-enabling debug permission.
Disabling a flag does not close an existing owner; clean it up explicitly.

### Non-interactive flags (agent / automation workflows)

```bash
# Pass password via environment variable to avoid shell history exposure.
# configure stores it in the keystore; it does not remain in config.json.
SAP_PASSWORD="secret" sap-adt configure --profile dev \
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
| `update [--check] [--major] [--yes]` | Explicit CLI check/update; same-major stable by default; recognized npm-global and pip/pipx only; no SAP connection |
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
| `write-source <TYPE> <NAME> --file <PATH> [--activate] [--group <FG>] [--transport <TRKORR>] [--dry-run] [--expect-baseline-sha256 <H>] [--expect-content-sha256 <H>] [--yes]` | Verified write *(allow_write + confirm each time)*: diff preview, lock, in-lock baseline re-check, write, readback, unlock; `--activate` activates and verifies the active version; `--dry-run` shows the diff and hashes only; `--yes` requires `--expect-baseline-sha256` (CLI 1.6.2+); `--group` required when TYPE is `function`; `--transport` pins the transport request |
| `activate <TYPE> <NAME> [--group <FG>]` | Activate ABAP object *(allow_write + confirm each time)*; `--group` required when TYPE is `function` |
| `list-transports [--user U] [--status D\|R]` | List transport requests (JSON, read-only); default `--status D` (in development) |
| `list-feeds` | Diagnostic feed catalog with FQL attributes and query variants |
| `query-feed <URI> [--query FQL] [--max-results N] [--page-uri URI]` | One advertised feed page; default 20, maximum 500; continuation may overlap |
| `get-versions <TYPE> <NAME> [--group FG] [--max-results N]` | Per-part object history; default 100 versions per part; partial history exits 1 |
| `get-version-source <URI>` | Read an opaque historical content URI; plain source by default |
| `diff-versions <FROM_URI> <TO_URI> [--context N]` | Compare two version contents locally; `--format text` for unified patches |
| `get-transport <TRKORR>` | Request/task metadata and deduplicated objects |
| `transport diff <TRKORR> [--max-objects N] [--context N]` | Object differences; default 50 objects; missing snapshots/baselines are evidence gaps, exit 1 |
| `create-transport --package <DEVCLASS> --description "<DESC>" --ref <object-uri>` | Create transport via CreateCorrectionRequest *(allow_transport + confirm each time)*; package + object REF required; `$TMP` creates a local request; real-verified on Basis 7.56 (2026-09-17) |
| `release-transport <TRKORR> [--yes]` | Release transport — irreversible *(allow_transport + confirm each time)* |
| `transport ping` | ADT connectivity check for transport collection (plain text) |
| `transport collect <TRKORR> [--output-dir DIR] [--verbose]` | Read-only collection of a TR's object list + sources into `review_package/` (`manifest.json` + `sources/`); `--legacy-config` explicitly opts into the deprecated plaintext collector config |

Run any command with `--help` for full details.
For the new read-only commands, see the workflows in
[references/examples.md](references/examples.md). A modifiable request compares
active source, not a frozen transport snapshot. A released request requires
stored versions attributable to that request; active `00000` is not a snapshot.
Do not treat partial output or empty diffs as release approval.

---

## Examples

```bash


# Source code
sap-adt get-program SAPMV45A
sap-adt get-class ZCL_MY_CLASS
sap-adt get-function BAPI_SALESORDER_CREATEFROMDAT2 --group BAPI_SD_SALESORDER
sap-adt get-include MV45AFZZ
sap-adt get-interface ZIF_MY_INTERFACE

# Dictionary objects
sap-adt get-table VBAK
sap-adt get-structure VBAKKOM
sap-adt get-type-info MATNR
sap-adt get-type-group ICON

# Discovery
sap-adt search-object "ZCL_ORDER*" --max-results 20
sap-adt get-package ZMYPACKAGE
sap-adt get-transaction VA01
sap-adt get-cds-view ZI_INVENTORY_POSITION

# Analysis (read-only)
sap-adt syntax-check class ZCL_MY_CLASS
sap-adt where-used class ZCL_PAYMENT_PROCESSOR
sap-adt run-sql "SELECT * FROM t001 UP TO 5 ROWS"

# Write & activate (allow_write + confirm each time)
sap-adt write-source class ZCL_MY_CLASS --file /tmp/zcl.abap
sap-adt write-source class ZCL_MY_CLASS --file /tmp/zcl.abap --activate   # write + activate in one step
sap-adt write-source class ZCL_MY_CLASS --file /tmp/zcl.abap --dry-run    # diff + hashes, nothing written
sap-adt activate class ZCL_MY_CLASS

# Transport management
sap-adt list-transports --status D                              # read-only
sap-adt create-transport --package '$TMP' --description "My feature" \
  --ref /sap/bc/adt/programs/programs/zmy_feature/source/main        # allow_transport + confirm
sap-adt release-transport DEVK900001                           # allow_transport + confirm
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
`source`, `fields`, `objects`, `rows`, `records`, `findings`, `scalar`,
`capabilities`, `feeds`, `versions`, `diff`.
`-f/--format json|text|xml` (`SAP_ADT_FORMAT`) selects the format; `xml`
returns the raw ADT payload. Empty results are `ok:true,row_count:0,exit 0`.
Partial history/transport diffs instead return `meta.partial:true` and
`data.evidence_gaps` with exit 1, even if `ok:true`. Aggregated history and
computed diffs do not provide raw XML.

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

### v1.4.0 — Installable CLI & multichannel distribution

- **The CLI is now installable independently of the skill docs**: `src/sap_adt` package, `sap-adt` entry point, npm (`sap-adt-cli`), PyPI (`sap-adt`), Linux portable runtime
- **No runtime auto-install**: dependencies must be installed once; old skill-local script entry points were removed
- **Transport collection in the CLI**: `sap-adt transport collect|ping` (read-only); the legacy plaintext collector config is read only via explicit `--legacy-config`
- **Dotenv is explicit**: `SAP_ADT_DOTENV` declares the file; the CLI never scans the CWD or skill folder
- Program name `sap-adt-cli` → `sap-adt`; all command semantics, the 18 error codes, exit tiers and safety gates unchanged

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
- `SAP_ADT_DOTENV` / `SAP_*` environment variables remain a single-environment override layer that wins over all profiles

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

[MIT](https://github.com/shrek-abaper/sap-engineering-skill/blob/main/LICENSE)
