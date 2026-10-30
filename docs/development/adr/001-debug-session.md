# ADR 001: bounded HTTP debugger owner

Status: accepted for the unreleased CLI 1.6.1 candidate, 2026-10-30.

## Context and decision

Batch two needs one debugger context to survive several CLI processes.
This is a new requirement, not a reason to reopen the rejected on-disk
cookie/lock layer. Use a foreground `debug serve` process owning a dedicated
`requests.Session`, CSRF token and stateful ADT context. Other commands use
authenticated loopback IPC and an explicit random session handle.

The operator starts this process in another terminal or their process
supervisor. The CLI does not silently spawn a daemon, background business
execution, install SAP objects, use a workflow engine or persist SAP cookies.
The foreground model also works inside native PyInstaller distributions
without finding an external Python interpreter.

## Contracts before implementation

All `debug` commands emit format-version 1 `kind=debug` envelopes, with
`data.session`, `data.state`, `data.operation`, operation-specific evidence
and `data.evidence_gaps`; `meta.partial` is true on incomplete cleanup.
Cleanup explicitly distinguishes accepted requests/local owner closure from
independently verified remote release (`remote_cleanup_verified=false`).
The existing 18 error codes and exit tiers apply. Timeout is a bounded
`timed_out` result, not a hit or successful attachment. Unknown responses
are errors, not empty evidence. XML passthrough is not supported.

Commands: `serve`, `status`, `breakpoint`, `listen`, `attach`, `stack`,
`vars`, `step`, `continue`, `detach`, `cleanup`. No variable modification,
arbitrary evaluation, system debugging, jump-to-line, terminate-debuggee,
foreign-user debugging or bulk deletion of another tool's breakpoints.
`vars` expands one explicit parent or reads explicit IDs, with count/value
budgets; it does not recursively dump memory.

`serve`, `breakpoint`, `listen`, `attach`, `step` and `continue` require
`allow_write`, non-production environment and fresh confirmation. Attaching
pauses a work process; stepping/continuing can execute application writes.
Stack/variable reads require a previously attached context. Cleanup remains
available when the current profile's write flag is disabled. Normal detach,
expiry and Ctrl-C use **detachDebugger**, never **terminateDebuggee**.
Detaching can allow the application's existing execution to proceed.

One owner handles one debuggee and one independently named external
breakpoint scope. The session is bound to profile, origin, client and user;
no credentials are passed through IPC. Listener and control deadlines,
idle/hard lifetimes, serialized actions and bounded IPC prevent accidental
unbounded work. Interrupted/ambiguous state-changing calls are never
replayed automatically. Cleanup deletes only tracked breakpoints and this
listener and attempts detach even if an earlier cleanup phase fails.

The private session descriptor holds an IPC capability token and port, not
SAP credentials, source or variables. POSIX files/directories are user-only;
Windows uses a protected current-user DACL. No pickle, shell commands,
remote URLs or arbitrary RPC methods are accepted. Responses are not logged.
Owner death loses the SAP context. `cleanup --discard-local --yes` can
remove a stale local descriptor, but must report unknown remote state and
manual ADT/Basis follow-up. It cannot safely recover or kill a PID.

## Alternatives and provenance

- Pinned RFC: viable transport affinity but requires SAP RFC native runtime
  and deployment/installation work. Deferred; HTTP avoids a new native
  dependency and keeps Linux/Windows/macOS packaging unchanged.
- Persist cookies to disk: rejected; credentials-equivalent material and no
  safe proof of server-side ownership from a lock/session ID alone.
- One-shot HTTP calls: rejected; process lifetime and transport affinity are
  independent. A stateful header alone does not keep an exited client alive.

Protocol/architecture references inspected, not vendored/copied:

- [vsp debugger](https://github.com/oisee/vibing-steampunk/blob/c007cebfc3474e5aa72e07ebc80628ad4b8cd34a/pkg/adt/debugger.go)
  (MIT): request/response shapes, listener and debugger models.
- [abapgit-agent session](https://github.com/SylvosCai/abapgit-agent/blob/c968c0df64f06814ff66a956e3ec8feb89ca47b5/src/utils/debug-session.js):
  independent HTTP owner and stateful affinity; no code reuse because the
  inspected repository did not declare a clear license.
- [abap-adt-api debugger](https://github.com/marcellourbani/abap-adt-api/blob/master/src/api/debugger.ts):
  **detachDebugger** is distinct from terminateDebuggee. Never treat generic
  HTTP 500 as successful continuation or retry stepping after ambiguity.
- adt-clients' in-memory lock registry informs scoped cleanup, not disk
  recovery. Batch two does not change repository-write lock semantics.

## Validation and release boundary

Synthetic HTTP integration must demonstrate cross-process cookie/context
affinity, CSRF including DELETE, timeouts, profile mismatch, authorization
and PRD gates, denied IPC, concurrent-action rejection, malformed responses,
non-replayed step errors, independent cleanup phases, expired/abrupt owners,
UTF-8 and installed wheel/native-runtime behavior. Live discovery does not
prove debug authorization or a real attached session. Any live attachment
needs an explicitly approved non-business target; never create or interrupt
business execution to obtain a test. Keep unverified paths experimental.
No tagging, pushing or publishing is authorized by implementation completion.
