"""One contract suite executed against every keystore backend.

Per the credential design, this is the safety net for future backend
refactors: each backend is forced via select(preferred=...) and must
satisfy the same set/get/delete behavior. OS-specific backends use
injected seams (PowerShell, pass binary, keyring module); the file
backend runs against the real cryptography implementation.
"""
import base64
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "sap-adt-cli" / "scripts"
sys_path_insert = str(SCRIPTS_PATH)
import sys  # noqa: E402

sys.path.insert(0, sys_path_insert)

from lib.keystore import (  # noqa: E402
    dpapi_store,
    env_store,
    file_store,
    keyring_store,
    pass_store,
    select,
)
from lib.keystore.base import BackendNotWritableError  # noqa: E402

SECRET = "Contract-Secret-口令-42"
PASSPHRASE = "contract-master"


class KeystoreContract:
    """Backend must implement make_store(); stores are isolated per test."""

    def make_store(self):
        raise NotImplementedError

    def test_preferred_selection_returns_this_backend_fail_closed(self):
        store = self.make_store()
        self.assertIs(select(preferred=store.name, candidates=[store]), store)

    def test_set_get_roundtrip(self):
        store = self.make_store()
        store.set("contract-dev", SECRET)
        try:
            self.assertEqual(store.get("contract-dev"), SECRET)
        finally:
            store.delete("contract-dev")

    def test_get_missing_is_none(self):
        store = self.make_store()
        store.delete("contract-missing")
        self.assertIsNone(store.get("contract-missing"))

    def test_delete_idempotent(self):
        store = self.make_store()
        store.set("contract-dev", SECRET)
        store.delete("contract-dev")
        self.assertIsNone(store.get("contract-dev"))
        store.delete("contract-dev")

    def test_overwrite(self):
        store = self.make_store()
        try:
            store.set("contract-dev", "one")
            store.set("contract-dev", SECRET)
            self.assertEqual(store.get("contract-dev"), SECRET)
        finally:
            store.delete("contract-dev")


class FileBackendContract(KeystoreContract, unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.enc = Path(self._td.name) / "secrets.enc"
        self._env = patch.dict(os.environ, {"SAP_ADT_MASTER_PASSPHRASE": PASSPHRASE})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._td.cleanup()

    def make_store(self):
        return file_store.FileStore(store_file=self.enc, interactive=False)


class _FakeKeyringLib:
    def __init__(self):
        self.store = {}

    def get_keyring(self):
        return _MemoryBackend(self.store)

    def get_password(self, service, user):
        if user == "__probe__":
            return None
        return self.store.get((service, user))

    def set_password(self, service, user, password):
        self.store[(service, user)] = password

    def delete_password(self, service, user):
        self.store.pop((service, user), None)


class _MemoryBackend:
    name = "memory fake"

    def __init__(self, store):
        self.store = store


class KeyringBackendContract(KeystoreContract, unittest.TestCase):
    def make_store(self):
        lib = _FakeKeyringLib()
        store = keyring_store.KeyringStore()
        store._load_keyring = lambda: lib  # noqa: E731
        return store


class DpapiBackendContract(KeystoreContract, unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.enc = Path(self._td.name) / ".sap-adt-cli" / "secrets.json"

    def tearDown(self):
        self._td.cleanup()

    def make_store(self):
        store = dpapi_store.DpapiStore(secrets_file=self.enc)
        store._is_wsl = lambda: True  # noqa: E731
        store._find_powershell = lambda: "/mnt/c/WINDOWS/.../powershell.exe"  # noqa: E731

        def fake_run(script, payload):
            if "ConvertFrom-SecureString" in script:
                return "ENC:" + base64.b64encode(payload["secret"].encode()).decode()
            return base64.b64decode(payload["cipher"][4:]).decode()

        store._run_powershell = fake_run
        return store


class PassBackendContract(KeystoreContract, unittest.TestCase):
    def make_store(self):
        store = pass_store.PassStore()
        store._which = lambda: "/usr/bin/pass"  # noqa: E731
        data = {}

        def fake_run(args, stdin_text=None):
            proc = types.SimpleNamespace(returncode=0, stdout="", stderr="")
            if args[:2] == ["pass", "ls"]:
                proc.stdout = "Password Store\n"
            elif args[:2] == ["pass", "show"]:
                value = data.get(args[2])
                if value is None:
                    proc.returncode = 1
                    proc.stderr = f"{args[2]} is not in the password store."
                else:
                    proc.stdout = value
            elif args[:2] == ["pass", "insert"]:
                data[args[-1]] = stdin_text
            elif args[:2] == ["pass", "rm"]:
                data.pop(args[-1], None)
            return proc

        store._run = fake_run
        return store


class EnvBackendReadOnlyContract(unittest.TestCase):
    def setUp(self):
        self.store = env_store.EnvStore()

    def test_preferred_selection(self):
        with patch.dict(os.environ, {"SAP_ADT_CONTRACT-DEV_PASSWORD": SECRET}):
            self.assertIs(
                select(preferred="env", candidates=[self.store]), self.store
            )

    def test_get_and_no_write(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(self.store.get("contract-dev"))
            with self.assertRaises(BackendNotWritableError):
                self.store.set("contract-dev", SECRET)
            with self.assertRaises(BackendNotWritableError):
                self.store.delete("contract-dev")

    def test_get_reads_value(self):
        with patch.dict(os.environ, {"SAP_ADT_CONTRACT-DEV_PASSWORD": SECRET}):
            self.assertEqual(self.store.get("contract-dev"), SECRET)


if __name__ == "__main__":
    unittest.main()
