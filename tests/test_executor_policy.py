"""Target identity, strict profile selection and connection scope contracts."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from test_sap_adt_cli_config import load_cli_module


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.cli, self.config = load_cli_module()
        self.policy = sys.modules["sap_adt.policy"]
        self.client = sys.modules["sap_adt.adt.client"]
        self.cfg = self.config.SapConfig("https://example.invalid", "USER", "secret", "100",
                                         profile_name="dev")

    def test_target_binds_origin_client_environment_not_alias_or_password(self):
        first = self.policy.target(self.cfg)["fingerprint"]
        self.cfg.profile_name, self.cfg.password = "alias", "other"
        self.cfg.url = "https://example.invalid:443"
        self.assertEqual(first, self.policy.target(self.cfg)["fingerprint"])
        self.cfg.client = "200"
        self.assertNotEqual(first, self.policy.target(self.cfg)["fingerprint"])

    def test_target_mismatch_refuses_before_handler(self):
        with patch.object(self.cli, "load_config", return_value=self.cfg), \
                patch.object(self.cli.handlers, "get_class") as handler:
            result = CliRunner().invoke(self.cli.cli, [
                "--expect-client", "200", "get-class", "ZCL_TEST"])
        self.assertEqual(result.exit_code, 3, result.output)
        self.assertEqual(json.loads(result.output)["error"]["category"], "policy_or_precondition")
        handler.assert_not_called()

    def test_nested_target_guard_is_enforced(self):
        with patch.object(self.cli, "load_config", return_value=self.cfg), \
                patch.object(self.cli.handlers, "diff_transport") as handler:
            result = CliRunner().invoke(self.cli.cli, [
                "--expect-environment", "prd", "transport", "diff", "DEVK900001"])
        self.assertEqual(result.exit_code, 3, result.output)
        handler.assert_not_called()

    def test_strict_profile_does_not_consult_environment_connection(self):
        raw = {"profiles": {"qas": {"url": "https://qas.invalid", "username": "U", "client": "200"}}}
        with patch.object(self.config, "_read_raw", return_value=raw), \
                patch.object(self.config, "_stored_password", return_value="secret"), \
                patch.object(self.config, "load_env_connection", side_effect=AssertionError):
            cfg = self.config.load_profile_connection("qas")
        self.assertEqual(cfg.client, "200")
        self.assertFalse(cfg.from_environment)

    def test_connection_scope_restores_all_state_on_failure(self):
        previous = self.config.SapConfig("https://old.invalid", "OLD", "old", "200")
        session = object()
        self.client.set_config(previous)
        self.client._session, self.client._csrf_token = session, "old-token"
        self.client._session_cookies = {"old": "cookie"}
        with self.assertRaises(RuntimeError):
            with self.client.connection_scope(self.cfg):
                self.assertIsNone(self.client._session)
                self.assertIsNone(self.client._csrf_token)
                self.assertIs(self.client.active_config(), self.cfg)
                raise RuntimeError("interrupted")
        self.assertIs(self.client.active_config(), previous)
        self.assertIs(self.client._session, session)
        self.assertEqual(self.client._session_cookies, {"old": "cookie"})

    def test_unit_risk_annotation_does_not_claim_human_approval(self):
        item = self.policy.operation("run-unit-test", {"risk_level": ["critical"]})
        self.assertTrue(item["approval_required"])
        self.assertEqual(item["risk_level"], "high")
        self.assertEqual(item["approval_identity"], "not_attested_by_cli")
