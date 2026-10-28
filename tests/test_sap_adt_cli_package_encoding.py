"""get-package query-parameter encoding regression (real-verified DEV + QAS,
2026-10-28; see references/adt_api.md fact 14).

``parent_name`` was pre-encoded with ``quote(name, safe="")`` and then passed
through ``requests``' params dict, which encodes it a second time: ``$TMP``
became ``%2524TMP``. The server answered HTTP 200 with an **empty body**, so
the CLI reported PARSE_FAILED for a package that has 29 KB of contents.
"""
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sap_adt.adt import handlers  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "sap_adt_cli"
BASE_URL = "https://sap-dev.example.com:8000"


class FakeResponse:
    def __init__(self, text, status=200, headers=None):
        self.text = text
        self.content = text.encode()
        self.status_code = status
        self.headers = headers or {}


def _config():
    return types.SimpleNamespace(
        base_url=lambda: BASE_URL,
        username="DEVELOPER",
        password="",
        client="400",
        verify_ssl=True,
    )


class PackageParameterEncodingTests(unittest.TestCase):
    def _call(self, package_name):
        calls = []
        payload = (FIXTURES / "get-package.SABP_UNIT.asxml.xml").read_text(
            encoding="utf-8")

        def fake(url, method="GET", **kw):
            calls.append({"url": url, "method": method, **kw})
            return FakeResponse(payload)

        with patch.object(handlers, "make_adt_request", side_effect=fake), \
                patch.object(handlers, "get_config", return_value=_config()):
            result = handlers.get_package(package_name)
        return result, calls

    def test_dollar_tmp_is_passed_verbatim(self):
        result, calls = self._call("$TMP")
        self.assertFalse(result.is_error, result.text)
        self.assertEqual(calls[0]["params"]["parent_name"], "$TMP")

    def test_namespace_package_is_passed_verbatim(self):
        _, calls = self._call("/IPRO/BASI")
        self.assertEqual(calls[0]["params"]["parent_name"], "/IPRO/BASI")

    def test_request_uses_nodestructure_post(self):
        _, calls = self._call("VA")
        self.assertEqual(calls[0]["method"], "POST")
        self.assertTrue(calls[0]["url"].endswith(
            "/sap/bc/adt/repository/nodestructure"))


if __name__ == "__main__":
    unittest.main()
