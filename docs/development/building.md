# Building

Linux/Windows builds and live SAP verification run locally. The manually
dispatched `build-macos-runtime.yml` workflow builds on native Intel and
Apple Silicon macOS runners, runs offline tests and verifies an isolated
npm installation. It never connects to SAP or publishes packages.
See [releasing.md](releasing.md).

## One-time environment

```bash
python3 -m venv .venv
.venv/bin/pip install -e . click requests urllib3 keyring cryptography build pyinstaller
```

Node.js ≥ 18 and npm are only needed for the npm channel; Inno Setup 6 only
for the Windows installer (on Windows).

## Steps

```bash
# 1. Python artifacts
.venv/bin/python -m build                     # -> dist/*.whl, dist/*.tar.gz

# 2. Self-contained runtime (current platform only)
.venv/bin/python tools/build_runtime.py       # -> dist/runtime/<os>-<arch>/

# 3. Portable / installer
.venv/bin/python tools/build_installer.py     # Linux: portable archive;
                                              # Windows: Inno Setup if present

# 4. npm staging + tarball
.venv/bin/python tools/build_npm.py
cd dist/npm && npm pack && cd ../..

# 5. Skill snapshots + plugin payload
.venv/bin/python tools/sync_skill_runtime_docs.py
.venv/bin/python tools/build_skills.py
.venv/bin/python tools/build_plugin.py

# 6. Release candidate (copies artifacts, writes SHA256SUMS + manifest)
.venv/bin/python tools/build_manifest.py
.venv/bin/python tools/check_release.py --skip-marketplace
```

## Windows runtime from WSL

WSL can drive a native Windows build when Windows Python, Node.js/npm and
`tar.exe` are installed on the host. This is not cross-compilation:
PyInstaller and the npm smoke test must run as Windows processes.
Inno Setup is only needed for the separate desktop installer, not the npm ZIP.

From the checkout, use `py.exe -0p` to locate a Windows Python supported by
PyInstaller (Python 3.12 was verified). In Windows PowerShell, with the
checkout as the current directory:

```powershell
$python = 'C:\Path\To\Python312\python.exe' # use the path from py.exe -0p
$venv = Join-Path $env:TEMP 'sap-adt-windows-build\venv'
& $python -m venv $venv
$python = Join-Path $venv 'Scripts\python.exe'
& $python -m pip install -e . keyring cryptography pyinstaller
& $python tools/build_runtime.py
```

Alternatively, invoke that Windows venv from WSL (replace its path):

```bash
powershell.exe -NoProfile -NonInteractive -Command \
  '& "C:\Path\To\venv\Scripts\python.exe" tools/build_runtime.py; exit $LASTEXITCODE'
```

The build produces `dist/runtime/sap-adt-<ver>-windows-x86_64.zip`.
Keep the Linux archive of the same version alongside it, then stage both:

```bash
.venv/bin/python tools/build_npm.py
powershell.exe -NoProfile -NonInteractive -Command \
  '& "C:\Path\To\venv\Scripts\python.exe" tools/smoke_npm.py; exit $LASTEXITCODE'
powershell.exe -NoProfile -NonInteractive -Command \
  'node --test packaging/npm/test/install.test.js; exit $LASTEXITCODE'
```

The smoke tool uses a temporary Windows-local npm prefix/cache, so npm does
not run from a UNC current directory. It verifies the real runtime through
the npm `.cmd` shim without changing the user's global installation or
contacting SAP. It also checks local artifact SHA-256 before testing.
The GNU-tar-specific traversal fixture is skipped on Windows; it still runs
in the Linux suite.

Build and local verification do not publish anything. A new npm version
and its Windows release ZIP must be published together before registry
users can install it.

## macOS runtime on hosted runners

After pushing a reviewed source commit, explicitly dispatch:

```bash
gh workflow run build-macos-runtime.yml --ref main
```

The workflow uses macOS 15 Intel and Apple Silicon runners with Python
3.12 and Node.js 22. Each job checks its native target, runs offline tests,
builds the runtime and tests `npm pack` through runtime installation in a
temporary global prefix/cache. Only successful jobs upload versioned
archives and build metadata; download them before assembling the release.
No SAP credentials, signing certificates or publishing tokens are used.

This does not verify a personal Mac, older macOS, Keychain interaction,
Gatekeeper/quarantine behavior, signing/notarization or live SAP access.
Do not mark a target verified until its native job actually succeeds.

### Desktop installer verification

With Inno Setup 6 installed, add the directory containing `ISCC.exe` to the
Windows process PATH, then run with the Windows build venv:

```powershell
$env:PATH = 'C:\Path\To\Inno Setup 6;' + $env:PATH
& $python tools/build_installer.py
& $python tools/smoke_windows_installer.py
```

The smoke test compiles native PATH cleanup tests, then performs silent
per-user installation, same-version upgrade, CLI launch and uninstall of
the actual desktop installer. It refuses to run over an existing install,
uses a synthetic home and a temporary Unicode/space install path, and
disables the PATH task and shortcuts. Logs stay in `dist/installer-smoke/`.
No real credentials or SAP connection are used.

This verifies the silent installer lifecycle, not graphical wizard clicks,
real PATH registry mutation, elevated installs or SmartScreen behavior.
Publishing and signing remain separate authorized steps.

## Verification baseline

```bash
.venv/bin/python -m unittest discover -s tests -v   # unit/contract/distribution
.venv/bin/python tests/check_contract.py            # SKILL.md vs code
node --test packaging/npm/test/install.test.js      # installer error paths
gitleaks protect --staged --config .gitleaks.toml    # pre-commit secret scan
```

Before publishing an upgrade, `--skip-marketplace` leaves the previous
published plugin archive live. After publication and the marketplace
update, run `tools/check_release.py` again without that flag.

## Rules

- Never mark a platform verified from the existence of a script. A target is
  verified only after a real build + install smoke on that OS/arch
  (`packaging/targets.json`).
- Builds must not install dependencies at run time, auto-upgrade, read
  secrets, or write into the CLI install directory.
