# Portable runtime

The portable archive and the desktop installer use the **same** PyInstaller
onedir runtime — built by `tools/build_runtime.py` on the target OS.

| Platform | Archive | Verified |
|---|---|---|
| Linux x86_64 | `dist/runtime/sap-adt-<ver>-linux-x86_64.tar.gz` | ✅ local (glibc 2.39, Ubuntu 24.04) |
| Windows x86_64 | `dist/runtime/sap-adt-<ver>-windows-x86_64.zip` | ✅ local (Windows 11 x64 via WSL interop; CLI 1.5.3+) |
| macOS arm64 | `dist/runtime/sap-adt-<ver>-darwin-arm64.tar.gz` | ❌ planned (no macOS host) |

## Use

```bash
tar -xzf sap-adt-<ver>-linux-x86_64.tar.gz -C /opt   # newest 1.x, any directory
/opt/sap-adt/sap-adt --version
/opt/sap-adt/sap-adt credentials doctor
```

On Windows PowerShell, download the newest compatible Windows ZIP from
the release page and extract into a directory you can write:

```powershell
Expand-Archive .\sap-adt-<ver>-windows-x86_64.zip -DestinationPath .\sap-adt-portable
.\sap-adt-portable\sap-adt\sap-adt.exe --version
```

Portable extraction does not modify PATH. The separate
[Windows desktop installer](windows.md) offers a PATH task.

The new source-only `sap-adt update --check` can check the stable Python
release version, but that does not prove a matching standalone build exists.
Portable/desktop installations are not self-overwritten: `update` directs
you to use the matching release archive/installer. It never tries to run pip
inside a frozen runtime. Configuration and keystore entries stay separate.

The archive is relocatable: it contains the interpreter, Python runtime,
keyring/cryptography and CA bundle. External system components are still
capability-probed, not bundled: Secret Service daemon, GPG/`pass`, Windows
PowerShell (DPAPI). Configuration remains in `~/.sap-adt-cli`; nothing is
written inside the extracted directory except at run time by the OS.

## glibc boundary

A build succeeds only for the platform it runs on. A Linux binary built on
glibc 2.39 will not run on older enterprise distributions with an older
glibc; build (and verify) there instead of assuming portability.
