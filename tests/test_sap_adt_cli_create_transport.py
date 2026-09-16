"""Batch 10: create-transport CreateCorrectionRequest protocol (real-verified
on Basis 7.56, 2026-09-17; see references/adt_api.md fact 12)."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "sap-adt-cli" / "scripts"))

from lib import handlers  # noqa: E402


class FakeResponse:
    def __init__(self, text, status=200, headers=None):
        self.text = text
        self.content = text.encode()
        self.status_code = status
        self.headers = headers or {}


class CreateTransportProtocolTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def fake(url, method="GET", **kw):
            self.calls.append({"url": url, "method": method, **kw})
            return FakeResponse("/com.sap.cts/object_record/ECDK944393")

        self._p = patch.object(handlers, "make_adt_request", side_effect=fake)
        self.mock = self._p.start()
        self.addCleanup(self._p.stop)

    def test_request_shape_is_asx_create_correction_request(self):
        result = handlers.create_transport(
            "$TMP", "ADT-CLI PROBE 20260917",
            "/sap/bc/adt/programs/programs/z_adt_session_probe/source/main")
        self.assertFalse(result.is_error, result.text)
        self.assertEqual(result.text, "Created transport: ECDK944393")
        self.assertEqual(len(self.calls), 1)
        call = self.calls[0]
        self.assertEqual(call["method"], "POST")
        self.assertTrue(call["url"].endswith("/sap/bc/adt/cts/transports"))
        headers = call["extra_headers"]
        self.assertIn("com.sap.adt.CreateCorrectionRequest",
                      headers["Content-Type"])
        self.assertEqual(headers["Accept"], "text/plain")
        body = call["data"].decode()
        for fragment in (
            '<asx:abap xmlns:asx="http://www.sap.com/abapxml"',
            "<DEVCLASS>$TMP</DEVCLASS>",
            "<REQUEST_TEXT>ADT-CLI PROBE 20260917</REQUEST_TEXT>",
            "<REF>/sap/bc/adt/programs/programs/z_adt_session_probe/source/main</REF>",
            "<OPERATION>I</OPERATION>",
        ):
            self.assertIn(fragment, body)

    def test_description_is_xml_escaped(self):
        result = handlers.create_transport(
            "$TMP", 'a < b & c > d "q"',
            "/sap/bc/adt/programs/programs/zfoo/source/main")
        self.assertFalse(result.is_error, result.text)
        body = self.calls[0]["data"].decode()
        self.assertIn("<REQUEST_TEXT>a &lt; b &amp; c &gt; d &quot;q&quot;</REQUEST_TEXT>",
                      body)

    def test_missing_required_arguments_are_bad_request(self):
        for args in (("", "desc", "/sap/bc/adt/x"),
                     ("$TMP", "", "/sap/bc/adt/x"),
                     ("$TMP", "desc", "   ")):
            result = handlers.create_transport(*args)
            self.assertTrue(result.is_error, args)

    def test_ref_must_be_relative_adt_uri(self):
        result = handlers.create_transport(
            "$TMP", "desc", "https://host.example/sap/bc/adt/programs/x")
        self.assertTrue(result.is_error)
        self.mock.assert_not_called()

    def test_unreadable_trkorr_in_response_is_an_error(self):
        self.mock.side_effect = lambda url, method="GET", **kw: FakeResponse("")
        result = handlers.create_transport(
            "$TMP", "desc",
            "/sap/bc/adt/programs/programs/zfoo/source/main")
        self.assertTrue(result.is_error)


if __name__ == "__main__":
    unittest.main()
