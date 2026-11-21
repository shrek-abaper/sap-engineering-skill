"""Source-derived signatures, generated calls and strict result evidence."""
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from test_sap_adt_cli_config import load_cli_module


SOURCE = """FUNCTION z_test
IMPORTING VALUE(iv_text) TYPE string DEFAULT '/src/file.txt'
CHANGING REFERENCE(cv_value) TYPE bapiret2
EXPORTING VALUE(ev_count) TYPE i
TABLES tt_return STRUCTURE bapiret2
EXCEPTIONS failed.
ENDFUNCTION."""


class TypedExecutionTests(unittest.TestCase):
    def setUp(self):
        self.cli, config = load_cli_module()
        self.f = importlib.import_module("sap_adt.adt.function_call")
        self.r = importlib.import_module("sap_adt.adt.report_execution")
        self.e = importlib.import_module("sap_adt.adt.execution")
        self.config = config.SapConfig("https://sap.example.invalid", "TESTER", "secret", "400",
            allow_execute=True, profile_name="dev", environment_source="explicit")

    def test_parser_keeps_literal_period_and_declared_types(self):
        sig = self.f.parse_signature(SOURCE, "Z_TEST")
        self.assertEqual(len(sig["parameters"]), 4)
        self.assertEqual(sig["parameters"][0]["default"], "'/src/file.txt'")
        code = self.f.build(sig, {"changing": {"CV_VALUE": {}}}, "TOKEN")
        self.assertNotIn("iv_text =", code.lower())
        self.assertIn("TYPE STANDARD TABLE OF BAPIRET2 WITH DEFAULT KEY", code)
        self.assertIn("IMPORTING\n  EV_COUNT", code)
        self.assertIn("CHANGING\n  CV_VALUE", code)
        self.assertLess(code.index("\nTABLES\n"), code.index("\nCHANGING\n"))
        self.assertIn("failed = 1".upper(), code)
        self.assertNotIn("COMMIT", code)
        self.assertNotIn("/UI2/", code)

    def test_legacy_interface_and_unsupported_types_fail_closed(self):
        source = """FUNCTION z_test.
*"----------------------------------------------------------------------
*"*"Local Interface:
*"  IMPORTING
*"     VALUE(IV_TEXT) TYPE STRING OPTIONAL
*"  EXPORTING
*"     VALUE(EV_COUNT) TYPE I
*"----------------------------------------------------------------------
ENDFUNCTION."""
        sig = self.f.parse_signature(source, "Z_TEST")
        self.assertEqual([p["name"] for p in sig["parameters"]], ["IV_TEXT", "EV_COUNT"])
        for declaration in ("IMPORTING X TYPE ANY", "IMPORTING X TYPE REF TO object",
                            "IMPORTING X TYPE STANDARD TABLE OF string", "IMPORTING X",
                            "IMPORTING X TYPE string X TYPE i"):
            with self.subTest(declaration=declaration), self.assertRaises(ValueError):
                self.f.parse_signature("FUNCTION z_test " + declaration + ".", "Z_TEST")

    def test_inputs_cannot_inject_names_types_or_ignore_unknown_fields(self):
        sig = self.f.parse_signature(SOURCE, "Z_TEST")
        for value in ({"exporting": {}}, {"importing": {"UNKNOWN": 1}},
                      {"importing": {"CV_VALUE": {}}}, {"changing": {}},
                      {"changing": {"CV_VALUE": {}}, "tables": {"TT_RETURN": {}}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.f.build(sig, value, "TOKEN")
        code = self.f.build(sig, {"importing": {"IV_TEXT": "'; COMMIT WORK."},
                                 "changing": {"CV_VALUE": {}}}, "TOKEN")
        self.assertIn("''; COMMIT WORK.", code)

    def test_structured_markers_duplicates_truncation_and_subrc_are_strict(self):
        def result(text, truncated=False):
            return {"execution": {"status": "completed"},
                    "output": {"text": text, "truncated": truncated}}
        valid = 'TOKEN:BEGIN\n{"SUBRC":0,"VALUE":"ok"}\nTOKEN:END'
        self.assertEqual(self.f.extract(result(valid), "TOKEN")["VALUE"], "ok")
        for text in (valid + valid, valid.replace('"SUBRC":0', '"SUBRC":"0"'),
                     valid.replace('"SUBRC":0', '"SUBRC":0,"SUBRC":1'),
                     valid + "extra", valid.replace("TOKEN:END", ""), "not JSON"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.f.extract(result(text), "TOKEN")
        with self.assertRaises(ValueError):
            self.f.extract(result(valid, True), "TOKEN")

    def test_reserved_output_name_is_refused_before_execution(self):
        sig = self.f.parse_signature("FUNCTION z_test EXPORTING VALUE(subrc) TYPE i.", "Z_TEST")
        with self.assertRaisesRegex(ValueError, "conflicts"):
            self.f.build(sig, {}, "TOKEN")

    def test_modern_tables_type_declares_an_internal_table_not_a_structure(self):
        sig = self.f.parse_signature(
            "FUNCTION z_test TABLES tt_return TYPE bapiret2.", "Z_TEST")
        code = self.f.build(sig, {"tables": {"TT_RETURN": []}}, "TOKEN")
        self.assertIn("DATA lv_p0 TYPE STANDARD TABLE OF BAPIRET2 WITH DEFAULT KEY.", code)

    def test_report_wrapper_quotes_values_and_has_no_invented_adt_parameters(self):
        with patch.object(self.cli.handlers, "read_source_main",
                          return_value=self.cli.handlers.AdtResult(text="REPORT z_test.")):
            binding = self.r.prepare("Z_TEST", "VARIANT", [
                {"name": "P_TEXT", "low": "a'b"},
                {"name": "S_DATE", "kind": "S", "option": "BT", "low": "20260101", "high": "20261231"}])
        code = self.r.build(binding, "TOKEN")
        self.assertIn("SUBMIT Z_TEST\nUSING SELECTION-SET 'VARIANT'", code)
        self.assertIn("'a''b'", code)
        self.assertIn("EXPORTING LIST TO MEMORY AND RETURN", code)
        self.assertIn("'LIST_TO_ASCI'", code)
        self.assertNotIn("COMMIT", code)
        for row in ({"name": "TOO_LONG_NAME"}, {"name": "P_X", "low": "x" * 46},
                    {"name": "P_X", "option": "BT"}):
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.r.prepare("Z_TEST", None, [row])

    def test_execute_only_dry_run_hash_recheck_and_result_collection(self):
        source = "FUNCTION z_test IMPORTING VALUE(iv) TYPE string EXPORTING VALUE(ev) TYPE string."
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text('{"importing":{"IV":"hello"}}')
            args = ["run-function", "Z_TEST", "--group", "ZGROUP", "--input-file", str(path)]
            with patch.object(self.cli, "load_config", return_value=self.config), \
                    patch.object(self.cli.handlers, "read_source_main",
                                 return_value=self.cli.handlers.AdtResult(text=source)):
                first = CliRunner().invoke(self.cli.cli, args + ["--dry-run"])
                self.assertEqual(first.exit_code, 0, f"{first.output} {first.exception!r}")
                prepared = json.loads(first.stdout)["data"]
                plan = prepared["plan"]
                second = CliRunner().invoke(self.cli.cli, args + ["--dry-run"])
                self.assertEqual(json.loads(second.stdout)["data"]["plan"], plan)
                def run(plan, code):
                    token = self.f.marker(plan["binding"])
                    return {"execution": {"status": "completed"}, "cleanup": {"status": "verified"},
                            "output": {"text": token + ':BEGIN\n{"SUBRC":0,"EV":"hello"}\n' + token + ":END",
                                       "truncated": False}, "evidence_gaps": []}, None
                with patch.object(self.e, "run", side_effect=run) as execute:
                    executed = CliRunner().invoke(self.cli.cli, args + [
                        "--yes", "--expect-plan-sha256", plan["plan_sha256"]])
                    self.assertEqual(executed.exit_code, 0, executed.output)
                    self.assertEqual(json.loads(executed.stdout)["data"]["result"]["EV"], "hello")
                    execute.assert_called_once()
                path.write_text('{"importing":{"IV":"changed"}}')
                with patch.object(self.e, "run") as execute:
                    refused = CliRunner().invoke(self.cli.cli, args + [
                        "--yes", "--expect-plan-sha256", plan["plan_sha256"]])
                    self.assertEqual(refused.exit_code, 3, refused.output)
                    execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
