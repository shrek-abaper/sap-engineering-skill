# Controlled ABAP execution (CLI 1.6.3+)

Use only after an explicit execution request. Source inspection, diagnosis,
SQL and Unit requests do not authorize arbitrary execution.

## Select an entry point

| Command | Target | Output |
|---|---|---|
| `run-class NAME` | Active class implementing `IF_OO_ADT_CLASSRUN~MAIN` | Raw console text inside the JSON execution envelope |
| `run-report NAME` | Active executable Report, default selection values | Raw List text including page headers; not GUI/ALV control/Spool automation |
| `run-abap --file FILE` | UTF-8 statements inside a generated method body; `-` accepts stdin | Explicit `out->write` output; variables are not returned automatically |

These are ADT HTTP operations, not a native RFC connection. A snippet can
call local functions (including non-RFC functions), BAPIs and accessible
methods using typed ABAP parameters. Language-version/API restrictions,
authorizations and background/GUI dependencies still apply.

## Authorization and confirmation

- Independent profile-only `allow_execute`, false by default; source,
  transport, debugger and legacy global flags never grant execution.
- `configure --profile dev --allow-execute` preserves unspecified write,
  debug and TLS settings. `--no-allow-execute` disables the capability.
- Complete env/dotenv connections use `SAP_ALLOW_EXECUTE=true` with explicit
  `SAP_ENVIRONMENT=dev|qas`. PRD is hard-refused regardless of flags.
- `run-abap` also needs `allow_write`: its approval covers creating,
  writing, activating, executing and attempting to delete one owned Class.
  Package is fixed to `$TMP`; no generic create/delete command is exposed.
- Each invocation requires fresh confirmation. `--yes` only skips the
  prompt when `--expect-plan-sha256` matches the reviewed dry-run plan.

```bash
sap-adt --profile dev run-class ZCL_DEMO --dry-run
sap-adt --profile dev run-class ZCL_DEMO \
  --yes --expect-plan-sha256 REVIEWED_PLAN_HASH

sap-adt --profile dev run-report ZREPORT --dry-run
sap-adt --profile dev run-abap --file probe.abap --dry-run
sap-adt --profile dev run-abap --file probe.abap \
  --yes --expect-plan-sha256 REVIEWED_PLAN_HASH
```

Changing the system/client/user, entry point, source, timeout or output cap
changes the plan hash. Existing-object hashes bind the observed active main
source only, not includes/dependencies or an atomic snapshot; source can
still change after the final check. No whole-program immutability is claimed.
The CLI rechecks the main source/file before execution.

## Local function example

```abap
DATA lv_output TYPE c LENGTH 18.
CALL FUNCTION 'CONVERSION_EXIT_ALPHA_INPUT'
  EXPORTING input = '123'
  IMPORTING output = lv_output.
out->write( lv_output ).
```

For business calls, inspect the real signature first, declare parameters,
handle classical/class-based exceptions and inspect BAPI `RETURN`.
Use explicit ABAP JSON serialization if structured output is needed; the
CLI does not infer a JSON schema from console text.

No automatic `COMMIT`, rollback or transaction chaining is provided.
If explicitly authorized, a BAPI call and its transaction decision must
be in the same service-side execution; distinct CLI runs do not share a LUW.
Deleting a temporary Class does not undo business changes. DEV is not a sandbox.
Remote `DESTINATION` calls use SAP-side destination configuration and may
execute under a different user; no remote identity propagation is promised.

## Results and uncertain outcomes

Default JSON; `--format text` retains the full evidence object. XML is
rejected before execution. Inspect:

- `execution.status`: `not_started`, `completed` or `unknown`. A complete
  HTTP 200 text response confirms protocol completion, not business success.
- `output`: raw UTF-8 `text`, `format:text`, `truncated`. Empty complete
  output is allowed; it is not evidence that business work succeeded.
- `preparation`: temporary-Class write/lock/unlock/activation evidence.
- `cleanup.status`: `not_required`, `verified`, `not_attempted`, `retained`
  or `unknown`; retained object identity is in `temporary_object`.
- `evidence_gaps` and any `failure`: always report them.

`--timeout` defaults to 30 seconds (1..300); it is an HTTP timeout, not a
server-side execution deadline. `--max-chars` defaults to 100000 (1..1000000).
Truncation exits non-zero, preserves the prefix and leaves completion
unknown. No execution POST is automatically retried, including CSRF errors;
redirects are not followed. Each execution uses an isolated in-memory SAP
Session with CSRF fetched from discovery; no cookies are persisted.

`EXECUTE_DISABLED`, `EXECUTION_FAILED`, `EXECUTION_INCOMPLETE` exit 3.
Failures keep lifecycle evidence on stderr. A network timeout, runtime
failure or lost output can follow business side effects: never replay
to recover output. No asynchronous status/cancellation API is promised.

Temporary names are unique `ZADT_RUN_...`; deletion requires confirmed
creation, the original metadata marker and an expected source hash.
Unknown execution/lock state prevents deletion. Cleanup success requires
an independent object-not-found readback, not deletion HTTP 2xx alone.
Creation uncertainty, process termination or server/network failure can
leave objects behind. Report the exact object for operator inspection;
do not issue broad prefix-based deletion or claim automatic recovery.
