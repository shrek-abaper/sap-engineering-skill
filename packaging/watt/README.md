# Watt

**Power your SAP Engineering.**

Watt is an engineering CLI for SAP lifecycle work: implementation, development,
testing, delivery and operations. Named after the unit of power, Watt aims for
steady, sustained and controllable engineering work. It can be used directly
by people or called by AI agents.

Today, Watt starts with ADT and ABAP: source and metadata access, diagnostic
evidence, governed changes and execution. Companion Skills support code review,
transport risk assessment and integration guidance. Broader lifecycle coverage
is a direction, not a claim that every SAP task is already supported.

The CLI does not embed an LLM or autonomous workflow engine. It supplies
deterministic operations; Skills and agents provide interpretation and planning.
Evidence comes first, authorization is explicit, and missing evidence remains
a gap. Read-only by default does not mean incapable of change: writes,
execution and debugging have separate consent gates and can affect SAP data.
Reviews do not replace human approval.

This is an independent community project, not an official SAP product.

## Install

With Node.js >=18 (no Python needed):

```bash
npm install -g "sap-watt@^1.6.7"
sap-watt install
sap-watt --version
```

Or with Python >=3.10, preferably in a virtual environment:

```bash
python -m pip install "sap-watt>=1.6.7,<2"
sap-watt --version
```

For npx, keep the same selector on every call:
`npx "sap-watt@^1.6.7" install`, then
`npx "sap-watt@^1.6.7" <command>`.

The npm package downloads a matching native runtime only on explicit `install`;
normal commands never install or upgrade anything. Linux x86_64, Windows x86_64
and experimental macOS 15+ Intel/Apple Silicon runtimes are supported.
Native platform checks gate publication; signing/notarization and live SAP on
Windows/macOS are not certified. Windows requires `tar.exe`.

```bash
sap-watt configure
sap-watt status
sap-watt credentials doctor
sap-watt get-class ZCL_EXAMPLE
sap-watt update --check
```

Never put SAP passwords in command arguments or chat. Configuration stays in
`~/.sap-adt-cli`, passwords in the existing credential backends. Existing
`SAP_*` variables, authorization gates and JSON contracts are unchanged.

## Compatibility and updates

`sap-watt` and `sap-adt` share the same implementation and subcommands.
The existing `sap-adt-cli` package owns `sap-adt`; the new package owns only
`sap-watt`, so neither package overwrites the other's command.

Python `sap-watt` depends on the exact same version of `sap-adt-cli` and
provides optional `keystore`, `file` and `all` extras. In a shared Python
environment, use `sap-watt update` (or either current entry's updater) to
update the entry and core together; do not independently upgrade the pinned
core. Uninstalling the entry leaves the core; uninstalling the core while
Watt depends on it breaks Watt and is not supported.

The npm packages have independent runtime slots. They can coexist and update
separately. Installing npm `sap-watt` does not install a global `sap-adt`.
Removing one does not remove the other or shared user configuration.

`update --check` checks the owning channel without SAP access; `update`
requires confirmation (`--yes` for explicit automation). npm stages and verifies
before committing, but does not promise a full npm rollback. pipx, npx and
project-local installations retain their channel boundaries; local/npx installs
receive update guidance rather than being silently replaced.

Native portable executables, Windows installer identity and release asset
names remain `sap-adt` in this transition. No configuration migration is needed.
Bare `watt` is not installed.

See the [repository](https://github.com/shrek-abaper/sap-watt),
[installation guide](https://github.com/shrek-abaper/sap-watt/blob/main/docs/installation/runtime-setup.md)
and [design principles](https://github.com/shrek-abaper/sap-watt/blob/main/docs/design-principles.md).
