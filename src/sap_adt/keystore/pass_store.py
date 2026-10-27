"""Backend for the GPG-based ``pass`` password manager (headless Linux).

Usable on servers and containers that already run password-store with a
GPG key — no D-Bus/Secret Service required. Secrets live under the
``sap-adt-cli/`` prefix and are piped over stdin, never via argv.
"""
import shutil
import subprocess
from typing import Optional

from . import register
from .base import KeyStoreError

PREFIX = "sap-adt-cli"
_TIMEOUT_SECONDS = 15


class PassStore:
    name = "pass"
    writable = True

    def _which(self) -> Optional[str]:
        return shutil.which("pass")

    def _run(self, args: list, stdin_text: Optional[str] = None):
        return subprocess.run(
            args,
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )

    def available(self):
        if not self._which():
            return False, "`pass` not installed (GPG password manager)"
        try:
            proc = self._run(["pass", "ls"])
        except (OSError, subprocess.SubprocessError) as e:
            return False, f"`pass ls` failed: {e}"
        if proc.returncode != 0:
            return False, "`pass ls` failed (password store not initialized with `pass init`?)"
        return True, "GPG password store (sap-adt-cli/ prefix)"

    def _path(self, key: str) -> str:
        return f"{PREFIX}/{key}"

    def get(self, key: str) -> Optional[str]:
        proc = self._run(["pass", "show", self._path(key)])
        if proc.returncode == 0:
            return proc.stdout.strip()
        if "is not in the password store" in (proc.stderr or ""):
            return None
        raise KeyStoreError(f"`pass show` failed: {(proc.stderr or '').strip()[:300]}")

    def list_keys(self):
        try:
            proc = self._run(["pass", "ls", PREFIX])
        except (OSError, subprocess.SubprocessError):
            return []
        if proc.returncode != 0:
            return []
        # `pass ls` prints a tree; leaf lines contain our one-segment keys.
        keys = set()
        for line in (proc.stdout or "").splitlines():
            leaf = line.replace("├──", " ").replace("└──", " ").replace("│", " ").strip()
            if "/" in leaf:
                leaf = leaf.rsplit("/", 1)[-1].strip()
            if leaf and all(c.isalnum() or c in "_-" for c in leaf):
                keys.add(leaf)
        return sorted(keys)

    def set(self, key: str, secret: str) -> None:
        proc = self._run(
            ["pass", "insert", "-m", "-f", self._path(key)],
            stdin_text=secret,
        )
        if proc.returncode != 0:
            raise KeyStoreError(f"`pass insert` failed: {(proc.stderr or '').strip()[:300]}")

    def delete(self, key: str) -> None:
        # -f keeps the command non-interactive; a missing entry is not an error.
        self._run(["pass", "rm", "-f", self._path(key)])


register(PassStore())
