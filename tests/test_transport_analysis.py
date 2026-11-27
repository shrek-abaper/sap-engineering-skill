"""Transport indicators and strict two-target comparisons never infer release safety."""
import unittest
from unittest.mock import patch
from test_sap_adt_cli_config import load_cli_module


class TransportAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.cli, self.config = load_cli_module()
        from sap_adt.transport import analysis
        self.m = analysis
        self.a = self.config.SapConfig("https://a.invalid", "U", "secret", "100", profile_name="dev")
        self.b = self.config.SapConfig("https://b.invalid", "U", "secret", "200", profile_name="qas")
        self.h = self.cli.handlers

    def test_strict_comparison_rejects_aliases_of_the_same_system_client(self):
        from sap_adt.adt import comparison
        alias = self.config.SapConfig(self.a.url, "OTHER", "other", "100",
                                      profile_name="alias", environment="qas")
        with patch.object(self.config, "load_profile_connection", side_effect=[self.a, alias]):
            with self.assertRaisesRegex(ValueError, "same SAP"):
                comparison.profiles("dev", "alias")

    def test_cross_target_diff_preserves_unavailable_side_and_never_uses_empty_source(self):
        from sap_adt.adt import comparison
        with patch.object(comparison, "snapshot", side_effect=[
                {"source": "one\n", "sha256": "a", "uri": "/one"},
                ValueError("unavailable")]):
            result = comparison.compare((self.a, self.b), "class", "ZCL_A")
        self.assertIsNone(result["changed"])
        self.assertIsNone(result["diff"])
        self.assertEqual(len(result["evidence_gaps"]), 1)

    def test_cross_target_diff_reads_each_source_on_its_own_isolated_connection(self):
        from sap_adt.adt import comparison
        def snapshot(*args, **kwargs):
            c = comparison.client.active_config()
            return {"source": c.client + "\n", "sha256": c.client, "uri": "/source"}
        with patch.object(comparison, "snapshot", side_effect=snapshot):
            result = comparison.compare((self.a, self.b), "class", "ZCL_A")
        self.assertTrue(result["changed"])
        self.assertIn("-100", result["diff"])
        self.assertIn("+200", result["diff"])
        self.assertIsNone(comparison.client.config_override())

    def test_request_tasks_are_deduplicated_and_budget_gaps_are_visible(self):
        item = {"pgmid": "R3TR", "type": "CLAS", "name": "ZCL_A"}
        detail = self.h.AdtResult(data={"transport": {"tasks": [{"trkorr": "TASK"}]},
                                      "objects": [item]})
        with patch.object(self.h, "get_transport", return_value=detail) as request:
            found, _, gaps = self.m.objects("ROOT", 2)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(found, [item])
        self.assertFalse(gaps)

    def test_customizing_and_unsupported_objects_cannot_become_release_approval(self):
        objects = [{"pgmid": "R3TR", "type": "TABU", "name": "T001"}]
        with patch.object(self.m, "objects", return_value=(objects, [], [])):
            result = self.m.analyze(self.a, "DEVK900001")
        self.assertFalse(result["risk"]["release_approval"])
        self.assertFalse(result["risk"]["evidence_complete_within_scope"])
        self.assertIn("CUSTOMIZING_KEYS_NOT_COLLECTED", {g["code"] for g in result["evidence_gaps"]})
