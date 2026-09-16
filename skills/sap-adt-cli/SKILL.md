---
name: sap-adt-cli
description: "Read/write ABAP source and metadata via SAP ADT REST API: programs, classes,
  function modules/groups, interfaces, includes, CDS views, DDIC tables/structures,
  data elements/domains, type groups, transactions, packages, search, where-used,
  syntax check, Open SQL preview, and transport requests (list/create/release).
  Write and transport operations each require a global capability flag AND a
  per-operation [y/N] confirmation that is never cached or reused across operations.
  On first use, configure credentials interactively (see references/credentials.md)."
---

# SAP ADT CLI

CLI: `scripts/sap_adt_cli.py` in this skill directory. First run auto-installs
`click`/`requests`/`urllib3`. Always run `status` first to check the profile and switches.

```bash
SKILL_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]:-$0}")")"
SAP_CLI="$SKILL_DIR/scripts/sap_adt_cli.py"
python3 "$SAP_CLI" status
python3 "$SAP_CLI" <command> [args]
# Windows: python "%USERPROFILE%\.agents\skills\sap-adt-cli\scripts\sap_adt_cli.py"
```

Unconfigured → `CONFIG_MISSING` (exit 2). First-use credential collection and
non-interactive `configure`: read **references/credentials.md**.
Multiple systems/profiles (`--profile`, `SAP_PROFILE`, PRD danger of global flags):
read **references/profiles.md**.

## Output contract

Every read command prints a JSON envelope (source commands print plain ABAP by default):

```json
{ "ok": true, "format_version": 1, "command": "get-table", "profile": "dev",
  "object": {"type": "table", "name": "VBAK"},
  "kind": "fields", "data": { }, "meta": {"row_count": 0} }
```

Errors on stderr: `{ "ok": false, …, "error": {"code","message","http_status","hint"} }`.

| kind | commands | `data` shape |
|------|----------|--------------|
| `source` | get-program/class/function-group/function/include/interface/cds-view/type-group | `{source, line_count}`; default output = verbatim source |
| `fields` | get-table, get-structure | `{fields:[{name,type,length,decimals,is_key,not_null}]}` (S/4 DDL: length null for element refs, listed in `meta.unparsed_types`; no description key) |
| `objects` | search-object, get-package, where-used | `{objects:[{name,type,uri,package,description}]}`; where-used may add optional `usage_line`/`usage_uri` |
| `rows` | run-sql | `{columns:[{name,type}], rows:[[…]]}` |
| `records` | list-transports | `{transports:[{trkorr,description,status,status_text,owner,target,tasks}]}` |
| `findings` | syntax-check | `{findings:[{severity,text,line,uri}]}` |
| `scalar` | get-type-info, get-transaction | object dictionary; type info has `resolved_as: domain\|dataelement` |
| `capabilities` | discovery | `{collections:[{href,title,content_types}]}` (Atom discovery; use `credentials doctor --coverage` for the command matrix) |

> `doctor --coverage` "available" only guarantees the **resource root**
> exists — discovery omits sub-paths, HTTP methods and required content
> types. Sub-path moves, GET→POST and content-type mismatches are invisible
> to it and only real-machine fixture regression catches them.

Format selection: **source defaults to `text` (byte-identical, safe to redirect),
every other kind defaults to `json`**. Global `-f/--format json|text|xml`
or `SAP_ADT_FORMAT` (flag wins). `--format xml` returns the original ADT payload
(escape hatch for parsers). Empty results are still `ok:true`, `row_count:0`, exit 0.
Full examples: **references/examples.md**.

## Error codes and exit tiers

| Exit | Meaning | Codes |
|------|---------|-------|
| 0 | success, including empty results | — |
| 1 | operational, retryable | `CSRF_EXPIRED`, `SERVICE_NOT_ACTIVE`, `BAD_REQUEST`, `SERVER_ERROR`, `LOCKED_BY_OTHER`, `NETWORK_ERROR`, `PARSE_FAILED` |
| 2 | configuration / credentials | `CONFIG_MISSING`, `PROFILE_NOT_FOUND`, `AUTH_FAILED` |
| 3 | policy refusal / operation did not happen — **do not retry** | `WRITE_DISABLED`, `TRANSPORT_DISABLED`, `CONFIRM_REQUIRED`, `USER_ABORTED`, `DML_REJECTED` |
| 4 | requested object does not exist | `OBJECT_NOT_FOUND` |

All 16 codes: the 15 above. Our errors on stderr are **JSON envelopes**; Click
usage errors (missing argument, bad `--format`) are **plain text** (also exit 2 —
distinguish by content, not code). `OBJECT_NOT_FOUND` requires a 404
`ExceptionResourceNotFound` body (a 404 "No suitable resource found" is
`BAD_REQUEST`); non-CSRF 403 is `AUTH_FAILED`, CSRF 403 is `CSRF_EXPIRED`.

## Command index

| Command | One-liner | kind |
|---|---|---|
| `status` | active profile, switches, config source (plain text) | — |
| `configure [--profile N]` | save a profile (flags = non-interactive JSON; no flags = interactive wizard) | — |
| `profile list\|use\|remove` | manage environments | — |
| `credentials set\|forget\|status\|doctor [--coverage]` | keystore management; `doctor --coverage` = command/resource matrix for this system | — |
| `discovery` | ADT resources this system exposes (href/title/content-types) | capabilities |
| `get-program / -class / -function-group / -function --group / -include / -interface / -cds-view / -type-group` | read source | source |
| `get-table / get-structure <N>` | DDIC fields (DDL on S/4) | fields |
| `get-type-info <N>` | domain/data element with `resolved_as` | scalar |
| `get-transaction <CODE>` | package/application/facets | scalar |
| `search-object "<PATTERN>" [--max-results N]` | wildcard search (`*`) | objects |
| `get-package <N>` | package contents | objects |
| `where-used <TYPE> <N> [--group G] [--max-results N]` | referencing objects | objects |
| `syntax-check <TYPE> <N> [--group G]` | findings; hard errors exit 1, warnings exit 0 | findings |
| `run-unit-test <N> [--type T] [--risk-level harmless\|dangerous\|critical] [--duration short\|medium\|long] [--fail-on error\|warning\|info\|never]` | ABAP Unit; harmless default (read-only); meta `no_tests_found` distinguishes "no tests" (total 0) from "all passed" | findings |
| `run-atc <N> [--type T] [--variant V] [--fail-on …]` | Static ATC checks (no gate); stable `check_id`/`message_id`, priority 1/2/3→error/warning/info; exempted findings auditable but never fail | findings |

> **Unit risk levels**: `dangerous`/`critical` tests **execute ABAP that may modify
> business data** — they require `allow_write`, show a risk-level + object +
> data-change warning in the `[y/N]` preview, and are hard-refused (no prompt)
> on `environment=prd`. Empty `runResult` is
> `ok:true, no_tests_found:true, total:0, exit 0`; an alert-only run (defective
> test class) also has `no_tests_found:true` with warning findings.
| `run-sql "<SELECT>" [--max-rows N]` | Open SQL preview; SELECT only; `--max-rows` (rowNumber) is the hard cap and overrides SQL `UP TO N ROWS` — conflicts flagged in `meta.row_limit_conflict` | rows |
| `list-transports [--user U] [--status D\|R]` | transport tree (read-only) | records |
| `write-source <TYPE> <N> --file F [--group G] [--transport T] [--activate] [--yes]` | lock→PUT→unlock | gated |
| `activate <TYPE> <N> [--group G] [--yes]` | activate objects | gated |
| `create-transport --description D [--category C] [--yes]` | create workbench/customizing request | gated |
| `release-transport <TRKORR> [--yes]` | irreversible release | gated |

## Safety gates (do not weaken)

- Capabilities are **profile-scoped** (`configure --allow-write/--allow-transport`
  write the profile section). The top-level `--global-allow-*` switches are a
  legacy fallback used only when the profile declares neither. Agents should
  always use the profile scope.
- Each profile has `environment: dev|qas|prd` (`--environment`; default inferred
  loosely from the name: contains `prd`/`prod`→prd, `qas`/`qa`→qas, else dev;
  `reproduce` matches `prod` by design — a false prd only blocks, use `--environment dev`).
- **environment=prd hard-refuses ALL writes** (write/activate/create/release,
  dangerous/critical Unit): no prompt, no flag override → exit 3; inferred-prd
  hints explain how to override via `--environment dev`.
- Off flags → exit 3 before any HTTP call. Every write/create/release then
  shows a preview and requires a fresh `[y/N]`, used for one operation only,
  never cached/reused even within the conversation.
- Non-interactive stdin without `--yes` → `CONFIRM_REQUIRED` (exit 3);
  answering N → `USER_ABORTED` (exit 3). Never add `--yes` on the user's behalf.
- **Env/.env writes**: `SAP_ALLOW_WRITE/TRANSPORT=true` requires `SAP_ENVIRONMENT`
  explicitly (nothing to infer from), else `CONFIG_MISSING` exit 3; `…=prd` refuses.
- `run-sql` blocks non-SELECT DML before sending (`DML_REJECTED`, exit 3).
- write-source always unlocks in `finally`; release-transport cannot be undone.

## References (load on demand)

- `references/credentials.md` — first-time setup, keystore backends, `.env`/env overrides, credential commands
- `references/profiles.md` — multi-environment management and agent rules
- `references/examples.md` — all command examples and workflows
- `references/adt_api.md` — endpoint reference incl. verified S/4HANA 2021 protocol facts (old→new, dated)
