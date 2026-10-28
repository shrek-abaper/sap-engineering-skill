# Windows runtime and installer

**Runtime / npm: verified locally** on 2026-10-29. The Windows x64 runtime
was built with Windows Python 3.12 through WSL interop, then installed from
a locally packed npm package using Windows Node.js. SHA-256 verification,
ZIP extraction, the npm command shim, `--version` and `--help` passed.
This does not verify SAP connectivity.

Windows npm support starts with **CLI 1.5.3**. Older packages may list only
`linux-x86_64`; upgrade with `npm install -g "sap-adt-cli@^1.5.3"` and then
run `sap-adt install` again. The Windows ZIP and desktop installer are
available from the corresponding
[GitHub Release](https://github.com/shrek-abaper/sap-engineering-skill/releases/tag/sap-adt-v1.5.3).

**Desktop installer: silent per-user lifecycle verified locally** on
Windows 11 x64, using Inno Setup 6.7.4 through WSL interop. Installation into
a path containing spaces and Chinese characters, runtime startup,
same-version upgrade, and uninstall passed. A synthetic configuration file
was preserved. The PATH task and Start Menu shortcuts were disabled for
this smoke test to avoid changing the host's environment.

The PATH cleanup helper is separately tested with native Inno Setup code.
Actual user PATH mutation, graphical wizard clicks, interactive credential
configuration, elevation, and SAP connectivity are not verified.
The installer is unsigned; SmartScreen or antivirus warnings may appear.

For repeatable builds from WSL, see
[Building on Windows from WSL](../development/building.md#windows-runtime-from-wsl).

## What the installer does (when built on Windows)

1. `tools/build_runtime.py` produces `dist/runtime/windows-x86_64/sap-adt/`
   (PyInstaller onedir).
2. `tools/build_installer.py` compiles `packaging/windows/setup.iss` with
   Inno Setup 6 into `dist/installers/sap-adt-<ver>-windows-x86_64-setup.exe`.

Installer behavior (per-user, no admin by default):

- copies the runtime + `configure.cmd` into `%USERPROFILE%\...\sap-adt`;
- offers an enabled-by-default task to add the directory to **user** PATH;
- checks `sap-adt --version` from the absolute install path, and fails
  setup if the runtime cannot launch or returns an error;
- runs `sap-adt credentials doctor` for interactive installs only;
- tells the user to restart their terminal/agent;
- uninstall removes program files and the PATH entry only if this installer
  added it — user config (`~/.sap-adt-cli`) and keystore entries stay.

## Repeatable local smoke test

With Windows Python, the built runtime, and Inno Setup's `iscc` on PATH:

```powershell
python tools/build_installer.py
python tools/smoke_windows_installer.py
```

The smoke test refuses to overwrite an existing desktop installation.
It uses a temporary install directory and a synthetic home directory,
then verifies cleanup and unchanged user PATH. Logs are retained under
`dist/installer-smoke/`; it does not read real SAP credentials.
It covers same-version reinstall, not an upgrade from an older release.

For unattended installation without PATH or shortcuts:

```powershell
.\sap-adt-<ver>-windows-x86_64-setup.exe /CURRENTUSER /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NOICONS /TASKS=""
```

## Manual steps

```
sap-adt configure          # interactive; password entered locally
sap-adt credentials doctor # backend diagnostics (no secrets)
sap-adt status             # local config state, not a live SAP login
```

## Known gaps

- Interactive wizard / configuration and elevated installs need a separate
  verification pass; the local smoke test does not certify them.
- No code signing: SmartScreen/AV warnings cannot be "eliminated" without a
  signing certificate and a real Windows verification pass.
- `iscc` absence exits 2 with a clear BLOCKED message; it never fakes output.
