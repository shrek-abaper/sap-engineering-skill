# sap-adt-cli

npm/npx channel for the self-contained **sap-adt** CLI (SAP ADT REST API:
read/write ABAP source and metadata, transport request collection).

The runtime is a native executable per platform — **no Python, pip or venv
required**. This npm package itself needs **Node.js ≥ 18** (npx + installer);
if Node.js is not an option, use the desktop installer / portable archive
from the [repository releases](https://github.com/shrek-abaper/sap-engineering-skill)
instead.

Linux x86_64 and Windows x86_64 runtimes are provided. Windows support
starts with package 1.5.3 and also requires `tar.exe` (included in current
Windows 10/11). macOS has no self-contained runtime yet; use the Python
package there. Upgrading an older Windows launcher requires reinstalling
the npm package before running `sap-adt install` again.

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

The source installer (not yet published) selects an explicit proxy environment
variable first, then npm's persistent proxy settings, then Windows current-user
manual proxy settings. It respects `NO_PROXY` and Windows manual bypass rules.
It prints the selected route without credentials, bounds connection setup
to 30 seconds, and aborts stalled downloads after 60 seconds of inactivity.
System settings are never modified. PAC/WPAD scripts, SOCKS and integrated
NTLM/Kerberos proxy authentication are not evaluated or enabled automatically.

For published versions, set `HTTPS_PROXY` (and `NO_PROXY` for hosts that go
direct) before `install`. An `http://` CONNECT proxy is required; interception
proxies need their CA configured with `NODE_EXTRA_CA_CERTS`, not disabled TLS.

The source installer retains the previous runtime until the new self-test
succeeds, restores it on failure and reports a retained backup if recovery
is blocked. Extraction/self-test are limited to 120/60 seconds, configurable
through `SAP_ADT_INSTALL_EXTRACT_TIMEOUT_MS` /
`SAP_ADT_INSTALL_SELFTEST_TIMEOUT_MS`. Failures include actionable network,
CA, permission, disk and OS-runtime hints; unsupported platforms get Python
venv instructions. The source update launcher passes discovered Windows
manual proxies to npm's registry/package steps too, without changing user
configuration. Bootstrap `npm install` remains npm's own operation.

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
`install` (the runtime slot lives next to the launcher). Once published,
`sap-adt update` handles both steps for a confirmed global npm installation.

## Explicit updates (not yet published)

```bash
sap-adt update --check
sap-adt update             # preview + confirmation, current major only
sap-adt update --yes       # explicit approval for automation
```

The launcher first stages and verifies the new runtime, then updates this
global package and verifies the final version. It replaces files only after
the frozen runtime has exited. Staging failures keep the existing install;
the npm commit itself is not a full transaction, and later errors provide
repair instructions. Local/workspace installs and npx get guidance instead
of being silently rewritten. No SAP config or credentials are needed.
`--major` explicitly allows a new major, outside the default skill range.
Older versions need one manual package upgrade to obtain this command.

## Security model notes

- The CLI is read-only by default; write/activate/transport commands need a
  per-profile capability flag, are hard-refused on `environment=prd`, and ask
  for a fresh `[y/N]` confirmation per operation.
- The installer refuses digest mismatches, unsupported platforms, non-HTTPS
  or unlisted redirect hosts, and archives with path traversal or symlinks.
- Normal SAP commands never download or upgrade anything; only explicit
  `install` and confirmed `update` requests do.

Package versions track the CLI version exactly; installing version X always
installs runtime X (no `latest` surprises).
