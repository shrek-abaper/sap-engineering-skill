"""Tests for the read-only environment-variable keystore backend."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "sap-adt-cli" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from lib.keystore import env_store, BackendNotWritableError  # noqa: E402


class EnvStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = env_store.EnvStore()

    def test_name_and_read_only(self):
        self.assertEqual(self.store.name, "env")
        self.assertFalse(self.store.writable)

    def test_get_reads_sap_adt_profile_password(self):
        with patch.dict(os.environ, {"SAP_ADT_DEV_PASSWORD": "env-secret"}):
            self.assertEqual(self.store.get("dev"), "env-secret")

    def test_variable_name_is_profile_uppercased(self):
        with patch.dict(os.environ, {"SAP_ADT_QAS1_PASSWORD": "env-secret"}):
            self.assertEqual(self.store.get("qas1"), "env-secret")

    def test_get_missing_returns_none(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(self.store.get("dev"))

    def test_set_and_delete_are_rejected(self):
        with self.assertRaises(BackendNotWritableError):
            self.store.set("dev", "x")
        with self.assertRaises(BackendNotWritableError):
            self.store.delete("dev")

    def test_available_when_no_profile_password_is_set(self):
        with patch.dict(os.environ, {}, clear=True):
            ok, reason = self.store.available()
        self.assertFalse(ok)
        self.assertIn("SAP_ADT_*_PASSWORD", reason)

    def test_available_when_a_profile_password_is_set(self):
        with patch.dict(os.environ, {"SAP_ADT_DEV_PASSWORD": "x"}):
            ok, reason = self.store.available()
        self.assertTrue(ok)
        self.assertIn("SAP_ADT_DEV_PASSWORD", reason)

    def test_available_ignores_unrelated_sap_vars(self):
        with patch.dict(os.environ, {"SAP_PASSWORD": "global", "SAP_URL": "https://x"}):
            ok, _reason = self.store.available()
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
