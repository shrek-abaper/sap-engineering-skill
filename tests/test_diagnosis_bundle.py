"""Diagnostic collection is bounded, literal and evidence-first."""
import unittest
from unittest.mock import patch
from test_sap_adt_cli_config import load_cli_module


class DiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.cli, self.config = load_cli_module()
        from sap_adt.adt import diagnosis
        self.m, self.h = diagnosis, self.cli.handlers
        self.cfg = self.config.SapConfig("https://example.invalid", "U", "s", "100")

    def test_explicit_dump_collects_only_its_source_window(self):
        dump = {"termination": {"uri": "/sap/bc/adt/programs/programs/zx/source/main", "line": 40},
                "evidence_gaps": [], "stack": []}
        with patch.object(self.h, "get_dump", return_value=self.h.AdtResult(data=dump, raw="<dump/>")), \
                patch.object(self.h, "get_source", return_value=self.h.AdtResult(
                    data={"source": "REPORT zx.", "line_count": 1})) as source, \
                patch.object(self.h, "list_feeds", side_effect=AssertionError):
            data, assets = self.m.collect(self.cfg, dump_id="EXPLICIT")
        source.assert_called_once_with(dump["termination"]["uri"], 25, 55)
        self.assertIn("dumps/0.xml", assets)
        self.assertFalse(data["evidence_gaps"])

    def test_message_is_not_interpolated_into_a_query_or_root_cause(self):
        feed = "/sap/bc/adt/runtime/dumps"
        catalog = self.h.AdtResult(data={"entries": [{"content_uri": feed}]})
        page = self.h.AdtResult(data={"entries": [
            {"title": "different", "content_uri": "/sap/bc/adt/runtime/dump/ONE"}]},
            meta={"has_more": True})
        with patch.object(self.h, "list_feeds", return_value=catalog), \
                patch.object(self.h, "query_feed", return_value=page) as query, \
                patch.object(self.h, "get_dump") as dump:
            data, _ = self.m.collect(self.cfg, message="missing", max_entries=1)
        query.assert_called_once_with(feed, "", 1)
        dump.assert_not_called()
        self.assertEqual({g["code"] for g in data["evidence_gaps"]},
                         {"FEED_SCOPE_LIMITED", "NO_CANDIDATE_IN_SCOPE"})

    def test_dump_failure_is_preserved_in_a_partial_package(self):
        with patch.object(self.h, "get_dump", return_value=self.h.AdtResult(
                is_error=True, error_code="AUTH_FAILED", text="denied")):
            data, assets = self.m.collect(self.cfg, dump_id="ONE")
        self.assertEqual(data["evidence_gaps"][0]["code"], "AUTH_FAILED")
        self.assertIn("diagnosis.json", assets)
