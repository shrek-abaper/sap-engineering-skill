# Windows installer

**Status: implemented, NOT verified** — no Windows build host was available
(`packaging/targets.json` marks `windows-x86_64` as
`blocked-no-windows-host`). Do not treat this document as evidence that a
Windows build or install has been tested.

## What the installer does (when built on Windows)

1. `tools/build_runtime.py` produces `dist/runtime/windows-x86_64/sap-adt/`
   (PyInstaller onedir).
2. `tools/build_installer.py` compiles `packaging/windows/setup.iss` with
   Inno Setup 6 into `dist/installers/sap-adt-<ver>-windows-x86_64-setup.exe`.

Installer behavior (per-user, no admin by default):

- copies the runtime + `configure.cmd` into `%USERPROFILE%\...\sap-adt`;
- adds the install directory to the **user** PATH;
- runs `sap-adt --version` and `sap-adt credentials doctor` from the
  absolute install path (never the not-yet-refreshed PATH);
- tells the user to restart their terminal/agent;
- uninstall removes program files only — user config (`~/.sap-adt-cli`) and
  keystore entries stay.

## Manual steps

```
sap-adt configure          # interactive; password entered locally
sap-adt credentials doctor # backend diagnostics (no secrets)
sap-adt status             # local config state, not a live SAP login
```

## Known gaps

- No code signing: SmartScreen/AV warnings cannot be "eliminated" without a
  signing certificate and a real Windows verification pass.
- `iscc` absence exits 2 with a clear BLOCKED message; it never fakes output.
