"""Batch 3 tests: commands emit the unified envelope (offline).

Handlers are driven with sanitized fixtures by patching make_adt_request and
get_config; no HTTP, credentials or SAP system are involved.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from test_sap_adt_cli_config import SCRIPTS_PATH, load_cli_module  # noqa: E402

sys.path.insert(0, str(SCRIPTS_PATH))

FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "skills" / "sap-adt-cli" / "tests" / "fixtures"
)


def fx(name) -> bytes:
    return (FIXTURES / name).read_bytes()


class FakeResponse:
    def __init__(self, payload: bytes):
        self.content = payload
        self.text = payload.decode("utf-8", errors="replace")


class FakeConfig:
    def base_url(self):
        return "https://sap-dev.example.com:8000"


class EnvelopeCommandTests(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()
        self.handlers = sys.modules["lib.handlers"]
        self.output = sys.modules["lib.output"]
        self.AdtHttpError = sys.modules["lib.client"].AdtHttpError
        self.output.set_format(None)
        class _CliConfig:
            username = "DEVELOPER"
            profile_name = "dev"

        # Commands like run-sql/list-transports call load_config() up front;
        # make it resolve without a real config file.
        self._patches = [
            patch.object(self.handlers, "get_config", return_value=FakeConfig()),
            patch.object(self.cli, "load_config", return_value=_CliConfig()),
        ]
        for p in self._patches:
            p.start()
        self.addCleanup(self._stop)

    def _stop(self):
        for p in self._patches:
            p.stop()

    def _serve(self, mapping):
        """Patch make_adt_request; mapping: url-substring -> payload bytes."""
        def fake_request(url, method="GET", **kwargs):
            for needle, payload in mapping.items():
                if needle in url:
                    return FakeResponse(payload)
            raise AssertionError(f"unexpected URL {url}")
        patcher = patch.object(self.handlers, "make_adt_request", side_effect=fake_request)
        patcher.start()
        self._patches.append(patcher)
        return patcher

    def _invoke_json(self, *args):
        r = CliRunner().invoke(self.cli.cli, list(args))
        self.assertEqual(r.exit_code, 0, r.output)
        return json.loads(r.output)

    # ---- fields -----------------------------------------------------------
    def test_get_table_fields_envelope(self):
        self._serve({"ddic/tables": fx("get-table.T001.s4hana.xml")})
        d = self._invoke_json("get-table", "T001")
        self.assertEqual(d["ok"], True)
        self.assertEqual(d["format_version"], 1)
        self.assertEqual(d["command"], "get-table")
        self.assertEqual(d["object"], {"type": "table", "name": "T001"})
        self.assertEqual(d["kind"], "fields")
        self.assertEqual(d["meta"]["row_count"], 22)
        f0 = d["data"]["fields"][0]
        self.assertEqual(f0["name"], "mandt")
        self.assertTrue(f0["is_key"])
        self.assertIsNone(f0["length"])

    # ---- objects ----------------------------------------------------------
    def test_search_empty_is_ok_zero(self):
        self._serve({"informationsystem/search": fx("search-object.empty.xml")})
        d = self._invoke_json("search-object", "ZZZ_*")
        self.assertEqual(d["kind"], "objects")
        self.assertEqual(d["data"]["objects"], [])
        self.assertEqual(d["meta"]["row_count"], 0)

    def test_get_package_envelope_fixes_namespace_bug(self):
        self._serve({"nodestructure": fx("get-package.SABP_UNIT.asxml.xml")})
        d = self._invoke_json("get-package", "SABP_UNIT")
        self.assertEqual(d["meta"]["row_count"], 14)
        self.assertEqual(d["data"]["objects"][0]["name"], "SABP_UNIT_AUTHORITY")

    def test_objects_xml_passthrough(self):
        payload = fx("search-object.empty.xml")
        self._serve({"informationsystem/search": payload})
        r = CliRunner().invoke(
            self.cli.cli, ["--format", "xml", "search-object", "ZZZ_*"]
        )
        self.assertEqual(r.exit_code, 0, r.output)
        self.assertEqual(r.output, payload.decode() + "\n")

    # ---- where-used (usageReferences) ------------------------------------
    def test_where_used_posts_new_endpoint_with_relative_lowercase_uri(self):
        calls = []

        def fake_request(url, method="GET", **kwargs):
            calls.append((method, url, kwargs.get("params"),
                          kwargs["extra_headers"]["Content-Type"],
                          kwargs["extra_headers"]["Accept"], kwargs.get("data")))
            return FakeResponse(fx("where-used.CL_GUI_FRONTEND_SERVICES.xml"))

        with patch.object(self.handlers, "make_adt_request", side_effect=fake_request):
            d = self._invoke_json(
                "where-used", "class", "CL_GUI_FRONTEND_SERVICES",
                "--max-results", "2",
            )
        method, url, params, ctype, accept, body = calls[0]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith("/informationsystem/usageReferences"))
        self.assertEqual(
            params["uri"],
            "/sap/bc/adt/oo/classes/cl_gui_frontend_services",
        )
        self.assertEqual(ctype, "application/*")
        self.assertEqual(accept, "application/*")
        self.assertIn(b"affectedObjects", body)
        self.assertEqual(d["kind"], "objects")
        self.assertEqual(d["meta"]["row_count"], 2)

    def test_where_used_body_contains_empty_affected_objects(self):
        captured = {}

        def fake_request(url, method="GET", **kwargs):
            captured["data"] = kwargs.get("data")
            return FakeResponse(fx("where-used.empty.xml"))

        with patch.object(self.handlers, "make_adt_request", side_effect=fake_request):
            d = self._invoke_json("where-used", "class", "ZCL_X")
        body = captured["data"].decode()
        self.assertIn("usageReferenceRequest", body)
        self.assertIn("<usagereferences:affectedObjects/>", body)
        self.assertEqual(d["data"]["objects"], [])
        self.assertEqual(d["meta"]["row_count"], 0)

    def test_where_used_falls_back_to_legacy_get_on_405(self):
        calls = []

        def fake_request(url, method="GET", **kwargs):
            calls.append(method)
            if "usageReferences" in url:
                raise self.AdtHttpError("HTTP 405", status=405)
            return FakeResponse(fx("search-object.empty.xml"))

        with patch.object(self.handlers, "make_adt_request", side_effect=fake_request):
            d = self._invoke_json("where-used", "class", "ZCL_X")
        self.assertEqual(calls, ["POST", "GET"])
        self.assertEqual(d["data"]["objects"], [])

    # ---- records ----------------------------------------------------------
    def test_list_transports_empty(self):
        self._serve({"cts/transportrequests": fx("list-transports.empty.xml")})
        d = self._invoke_json("list-transports")
        self.assertEqual(d["kind"], "records")
        self.assertEqual(d["data"]["transports"], [])
        self.assertEqual(d["meta"]["row_count"], 0)

    # ---- findings ---------------------------------------------------------
    def test_syntax_check_clean(self):
        self._serve({"checkruns": fx("syntax-check.CL_GUI.clean.xml")})
        d = self._invoke_json("syntax-check", "class", "CL_GUI_FRONTEND_SERVICES")
        self.assertEqual(d["kind"], "findings")
        self.assertEqual(d["data"]["findings"], [])

    def test_syntax_check_warnings_exit_zero(self):
        self._serve({"checkruns": fx("syntax-check.SAPMV45A.warnings.xml")})
        r = CliRunner().invoke(
            self.cli.cli, ["syntax-check", "program", "SAPMV45A"]
        )
        self.assertEqual(r.exit_code, 0, r.output)
        d = json.loads(r.output)
        self.assertEqual(d["meta"]["row_count"], 49)
        self.assertTrue(all(f["severity"] == "warning" for f in d["data"]["findings"]))

    # ---- scalar -----------------------------------------------------------
    def test_type_info_domain(self):
        self._serve({"ddic/domains": fx("get-type-info.CHAR10.domain.xml")})
        d = self._invoke_json("get-type-info", "CHAR10")
        self.assertEqual(d["data"]["resolved_as"], "domain")
        self.assertEqual(d["data"]["data_type"], "CHAR")
        self.assertEqual(d["data"]["length"], 10)

    def test_type_info_falls_back_to_dataelement_on_404(self):
        dtel = fx("get-type-info.MATNR.dtel.xml")

        def fake_request(url, method="GET", **kwargs):
            if "ddic/domains" in url:
                raise self.AdtHttpError("HTTP 404", status=404)
            return FakeResponse(dtel)
        with patch.object(self.handlers, "make_adt_request", side_effect=fake_request):
            d = self._invoke_json("get-type-info", "MATNR")
        self.assertEqual(d["data"]["resolved_as"], "dataelement")
        self.assertEqual(d["data"]["adt_type"], "DTEL/DE")

    def test_type_info_domain_non404_error_surfaces(self):
        def fake_request(url, method="GET", **kwargs):
            if "ddic/domains" in url:
                raise self.AdtHttpError("HTTP 403", status=403)
            return FakeResponse(fx("get-type-info.MATNR.dtel.xml"))
        with patch.object(self.handlers, "make_adt_request", side_effect=fake_request):
            r = CliRunner().invoke(self.cli.cli, ["get-type-info", "MATNR"])
        self.assertEqual(r.exit_code, 1)

    def test_transaction_scalar(self):
        self._serve({"objectproperties": fx("get-transaction.VA01.xml")})
        d = self._invoke_json("get-transaction", "VA01")
        self.assertEqual(d["data"]["name"], "VA01")
        self.assertEqual(d["data"]["package"], "VA")
        self.assertEqual(d["data"]["application"], ["SD", "SD-SLS"])

    def test_fields_meta_lists_unparsed_types_and_omits_description(self):
        self._serve({"ddic/tables": fx("get-table.T001.s4hana.xml")})
        d = self._invoke_json("get-table", "T001")
        self.assertIn("unparsed_types", d["meta"])
        self.assertIn("bukrs", d["meta"]["unparsed_types"])
        self.assertNotIn("description", d["data"]["fields"][0])

    # ---- rows -------------------------------------------------------------
    def test_run_sql_rows(self):
        self._serve({"datapreview": fx("run-sql.t100.raw.xml")})
        d = self._invoke_json("run-sql", "SELECT arbgb FROM t100 UP TO 5 ROWS")
        self.assertEqual(d["kind"], "rows")
        self.assertEqual([c["name"] for c in d["data"]["columns"]],
                         ["ARBGB", "MSGNR", "TEXT"])
        self.assertEqual(d["meta"]["row_count"], 5)
        self.assertEqual(len(d["data"]["rows"]), 5)

    def test_run_sql_posts_sql_body_first(self):
        calls = []

        def fake_request(url, method="GET", **kwargs):
            calls.append((method, kwargs.get("data"), kwargs.get("params")))
            return FakeResponse(fx("run-sql.t100.post.raw.xml"))

        with patch.object(self.handlers, "make_adt_request", side_effect=fake_request):
            d = self._invoke_json("run-sql", "SELECT arbgb FROM t100 UP TO 5 ROWS")
        self.assertEqual(calls[0][0], "POST")
        self.assertEqual(calls[0][1], b"SELECT arbgb FROM t100 UP TO 5 ROWS")
        self.assertNotIn("sqlCommand", calls[0][2])
        self.assertEqual(d["meta"]["row_count"], 5)

    def test_run_sql_falls_back_to_get_on_405(self):
        calls = []

        def fake_request(url, method="GET", **kwargs):
            calls.append(method)
            if method == "POST":
                raise self.AdtHttpError("HTTP 405", status=405)
            return FakeResponse(fx("run-sql.t100.raw.xml"))

        with patch.object(self.handlers, "make_adt_request", side_effect=fake_request):
            d = self._invoke_json("run-sql", "SELECT x FROM z")
        self.assertEqual(calls, ["POST", "GET"])
        self.assertEqual(d["ok"], True)

    # ---- source -----------------------------------------------------------
    def test_source_default_text_is_verbatim(self):
        payload = fx("get-class.CL_GUI_FRONTEND_SERVICES.abap")
        self._serve({"oo/classes": payload})
        r = CliRunner().invoke(self.cli.cli, ["get-class", "CL_GUI_FRONTEND_SERVICES"])
        self.assertEqual(r.exit_code, 0, r.output)
        # CliRunner captures stdout with universal-newline translation; real
        # redirection preserves CRLF (verified byte-for-byte against DEV).
        expected = payload.decode("utf-8").replace("\r\n", "\n") + "\n"
        self.assertEqual(r.output, expected)

    def test_source_json_envelope(self):
        self._serve({"oo/classes": fx("get-class.CL_GUI_FRONTEND_SERVICES.abap")})
        d = self._invoke_json("--format", "json", "get-class", "CL_GUI_FRONTEND_SERVICES")
        self.assertEqual(d["kind"], "source")
        self.assertEqual(d["data"]["line_count"], 7049)
        self.assertIn("source", d["data"])

    def test_source_xml_unsupported(self):
        self._serve({"oo/classes": b"class zcl_foo."})
        r = CliRunner().invoke(
            self.cli.cli, ["--format", "xml", "get-class", "ZCL_FOO"]
        )
        self.assertEqual(r.exit_code, 1)
        self.assertIn("no raw ADT XML", r.output)


if __name__ == "__main__":
    unittest.main()
