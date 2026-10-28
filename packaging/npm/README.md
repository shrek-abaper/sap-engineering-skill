# sap-adt-cli

npm/npx channel for the self-contained **sap-adt** CLI (SAP ADT REST API:
read/write ABAP source and metadata, transport request collection).

The runtime is a native executable per platform — **no Python, pip or venv
required**. This npm package itself needs **Node.js ≥ 18** (npx + installer);
if Node.js is not an option, use the desktop installer / portable archive
from the [repository releases](https://github.com/shrek-abaper/sap-engineering-skill)
instead.

## Install the runtime (once)

The package is named `sap-adt-cli`; its bin is **`sap-adt`**.

**Global command (recommended):**

```bash
npm install -g "sap-adt-cli@^1.5.0"
sap-adt install
```

**npx (no global install) — keep the prefix on every call** (npx does not add
`sap-adt` to PATH):

```bash
npx "sap-adt-cli@^1.5.0" install
npx "sap-adt-cli@^1.5.0" --version
```

`install` is this package's own wizard (not an npm/npx built-in): it matches
your OS/arch against the version-bound manifest, downloads the matching
artifact over HTTPS, verifies its SHA-256 (from the manifest bundled with
the package — never from the download endpoint), extracts safely and swaps
it in atomically, then self-tests with the absolute install path.

## Use

```bash
sap-adt --version
sap-adt status
sap-adt configure            # interactive; password goes to the OS keystore
sap-adt credentials doctor   # backend diagnostics (no secrets shown)
```

With npx, prefix each command: `npx "sap-adt-cli@^1.5.0" <command>`.

Configuration and credentials live in `~/.sap-adt-cli/` and the OS keystore —
never inside this package. Upgrading the npm package requires re-running
`install` (the runtime slot lives next to the launcher).

## Security model notes

- The CLI is read-only by default; write/activate/transport commands need a
  per-profile capability flag, are hard-refused on `environment=prd`, and ask
  for a fresh `[y/N]` confirmation per operation.
- The installer refuses digest mismatches, unsupported platforms, non-HTTPS
  or unlisted redirect hosts, and archives with path traversal or symlinks.
- A normal `sap-adt` invocation never downloads or upgrades anything.

Package versions track the CLI version exactly; installing version X always
installs runtime X (no `latest` surprises).
