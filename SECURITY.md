# Security policy

## Reporting a vulnerability

Open a private security advisory on the GitHub repository
(https://github.com/shrek-abaper/sap-engineering-skill) or contact the
maintainer listed in the repository profile. Do not file a public issue for
credential leaks or gate bypasses.

## Scope

In scope: the `sap-adt` CLI, the packaged runtimes (PyInstaller binaries,
npm installer), the skill documents' security rules, and the release
tooling.

## Design guarantees (regression-tested)

- Read-only by default; write/activate/transport require a profile-scoped
  capability flag and a fresh per-operation confirmation.
- `environment=prd` hard-refuses all writes; no flag can override it.
- `run-sql` rejects DML before any request is sent.
- Passwords are never stored in plaintext when a writable OS keystore
  exists; `status`/`doctor` never print secrets; logs redact credentials.
- The npm installer refuses digest mismatches, non-HTTPS or unlisted
  redirect hosts, unsafe archive entries and unsupported platforms; a
  failed install keeps the previous runtime.
- The released plugin payload contains documentation only — no CLI code, no
  execution shims, no secrets.

## Non-guarantees

- Installing via pip/npm/portable does not sandbox the process: it runs with
  the invoking user's permissions, like any CLI.
- Unsigned Windows/macOS binaries may trigger SmartScreen/Gatekeeper
  warnings; signing requires a certificate and a real verification pass.
- The legacy `~/.sap-transport-gate/config.json` is plaintext by design of
  the old collector; migrate with `sap-adt configure` and delete it.
