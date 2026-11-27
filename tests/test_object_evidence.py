"""Metadata trees and budgeted static reference graphs, no SAP writes."""
import sys
import unittest
from unittest.mock import patch
from test_sap_adt_cli_config import load_cli_module


class ObjectEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()
        from sap_adt.adt import object_evidence
        self.m = object_evidence
        self.h = self.cli.handlers

    def response(self, xml):
        return type("Response", (), {"content": xml.encode(), "text": xml})()

    def test_metadata_keeps_nested_message_evidence_and_identity(self):
        response = self.response("<messageClass name='00'><messages number='001'>Text</messages></messageClass>")
        with patch.object(self.h, "_read_adt", return_value=response):
            result = self.m.read("message-class", "00")
        self.assertFalse(result.is_error)
        node = result.data["metadata"]["children"][0]
        self.assertEqual(node["attributes"]["number"], "001")
        self.assertEqual(node["text"], "Text")
        with patch.object(self.h, "_read_adt", return_value=response):
            self.assertTrue(self.m.read("message-class", "OTHER").is_error)

    def test_metadata_node_budget_reports_a_gap(self):
        response = self.response("<lockobject name='E_TEST'><one/><two/></lockobject>")
        with patch.object(self.h, "_read_adt", return_value=response):
            result = self.m.read("lock-object", "E_TEST", max_nodes=1)
        self.assertTrue(result.meta["partial"])
        self.assertEqual(result.data["evidence_gaps"][0]["code"], "METADATA_TRUNCATED")

    def test_reference_cycles_are_deduplicated_and_edges_retained(self):
        def result(*args, **kwargs):
            uri = kwargs["object_uri"]
            return self.h.AdtResult(data={"objects": [
                {"name": "ZB" if uri.endswith("za") else "ZA",
                 "uri": "/sap/bc/adt/oo/classes/" + ("zb" if uri.endswith("za") else "za")}]})
        with patch.object(self.h, "_base", return_value="https://example.invalid"), \
                patch.object(self.h, "where_used", side_effect=result) as request:
            data = self.m.references("class", "ZA", depth=5)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(len(data["nodes"]), 2)
        self.assertEqual(len(data["edges"]), 2)
        self.assertFalse(data["dynamic_dependencies_complete"])

    def test_reference_limit_and_request_failure_are_not_empty_success(self):
        result = self.h.AdtResult(data={"objects": [
            {"uri": "/sap/bc/adt/oo/classes/zb", "name": "ZB"}]}, meta={"limit_reached": True})
        with patch.object(self.h, "_base", return_value="https://example.invalid"), \
                patch.object(self.h, "where_used", return_value=result):
            data = self.m.references("class", "ZA", max_nodes=1)
        self.assertEqual({g["code"] for g in data["evidence_gaps"]},
                         {"REFERENCE_LIMIT_REACHED", "GRAPH_NODE_LIMIT_REACHED"})

    def test_enhancement_points_are_local_declarations_not_inferred_dependencies(self):
        with patch.object(self.h, "get_program", return_value=self.h.AdtResult(data={
                "source": "* ENHANCEMENT-POINT NOT_CODE SPOTS Z.\nENHANCEMENT-POINT ZPOINT SPOTS ZSPOT."})):
            result = self.m.read("enhancement-point", "ZPROG")
        self.assertEqual(len(result.data["points"]), 1)
        self.assertEqual(result.data["points"][0]["line"], 2)
