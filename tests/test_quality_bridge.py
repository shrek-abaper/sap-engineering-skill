"""Quality engine completeness and native abaplint JSON normalization."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_sap_adt_cli_config import load_cli_module


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.cli, self.config = load_cli_module()
        from sap_adt.adt import quality
        self.m = quality
        self.h = self.cli.handlers
        self.cfg = self.config.SapConfig("https://example.invalid", "U", "s", "100")

    def test_empty_incomplete_atc_is_not_a_passing_quality_gate(self):
        result = self.h.AdtResult(data={"findings": []}, meta={"result_incomplete": True})
        with patch.object(self.h, "run_atc", return_value=result):
            data = self.m.collect(self.cfg, "class", "ZCL_A", engines=["atc"])
        self.assertEqual(data["gate"]["status"], "incomplete")

    def test_engine_failure_is_not_hidden_by_another_engines_clean_result(self):
        with patch.object(self.h, "syntax_check", return_value=self.h.AdtResult(data={"findings": []})), \
                patch.object(self.h, "run_atc", return_value=self.h.AdtResult(
                    is_error=True, error_code="AUTH_FAILED", text="denied")):
            data = self.m.collect(self.cfg, "class", "ZCL_A")
        self.assertEqual(data["gate"]["status"], "incomplete")
        self.assertEqual(data["evidence_gaps"][0]["engine"], "atc")

    def test_findings_keep_their_engine_rules_and_exemptions(self):
        findings = [{"severity": "error", "text": "approved exemption", "exempted": True,
                     "check_id": "RULE"}]
        with patch.object(self.h, "run_atc", return_value=self.h.AdtResult(data={"findings": findings})):
            data = self.m.collect(self.cfg, "class", "ZCL_A", engines=["atc"])
        self.assertEqual(data["gate"]["status"], "passed")
        self.assertEqual(data["findings"][0]["engine"], "atc")
        self.assertTrue(data["findings"][0]["exempted"])

    def test_native_lint_issues_require_target_source_and_report_binding(self):
        from sap_adt import artifacts, policy
        report = [{"description": "Use a named constant", "key": "rule", "file": "zcl_a.clas.abap",
                   "start": {"row": 1, "col": 2}, "end": {"row": 1, "col": 3}, "severity": "Warning"}]
        snapshot = {"sha256": "sourcehash", "uri": "/sap/bc/adt/oo/classes/zcl_a/source/main"}
        manifest = {"schema_version": 1, "completed": True, "files_checked": 1,
                    "engine_version": "test-version", "source_file": report[0]["file"],
                    "target_fingerprint": policy.target(self.cfg)["fingerprint"],
                    "source_sha256": snapshot["sha256"], "object_uri": snapshot["uri"],
                    "report_sha256": hashlib.sha256(artifacts.json_bytes(report)).hexdigest()}
        with tempfile.TemporaryDirectory() as directory:
            p, m = Path(directory) / "report.json", Path(directory) / "manifest.json"
            p.write_bytes(artifacts.json_bytes(report)); m.write_bytes(artifacts.json_bytes(manifest))
            with patch.object(self.m.comparison, "snapshot", return_value=snapshot):
                result = self.m.collect(self.cfg, "class", "ZCL_A", engines=["abaplint"],
                                        abaplint_report=p, abaplint_manifest=m, fail_on="warning")
                self.assertEqual(result["gate"]["status"], "failed")
                self.assertEqual(result["findings"][0]["rule_id"], "rule")
                manifest["source_sha256"] = "stale"
                m.write_bytes(artifacts.json_bytes(manifest))
                result = self.m.collect(self.cfg, "class", "ZCL_A", engines=["abaplint"],
                                        abaplint_report=p, abaplint_manifest=m)
                self.assertEqual(result["gate"]["status"], "incomplete")
