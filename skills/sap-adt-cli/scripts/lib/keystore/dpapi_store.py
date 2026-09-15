"""WSL-only backend: Windows DPAPI through ``powershell.exe`` interop.

DPAPI binds the ciphertext to the current Windows user account, giving
the same protection level as Credential Manager without any extra
package. Detection is capability based (WSL markers + interop binary),
not OS based: plain ``platform.system()`` returns ``Linux`` in WSL.

The plaintext secret is passed over stdin as JSON — never as a command
line argument (argv is visible in the Windows task manager and WSL
``ps``). Only DPAPI blobs are persisted, in ``secrets.json`` (0600).
"""
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from . import register
from .base import KeyStoreError

SECRETS_FILE = Path.home() / ".sap-adt-cli" / "secrets.json"
_POWERSHELL = "powershell.exe"
_TIMEOUT_SECONDS = 15

# Encrypt: stdin JSON {"secret": "..."} -> DPAPI blob on stdout.
_ENCRYPT_SCRIPT = (
    "$ErrorActionPreference='Stop';"
    "[Console]::InputEncoding=[Text.Encoding]::UTF8;"
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
    "$obj=[Console]::In.ReadToEnd()|ConvertFrom-Json;"
    "$ss=ConvertTo-SecureString $obj.secret -AsPlainText -Force;"
    "ConvertFrom-SecureString $ss"
)

# Decrypt: stdin JSON {"cipher": "..."} -> plaintext on stdout.
# No -Key is passed to either cmdlet: key derivation is handled by DPAPI
# for the current Windows user.
_DECRYPT_SCRIPT = (
    "$ErrorActionPreference='Stop';"
    "[Console]::InputEncoding=[Text.Encoding]::UTF8;"
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
    "$obj=[Console]::In.ReadToEnd()|ConvertFrom-Json;"
    "$ss=ConvertTo-SecureString $obj.cipher;"
    "$ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($ss);"
    "try{[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}"
    "finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}"
)


class DpapiStore:
    name = "dpapi"
    writable = True

    def __init__(self, secrets_file: Optional[Path] = None):
        self.secrets_file = Path(secrets_file) if secrets_file else SECRETS_FILE

    # -- environment probes (overridable seams for tests) ---------------

    def _is_wsl(self) -> bool:
        if os.environ.get("WSL_DISTRO_NAME"):
            return True
        try:
            with open("/proc/version", encoding="utf-8") as f:
                return "microsoft" in f.read().lower()
        except OSError:
            return False

    def _find_powershell(self) -> Optional[str]:
        return shutil.which(_POWERSHELL)

    def _run_powershell(self, script: str, payload: dict) -> str:
        powershell = self._find_powershell()
        if not powershell:
            raise KeyStoreError(
                "powershell.exe not found on PATH; WSL interop may be disabled "
                "(check interop.appendWindowsPath in /etc/wsl.conf)"
            )
        try:
            proc = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=_TIMEOUT_SECONDS,
            )
        except OSError as e:
            raise KeyStoreError(f"could not invoke powershell.exe: {e}") from e
        except subprocess.TimeoutExpired as e:
            raise KeyStoreError("powershell.exe DPAPI call timed out") from e
        if proc.returncode != 0:
            detail = (proc.stderr or "").strip()
            raise KeyStoreError(
                f"powershell.exe DPAPI call failed (exit {proc.returncode}): {detail[:300]}"
            )
        return proc.stdout.strip()

    # -- KeyStore protocol ----------------------------------------------

    def available(self):
        if not self._is_wsl():
            return False, "only usable inside WSL with Windows interop (DPAPI is Windows-only)"
        if not self._find_powershell():
            return (
                False,
                "powershell.exe not found; WSL interop may be disabled "
                "(check interop.appendWindowsPath in /etc/wsl.conf)",
            )
        return True, "WSL + Windows DPAPI (bound to current Windows user)"

    def _read_entries(self) -> dict:
        try:
            with open(self.secrets_file, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as e:
            raise KeyStoreError(f"cannot read {self.secrets_file}: {e}") from e
        entries = data.get("entries") if isinstance(data, dict) else None
        return entries if isinstance(entries, dict) else {}

    def _write_entries(self, entries: dict) -> None:
        self.secrets_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.secrets_file.parent, 0o700)
        tmp = self.secrets_file.with_suffix(".json.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "entries": entries}, f, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.secrets_file)
        os.chmod(self.secrets_file, 0o600)

    def get(self, key: str) -> Optional[str]:
        blob = self._read_entries().get(key)
        if blob is None:
            return None
        return self._run_powershell(_DECRYPT_SCRIPT, {"cipher": blob})

    def set(self, key: str, secret: str) -> None:
        blob = self._run_powershell(_ENCRYPT_SCRIPT, {"secret": secret})
        entries = self._read_entries()
        entries[key] = blob
        self._write_entries(entries)

    def delete(self, key: str) -> None:
        entries = self._read_entries()
        if key in entries:
            del entries[key]
            self._write_entries(entries)


register(DpapiStore())
