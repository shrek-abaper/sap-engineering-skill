"""Transport collect config resolution: default vs. explicit legacy path.

Covers the phase-1 guarantee that the legacy plaintext collector config
(~/.sap-transport-gate/config.json) is ONLY read on the explicit
--legacy-config path and can never silently fill in for a missing ADT
profile or failed authentication.

No real SAP system is contacted; resolution stops before any HTTP call.
"""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from sap_adt.transport import legacy_config

from test_sap_adt_cli_config import MemoryKeystore  # noqa: E402


class LegacyConfigFileTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.legacy_file = self.tmp / ".sap-transport-gate" / "config.json"
        self.legacy_file.parent.mkdir(parents=True)
        self._file_patch = patch.object(
            legacy_config, "LEGACY_CONFIG_FILE", self.legacy_file
        )
        self._file_patch.start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self._td.cleanup)

    def test_missing_file_raises_with_path_and_migration_hint(self):
        with self.assertRaises(legacy_config.LegacyConfigError) as ctx:
            legacy_config.load_legacy_config()
        message = str(ctx.exception)
        self.assertIn(str(self.legacy_file), message)
        self.assertIn("sap-adt configure", message)

    def test_valid_file_loads_and_warns_without_secrets(self):
        self.legacy_file.write_text(json.dumps({
            "url": "https://legacy.example.com:8000",
            "username": "LEGACY_USER",
            "password": "top-secret-value",
            "client": "100",
        }))
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            cfg = legacy_config.load_legacy_config()
        self.assertEqual(cfg.url, "https://legacy.example.com:8000")
        self.assertEqual(cfg.client, "100")
        warning = stderr.getvalue()
        self.assertIn("legacy plaintext config", warning)
        self.assertIn(str(self.legacy_file), warning)
        self.assertIn("sap-adt configure", warning)
        # The warning must never echo the secret it just read.
        self.assertNotIn("top-secret-value", warning)

    def test_invalid_json_reports_path_without_secret(self):
        self.legacy_file.write_text("{not json")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            with self.assertRaises(legacy_config.LegacyConfigError) as ctx:
                legacy_config.load_legacy_config()
        self.assertIn(str(self.legacy_file), str(ctx.exception))
        self.assertEqual(stderr.getvalue(), "")


class TransportConfigResolutionTests(unittest.TestCase):
    """cli._transport_config: legacy file is never an implicit fallback."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.legacy_file = self.tmp / ".sap-transport-gate" / "config.json"
        self.legacy_file.parent.mkdir(parents=True)
        self.legacy_file.write_text(json.dumps({
            "url": "https://legacy.example.com:8000",
            "username": "LEGACY_USER",
            "password": "top-secret-value",
            "client": "100",
        }))
        # Import cli at runtime and patch through the module tree it actually
        # uses: CLI tests re-import sap_adt fresh per test, so module objects
        # bound at this file's import time may belong to a stale tree.
        from sap_adt import cli as cli_module

        self.cli = cli_module
        self.config_mod = cli_module.config_module
        self.legacy_mod = cli_module.legacy_config

        self.config_file = self.tmp / "home" / ".sap-adt-cli" / "config.json"
        self.config_file.parent.mkdir(parents=True)
        self.keystore = MemoryKeystore()
        patches = [
            patch.object(self.legacy_mod, "LEGACY_CONFIG_FILE", self.legacy_file),
            patch.object(self.config_mod, "CONFIG_DIR", self.config_file.parent),
            patch.object(self.config_mod, "CONFIG_FILE", self.config_file),
            patch.object(self.config_mod, "_OLD_CONFIG_DIR", self.tmp / "nope-old"),
            patch.object(self.config_mod, "_OLD_CONFIG_FILE", self.tmp / "nope-old" / "config.json"),
            patch.object(self.config_mod.credentials, "REGISTRY", [self.keystore]),
        ]
        for p in patches:
            p.start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self._td.cleanup)

    def test_default_path_never_reads_legacy_file(self):
        # Legacy file exists, no env, no profile: default resolution must
        # fail with CONFIG_MISSING rather than silently using the legacy file.
        stderr = io.StringIO()
        with patch.dict("os.environ", {}, clear=True):
            with redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as ctx:
                    self.cli._transport_config(legacy=False)
        self.assertEqual(ctx.exception.code, 2)

    def test_explicit_legacy_reads_legacy_file(self):
        stderr = io.StringIO()
        with patch.dict("os.environ", {}, clear=True):
            with redirect_stderr(stderr):
                cfg = self.cli._transport_config(legacy=True)
        self.assertEqual(cfg.url, "https://legacy.example.com:8000")
        self.assertIn("legacy plaintext config", stderr.getvalue())

    def test_legacy_path_prefers_complete_env_connection(self):
        # Old collector semantics: env beats the legacy file.
        env = {
            "SAP_URL": "https://env.example.com:8000",
            "SAP_USERNAME": "ENV_USER",
            "SAP_PASSWORD": "env-secret",
            "SAP_CLIENT": "200",
        }
        with patch.dict("os.environ", env, clear=True):
            cfg = self.cli._transport_config(legacy=True)
        self.assertEqual(cfg.url, "https://env.example.com:8000")
        self.assertEqual(cfg.client, "200")


if __name__ == "__main__":
    unittest.main()
