"""CLI tests: credentials set/forget/status/doctor and global --keystore."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "sap-adt-cli" / "scripts"))

from test_sap_adt_cli_config import load_cli_module  # noqa: E402


SECRET_PLACEHOLDER = "PLACEHOLDER-SECRET-789"


class CredentialsCliTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.cli, self.config_module = load_cli_module()
        self.credentials = sys.modules["lib.credentials"]
        self.dpapi_store = sys.modules["lib.keystore.dpapi_store"]
        self.file_store = sys.modules["lib.keystore.file_store"]
        self.keystore_pkg = sys.modules["lib.keystore"]

        self.home = self.tmp / "home"
        self.config_dir = self.home / ".sap-adt-cli"
        self.config_dir.mkdir(parents=True)
        self.config_file = self.config_dir / "config.json"
        self.config_module.CONFIG_DIR = self.config_dir
        self.config_module.CONFIG_FILE = self.config_file
        self.dpapi_store.SECRETS_FILE = self.config_dir / "secrets.json"
        self.file_store.STORE_FILE = self.config_dir / "secrets.enc"
        # Registered singletons hold the old module default path; repoint them.
        for store in self.keystore_pkg.REGISTRY:
            if store.name == "dpapi":
                store.secrets_file = self.dpapi_store.SECRETS_FILE
            if store.name == "file":
                store.store_file = self.file_store.STORE_FILE
                store.interactive = False
                store._passphrase = None
                store._fernet_cache = None
        self.credentials.reset_test_overrides()
        self.write_v2_config()

    def tearDown(self):
        self.credentials.reset_test_overrides()
        self._td.cleanup()

    def write_v2_config(self, active="dev"):
        raw = {
            "version": 2,
            "active_profile": active,
            "allow_write": False,
            "allow_transport": False,
            "profiles": {
                "dev": {"url": "https://D01.example.com", "username": "DEVUSER", "client": "100", "language": "EN", "verify_ssl": True},
                "qas": {"url": "https://Q01.example.com", "username": "DEVUSER", "client": "200", "language": "EN", "verify_ssl": True},
            },
        }
        self.config_file.write_text(json.dumps(raw), encoding="utf-8")

    def invoke(self, *args):
        return CliRunner().invoke(self.cli.cli, list(args))

    # -- status ------------------------------------------------------------

    def test_status_reports_unconfigured_profiles_without_secrets(self):
        result = self.invoke("credentials", "status")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("dev", result.output)
        self.assertIn("not configured", result.output.lower())
        self.assertNotIn(SECRET_PLACEHOLDER, result.output)

    # -- set ---------------------------------------------------------------

    def test_set_rejects_unknown_profile(self):
        result = self.invoke("credentials", "set", "nope", "--password", SECRET_PLACEHOLDER)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("nope", result.output)

    def test_set_via_env_var_on_selected_backend_and_status_shows_configured(self):
        # Force the file backend so the test is hermetic (no DPAPI/keyring).
        env = {
            "SAP_ADT_MASTER_PASSPHRASE": "test-master",
            "SAP_ADT_DEV_PASSWORD": SECRET_PLACEHOLDER,
        }
        with patch.dict(os.environ, env, clear=False):
            result = self.invoke("--keystore", "file", "credentials", "set", "dev")
            self.assertEqual(result.exit_code, 0, result.output)
            result2 = self.invoke("--keystore", "file", "credentials", "status")
        self.assertIn("configured", result2.output.lower())
        self.assertNotIn(SECRET_PLACEHOLDER, result2.output)
        # Ciphertext on disk only.
        raw = (self.config_dir / "secrets.enc").read_text()
        self.assertNotIn(SECRET_PLACEHOLDER, raw)

    def test_set_file_backend_without_passphrase_refuses(self):
        clean_env = {k: v for k, v in os.environ.items() if k != "SAP_ADT_MASTER_PASSPHRASE"}
        with patch.dict(clean_env, {}, clear=True):
            result = self.invoke(
                "--keystore", "file", "credentials", "set", "dev",
                "--password", SECRET_PLACEHOLDER,
            )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("SAP_ADT_MASTER_PASSPHRASE", result.output)

    def test_unknown_keystore_preference_fails_closed(self):
        result = self.invoke("--keystore", "nope", "credentials", "status")
        self.assertNotEqual(result.exit_code, 0)

    # -- forget ------------------------------------------------------------

    def test_forget_removes_entry_and_is_idempotent(self):
        env = {"SAP_ADT_MASTER_PASSPHRASE": "test-master"}
        with patch.dict(os.environ, env, clear=False):
            r1 = self.invoke("--keystore", "file", "credentials", "set", "dev", "--password", SECRET_PLACEHOLDER)
            self.assertEqual(r1.exit_code, 0, r1.output)
            r2 = self.invoke("--keystore", "file", "credentials", "forget", "dev")
            self.assertEqual(r2.exit_code, 0, r2.output)
            r3 = self.invoke("--keystore", "file", "credentials", "status")
        self.assertNotIn(SECRET_PLACEHOLDER, r3.output)

    def test_forget_unknown_profile_errors(self):
        result = self.invoke("credentials", "forget", "ghost")
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("ghost", result.output)

    # -- doctor ------------------------------------------------------------

    def test_doctor_lists_all_backends_with_marks_and_selected_tag(self):
        result = self.invoke("credentials", "doctor")
        self.assertEqual(result.exit_code, 0, result.output)
        for name in ("env", "keyring", "dpapi", "pass", "file"):
            self.assertIn(name, result.output)
        self.assertIn("selected", result.output)
        self.assertNotIn(SECRET_PLACEHOLDER, result.output)

    def test_doctor_warns_about_drvfs_when_config_dir_on_windows_mount(self):
        reports = sys.modules["lib.credentials_reports"]
        mounts = self.tmp / "mounts"
        mounts.write_text("C:\\134 /mnt/c drvfs rw 0 0\n/dev/sda / ext4 rw 0 0\n")
        fs = reports.mount_fs_for(Path("/mnt/c/home/.sap-adt-cli"), mounts_path=str(mounts))
        self.assertEqual(fs, "drvfs")
        warn = reports.drvfs_warning(Path("/mnt/c/home/.sap-adt-cli"), mounts_path=str(mounts))
        self.assertIn("drvfs", warn)
        self.assertIn("chmod", warn)
        # Native fs produces no warning.
        native = reports.drvfs_warning(Path("/home/user/.sap-adt-cli"), mounts_path=str(mounts))
        self.assertEqual(native, "")

    def test_doctor_entries_line_lists_local_file_entries_without_decrypting(self):
        env = {"SAP_ADT_MASTER_PASSPHRASE": "test-master"}
        with patch.dict(os.environ, env, clear=False):
            self.invoke("--keystore", "file", "credentials", "set", "dev", "--password", SECRET_PLACEHOLDER)
        result = self.invoke("credentials", "doctor")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("dev", result.output)


if __name__ == "__main__":
    unittest.main()
