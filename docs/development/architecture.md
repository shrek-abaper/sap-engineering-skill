# Architecture

Two source assets, several generated distributions.

## Source of truth

| Asset | Path | Notes |
|---|---|---|
| CLI implementation | `src/sap_adt/` | the only business implementation |
| CLI version | `pyproject.toml` `[project] version` | read at run time via `importlib.metadata`; no second constant |
| Skill content | `skills/<name>/` | SKILL.md, references, templates, generators |
| Install guide body | `docs/installation/runtime-setup.md` | embedded into per-skill snapshots |
| Compatibility declaration | `compatibility.json` | per-skill CLI requirement + range |
| Plugin metadata | `.claude-plugin/plugin.json` | plugin version authority |

## Generated (never hand-edited)

| Output | Producer |
|---|---|
| `skills/<name>/references/{setup.md,runtime-compatibility.json}` + README cli-setup blocks | `tools/sync_skill_runtime_docs.py` |
| `dist/skills/`, `dist/plugin/` | `tools/build_skills.py`, `tools/build_plugin.py` |
| `dist/runtime/` | `tools/build_runtime.py` (PyInstaller onedir) |
| `dist/npm/` | `tools/build_npm.py` |
| `dist/release/` | `tools/build_manifest.py` |

`dist/` is ignored by git.

## Package layout

```
src/sap_adt/
├── cli.py            Click group `sap-adt` (commands, gates, confirmations)
├── config.py         profiles/env/dotenv resolution, ~/.sap-adt-cli
├── credentials.py    keystore orchestration (+ *_reports.py for doctor output)
├── errors.py         closed 26-code set + exit tiers
├── output.py         envelope rendering (format_version = 1)
├── adt/              ADT client, handlers, parsers, coverage
├── keystore/         env / keyring / dpapi / pass / file backends
└── transport/        collector (read-only), legacy config adapter
```

## Single SAP access path

All SAP HTTP traffic goes through `sap_adt/adt/client.py` (Basic Auth, CSRF,
retry, redaction, `sap-client` query parameter). Transport collection injects
its connection with `set_config()` and reuses the ADT handlers for source
endpoints; it has no HTTP client of its own.

Controlled Class/Report execution and invocation-owned temporary Classes
live in `adt/execution.py`, reusing verified `source_write.py`. Execution
POSTs disable CSRF replay and redirects, use isolated in-memory Sessions and
fetch CSRF on discovery. `allow_execute` is independent and profile-only;
from CLI 1.6.4, snippet-owned `$TMP` Class creation/write/activation/cleanup
is covered by execution authorization without `allow_write`. Generic
source-write commands retain their independent gate; SAP development
permissions are still needed for the temporary Class. No persistent cookies
or native RFC dependencies are added.

## Debugger session ownership

An operator-started foreground `debug serve` process owns a dedicated
`requests.Session`, CSRF token and stateful ADT context across CLI calls.
Other commands use authenticated loopback IPC and an explicit random session
handle. A stateful header alone cannot preserve an exited client's context;
persisted cookies or session/lock identifiers are not ownership evidence.
The CLI never silently starts a daemon, backgrounds business execution,
installs SAP objects, introduces a workflow engine or persists SAP cookies.
Native distributions do not need an external Python interpreter for the owner.

### Authorization and scope

- `serve`, `breakpoint`, `listen`, `attach`, `step` and `continue` require
  independent, default-disabled, profile-only `allow_debug`, a non-production
  environment and fresh confirmation. Source/transport permissions and legacy
  global switches never grant debug authority. Complete env/dotenv connections
  use `SAP_ALLOW_DEBUG` and an explicit `SAP_ENVIRONMENT`.
- Stack/variable reads require an already authorized attached session, not
  source-write permission. Cleanup remains available after debug/write flags
  are disabled. Attaching pauses a work process; stepping, continuing and
  detaching may let application writes proceed even with `allow_write=false`.
- One owner handles one debuggee and one independently named external breakpoint
  scope, bound to profile, origin, client and user. Variable reads expand only
  an explicit parent or explicit IDs within count/value budgets, never a
  recursive memory dump.
- No variable modification, arbitrary evaluation, system/foreign-user debugging,
  jump-to-line, terminate-debuggee or bulk deletion of another tool's breakpoints.
  Normal detach, expiry and Ctrl-C use `detachDebugger`, never `terminateDebuggee`.

### IPC and cleanup

- Listener/control deadlines, idle/hard lifetimes, serialized actions and bounded
  IPC prevent unbounded work. Interrupted or ambiguous state-changing calls are
  never replayed; generic HTTP 500 is not successful continuation or permission
  to retry a step.
- The private descriptor contains an IPC capability token and port, not SAP
  credentials, source or variables. POSIX files/directories are user-only;
  Windows uses a protected current-user DACL. No SAP credentials cross IPC.
  No pickle, shell commands, remote URLs or arbitrary RPC methods are accepted;
  responses are not logged.
- Cleanup deletes only tracked breakpoints and this listener, attempts detach
  even after an earlier cleanup failure, and does not change repository-write
  lock semantics. Owner death loses the SAP context. Stale-descriptor removal
  with `cleanup --discard-local --yes` must report unknown remote state and
  manual ADT/Basis follow-up; it cannot safely recover a session or kill a PID.

### Result and verification contracts

Debug commands use format-version 1 `kind=debug` envelopes with `data.session`,
`data.state`, `data.operation`, operation-specific evidence and
`data.evidence_gaps`; incomplete cleanup sets `meta.partial=true`.
Accepted cleanup or local owner closure is distinct from independently verified
remote release; report `remote_cleanup_verified=false` when it is unverified.
The closed error registry and exit tiers apply; `DEBUG_DISABLED` is a tier-3
policy refusal, not advice to enable source writes. Timeouts are `timed_out`,
not hits or successful attachments. Unknown responses are errors, not empty
evidence. XML passthrough is unsupported.

Synthetic integration must cover cross-process cookie/context affinity, CSRF
including DELETE, timeouts, profile mismatch, authorization/production gates,
denied IPC, concurrent-action rejection, malformed responses, non-replayed step
errors, independent cleanup phases, expired/abrupt owners, UTF-8 and installed
wheel/native-runtime behavior. Live discovery does not prove debug authorization
or attachment. Live attachment requires an explicitly approved non-business
target; never create or interrupt business execution merely to obtain a test.
Unverified paths remain experimental; implementation completion does not
authorize tagging, pushing or publishing.

## No compatibility shims

The old skill-local script entry points (`skills/*/scripts/sap_adt_cli.py`,
`tr_collector.py`) were removed: they only forwarded to the installed
package and no distribution ever shipped them. Every path now uses the
`sap-adt` command. The deprecated plaintext collector config is still read
only on the explicit `--legacy-config` flag; `sap-adt configure` replaces the
old collector wizard.

## Data & credentials (unchanged by packaging)

- Config: `~/.sap-adt-cli/config.json` (v2 profiles, 0600).
- Passwords: OS keystore; backend priority env → keyring → WSL DPAPI → pass
  → encrypted file (`SAP_ADT_MASTER_PASSPHRASE`).
- Env precedence: process env → explicit dotenv (`SAP_ADT_DOTENV`) →
  profile. The CLI never scans the CWD for `.env`.
- Legacy `~/.sap-transport-gate/config.json` (plaintext) is read only on the
  explicit `--legacy-config` path, with a migration warning.
