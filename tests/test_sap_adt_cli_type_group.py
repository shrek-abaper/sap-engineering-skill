"""get-type-group endpoint regression (real-verified DEV + QAS, Basis 7.56,
2026-10-28; see references/adt_api.md fact 13).

The legacy ``/sap/bc/adt/typegroups/groups/{name}/source/main`` returned 404
on both systems; ``/sap/bc/adt/ddic/typegroups/{name}/source/main`` serves the
source as ``text/plain``. The command had no fixture or test before, so a
green offline suite could not catch the wrong sub-path.
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


class TypeGroupEndpointTests(unittest.TestCase):
    def _call(self):
        calls = []
        source = (FIXTURES / "get-type-group.SLIS.s4hana.txt").read_text(
            encoding="utf-8")

        def fake(url, method="GET", **kw):
            calls.append((url, method))
            return FakeResponse(source)

        with patch.object(handlers, "make_adt_request", side_effect=fake), \
                patch.object(handlers, "get_config", return_value=_config()):
            result = handlers.get_type_group("SLIS")
        return result, calls

    def test_uses_ddic_typegroups_source_endpoint(self):
        result, calls = self._call()
        self.assertFalse(result.is_error, result.text)
        self.assertEqual(
            calls,
            [(f"{BASE_URL}/sap/bc/adt/ddic/typegroups/SLIS/source/main", "GET")],
        )

    def test_source_is_parsed_into_the_source_kind(self):
        result, _ = self._call()
        self.assertEqual(result.kind, "source")
        self.assertEqual(result.object, {"type": "type-group", "name": "SLIS"})
        self.assertTrue(result.data["source"].startswith("type-pool slis ."))
        self.assertGreater(result.data["line_count"], 1)

    def test_legacy_groups_subpath_is_not_requested(self):
        _, calls = self._call()
        self.assertNotIn("/typegroups/groups/", calls[0][0])


if __name__ == "__main__":
    unittest.main()
