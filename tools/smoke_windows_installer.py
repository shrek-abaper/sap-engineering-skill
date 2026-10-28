#!/usr/bin/env python3
"""Verify the Windows desktop installer without touching user PATH or SAP data.

Runs silent install, same-version upgrade and uninstall in a temporary path
containing spaces and Unicode. Refuses to run over an existing installation.
The PATH task and Start Menu icons are disabled; real credentials are never
used. Run with Windows Python after tools/build_installer.py.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNINSTALL_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
    r"\{9C9C0D2E-3F2A-4B1C-9E1A-5A0A0D7C1A11}_is1"
)


def main() -> int:
    if os.name != "nt":
        raise SystemExit("Run this smoke test with Windows Python.")
    import winreg

    def installed() -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY):
                return True
        except FileNotFoundError:
            return False

    def user_path():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                return winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            return None

    if installed():
        raise SystemExit("Existing sap-adt desktop installation found; refusing to alter it.")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\sap-adt-cli\Installer"):
            raise SystemExit("Existing sap-adt installer state found; refusing to alter it.")
    except FileNotFoundError:
        pass
    for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY,
                                0, winreg.KEY_READ | view):
                raise SystemExit("Existing machine-wide sap-adt installation found; refusing to alter it.")
        except FileNotFoundError:
            pass

    info = json.loads(
        (ROOT / "dist" / "runtime" / "windows-x86_64" / "build-info.json")
        .read_text(encoding="utf-8"))
    version = info["version"]
    installer = ROOT / "dist" / "installers" / f"sap-adt-{version}-windows-x86_64-setup.exe"
    if not installer.is_file():
        raise SystemExit(f"Installer missing: {installer}")
    iscc = shutil.which("iscc")
    if not iscc:
        raise SystemExit("Inno Setup (iscc) must be on PATH to run the PATH cleanup tests.")

    before_path = user_path()
    logs = ROOT / "dist" / "installer-smoke"
    logs.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sap-adt-installer-smoke-") as tmp:
        work = Path(tmp)
        subprocess.run(
            [iscc, "/Q", f"/O{work}", str(ROOT / "tests" / "windows" / "path-tests.iss")],
            check=True, timeout=60,
        )
        path_test_log = logs / "path-tests.log"
        subprocess.run(
            [str(work / "path-tests.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES",
             "/NORESTART", "/SP-", f"/LOG={path_test_log}"],
            cwd=work, check=True, timeout=60,
        )
        if "Installer PATH cleanup tests passed." not in path_test_log.read_text(encoding="utf-8-sig"):
            raise RuntimeError("Installer PATH cleanup tests did not complete.")
        app = work / "\u5b89\u88c5 \u8def\u5f84" / "sap-adt"
        home = work / "home"
        config = home / ".sap-adt-cli" / "config.json"
        config.parent.mkdir(parents=True)
        config.write_text('{"smoke_test": "preserve"}\n', encoding="utf-8")
        saved_config = config.read_bytes()
        env = {**os.environ, "USERPROFILE": str(home)}
        local_setup = work / "setup.exe"
        local_setup.write_bytes(installer.read_bytes())
        uninstaller = app / "unins000.exe"

        def uninstall():
            subprocess.run(
                [str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                 f"/LOG={logs / 'uninstall.log'}"],
                cwd=work, env=env, check=True, timeout=120,
            )
            deadline = time.monotonic() + 30
            while installed() or (app / "sap-adt.exe").exists():
                if time.monotonic() >= deadline:
                    raise RuntimeError("Uninstall did not remove the application and registration.")
                time.sleep(0.2)

        try:
            for phase in ("install", "upgrade"):
                subprocess.run(
                    [str(local_setup), "/CURRENTUSER", "/VERYSILENT", "/SUPPRESSMSGBOXES",
                     "/NORESTART", "/SP-", "/NOICONS", "/TASKS=",
                     f"/DIR={app}", f"/LOG={logs / (phase + '.log')}"],
                    cwd=work, env=env, check=True, timeout=120,
                )
                if not installed() or not (app / "configure.cmd").is_file():
                    raise RuntimeError(f"{phase}: installation is incomplete.")
                log = (logs / (phase + ".log")).read_text(encoding="utf-8-sig")
                if "Installed sap-adt --version self-test passed." not in log:
                    raise RuntimeError(f"{phase}: installer self-test did not complete.")
                actual = subprocess.run(
                    [str(app / "sap-adt.exe"), "--version"], env=env,
                    capture_output=True, text=True, check=True, timeout=30,
                ).stdout.strip()
                if actual != f"sap-adt, version {version}":
                    raise RuntimeError(f"{phase}: unexpected runtime version: {actual}")
                subprocess.run(
                    [str(app / "sap-adt.exe"), "--help"], env=env,
                    stdout=subprocess.DEVNULL, check=True, timeout=30,
                )
                if user_path() != before_path or config.read_bytes() != saved_config:
                    raise RuntimeError(f"{phase}: user PATH or configuration changed.")
        finally:
            if uninstaller.is_file():
                uninstall()
        if user_path() != before_path or config.read_bytes() != saved_config:
            raise RuntimeError("Uninstall changed user PATH or configuration.")
        print(f"[smoke_windows_installer] OK: {version}: silent install -> upgrade -> uninstall")
        print(f"[smoke_windows_installer] Logs: {logs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
