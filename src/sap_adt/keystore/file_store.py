"""Fallback backend: passphrase-derived encrypted file (AEAD).

Last-resort backend for machines with neither an OS vault, WSL interop
nor password-store (minimal containers, unusual servers). A random
per-file salt and scrypt derive the key; Fernet (AES-128-CBC + HMAC)
provides authenticated encryption. The passphrase comes from
``SAP_ADT_MASTER_PASSPHRASE`` or an interactive prompt — there is no
keyless "encryption" mode, and non-interactive runs fail closed.

``cryptography`` is an OPTIONAL dependency (the ``[file]`` extra).
"""
import base64
import json
import os
import sys
from pathlib import Path
from typing import Optional

from . import register
from .base import KeyStoreError

STORE_FILE = Path.home() / ".sap-adt-cli" / "secrets.enc"
PASSPHRASE_ENV = "SAP_ADT_MASTER_PASSPHRASE"
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_LEN = 32
_SALT_LEN = 16


class FileStore:
    name = "file"
    writable = True

    def __init__(self, store_file: Optional[Path] = None, interactive: bool = True):
        self.store_file = Path(store_file) if store_file else STORE_FILE
        self.interactive = interactive
        self._passphrase: Optional[str] = None
        self._fernet_cache: Optional[tuple] = None  # (salt, Fernet)

    def _load_crypto(self):
        """Import seam so tests can simulate a missing cryptography package."""
        from cryptography.fernet import Fernet, InvalidToken  # noqa: PLC0415
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt  # noqa: PLC0415

        return Fernet, InvalidToken, Scrypt

    def available(self):
        try:
            self._load_crypto()
        except ImportError:
            return False, "cryptography package not installed (pip install cryptography, the [file] extra)"
        return True, "available (requires passphrase)"

    # -- passphrase / key derivation ------------------------------------

    def _get_passphrase(self, confirm_new: bool = False) -> str:
        if self._passphrase is not None:
            return self._passphrase
        env_value = os.environ.get(PASSPHRASE_ENV)
        if env_value:
            self._passphrase = env_value
            return env_value
        if not self.interactive or not sys.stdin.isatty():
            raise KeyStoreError(
                f"the 'file' keystore needs a master passphrase: set {PASSPHRASE_ENV} "
                "for non-interactive use, or run in a terminal"
            )
        import getpass  # noqa: PLC0415

        first = getpass.getpass("Master passphrase for the encrypted credential file: ")
        if confirm_new:
            second = getpass.getpass("Confirm master passphrase: ")
            if first != second:
                raise KeyStoreError("passphrases do not match")
        self._passphrase = first
        return first

    def _fernet_for(self, salt: bytes):
        if self._fernet_cache and self._fernet_cache[0] == salt:
            return self._fernet_cache[1]
        Fernet, _invalid, Scrypt = self._load_crypto()
        kdf = Scrypt(salt=salt, length=_KEY_LEN, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
        derived = kdf.derive(self._get_passphrase().encode("utf-8"))
        fernet = Fernet(base64.urlsafe_b64encode(derived))
        self._fernet_cache = (salt, fernet)
        return fernet

    # -- on-disk format --------------------------------------------------

    def _read_raw(self) -> Optional[dict]:
        try:
            with open(self.store_file, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as e:
            raise KeyStoreError(f"cannot read {self.store_file}: {e}") from e
        if not isinstance(data, dict) or "salt" not in data:
            raise KeyStoreError(f"unrecognized credential file format in {self.store_file}")
        return data

    def _write_raw(self, salt: bytes, entries: dict) -> None:
        self.store_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.store_file.parent, 0o700)
        payload = {
            "version": 1,
            "kdf": "scrypt",
            "salt": base64.b64encode(salt).decode("ascii"),
            "entries": entries,
        }
        tmp = self.store_file.with_suffix(".enc.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.store_file)
        os.chmod(self.store_file, 0o600)

    # -- KeyStore protocol ----------------------------------------------

    def get(self, key: str) -> Optional[str]:
        raw = self._read_raw()
        if raw is None:
            return None
        token = (raw.get("entries") or {}).get(key)
        if token is None:
            return None
        fernet = self._fernet_for(base64.b64decode(raw["salt"]))
        _Fernet, InvalidToken, _Scrypt = self._load_crypto()
        try:
            return fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken as e:
            raise KeyStoreError(
                "decryption failed: wrong master passphrase or a corrupt credential file"
            ) from e

    def list_keys(self):
        """Profile names in the encrypted file (keys are plaintext; values are not)."""
        raw = self._read_raw()
        return sorted((raw.get("entries") or {}).keys()) if raw else []

    def set(self, key: str, secret: str) -> None:
        raw = self._read_raw()
        if raw is None:
            salt = os.urandom(_SALT_LEN)
            entries = {}
            self._get_passphrase(confirm_new=True)
        else:
            salt = base64.b64decode(raw["salt"])
            entries = dict(raw.get("entries") or {})
        fernet = self._fernet_for(salt)
        entries[key] = fernet.encrypt(secret.encode("utf-8")).decode("ascii")
        self._write_raw(salt, entries)

    def delete(self, key: str) -> None:
        raw = self._read_raw()
        if raw is not None and key in (raw.get("entries") or {}):
            entries = dict(raw["entries"])
            del entries[key]
            self._write_raw(base64.b64decode(raw["salt"]), entries)


register(FileStore())
