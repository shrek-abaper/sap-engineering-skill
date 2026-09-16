"""Batch 8: ABAP Unit parser/command tests.

Real captures (empty shell, alert-only) live in tests/fixtures/. The
testMethod path is exercised only against synthetic/*.synthetic.xml and
is marked as such — see docs/known-issues.md.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "skills" / "sap-adt-cli" / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "skills" / "sap-adt-cli" / "scripts"))

from lib.parsers import findings  # noqa: E402
from test_sap_adt_cli_config import load_cli_module  # noqa: E402


class UnitParserRealTests(unittest.TestCase):
    def test_empty_shell_no_tests_found(self):
        d = findings.parse_unit((FIXTURES / "unit.empty.xml").read_bytes())
        self.assertEqual(d["findings"], [])
        m = d["_meta"]
        self.assertTrue(m["no_tests_found"])
        self.assertEqual((m["total"], m["failed"], m["skipped"]), (0, 0, 0))
        self.assertIsNone(m["duration_ms"])

    def test_alert_only_is_warning_still_no_tests_found(self):
        # A defective test class: an alert exists but NO method executed.
        # Distinct from both "no test class" and "all tests passed".
        d = findings.parse_unit((FIXTURES / "unit.alert-only.xml").read_bytes())
        self.assertEqual(len(d["findings"]), 1)
        f = d["findings"][0]
        self.assertEqual(f["severity"], "warning")  # kind, not severity attr
        self.assertEqual(f["source_severity"], "critical")
        self.assertEqual(f["line"], 1)
        self.assertTrue(d["_meta"]["no_tests_found"])
        self.assertEqual(d["_meta"]["duration_category"], "short")
        self.assertIn("defective", f["text"])


class UnitParserSyntheticTests(unittest.TestCase):
    def setUp(self):
        self.path = FIXTURES / "synthetic" / "unit.methods.synthetic.xml"

    def test_methods_counts_and_failed_assertion(self):
        d = findings.parse_unit(self.path.read_bytes())
        m = d["_meta"]
        self.assertFalse(m["no_tests_found"])
        self.assertEqual(m["total"], 3)
        self.assertEqual(m["failed"], 1)
        self.assertEqual(m["skipped"], 1)
        self.assertEqual(m["duration_ms"], 49)
        self.assertEqual(m["duration_category"], "short")
        self.assertEqual(len(d["findings"]), 1)
        f = d["findings"][0]
        self.assertEqual(f["severity"], "error")
        self.assertEqual(f["source_severity"], "critical")
        self.assertEqual(f["line"], 18)
        self.assertIn("Expected: 2 but was: 3", f["text"])


class UnitCommandTests(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()
        self.handlers = sys.modules["lib.handlers"]

        class Cfg:
            username = "DEVELOPER"
            profile_name = "dev"
            allow_write = False
            allow_transport = False

        self.cfg = Cfg()
        self.payload = (FIXTURES / "unit.empty.xml").read_bytes()

        class FakeResponse:
            content = self.payload
            text = self.payload.decode()

        class FakeConfig:
            def base_url(self):
                return "https://sap-dev.example.com:8000"

        self._patches = [
            patch.object(self.cli, "load_config", return_value=self.cfg),
            patch.object(self.handlers, "get_config", return_value=FakeConfig()),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)
        self.req = patch.object(self.handlers, "make_adt_request",
                                 return_value=FakeResponse())
        self.req.start()
        self.addCleanup(self.req.stop)

    def _invoke(self, *args):
        return CliRunner().invoke(self.cli.cli, ["run-unit-test", *args])

    def test_harmless_default_read_only_envelope(self):
        r = self._invoke("ZCL_X")
        self.assertEqual(r.exit_code, 0, r.output)
        d = json.loads(r.output)
        self.assertEqual(d["kind"], "findings")
        self.assertTrue(d["meta"]["no_tests_found"])
        self.assertEqual(d["meta"]["risk_level"], "harmless")
        self.assertEqual(d["meta"]["config_version"], "v4")

    def test_dangerous_without_allow_write_is_gate_3(self):
        # gate fires before any HTTP call: the mocked request must not run
        with patch.object(self.handlers, "make_adt_request") as no_http:
            r = self._invoke("ZCL_X", "--risk-level", "dangerous")
        self.assertEqual(r.exit_code, 3, r.output)
        self.assertEqual(json.loads(r.output)["error"]["code"], "WRITE_DISABLED")
        no_http.assert_not_called()

    def test_critical_against_prod_profile_refused_before_prompt(self):
        self.cfg.allow_write = True
        self.cfg.profile_name = "PRD-100"
        r = self._invoke("ZCL_X", "--risk-level", "critical", "--yes")
        self.assertEqual(r.exit_code, 3, r.output)
        self.assertEqual(json.loads(r.output)["error"]["code"], "WRITE_DISABLED")
        self.assertIn("production", json.loads(r.output)["error"]["message"])

    def test_dangerous_requires_risk_text_in_confirmation(self):
        self.cfg.allow_write = True
        r = self._invoke("ZCL_X", "--risk-level", "dangerous")
        self.assertEqual(r.exit_code, 3, r.output)  # non-TTY -> CONFIRM_REQUIRED
        env = json.loads(r.output)
        self.assertEqual(env["error"]["code"], "CONFIRM_REQUIRED")

    def test_fail_on_never_succeeds_even_with_findings(self):
        class R:
            content = (FIXTURES / "unit.alert-only.xml").read_bytes()
            text = content.decode()
        with patch.object(self.handlers, "make_adt_request", return_value=R()):
            r = self._invoke("ZCL_X", "--fail-on", "never")
        self.assertEqual(r.exit_code, 0, r.output)

    def test_fail_on_warning_exits_1_for_alert(self):
        class R:
            content = (FIXTURES / "unit.alert-only.xml").read_bytes()
            text = content.decode()
        with patch.object(self.handlers, "make_adt_request", return_value=R()):
            r = self._invoke("ZCL_X", "--fail-on", "warning")
        self.assertEqual(r.exit_code, 1, r.output)


if __name__ == "__main__":
    unittest.main()
