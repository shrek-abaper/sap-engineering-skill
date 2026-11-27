"""Explicit JSON includes maintenance commands, legacy results and usage errors."""
import json
import unittest
from unittest.mock import patch

from click.testing import CliRunner
from test_sap_adt_cli_config import load_cli_module


class ExecutorOutputTests(unittest.TestCase):
    def setUp(self):
        self.cli, self.config = load_cli_module()
        self.cfg = self.config.SapConfig("https://example.invalid", "U", "secret", "100",
                                        profile_name="dev")

    def invoke(self, *args):
        with patch.object(self.cli, "load_config", return_value=self.cfg), \
                patch.object(self.cli, "load_config_with_source", return_value=(self.cfg, "profile")):
            return CliRunner().invoke(self.cli.cli, ["--format", "json", *args])

    def test_status_exposes_target_binding_but_never_secret(self):
        result = self.invoke("status")
        self.assertEqual(result.exit_code, 0, result.output)
        data = json.loads(result.stdout)
        self.assertEqual(data["data"]["target"]["client"], "100")
        self.assertEqual(len(data["data"]["target"]["fingerprint"]), 64)
        self.assertNotIn("secret", result.output)
        for key in ("meta", "data", "warnings", "next_steps"):
            self.assertIn(key, data)

    def test_local_reports_and_profile_list_are_enveloped(self):
        with patch.object(self.cli, "list_profiles", return_value=[]), \
                patch.object(self.cli.credentials_reports, "status_text", return_value="ready"), \
                patch.object(self.cli.credentials_reports, "doctor_text", return_value="healthy"):
            for args in (("profile", "list"), ("credentials", "status"), ("credentials", "doctor")):
                result = self.invoke(*args)
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertTrue(json.loads(result.stdout)["ok"])

    def test_usage_errors_are_one_json_document_on_stderr(self):
        for args in (("no-such-command",), ("get-class",), ("get-class", "ZCL_X", "--unknown")):
            result = self.invoke(*args)
            self.assertNotEqual(result.exit_code, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(json.loads(result.stderr)["error"]["code"], "BAD_REQUEST")

    def test_json_configure_never_starts_an_interactive_wizard(self):
        with patch.object(self.cli, "run_configure_wizard") as wizard:
            result = self.invoke("configure")
        self.assertEqual(result.exit_code, 3)
        wizard.assert_not_called()

    def test_partial_evidence_is_visible_outside_business_data(self):
        result = self.cli.handlers.AdtResult(kind="scalar", data={
            "evidence_gaps": [{"code": "UNAVAILABLE"}]}, meta={"partial": True})
        with patch.object(self.cli.handlers, "get_type_info", return_value=result):
            output = self.invoke("get-type-info", "ZTYPE")
        item = json.loads(output.stdout)
        self.assertEqual(item["warnings"][0]["code"], "UNAVAILABLE")
        self.assertTrue(item["next_steps"])
