"""Bounded DAG planning, baseline binding and partial-operation evidence."""
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_sap_adt_cli_config import load_cli_module


class ChangeSetTests(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()
        self.cs = importlib.import_module("sap_adt.adt.change_set")
        self.h = self.cli.handlers
        self.sw = self.cli.source_write
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "changes.json"
        (self.path.parent / "a.abap").write_text("new A")
        (self.path.parent / "b.abap").write_text("new B")
        self.operations = [
            {"id": "b", "depends_on": ["a"], "action": "write-source", "type": "class",
             "name": "ZCL_B", "file": "b.abap", "check": False},
            {"id": "a", "action": "write-source", "type": "class", "name": "ZCL_A",
             "file": "a.abap", "check": False}]

    def prepare(self, operations=None, **options):
        self.path.write_text(json.dumps({"schema_version": 1,
                                        "operations": operations or self.operations, **options}))
        with patch.object(self.h, "read_source_main", return_value=self.h.AdtResult(text="old")):
            return self.cs.prepare(self.path, {"profile": "dev"})

    def test_dependency_order_and_hash_bind_all_sources_and_options(self):
        plan = self.prepare()
        self.assertEqual([o["id"] for o in plan["operations"]], ["a", "b"])
        self.assertEqual(plan["plan_sha256"], self.prepare()["plan_sha256"])
        (self.path.parent / "b.abap").write_text("changed")
        self.assertNotEqual(plan["plan_sha256"], self.prepare()["plan_sha256"])
        changed = self.prepare(activate=True)
        self.assertTrue(changed["activate"])

    def test_cycles_duplicates_unknown_keys_and_escaping_files_are_refused(self):
        variants = [
            [{**self.operations[0], "depends_on": ["b"]}],
            [self.operations[1], self.operations[1]],
            [{**self.operations[1], "file": "../escape.abap"}],
            [{**self.operations[1], "unknown": True}],
            [{**self.operations[1], "depends_on": ["missing"]}],
            [self.operations[1], {**self.operations[1], "id": "same-object"}],
        ]
        for ops in variants:
            with self.subTest(ops=ops), self.assertRaises((ValueError, FileNotFoundError)):
                self.prepare(ops)

    def test_unknown_first_write_stops_and_keeps_unattempted_scope(self):
        plan = self.prepare()
        failure = self.sw.WriteReport(self.sw.WritePlan(
            "class", "ZCL_A", None, "/sap/bc/adt/oo/classes/zcl_a", None, False, {}, "old", "new"))
        failure.fail("write", "WRITE_INCOMPLETE", "unknown")
        failure.write = {"status": "unknown"}
        with patch.object(self.cs, "prepare", return_value=plan), \
                patch.object(self.sw, "execute", return_value=failure) as write, \
                patch.object(self.h, "activate_objects") as activate:
            result = self.cs.execute(plan)
        self.assertTrue(result.is_error)
        write.assert_called_once()
        activate.assert_not_called()
        self.assertEqual(result.data["unattempted"], ["b"])
        self.assertEqual(result.data["operations"][0]["id"], "a")

    def test_schema_version_is_integer_and_options_are_action_specific(self):
        for version in (True, 1.0, "1"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                self.prepare(schema_version=version)
        with self.assertRaisesRegex(ValueError, "different action"):
            self.prepare([{**self.operations[1], "description": "not a creation"}])

    def test_manifest_drift_is_detected_before_first_mutation(self):
        plan = self.prepare()
        with patch.object(self.cs, "prepare", return_value={**plan, "plan_sha256": "changed"}), \
                patch.object(self.sw, "execute") as write:
            result = self.cs.execute(plan)
        self.assertEqual(result.error_code, "BASELINE_CHANGED")
        write.assert_not_called()

    def test_interrupted_mutation_is_unknown_not_incorrectly_unattempted(self):
        plan = self.prepare()
        with patch.object(self.cs, "prepare", return_value=plan), \
                patch.object(self.sw, "execute", side_effect=KeyboardInterrupt):
            result = self.cs.execute(plan)
        self.assertTrue(result.is_error)
        self.assertEqual(result.data["operations"][0]["id"], "a")
        self.assertIn("unknown", result.data["operations"][0]["error"])
        self.assertEqual(result.data["unattempted"], ["b"])

    def test_unfinished_atc_is_not_a_passing_final_gate(self):
        plan = self.prepare(activate=True, atc=[{"type": "class", "name": "ZCL_A"}])
        with patch.object(self.cs, "prepare", return_value=plan), \
                patch.object(self.sw, "execute", side_effect=lambda p, **_: self.sw.WriteReport(p)), \
                patch.object(self.h, "activate_objects", return_value=self.h.AdtResult()), \
                patch.object(self.h, "read_source_main", side_effect=[
                    self.h.AdtResult(text="new A"), self.h.AdtResult(text="new B")]), \
                patch.object(self.h, "object_version", return_value=self.h.AdtResult(text="active")), \
                patch.object(self.h, "run_atc", return_value=self.h.AdtResult(
                    data={"findings": []}, meta={"result_incomplete": True})):
            result = self.cs.execute(plan)
        self.assertTrue(result.is_error)
        self.assertEqual(result.data["activation"], "verified")

    def test_combined_activation_verifies_each_active_source_before_final_gates(self):
        plan = self.prepare(activate=True)
        def write(p, **_):
            return self.sw.WriteReport(p)
        with patch.object(self.cs, "prepare", return_value=plan), \
                patch.object(self.sw, "execute", side_effect=write), \
                patch.object(self.h, "activate_objects", return_value=self.h.AdtResult()) as activate, \
                patch.object(self.h, "read_source_main", side_effect=[
                    self.h.AdtResult(text="new A"), self.h.AdtResult(text="new B")]), \
                patch.object(self.h, "object_version", return_value=self.h.AdtResult(text="active")):
            result = self.cs.execute(plan)
        self.assertFalse(result.is_error, result.text)
        self.assertEqual(result.data["activation"], "verified")
        self.assertEqual(len(activate.call_args.args[0]), 2)

    def test_final_gates_require_activation_and_are_not_prewrite_proofs(self):
        with self.assertRaisesRegex(ValueError, "activate=true"):
            self.prepare(unit={"objects": ["ZCL_A"]})
        plan = self.prepare(activate=True, unit={"objects": ["ZCL_A"]})
        with patch.object(self.cs, "prepare", return_value=plan), \
                patch.object(self.sw, "execute", side_effect=lambda p, **_: self.sw.WriteReport(p)), \
                patch.object(self.h, "activate_objects", return_value=self.h.AdtResult()), \
                patch.object(self.h, "read_source_main", side_effect=[
                    self.h.AdtResult(text="new A"), self.h.AdtResult(text="new B")]), \
                patch.object(self.h, "object_version", return_value=self.h.AdtResult(text="active")), \
                patch.object(self.cs.unit_regression, "run", return_value=self.h.AdtResult(
                    data={"summary": {"status": "failed"}}, meta={"partial": False})):
            result = self.cs.execute(plan)
        self.assertTrue(result.is_error)
        self.assertEqual(result.data["activation"], "verified")
        self.assertEqual(result.data["gates"][0]["kind"], "unit")
        self.assertEqual(len(result.data["operations"]), 2)


if __name__ == "__main__":
    unittest.main()
