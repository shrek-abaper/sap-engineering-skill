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

## Tests (local only)

```bash
python -m unittest discover -s tests -v
python tests/check_contract.py
node --test packaging/npm/test/install.test.js
```
