"""Batch 1 tests for the unified output rendering seam (lib/output.py).

Everything is offline: handlers are patched, no HTTP or config files.
Batch 1 contract: every command is kind="raw" and its output stays
byte-for-byte identical regardless of --format / SAP_ADT_FORMAT.
"""
import os
import sys
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from test_sap_adt_cli_config import SCRIPTS_PATH, load_cli_module  # noqa: E402

sys.path.insert(0, str(SCRIPTS_PATH))


class OutputModuleTests(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()
        self.handlers = sys.modules["lib.handlers"]
        self.output = sys.modules["lib.output"]
        self.output.set_format(None)

    def test_raw_render_is_identity_for_every_format(self):
        result = self.handlers.AdtResult(text="REPORT zfoo.\n")
        for fmt in (None, "json", "text", "xml"):
            self.assertEqual(self.output.render(result, fmt), "REPORT zfoo.\n")

    def test_raw_render_preserves_xml_and_unicode(self):
        xml = "<?xml version=\"1.0\"?>\n<x>上海</x>"
        result = self.handlers.AdtResult(text=xml)
        self.assertEqual(self.output.render(result), xml)

    def test_format_override_roundtrip(self):
        self.assertIsNone(self.output.get_format())
        self.output.set_format("json")
        self.assertEqual(self.output.get_format(), "json")
        self.output.set_format(None)
        self.assertIsNone(self.output.get_format())

    def test_success_envelope_shape(self):
        env = self.output.Envelope(
            ok=True,
            command="get-table",
            profile="dev",
            object={"type": "table", "name": "VBAK"},
            kind="fields",
            data={"fields": []},
            meta={"row_count": 0, "elapsed_ms": 5},
        )
        d = env.to_dict()
        self.assertEqual(d["ok"], True)
        self.assertEqual(d["format_version"], self.output.FORMAT_VERSION)
        self.assertEqual(d["command"], "get-table")
        self.assertEqual(d["profile"], "dev")
        self.assertEqual(d["object"], {"type": "table", "name": "VBAK"})
        self.assertEqual(d["kind"], "fields")
        self.assertEqual(d["data"], {"fields": []})
        self.assertEqual(d["meta"]["row_count"], 0)

    def test_error_envelope_shape(self):
        env = self.output.Envelope(
            ok=False,
            command="get-class",
            error={"code": "OBJECT_NOT_FOUND", "message": "nope",
                   "http_status": 404, "hint": None},
        )
        d = env.to_dict()
        self.assertNotIn("data", d)
        self.assertNotIn("kind", d)
        self.assertEqual(d["error"]["code"], "OBJECT_NOT_FOUND")
        self.assertEqual(d["error"]["http_status"], 404)


class OutputCliPassthroughTests(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()
        self.handlers = sys.modules["lib.handlers"]
        self.output = sys.modules["lib.output"]
        self.output.set_format(None)

    def _patch_config(self):
        # get-class -> handlers.get_class -> _base() -> get_config(); short
        # circuit the network/config entirely with a fake base URL.
        class _FakeConfig:
            def base_url(self):
                return "https://sap-dev.example.com:8000"

        return patch.object(self.handlers, "get_config",
                            return_value=_FakeConfig())

    def test_default_stdout_byte_identical(self):
        with self._patch_config(), patch.object(
            self.handlers, "get_class",
            return_value=self.handlers.AdtResult("class zcl_foo.\n"),
        ):
            r = CliRunner().invoke(self.cli.cli, ["get-class", "ZCL_FOO"])
        self.assertEqual(r.exit_code, 0, r.output)
        self.assertEqual(r.output, "class zcl_foo.\n\n")

    def test_format_flag_does_not_change_raw_output(self):
        with self._patch_config(), patch.object(
            self.handlers, "get_class",
            return_value=self.handlers.AdtResult("<xml/>"),
        ):
            r = CliRunner().invoke(
                self.cli.cli, ["--format", "json", "get-class", "ZCL_FOO"]
            )
        self.assertEqual(r.exit_code, 0, r.output)
        self.assertEqual(r.output, "<xml/>\n")
        self.assertEqual(self.output.get_format(), "json")

    def test_format_envvar_is_accepted_and_passthrough(self):
        with patch.dict(os.environ, {"SAP_ADT_FORMAT": "xml"}), \
                self._patch_config(), patch.object(
                    self.handlers, "get_class",
                    return_value=self.handlers.AdtResult("RAW"),
                ):
            r = CliRunner().invoke(self.cli.cli, ["get-class", "ZCL_FOO"])
        self.assertEqual(r.exit_code, 0, r.output)
        self.assertEqual(r.output, "RAW\n")

    def test_invalid_format_is_usage_error(self):
        r = CliRunner().invoke(
            self.cli.cli, ["--format", "yaml", "get-class", "ZCL_FOO"]
        )
        self.assertNotEqual(r.exit_code, 0)

    def test_error_result_keeps_stderr_and_exit_1(self):
        with self._patch_config(), patch.object(
            self.handlers, "get_class",
            return_value=self.handlers.AdtResult("HTTP 404 ...", is_error=True),
        ):
            r = CliRunner().invoke(self.cli.cli, ["get-class", "ZCL_FOO"])
        self.assertEqual(r.exit_code, 1)
        self.assertIn("HTTP 404 ...", r.output)


if __name__ == "__main__":
    unittest.main()
