import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner


CONFIG_PATH = Path(__file__).resolve().parents[1] / "src" / "sap_adt" / "config.py"
SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "src"


def load_config_module():
    # Load config.py under a unique synthetic package so its relative imports
    # (.credentials / .keystore) work and every test gets fresh modules.
    import types
    import uuid

    pkg_path = SCRIPTS_PATH / "sap_adt"
    pkg_base = f"cfgpkg_{uuid.uuid4().hex}"
    top = types.ModuleType(pkg_base)
    top.__path__ = []
    lib = types.ModuleType(f"{pkg_base}.sap_adt")
    lib.__path__ = [str(pkg_path)]
    sys.modules[pkg_base] = top
    sys.modules[f"{pkg_base}.sap_adt"] = lib
    spec = importlib.util.spec_from_file_location(f"{pkg_base}.sap_adt.config", CONFIG_PATH)
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
    # Drop the whole sap_adt package tree so each test gets fresh modules
    # (reports bind to config, stores bind to module-level paths).
    sys.modules.pop("sap_adt_cli_under_test", None)
    for name in [n for n in sys.modules if n == "sap_adt" or n.startswith("sap_adt.")]:
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location("sap_adt_cli_under_test", SCRIPTS_PATH / "sap_adt" / "cli.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, sys.modules["sap_adt.config"]


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
        self.module._DOTENV_OVERRIDE = self.env_path
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
                "SAP_ALLOW_WRITE": "",
                "SAP_ALLOW_TRANSPORT": "",
                "SAP_ALLOW_DEBUG": "",
                "SAP_ENVIRONMENT": "",
                "SAP_PROFILE": "",
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
        config_module._DOTENV_OVERRIDE = env_path
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

    def test_debug_is_never_inherited_from_global_or_write_capabilities(self):
        self.module.save_profile(
            name="qas", url="https://qas.example.invalid", username="OFFLINE",
            password="offline", client="000", allow_write=True, allow_transport=True,
        )
        raw = json.loads(self.config_file.read_text())
        raw.update(allow_write=True, allow_transport=True, allow_debug=True)
        self.config_file.write_text(json.dumps(raw))
        with self.clear_sap_env():
            config = self.module.load_config()
        self.assertTrue(config.allow_write)
        self.assertTrue(config.allow_transport)
        self.assertFalse(config.allow_debug)
        self.assertEqual(config.debug_source, "default")
        for value in (False, "true", "false", 1, None):
            with self.subTest(value=value), self.clear_sap_env():
                raw["profiles"]["qas"]["allow_debug"] = value
                self.config_file.write_text(json.dumps(raw))
                self.assertFalse(self.module.load_config().allow_debug)

    def test_profile_debug_is_preserved_isolated_and_refused_in_production(self):
        connection = dict(url="https://qas.example.invalid", username="OFFLINE",
                          password="offline", client="000")
        self.module.save_profile(name="qas", allow_debug=True, **connection)
        self.module.save_profile(name="qas", **connection)
        self.module.save_profile(name="dev", allow_write=True, **connection)
        self.module.save_profile(name="prd", allow_debug=True, **connection)
        with self.clear_sap_env():
            qas = self.module.load_config(profile="qas")
            self.assertTrue(qas.allow_debug)
            self.assertEqual(qas.debug_source, "profile")
            self.assertFalse(qas.allow_write)
            self.assertFalse(qas.allow_transport)
            self.assertFalse(self.module.load_config(profile="dev").allow_debug)
            prd = self.module.load_config(profile="prd")
        self.assertFalse(prd.allow_debug)
        self.assertEqual(prd.debug_source, "hard-refused")
        raw = json.loads(self.config_file.read_text())
        self.assertNotIn("allow_debug", raw)
        self.assertTrue(raw["profiles"]["prd"]["allow_debug"])

    def test_env_debug_has_its_own_flag_and_process_overrides_dotenv(self):
        self.write_dotenv("\n".join([
            "SAP_URL=https://dotenv.example.invalid", "SAP_USERNAME=OFFLINE",
            "SAP_PASSWORD=offline", "SAP_CLIENT=000", "SAP_ENVIRONMENT=qas",
            "SAP_ALLOW_WRITE=true", "SAP_ALLOW_TRANSPORT=true",
        ]))
        with self.clear_sap_env():
            self.assertFalse(self.module.load_config().allow_debug)
        with self.env_path.open("a") as stream:
            stream.write("\nSAP_ALLOW_DEBUG=true\n")
        for override, environment, expected in (("", "qas", True),
                                                 ("false", "qas", False),
                                                 ("true", "prd", False)):
            with self.subTest(override=override, environment=environment), self.clear_sap_env(), \
                    patch.dict(os.environ, {"SAP_ALLOW_DEBUG": override,
                                            "SAP_ENVIRONMENT": environment}):
                config = self.module.load_config()
                self.assertEqual(config.allow_debug, expected)
                self.assertEqual(config.debug_source,
                                 "hard-refused" if environment == "prd" else "env")

    def test_configure_debug_only_preserves_other_capabilities_and_tls(self):
        cli_module, module = load_cli_module()
        module.CONFIG_DIR = self.config_file.parent
        module.CONFIG_FILE = self.config_file
        module._OLD_CONFIG_FILE = self.old_config_file
        module._DOTENV_OVERRIDE = self.env_path
        module.credentials.set_registry_override([self.keystore])
        for writes in (False, True):
            with self.subTest(writes=writes), self.clear_sap_env():
                module.save_profile(
                    name="qas", url="https://qas.example.invalid", username="OFFLINE",
                    password="offline", client="000", allow_write=writes,
                    allow_transport=writes, verify_ssl=False,
                )
                for flag, enabled in (("--allow-debug", True), ("--no-allow-debug", False)):
                    result = CliRunner().invoke(
                        cli_module.cli, ["configure", "--profile", "qas", flag])
                    self.assertEqual(result.exit_code, 0, result.output)
                    config = module.load_config()
                    self.assertEqual(config.allow_debug, enabled)
                    self.assertEqual(config.allow_write, writes)
                    self.assertEqual(config.allow_transport, writes)
                    self.assertFalse(config.verify_ssl)
                    status = CliRunner().invoke(cli_module.cli, ["status"])
                    self.assertEqual(status.exit_code, 0, status.output)
                    self.assertIn("Debug mode:      " + ("ENABLED" if enabled else "DISABLED"),
                                  status.output)
        with self.clear_sap_env():
            module.save_profile(
                name="dev", url="https://dev.example.invalid", username="OFFLINE",
                password="offline", client="000", allow_debug=False,
            )
            result = CliRunner().invoke(
                cli_module.cli, ["--profile", "qas", "configure", "--allow-debug"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertTrue(module.load_config(profile="qas").allow_debug)
            self.assertFalse(module.load_config(profile="dev").allow_debug)

    def test_wizard_debug_defaults_off_and_opt_in_does_not_enable_writes(self):
        for answer, expected in (("", False), ("y", True)):
            with self.subTest(answer=answer), self.clear_sap_env(), \
                    patch("builtins.input", side_effect=[
                        "qas", "https://qas.example.invalid", "OFFLINE", "000",
                        "EN", "y", "N", "N", answer,
                    ]), patch("getpass.getpass", return_value="offline"), patch("builtins.print"):
                config = self.module.run_configure_wizard()
                self.assertEqual(config.allow_debug, expected)
                self.assertFalse(config.allow_write)
                self.assertFalse(config.allow_transport)
        for writes in (False, True):
            self.module.save_profile(
                name="qas", url="https://qas.example.invalid", username="OFFLINE",
                password="offline", client="000", allow_write=writes, allow_transport=writes,
            )
            self.module.set_global_capabilities(not writes, not writes)
            with self.subTest(writes=writes), self.clear_sap_env(), \
                    patch("builtins.input", side_effect=[""] * 8 + ["y"]), \
                    patch("getpass.getpass", return_value=""), patch("builtins.print"):
                config = self.module.run_configure_wizard()
            self.assertEqual(config.allow_write, writes)
            self.assertEqual(config.allow_transport, writes)
            self.assertTrue(config.allow_debug)


if __name__ == "__main__":
    unittest.main()
