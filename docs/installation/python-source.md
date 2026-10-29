# Python source / wheel install

For developers and contributors. The general guide (channels, diagnostics
matrix, version compatibility) is [runtime-setup.md](runtime-setup.md).

## From a checkout

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/sap-adt --version
```

`pip install -e .` gives `sap-adt` plus all commands; `python -m sap_adt`
works from an installed (also editable) package.

## From a built artifact

```bash
python -m build                      # dist/sap_adt_cli-<ver>-py3-none-any.whl + .tar.gz
python -m pip install dist/sap_adt_cli-<ver>-py3-none-any.whl
```

The wheel carries the same implementation as the frozen runtime; both read
the version from package metadata, and none of them installs dependencies at
run time. Missing optional backends (`keyring`, `cryptography`) degrade the
keystore selection — `sap-adt credentials doctor` shows what is available.

## Explicit updates (source-only until published)

`sap-adt update --check` checks the newest stable release in the installed
major. For a recognized registry pip install, `sap-adt update` previews and
confirms an upgrade using that same Python interpreter; user installs keep
`--user`. pipx main packages use their owning pipx environment. `--yes`
explicitly approves automation; `--major` allows crossing major versions.
Completion requires a version readback.

Editable and direct-URL/wheel-file installs are not replaced with registry
packages: update the original source/artifact instead. Externally managed
Python is not bypassed. Unknown installers get guidance rather than a guessed
`pip` command. No SAP configuration/keystore is read or changed, and there is
no automatic rollback of pip/pipx operations.

### Proxied networks

Python update checks now honor `PIP_PROXY`, then the current interpreter's
pip configuration (`install.proxy` before `global.proxy`, including
`PIP_CONFIG_FILE`). Only these proxy keys are queried; full pip configuration
and registry credentials are not printed. Configuration resolution runs in
a separate process with a 10-second limit.

Without a pip proxy, Requests retains its normal environment/system proxy
discovery and direct-connection behavior. Frozen standalone checks do not
try to run pip. Proxy credentials are not included in error messages, and
TLS verification remains enabled; use `REQUESTS_CA_BUNDLE` when metadata
checks need a corporate CA. Package installation still uses pip/pipx's own
network and certificate settings. This improvement is source-only until
the next publication.

### Failed installations and updates

Initial `python -m pip install` failures are reported by pip itself; see the
[diagnostics matrix](runtime-setup.md#diagnostics-matrix) for proxy, CA,
permissions, disk and externally-managed Python remedies.

The source updater classifies proxy authentication, TLS, connectivity,
permissions/file locks, disk space and unsupported tool/version failures.
Its error envelope includes a specific hint without dumping package-manager
output or credentials. A potentially modifying failure remains exit 3:
inspect first, then use the printed exact-version repair and verification
commands only if needed. Repairs retain the same interpreter, `--user`
scope or owning pipx environment/PIPX_HOME; none is run automatically.

## Tests (local only)

```bash
python -m unittest discover -s tests -v
python tests/check_contract.py
node --test packaging/npm/test/*.test.js
```
