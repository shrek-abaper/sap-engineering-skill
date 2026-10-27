"""Transport collection handlers after the ADT consolidation.

The collector must reuse the shared ADT client/handlers: source objects go
through `sap_adt.adt.handlers` (so auth/CSRF/redaction are not duplicated),
and a separate transport HTTP client must not come back.
"""
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sap_adt.adt.client import AdtHttpError
from sap_adt.transport import handlers as th

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "sap_adt_cli"


class FakeConfig:
    def base_url(self):
        return "https://sap-dev.example.com:8000"


def _resp(content: bytes):
    resp = MagicMock()
    resp.content = content
    resp.text = content.decode("utf-8", errors="replace")
    resp.status_code = 200
    return resp


class NoDuplicatedClientTests(unittest.TestCase):
    def test_transport_has_no_client_module(self):
        self.assertIsNone(importlib.util.find_spec("sap_adt.transport.client"))


class SourceDispatchTests(unittest.TestCase):
    def test_class_source_is_fetched_through_shared_handlers(self):
        source = b"CLASS zcl_x DEFINITION PUBLIC.\nENDCLASS."
        with patch.object(th.adt_handlers, "make_adt_request",
                          return_value=_resp(source)) as req, \
             patch.object(th.adt_handlers, "get_config", return_value=FakeConfig()):
            result = th.fetch_source_for_object("", "CLAS", "ZCL_X")
        self.assertFalse(result.is_error)
        self.assertEqual(result.text, source.decode())
        # The shared endpoint path was used (not a transport-local copy).
        self.assertIn("/sap/bc/adt/oo/classes/ZCL_X/source/main",
                      req.call_args.args[0])

    def test_table_returns_raw_payload_through_shared_fields_handler(self):
        payload = (FIXTURES / "get-table.VBAK.s4hana.xml").read_bytes()
        with patch.object(th.adt_handlers, "make_adt_request",
                          return_value=_resp(payload)), \
             patch.object(th.adt_handlers, "get_config", return_value=FakeConfig()):
            result = th.fetch_source_for_object("R3TR", "TABL", "VBAK")
        self.assertFalse(result.is_error)
        self.assertEqual(result.text, payload.decode())

    def test_shared_handler_error_is_propagated(self):
        with patch.object(th.adt_handlers, "make_adt_request",
                          side_effect=RuntimeError("boom")), \
             patch.object(th.adt_handlers, "get_config", return_value=FakeConfig()):
            result = th.fetch_source_for_object("", "CLAS", "ZCL_X")
        self.assertTrue(result.is_error)

    def test_no_source_and_unsupported_markers_unchanged(self):
        no_src = th.fetch_source_for_object("", "DEVC", "ZPACKAGE")
        self.assertFalse(no_src.is_error)
        self.assertTrue(no_src.text.startswith("[NO_SOURCE]"))

        unsupported = th.fetch_source_for_object("", "ZZZZ", "X")
        self.assertTrue(unsupported.is_error)
        self.assertTrue(unsupported.text.startswith("[UNSUPPORTED]"))


class TransportObjectListTests(unittest.TestCase):
    def test_404_falls_back_to_e071_rows(self):
        rows = [{"PGMID": "R3TR", "OBJECT": "CLAS",
                 "OBJ_NAME": "ZCL_X", "LOCKFLAG": "", "ACTIVITY": ""}]
        with patch.object(th, "make_adt_request",
                          side_effect=AdtHttpError("not found", status=404)), \
             patch.object(th, "_run_e071_sql", return_value=rows), \
             patch.object(th, "active_config", return_value=FakeConfig()):
            result = th.get_transport_objects("DEVK900123")
        self.assertFalse(result.is_error)
        parsed = json.loads(result.text)
        self.assertEqual(parsed[0]["object_name"], "ZCL_X")

    def test_http_error_is_reported(self):
        with patch.object(th, "make_adt_request",
                          side_effect=AdtHttpError("boom", status=500)), \
             patch.object(th, "active_config", return_value=FakeConfig()):
            result = th.get_transport_objects("DEVK900123")
        self.assertTrue(result.is_error)
        self.assertEqual(result.http_status, 500)


if __name__ == "__main__":
    unittest.main()
