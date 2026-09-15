import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner


CONFIG_PATH = Path(__file__).resolve().parents[1] / "skills" / "sap-adt-cli" / "scripts" / "lib" / "config.py"
SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "sap-adt-cli" / "scripts"


def load_config_module():
    # Load config.py under a unique synthetic package so its relative imports
    # (.credentials / .keystore) work and every test gets fresh modules.
    import types
    import uuid

    lib_path = SCRIPTS_PATH / "lib"
    pkg_base = f"cfgpkg_{uuid.uuid4().hex}"
    top = types.ModuleType(pkg_base)
    top.__path__ = []
    lib = types.ModuleType(f"{pkg_base}.lib")
    lib.__path__ = [str(lib_path)]
    sys.modules[pkg_base] = top
    sys.modules[f"{pkg_base}.lib"] = lib
    spec = importlib.util.spec_from_file_location(f"{pkg_base}.lib.config", CONFIG_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class MemoryKeystore:
    """In-memory KeyStore used to isolate config tests from OS backends."""

    def __init__(self, name="memory"):
        self.name = name
        self.writable = True
        self.data = {}

    def available(self):
        return True, "memory test backend"

    def get(self, key):
        return self.data.get(key)

    def set(self, key, secret):
        self.data[key] = secret

    def delete(self, key):
        self.data.pop(key, None)


def load_cli_module():
    sys.path.insert(0, str(SCRIPTS_PATH))
    # Drop the whole lib package tree so each test gets fresh modules
    # (reports bind to config, stores bind to module-level paths).
    sys.modules.pop("sap_adt_cli", None)
    for name in [n for n in sys.modules if n == "lib" or n.startswith("lib.")]:
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location("sap_adt_cli_under_test", SCRIPTS_PATH / "sap_adt_cli.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, sys.modules["lib.config"]


class SapAdtCliConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.module = load_config_module()
        self.keystore = MemoryKeystore()
        self.module.credentials.set_registry_override([self.keystore])
        self.env_path = self.tmp_path / "skill" / ".env"
        self.config_file = self.tmp_path / "home" / ".sap-adt-cli" / "config.json"
        self.old_config_file = self.tmp_path / "home" / ".sap-abap-cli" / "config.json"
        self.env_path.parent.mkdir(parents=True)
        self.config_file.parent.mkdir(parents=True)
        self.old_config_file.parent.mkdir(parents=True)
        self.module._SKILL_DOTENV = self.env_path
        self.module.CONFIG_DIR = self.config_file.parent
        self.module.CONFIG_FILE = self.config_file
        self.module._OLD_CONFIG_DIR = self.old_config_file.parent
        self.module._OLD_CONFIG_FILE = self.old_config_file

    def tearDown(self):
        self.tmp.cleanup()

    def write_json_config(self, **overrides):
        data = {
            "url": "https://json.example.com:8000",
            "username": "JSON_USER",
            "password": "json-secret",
            "client": "100",
            "language": "DE",
            "verify_ssl": False,
            "allow_write": True,
            "allow_transport": True,
        }
        data.update(overrides)
        self.config_file.write_text(json.dumps(data), encoding="utf-8")

    def write_dotenv(self, content):
        self.env_path.write_text(content, encoding="utf-8")

    def clear_sap_env(self):
        return patch.dict(
            os.environ,
            {
                "SAP_URL": "",
                "SAP_USERNAME": "",
                "SAP_PASSWORD": "",
                "SAP_CLIENT": "",
                "SAP_LANGUAGE": "",
                "SAP_VERIFY_SSL": "",
            },
            clear=False,
        )

    def test_process_environment_wins_over_dotenv_and_json(self):
        self.write_dotenv(
            "\n".join(
                [
                    "SAP_URL=https://dotenv.example.com:8000",
                    "SAP_USERNAME=DOTENV_USER",
                    "SAP_PASSWORD=dotenv-secret",
                    "SAP_CLIENT=200",
                ]
            )
        )
        self.write_json_config()

        with patch.dict(
            os.environ,
            {
                "SAP_URL": "https://env.example.com:8000",
                "SAP_USERNAME": "ENV_USER",
                "SAP_PASSWORD": "env-secret",
                "SAP_CLIENT": "300",
                "SAP_LANGUAGE": "FR",
                "SAP_VERIFY_SSL": "0",
            },
            clear=False,
        ):
            config, source = self.module.load_config_with_source()

        self.assertEqual(config.url, "https://env.example.com:8000")
        self.assertEqual(config.username, "ENV_USER")
        self.assertEqual(config.client, "300")
        self.assertEqual(config.language, "FR")
        self.assertFalse(config.verify_ssl)
        self.assertFalse(config.allow_write)
        self.assertFalse(config.allow_transport)
        self.assertEqual(source, "process environment (overrides config profiles)")

    def test_skill_dotenv_wins_over_json(self):
        self.write_dotenv(
            "\n".join(
                [
                    "SAP_URL=https://dotenv.example.com:8000",
                    "SAP_USERNAME=DOTENV_USER",
                    "SAP_PASSWORD=dotenv-secret",
                    "SAP_CLIENT=200",
                    "SAP_LANGUAGE=JA",
                    "SAP_VERIFY_SSL=0",
                ]
            )
        )
        self.write_json_config()

        with self.clear_sap_env():
            config, source = self.module.load_config_with_source()

        self.assertEqual(config.url, "https://dotenv.example.com:8000")
        self.assertEqual(config.username, "DOTENV_USER")
        self.assertEqual(config.client, "200")
        self.assertEqual(config.language, "JA")
        self.assertFalse(config.verify_ssl)
        self.assertFalse(config.allow_write)
        self.assertFalse(config.allow_transport)
        self.assertEqual(source, f"{self.env_path} (overrides config profiles)")

    def test_incomplete_dotenv_falls_back_to_json(self):
        self.write_dotenv(
            "\n".join(
                [
                    "SAP_URL=https://dotenv.example.com:8000",
                    "SAP_USERNAME=DOTENV_USER",
                ]
            )
        )
        self.write_json_config()

        with self.clear_sap_env():
            config, source = self.module.load_config_with_source()

        self.assertEqual(config.url, "https://json.example.com:8000")
        self.assertEqual(config.username, "JSON_USER")
        self.assertTrue(config.allow_write)
        self.assertTrue(config.allow_transport)
        self.assertEqual(source, f"{self.config_file} (profile 'default')")

    def test_quoted_dotenv_values_are_parsed(self):
        self.write_dotenv(
            "\n".join(
                [
                    'SAP_URL="https://quoted.example.com:8000"',
                    "SAP_USERNAME='QUOTED_USER'",
                    'SAP_PASSWORD="quoted-secret"',
                    "SAP_CLIENT='400'",
                ]
            )
        )

        with self.clear_sap_env():
            config, source = self.module.load_config_with_source()

        self.assertEqual(config.url, "https://quoted.example.com:8000")
        self.assertEqual(config.username, "QUOTED_USER")
        self.assertEqual(config.password, "quoted-secret")
        self.assertEqual(config.client, "400")
        self.assertEqual(config.language, "EN")
        self.assertTrue(config.verify_ssl)
        self.assertFalse(config.allow_write)
        self.assertFalse(config.allow_transport)
        self.assertEqual(source, f"{self.env_path} (overrides config profiles)")

    def test_dotenv_can_set_write_capability_flags(self):
        self.write_dotenv(
            "\n".join(
                [
                    "SAP_URL=https://dotenv.example.com:8000",
                    "SAP_USERNAME=DOTENV_USER",
                    "SAP_PASSWORD=dotenv-secret",
                    "SAP_CLIENT=200",
                    "SAP_ALLOW_WRITE=1",
                    "SAP_ALLOW_TRANSPORT=true",
                ]
            )
        )

        with self.clear_sap_env():
            config, source = self.module.load_config_with_source()

        self.assertTrue(config.allow_write)
        self.assertTrue(config.allow_transport)
        self.assertEqual(source, f"{self.env_path} (overrides config profiles)")

    def test_status_prints_active_dotenv_source(self):
        cli_module, config_module = load_cli_module()
        env_path = self.tmp_path / "cli-skill" / ".env"
        config_file = self.tmp_path / "cli-home" / ".sap-adt-cli" / "config.json"
        env_path.parent.mkdir(parents=True)
        config_file.parent.mkdir(parents=True)
        env_path.write_text(
            "\n".join(
                [
                    "SAP_URL=https://status-dotenv.example.com:8000",
                    "SAP_USERNAME=STATUS_USER",
                    "SAP_PASSWORD=status-secret",
                    "SAP_CLIENT=500",
                ]
            ),
            encoding="utf-8",
        )
        config_module._SKILL_DOTENV = env_path
        config_module.CONFIG_DIR = config_file.parent
        config_module.CONFIG_FILE = config_file
        config_module._OLD_CONFIG_DIR = self.tmp_path / "cli-home" / ".sap-abap-cli"
        config_module._OLD_CONFIG_FILE = config_module._OLD_CONFIG_DIR / "config.json"

        with self.clear_sap_env():
            result = CliRunner().invoke(cli_module.cli, ["status"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("URL:             https://status-dotenv.example.com:8000", result.output)
        self.assertIn(f"Config source:   {env_path} (overrides config profiles)", result.output)
        self.assertNotIn(f"Config:          {config_file}", result.output)


if __name__ == "__main__":
    unittest.main()
