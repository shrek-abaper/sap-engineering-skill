"""Regression selection, aggregate evidence, consent and JUnit contracts."""
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sap_adt.adt import handlers, unit_regression as unit
import test_sap_adt_cli_unit_tests as unit_tests


class RegressionTests(unittest.TestCase):
    def test_package_recursion_deduplicates_and_is_bounded_before_execution(self):
        data = {"objects": [
            {"type": "CLAS", "name": "ZCL_A"},
            {"type": "DEVC", "name": "ZPKG"},
            {"type": "TABL", "name": "ZTAB"}]}
        with patch.object(handlers, "get_package", return_value=handlers.AdtResult(data=data)):
            p = unit.plan([], "class", None, "ZPKG", None, True, 5,
                          ["harmless"], ["short"], {"profile": "dev"})
        self.assertEqual([o["name"] for o in p["objects"]], ["ZCL_A"])
        self.assertEqual(p["excluded"][0]["type"], "TABL")
        with patch.object(handlers, "get_package", return_value=handlers.AdtResult(
                data={"objects": [{"type": "CLAS", "name": "ZCL_A"},
                                  {"type": "CLAS", "name": "ZCL_B"}]})):
            with self.assertRaisesRegex(ValueError, "exceeds"):
                unit.plan([], "class", None, "ZPKG", None, False, 1,
                          ["harmless"], ["short"], {})

    def test_selection_hash_binds_scope_risk_and_target(self):
        args = (["ZCL_A"], "class", None, None, None, False, 5)
        p = unit.plan(*args, ["harmless"], ["short"], {"profile": "dev"})
        for risks, durations, target in [
                (["dangerous"], ["short"], {"profile": "dev"}),
                (["harmless"], ["long"], {"profile": "dev"}),
                (["harmless"], ["short"], {"profile": "qas"})]:
            self.assertNotEqual(p["plan_sha256"],
                                unit.plan(*args, risks, durations, target)["plan_sha256"])

    def test_package_include_and_function_member_are_not_misclassified(self):
        data = {"objects": [{"type": "PROG/I", "name": "ZINC"},
                            {"type": "INTF/OI", "name": "ZIF_TEST"},
                            {"type": "FUGR/FF", "name": "Z_FUNCTION"}]}
        with patch.object(handlers, "get_package", return_value=handlers.AdtResult(data=data)):
            prepared = unit.plan([], "class", None, "ZPKG", None, False, 10,
                                 ["harmless"], ["short"], {})
        self.assertEqual({o["type"] for o in prepared["objects"]}, {"include", "interface"})
        self.assertEqual(prepared["excluded"][0]["name"], "Z_FUNCTION")

    def test_interruption_preserves_unknown_current_and_unattempted_objects(self):
        prepared = unit.plan(["ZCL_A", "ZCL_B"], "class", None, None, None, False, 10,
                             ["harmless"], ["short"], {})
        with patch.object(handlers, "run_unit_test", side_effect=KeyboardInterrupt):
            result = unit.run(prepared)
        self.assertTrue(result.is_error)
        self.assertEqual(len(result.data["runs"]), 1)
        self.assertEqual(result.data["runs"][0]["error"]["code"], "EXECUTION_INCOMPLETE")
        self.assertTrue(any(g["code"] == "OBJECTS_NOT_ATTEMPTED" for g in result.data["evidence_gaps"]))

    def test_combined_risks_and_durations_are_one_request_not_nine_runs(self):
        xml = b"<runResult><testClass name='LTC'><testMethod name='OK'/></testClass></runResult>"
        response = type("Response", (), {"content": xml, "text": xml.decode()})()
        with patch.object(handlers, "_base", return_value="https://example.invalid"), \
                patch.object(handlers, "make_adt_request", return_value=response) as request:
            result = handlers.run_unit_test("class", "ZCL_X",
                                           risk_level=["harmless", "dangerous"],
                                           duration=["short", "long"])
        self.assertFalse(result.is_error)
        request.assert_called_once()
        body = ET.fromstring(request.call_args.kwargs["data"])
        self.assertEqual(body.find(".//testRiskLevels").attrib,
                         {"harmless": "true", "dangerous": "true", "critical": "false"})
        self.assertEqual(body.find(".//testDurations").attrib,
                         {"short": "true", "medium": "false", "long": "true"})
        self.assertFalse(request.call_args.kwargs["retry_csrf"])
        self.assertFalse(request.call_args.kwargs["allow_redirects"])

    def test_all_selection_cannot_hide_unknown_risk_or_duration(self):
        for risks, durations in ((["all", "unknown"], ["short"]),
                                 (["harmless"], ["all", "unknown"])):
            with self.subTest(risks=risks, durations=durations), self.assertRaises(ValueError):
                unit.selection(risks, unit.RISKS)
                unit.selection(durations, unit.DURATIONS)

    def test_informational_class_alerts_do_not_invent_passing_fixture_tests(self):
        data = {"runs": [{"object": {"type": "class", "name": "ZCL_A"}, "data": {
            "test_classes": [{"name": "LTC", "status": "passed", "methods": [],
                              "alerts": [{"severity": "info", "message": "informational"}]}],
            "evidence_gaps": [], "summary": {"status": "passed"}}}], "evidence_gaps": []}
        root = ET.fromstring(unit.junit(data))
        self.assertEqual(root.findall(".//testcase"), [])
        self.assertEqual(root.find("testsuite").get("tests"), "0")

    def test_unknown_execution_stops_remaining_objects_and_junit_reports_it(self):
        p = unit.plan(["ZCL_A", "ZCL_B"], "class", None, None, None, False, 5,
                      ["harmless"], ["short"], {})
        with patch.object(handlers, "run_unit_test", return_value=handlers.AdtResult(
                is_error=True, text="timeout", error_code="NETWORK_ERROR")) as execute:
            r = unit.run(p)
        execute.assert_called_once()
        self.assertEqual(r.data["summary"]["status"], "incomplete")
        self.assertTrue(r.meta["partial"])
        report = ET.fromstring(unit.junit(r.data))
        self.assertEqual(len(report.findall(".//error")), 2)

    def test_junit_preserves_failure_skip_and_partial_evidence(self):
        from sap_adt.adt.parsers.findings import parse_unit
        xml = b"""<runResult><testClass name="LTC"><testMethods>
        <testMethod name="FAIL" status="failed"/>
        <testMethod name="SKIP" status="skipped"/>
        </testMethods></testClass></runResult>"""
        parsed = parse_unit(xml)
        meta = parsed.pop("_meta")
        prepared = unit.plan(["ZCL_A"], "class", None, None, None, False, 5,
                             ["harmless"], ["short"], {})
        with patch.object(handlers, "run_unit_test", return_value=handlers.AdtResult(
                kind="findings", data=parsed, meta=meta)):
            result = unit.run(prepared)
        self.assertEqual(result.data["summary"]["status"], "failed")
        self.assertTrue(result.meta["partial"])
        root = ET.fromstring(unit.junit(result.data))
        self.assertEqual(len(root.findall(".//failure")), 1)
        self.assertEqual(len(root.findall(".//skipped")), 1)
        self.assertEqual(len(root.findall(".//error")), 1)


class RegressionConsentTests(unittest.TestCase):
    setUp = unit_tests.UnitCommandTests.setUp
    _invoke = unit_tests.UnitCommandTests._invoke

    def test_high_risk_execute_only_requires_reviewed_hash(self):
        self.cfg.allow_execute = True
        self.cfg.allow_write = False
        cli = CliRunner()
        dry = self._invoke("ZCL_A", "--risk-level", "dangerous", "--dry-run")
        self.assertEqual(dry.exit_code, 0, dry.output)
        digest = json.loads(dry.output)["data"]["plan"]["plan_sha256"]
        missing = self._invoke("ZCL_A", "--risk-level", "dangerous", "--yes")
        self.assertEqual(missing.exit_code, 3)
        actual = cli.invoke(self.cli.cli, [
            "run-unit-test", "ZCL_A", "--risk-level", "dangerous",
            "--yes", "--expect-plan-sha256", digest])
        self.assertEqual(actual.exit_code, 0, actual.output)
        changed = self._invoke("ZCL_B", "--risk-level", "dangerous", "--yes",
                               "--expect-plan-sha256", digest)
        self.assertEqual(json.loads(changed.output)["error"]["code"], "BASELINE_CHANGED")

    def test_write_permission_never_grants_test_execution(self):
        self.cfg.allow_write = True
        self.cfg.allow_execute = False
        result = self._invoke("ZCL_A", "--risk-level", "dangerous")
        self.assertEqual(result.exit_code, 3, result.output)
        self.assertEqual(json.loads(result.output)["error"]["code"], "EXECUTE_DISABLED")

    def test_junit_dry_run_binds_new_path_without_creating_report(self):
        self.cfg.allow_execute = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unit.xml"
            dry = self._invoke("ZCL_A", "--risk-level", "dangerous",
                               "--junit", str(path), "--dry-run")
            self.assertEqual(dry.exit_code, 0, dry.output)
            self.assertFalse(path.exists())
            prepared = json.loads(dry.output)["data"]["plan"]
            self.assertEqual(prepared["local_artifacts"]["junit"], str(path))
            changed = self._invoke("ZCL_A", "--risk-level", "dangerous",
                                   "--junit", str(path.with_name("other.xml")), "--yes",
                                   "--expect-plan-sha256", prepared["plan_sha256"])
            self.assertEqual(changed.exit_code, 3, changed.output)
            self.assertFalse(path.exists())
