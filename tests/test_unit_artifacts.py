"""Unit gate semantics, supplied coverage binding and private archive export."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from test_sap_adt_cli_config import load_cli_module


class UnitArtifactTests(unittest.TestCase):
    def setUp(self):
        self.cli, self.config = load_cli_module()
        from sap_adt.adt import test_artifacts
        from sap_adt import artifacts
        self.m, self.a = test_artifacts, artifacts
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_no_tests_partial_and_missing_required_coverage_never_pass(self):
        for state, meta, minimum in (
                ("not_run", {}, None), ("passed", {"partial": True}, None),
                ("passed", {}, 80)):
            gate = self.m.gate({"summary": {"status": state}}, meta, {"percent": None}, minimum)
            self.assertNotEqual(gate["status"], "passed")
        self.assertEqual(self.m.gate({"summary": {"status": "passed"}}, {},
                                    {"percent": 75}, 80)["status"], "failed")

    def test_supplied_coverage_is_bound_to_target_scope_and_source(self):
        cfg = self.config.SapConfig("https://example.invalid", "U", "s", "100")
        source = "one\ntwo\nthree\n"
        report = {"schema_version": 1,
                  "target_fingerprint": self.cli.policy.target(cfg)["fingerprint"],
                  "files": [{"uri": "/sap/bc/adt/oo/classes/zcl_a/source/main",
                             "source_sha256": self.cli.source_write.sha256_text(
                                 self.cli.source_write.canonical_source(source)),
                             "executable_lines": [1, 2], "covered_lines": [1]}]}
        path = self.root / "coverage.json"
        path.write_bytes(self.a.json_bytes(report))
        plan = {"objects": [{"uri": "/sap/bc/adt/oo/classes/zcl_a"}]}
        with patch.object(self.cli.handlers, "_base", return_value="https://example.invalid"), \
                patch.object(self.cli.handlers, "get_source", return_value=self.cli.handlers.AdtResult(
                    data={"source": source, "line_count": 3})):
            result = self.m.coverage(path, plan, cfg)
            self.assertEqual(result["percent"], 50)
            cfg.client = "200"
            with self.assertRaises(ValueError):
                self.m.coverage(path, plan, cfg)
            cfg.client = "100"
            report["files"][0]["source_sha256"] = "0" * 64
            path.write_bytes(self.a.json_bytes(report))
            with self.assertRaisesRegex(ValueError, "source hash"):
                self.m.coverage(path, plan, cfg)

    def test_archive_has_verifiable_hashes_and_never_overwrites(self):
        path = self.root / "unit.zip"
        result = self.a.write_package(path, "unit", {"results.json": {"status": "not_run"}})
        with ZipFile(path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            member = manifest["assets"][0]
            self.assertEqual(hashlib.sha256(archive.read(member["path"])).hexdigest(), member["sha256"])
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            self.a.write_package(path, "unit", {"different.json": {}})
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), result["sha256"])
        with self.assertRaises(ValueError):
            self.a.write_package(self.root / "bad.zip", "unit", {"../escape": b"x"})

    def test_skeleton_fails_until_assertions_are_supplied_and_is_local_only(self):
        path = self.root / "test.abap"
        result = self.m.skeleton("LTC_EXAMPLE", path)
        self.assertFalse(result["uploaded"])
        self.assertIn("cl_abap_unit_assert=>fail", path.read_text())
        with self.assertRaises(FileExistsError):
            self.m.skeleton("LTC_EXAMPLE", path)

    def test_approval_hash_binds_artifact_destination_and_gate(self):
        plan = {"objects": [], "plan_sha256": "old"}
        self.m.bind_options(plan, {}, "unit.zip", 80)
        before = plan["plan_sha256"]
        self.m.bind_options(plan, {}, "other.zip", 80)
        self.assertNotEqual(plan["plan_sha256"], before)
