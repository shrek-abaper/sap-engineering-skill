"""Batch-one diagnostic primitives; synthetic values in a live-checked layout."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from sap_adt import cli
from sap_adt.adt import handlers as h
from sap_adt.adt.client import AdtHttpError
from sap_adt.adt.parsers import dumps

FIXTURES = Path(__file__).parent / "fixtures" / "sap_adt_cli" / "synthetic"
XML = (FIXTURES / "dump.detail.synthetic.xml").read_bytes()
TEXT = (FIXTURES / "dump.formatted.synthetic.txt").read_text(encoding="utf-8")
BASE = "https://sap.example.com"
SOURCE = "/sap/bc/adt/oo/classes/zcl_demo/includes/testclasses"


def response(value):
    content = value.encode("utf-8") if isinstance(value, str) else value
    return SimpleNamespace(content=content, text=content.decode("utf-8"))


class DumpEvidenceTests(unittest.TestCase):
    def setUp(self):
        p = patch.object(h, "get_config", return_value=SimpleNamespace(base_url=lambda: BASE))
        p.start()
        self.addCleanup(p.stop)

    def test_metadata_and_chapter_evidence_keep_locations_and_values(self):
        with patch.object(h, "make_adt_request", side_effect=[response(XML), response(TEXT)]) as req:
            result = h.get_dump("DEMO")
        self.assertFalse(result.is_error, result.text)
        self.assertFalse(result.meta["partial"])
        d = result.data
        self.assertTrue(d["detail_available"])
        self.assertIsNone(d["fallback"])
        self.assertEqual(d["termination"], {"uri": SOURCE + "#start=42", "line": 42})
        self.assertEqual(d["source"][1], {
            "line": 42, "text": "  RAISE EXCEPTION TYPE cx_demo.", "is_termination": True,
        })
        self.assertEqual(d["stack"][0]["level"], 1)
        self.assertIn("ZCL_DEMO", d["stack"][0]["text"])
        self.assertEqual({s["role"] for s in d["sections"]}, {
            "short_text", "error_analysis", "termination", "source", "stack",
            "system_fields", "variables",
        })
        self.assertTrue(all(call.kwargs.get("method", "GET") == "GET" for call in req.call_args_list))

    def test_translated_titles_use_chapter_identifiers_not_english_labels(self):
        xml = XML.replace(b"Short Text", "Kurztext".encode())
        parsed = dumps.evidence(dumps.parse(xml), TEXT.replace("Short Text", "Kurztext"), 20000)
        self.assertTrue(parsed["chapter_layout_known"])
        self.assertEqual(parsed["sections"][0]["title"], "Kurztext")

    def test_unsupported_metadata_or_formatted_detail_degrades_to_st22(self):
        for replies, code in [
            ([AdtHttpError("No suitable resource", status=404)], "DUMP_DETAIL_UNAVAILABLE"),
            ([response(XML), AdtHttpError("Not supported", status=406)], "DUMP_FORMATTED_UNAVAILABLE"),
        ]:
            with self.subTest(code=code), patch.object(h, "make_adt_request", side_effect=replies):
                result = h.get_dump("DEMO")
                self.assertFalse(result.is_error)
                self.assertTrue(result.meta["partial"])
                self.assertFalse(result.data["detail_available"])
                self.assertEqual(result.data["fallback"], "ST22")
                self.assertEqual(result.data["evidence_gaps"][0]["code"], code)

    def test_permission_and_network_failures_are_not_disguised_as_unsupported_detail(self):
        for error, code in [
            (AdtHttpError("Forbidden", status=403), "AUTH_FAILED"),
            (AdtHttpError("Timeout"), "NETWORK_ERROR"),
        ]:
            for replies in ([error], [response(XML), error]):
                with self.subTest(code=code, stage=len(replies)), patch.object(
                    h, "make_adt_request", side_effect=replies
                ):
                    result = h.get_dump("DEMO")
                    self.assertTrue(result.is_error)
                    self.assertEqual(result.error_code, code)

    def test_truncation_and_unknown_layout_are_explicit_gaps(self):
        with patch.object(h, "make_adt_request", side_effect=[response(XML), response(TEXT)]):
            result = h.get_dump("DEMO", max_chars=40)
        self.assertTrue(result.meta["partial"])
        self.assertLessEqual(sum(len(s["text"]) for s in result.data["sections"]), 40)
        self.assertEqual(result.data["evidence_gaps"][0]["code"], "DUMP_TEXT_TRUNCATED")
        with patch.object(h, "make_adt_request", side_effect=[
            response(b"<dump error='DEMO'/>"), response("Unknown layout"),
        ]):
            result = h.get_dump("DEMO")
        self.assertEqual(result.data["text"], "Unknown layout")
        self.assertEqual(result.data["evidence_gaps"][0]["code"], "DUMP_LAYOUT_UNKNOWN")

    def test_html_or_empty_formatted_response_is_not_diagnostic_evidence(self):
        for text in ("", "<html>Login</html>"):
            with self.subTest(text=text), patch.object(h, "make_adt_request", side_effect=[
                response(XML), response(text),
            ]):
                result = h.get_dump("DEMO")
                self.assertFalse(result.data["detail_available"])
                self.assertEqual(result.data["evidence_gaps"][0]["code"], "DUMP_FORMATTED_INVALID")

    def test_invalid_chapter_offset_retains_other_evidence_and_reports_gap(self):
        xml = XML.replace(b'title="Source Code Extract" line="10"',
                          b'title="Source Code Extract" line="9999"')
        with patch.object(h, "make_adt_request", side_effect=[response(xml), response(TEXT)]):
            result = h.get_dump("DEMO")
        self.assertTrue(result.data["detail_available"])
        self.assertTrue(result.meta["partial"])
        gap = next(g for g in result.data["evidence_gaps"] if g["code"] == "DUMP_CHAPTERS_UNMAPPED")
        self.assertEqual(gap["chapters"], ["kap8"])
        self.assertTrue(result.data["stack"])

    def test_dump_uri_validation_rejects_other_endpoints_and_remote_destinations_before_http(self):
        for value in [
            "https://evil.example/sap/bc/adt/runtime/dump/DEMO",
            "/sap/bc/adt/activation", "/sap/bc/adt/runtime/dump/../activation",
            "/sap/bc/adt/runtime/dump/%252e%252e",
            "/sap/bc/adt/runtime/dump/DEMO?sap-client=999",
            "/sap/bc/adt/runtime/dump/DEMO#fragment", "bad%2Fidentifier",
        ]:
            with self.subTest(value=value), patch.object(h, "make_adt_request") as req:
                self.assertTrue(h.get_dump(value).is_error)
                req.assert_not_called()

    def test_dump_uri_encodes_compound_identifier_once(self):
        with patch.object(h, "make_adt_request", side_effect=[
            response(XML), response(TEXT),
        ]) as req:
            result = h.get_dump(BASE + "/sap/bc/adt/runtime/dump/DEMO%20USER%201")
        self.assertFalse(result.is_error)
        self.assertEqual(req.call_args_list[0].args[0], BASE + "/sap/bc/adt/runtime/dump/DEMO%20USER%201")

    def test_adt_navigation_never_changes_the_configured_network_destination(self):
        with patch.object(h, "make_adt_request", side_effect=[response(XML), response(TEXT)]) as req:
            result = h.get_dump("adt://SYS/sap/bc/adt/runtime/dump/DEMO")
        self.assertFalse(result.is_error)
        self.assertTrue(all(c.args[0].startswith(BASE + "/") for c in req.call_args_list))
        with patch.object(h, "make_adt_request", return_value=response("source")) as req:
            result = h.get_source("adt://SYS" + SOURCE + "#start=42")
        self.assertFalse(result.is_error)
        self.assertEqual(req.call_args.args[0], BASE + SOURCE)

    def test_source_navigation_reads_test_include_and_preserves_line_window(self):
        with patch.object(h, "make_adt_request", return_value=response("one\r\ntwo\r\nthree\r\n")) as req:
            result = h.get_source(SOURCE + "#start=2,1", start_line=2, end_line=2)
        self.assertFalse(result.is_error)
        self.assertEqual(result.data["source"], "two\r\n")
        self.assertEqual(result.data["total_lines"], 3)
        self.assertEqual(result.data["start_line"], 2)
        self.assertEqual(result.data["end_line"], 2)
        self.assertEqual(req.call_args.args[0], BASE + SOURCE)

    def test_source_keeps_encoded_namespace_in_object_name(self):
        uri = "/sap/bc/adt/oo/classes/%2Fdemo%2Fzcl_example/includes/testclasses"
        with patch.object(h, "make_adt_request", return_value=response("source")) as req:
            result = h.get_source(uri)
        self.assertFalse(result.is_error, result.text)
        self.assertEqual(req.call_args.args[0], BASE + uri)

    def test_source_rejects_non_source_reads_and_invalid_ranges(self):
        for uri, start, end in [
            ("/sap/bc/adt/activation", 1, None),
            ("https://evil.example" + SOURCE, 1, None),
            (SOURCE + "?sap-client=999", 1, None),
            (SOURCE, 0, None), (SOURCE, 2, 1),
        ]:
            with self.subTest(uri=uri), patch.object(h, "make_adt_request") as req:
                self.assertTrue(h.get_source(uri, start, end).is_error)
                req.assert_not_called()

    def test_cli_partial_result_exits_one_with_json_stdout_and_xml_is_metadata_only(self):
        with patch.object(h, "make_adt_request", side_effect=[
            response(XML), AdtHttpError("Not supported", status=404),
        ]):
            r = CliRunner().invoke(cli.cli, ["get-dump", "DEMO"])
        self.assertEqual(r.exit_code, 1, r.output)
        d = json.loads(r.stdout)
        self.assertTrue(d["ok"])
        self.assertEqual(d["kind"], "dumps")
        self.assertEqual(d["data"]["fallback"], "ST22")
        with patch.object(h, "make_adt_request", side_effect=[response(XML), response(TEXT)]):
            r = CliRunner().invoke(cli.cli, ["--format", "xml", "get-dump", "DEMO"])
        self.assertEqual(r.exit_code, 0, r.output)
        self.assertEqual(r.stdout.strip(), XML.decode().strip())


if __name__ == "__main__":
    unittest.main()
