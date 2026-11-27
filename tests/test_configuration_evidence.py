"""Single-entity queries, client normalization and honest partial differences."""
import copy
import unittest
from unittest.mock import patch
from test_sap_adt_cli_config import load_cli_module


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.cli, self.config = load_cli_module()
        from sap_adt.adt import configuration
        self.m = configuration
        self.fields = [
            {"name": "MANDT", "type": "CLNT", "length": "3", "decimals": "0", "is_key": True},
            {"name": "CODE", "type": "CHAR", "length": "4", "decimals": "0", "is_key": True},
            {"name": "VALUE", "type": "CHAR", "length": "10", "decimals": "0", "is_key": False}]

    def snapshot(self, rows):
        return {"entity": {"kind": "table", "name": "ZCONFIG"}, "filters": [],
                "fields": self.fields, "columns": [{"name": f["name"]} for f in self.fields],
                "rows": rows, "keys": ["MANDT", "CODE"], "client_field": "MANDT",
                "evidence_gaps": []}

    def test_comparison_aligns_keys_not_positions_and_normalizes_only_ddic_client(self):
        a = self.snapshot([["100", "A", ""], ["100", "B", "old"]])
        b = self.snapshot([["800", "B", "new"], ["800", "A", ""]])
        result = self.m.difference(a, b)
        self.assertFalse(result["equal"])
        self.assertEqual(len(result["changed"]), 1)
        self.assertEqual(result["changed"][0]["key"], ["B"])
        self.assertEqual(result["added_on_target"], [])
        self.assertEqual(result["ignored_fields"], ["MANDT"])

    def test_truncation_or_duplicate_keys_cannot_prove_equality_or_removal(self):
        a = self.snapshot([["100", "A", "same"]])
        b = self.snapshot([["800", "A", "same"]])
        a["evidence_gaps"] = [{"code": "CONFIGURATION_ROW_LIMIT_REACHED"}]
        result = self.m.difference(a, b)
        self.assertIsNone(result["equal"])
        self.assertIsNone(result["removed_on_target"])
        a["evidence_gaps"] = []
        b["rows"].append(["800", "A", "other"])
        self.assertIsNone(self.m.difference(a, b)["changed"])

    def test_schema_drift_is_not_a_value_difference(self):
        a, b = self.snapshot([]), copy.deepcopy(self.snapshot([]))
        b["fields"][2]["length"] = "20"
        result = self.m.difference(a, b)
        self.assertTrue(result["schema_changed"])
        self.assertIsNone(result["equal"])

    def test_filters_are_quoted_literals_and_rows_are_bounded_with_a_sentinel(self):
        cfg = self.config.SapConfig("https://example.invalid", "U", "s", "100")
        result = self.cli.handlers.AdtResult(data={
            "columns": [{"name": f["name"]} for f in self.fields],
            "rows": [["100", "A", "one"], ["100", "B", "two"]]})
        with patch.object(self.m, "schema", return_value=self.fields), \
                patch.object(self.cli.handlers, "run_sql", return_value=result) as sql:
            data = self.m.read(cfg, "ZCONFIG", filters=["CODE=x' OR '1'='1"], max_rows=1)
        self.assertIn("CODE = 'x'' OR ''1''=''1'", sql.call_args.args[0])
        self.assertEqual(sql.call_args.args[1], 2)
        self.assertEqual(len(data["rows"]), 1)
        self.assertFalse(data["complete_within_selection"])

    def test_maintenance_view_is_refused_not_read_as_an_arbitrary_base_table(self):
        with patch.object(self.m, "_records", return_value=[{"VIEWNAME": "V_TEST", "VIEWCLASS": "C"}]):
            with self.assertRaisesRegex(ValueError, "maintenance"):
                self.m.schema("V_TEST", "view")
