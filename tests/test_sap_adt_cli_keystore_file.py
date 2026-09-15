"""Tests for the passphrase-derived encrypted-file backend (fallback)."""
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "sap-adt-cli" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from lib.keystore import file_store  # noqa: E402
from lib.keystore.base import KeyStoreError  # noqa: E402

PASSPHRASE_ENV = "SAP_ADT_MASTER_PASSPHRASE"


class FileStoreTestBase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.enc = self.tmp / ".sap-adt-cli" / "secrets.enc"

    def tearDown(self):
        self._td.cleanup()

    def store(self, env_passphrase="master-pass", **kw):
        store = file_store.FileStore(store_file=self.enc, **kw)
        self._passphrase = env_passphrase
        return store

    def run_with_passphrase(self, fn):
        if self._passphrase is None:
            with patch.dict(os.environ, {}, clear=True):
                return fn()
        with patch.dict(os.environ, {PASSPHRASE_ENV: self._passphrase}):
            return fn()


class FileStoreAvailabilityTests(FileStoreTestBase):
    def test_name_and_writable(self):
        s = self.store()
        self.assertEqual(s.name, "file")
        self.assertTrue(s.writable)

    def test_available_when_cryptography_importable(self):
        s = self.store()
        ok, reason = s.available()
        self.assertTrue(ok)
        self.assertIn("passphrase", reason)

    def test_unavailable_without_cryptography_and_hints_extra(self):
        s = self.store()
        def boom():
            raise ImportError("No module named cryptography")
        s._load_crypto = boom
        ok, reason = s.available()
        self.assertFalse(ok)
        self.assertIn("cryptography", reason)
        self.assertIn("[file]", reason)


class FileStoreContractTests(FileStoreTestBase):
    def test_set_get_roundtrip(self):
        s = self.store()
        self.run_with_passphrase(lambda: s.set("dev", "file-secret"))
        self.assertEqual(self.run_with_passphrase(lambda: s.get("dev")), "file-secret")

    def test_ciphertext_only_on_disk_with_0600_and_random_salt(self):
        s = self.store()
        self.run_with_passphrase(lambda: s.set("dev", "file-secret"))
        raw = self.enc.read_text()
        self.assertNotIn("file-secret", raw)
        data = json.loads(raw)
        self.assertIn("salt", data)
        self.assertEqual(stat.S_IMODE(self.enc.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.enc.parent.stat().st_mode), 0o700)
        # A second store gets a fresh random salt.
        other = self.tmp / "other.enc"
        s2 = file_store.FileStore(store_file=other)
        with patch.dict(os.environ, {PASSPHRASE_ENV: "master-pass"}):
            s2.set("dev", "file-secret")
        self.assertNotEqual(json.loads(other.read_text())["salt"], data["salt"])

    def test_get_missing_key_returns_none_without_passphrase_prompt(self):
        s = self.store(env_passphrase=None)
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(s.get("never-set"))

    def test_delete_removes_secret_and_is_idempotent(self):
        s = self.store()
        self.run_with_passphrase(lambda: s.set("dev", "file-secret"))
        self.run_with_passphrase(lambda: s.delete("dev"))
        self.assertIsNone(self.run_with_passphrase(lambda: s.get("dev")))
        self.run_with_passphrase(lambda: s.delete("dev"))

    def test_overwrite_replaces_secret(self):
        s = self.store()
        self.run_with_passphrase(lambda: s.set("dev", "first"))
        self.run_with_passphrase(lambda: s.set("dev", "second"))
        self.assertEqual(self.run_with_passphrase(lambda: s.get("dev")), "second")

    def test_unicode_secret_roundtrip(self):
        s = self.store()
        self.run_with_passphrase(lambda: s.set("dev", "口令-Æ-🔐"))
        self.assertEqual(self.run_with_passphrase(lambda: s.get("dev")), "口令-Æ-🔐")

    def test_wrong_passphrase_raises_clear_error(self):
        s = self.store()
        self.run_with_passphrase(lambda: s.set("dev", "file-secret"))
        # A fresh process has an empty passphrase cache.
        s2 = file_store.FileStore(store_file=self.enc)
        with patch.dict(os.environ, {PASSPHRASE_ENV: "wrong-pass"}):
            with self.assertRaises(KeyStoreError) as ctx:
                s2.get("dev")
        self.assertIn("passphrase", str(ctx.exception).lower())

    def test_non_interactive_without_env_passphrase_fails_closed_without_prompt(self):
        s = self.store(env_passphrase=None)
        with patch.dict(os.environ, {}, clear=True), \
             patch("sys.stdin") as fake_stdin:
            fake_stdin.isatty.return_value = False
            with self.assertRaises(KeyStoreError) as ctx:
                s.set("dev", "secret")
        self.assertIn(PASSPHRASE_ENV, str(ctx.exception))

    def test_corrupt_store_file_raises_keystore_error(self):
        s = self.store()
        self.enc.parent.mkdir(parents=True, exist_ok=True)
        self.enc.write_text("{not json")
        with patch.dict(os.environ, {PASSPHRASE_ENV: "x"}):
            with self.assertRaises(KeyStoreError):
                s.get("dev")


if __name__ == "__main__":
    unittest.main()
