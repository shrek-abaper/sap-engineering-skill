"""Migration and keystore integration for config.json profiles."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "skills" / "sap-adt-cli" / "scripts"),
)

from test_sap_adt_cli_config import MemoryKeystore, load_config_module  # noqa: E402


class ConfigKeystoreMigrationTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.module = load_config_module()
        self.keystore = MemoryKeystore()
        self.module.credentials.set_registry_override([self.keystore])
        self.config_file = self.tmp / ".sap-adt-cli" / "config.json"
        self.config_file.parent.mkdir(parents=True)
        self.module.CONFIG_DIR = self.config_file.parent
        self.module.CONFIG_FILE = self.config_file

    def tearDown(self):
        self._td.cleanup()

    def write_config(self, raw):
        self.config_file.write_text(json.dumps(raw), encoding="utf-8")

    def v2_config(self, profiles=None, password="plain-secret", active="dev"):
        profiles = profiles or {
            "dev": {
                "url": "https://dev.example.com:8000",
                "username": "DEVUSER",
                "password": password,
                "client": "100",
                "language": "EN",
                "verify_ssl": True,
            }
        }
        return {"version": 2, "active_profile": active, "profiles": profiles}

    def read_config(self):
        return json.loads(self.config_file.read_text(encoding="utf-8"))

    def test_plaintext_password_is_migrated_to_keystore_and_stripped_from_config(self):
        self.write_config(self.v2_config())
        err = io.StringIO()
        with redirect_stderr(err):
            config = self.module.load_config()
        self.assertEqual(config.password, "plain-secret")
        self.assertNotIn("password", self.read_config()["profiles"]["dev"])
        self.assertEqual(self.keystore.get("dev"), "plain-secret")
        warning = err.getvalue()
        self.assertIn("plain text", warning.lower())
        self.assertIn("change", warning.lower())  # rotation advice

    def test_migration_creates_no_backup_files(self):
        self.write_config(self.v2_config())
        with redirect_stderr(io.StringIO()):
            self.module.load_config()
        entries = [p.name for p in self.config_file.parent.iterdir()]
        self.assertEqual(sorted(entries), ["config.json"])

    def test_migration_is_idempotent(self):
        self.write_config(self.v2_config())
        with redirect_stderr(io.StringIO()) as first:
            self.module.load_config()
        self.assertIn("plain", first.getvalue().lower())
        with redirect_stderr(io.StringIO()) as second:
            self.module.load_config()
        self.assertEqual(second.getvalue(), "")

    def test_migrated_profile_loads_password_from_keystore_on_subsequent_runs(self):
        self.write_config(self.v2_config())
        with redirect_stderr(io.StringIO()):
            self.module.load_config()
        config = self.module.load_config()
        self.assertEqual(config.password, "plain-secret")
        self.assertEqual(config.username, "DEVUSER")

    def test_all_plaintext_profiles_are_migrated_in_one_pass(self):
        raw = self.v2_config(profiles={
            "dev": {"url": "https://d", "username": "U1", "password": "p1", "client": "100"},
            "qas": {"url": "https://q", "username": "U2", "password": "p2", "client": "200"},
        })
        self.write_config(raw)
        with redirect_stderr(io.StringIO()):
            self.module.load_config()
        self.assertEqual(self.keystore.get("dev"), "p1")
        self.assertEqual(self.keystore.get("qas"), "p2")

    def test_when_no_writable_backend_exists_plaintext_keeps_working_with_warning(self):
        self.module.credentials.set_registry_override([])  # nothing to migrate into
        self.write_config(self.v2_config())
        err = io.StringIO()
        with redirect_stderr(err):
            config = self.module.load_config()
        self.assertEqual(config.password, "plain-secret")  # legacy path still works
        self.assertIn("password", self.read_config()["profiles"]["dev"])
        self.assertIn("plain text", err.getvalue().lower())


class ConfigKeystoreWriteTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.module = load_config_module()
        self.keystore = MemoryKeystore()
        self.module.credentials.set_registry_override([self.keystore])
        self.config_file = self.tmp / ".sap-adt-cli" / "config.json"
        self.config_file.parent.mkdir(parents=True)
        self.module.CONFIG_DIR = self.config_file.parent
        self.module.CONFIG_FILE = self.config_file

    def tearDown(self):
        self._td.cleanup()

    def read_config(self):
        return json.loads(self.config_file.read_text(encoding="utf-8"))

    def test_save_profile_writes_password_to_keystore_not_config(self):
        self.module.save_profile(
            name="dev", url="https://d", username="DEVUSER",
            password="new-secret", client="100",
        )
        self.assertNotIn("password", self.read_config()["profiles"]["dev"])
        self.assertEqual(self.keystore.get("dev"), "new-secret")
        config = self.module.load_config()
        self.assertEqual(config.password, "new-secret")

    def test_saving_profile_with_blank_password_keeps_existing_keystore_entry(self):
        self.module.save_profile(
            name="dev", url="https://d", username="DEVUSER",
            password="first-secret", client="100",
        )
        self.module.save_profile(
            name="dev", url="https://d2", username="DEVUSER",
            password="", client="100",
        )
        self.assertEqual(self.keystore.get("dev"), "first-secret")
        self.assertEqual(self.module.load_config().url, "https://d2")

    def test_remove_profile_deletes_keystore_entry(self):
        self.module.save_profile(
            name="dev", url="https://d", username="DEVUSER",
            password="x", client="100",
        )
        self.module.save_profile(
            name="qas", url="https://q", username="QUSER",
            password="y", client="200",
        )
        self.module.set_active_profile("qas")
        self.module.remove_profile("dev")
        self.assertIsNone(self.keystore.get("dev"))
        self.assertEqual(self.keystore.get("qas"), "y")

    def test_profile_without_password_fails_with_clear_error_not_traceback_in_get_config(self):
        raw = {
            "version": 2,
            "active_profile": "dev",
            "profiles": {
                "dev": {
                    "url": "https://d", "username": "DEVUSER",
                    "client": "100", "language": "EN", "verify_ssl": True,
                }
            },
        }
        self.write_config_file(raw)
        # Batch 4b: bootstrap failure is a ConfigError (mapped to exit 2 by
        # lib.errors) rather than print+SystemExit.
        with self.assertRaises(self.module.ConfigError):
            self.module.get_config()

    def write_config_file(self, raw):
        self.config_file.write_text(json.dumps(raw), encoding="utf-8")

    def test_sapconfig_repr_masks_password(self):
        cfg = self.module.SapConfig(
            url="https://d", username="DEVUSER", password="top-secret", client="100"
        )
        self.assertNotIn("top-secret", repr(cfg))
        self.assertIn("***", repr(cfg))


if __name__ == "__main__":
    unittest.main()
