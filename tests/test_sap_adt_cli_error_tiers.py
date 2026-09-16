"""Batch 4b tests: error envelopes and exit-code tiers at the CLI boundary.

Fully offline: config and handlers are patched, no HTTP or keystore access.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from test_sap_adt_cli_config import load_cli_module  # noqa: E402


def _envelope(runner_result):
    # CliRunner mixes stderr into output; the envelope is the final JSON block.
    text = runner_result.output
    start = text.find("{")
    return json.loads(text[start:])


class GateTier3Tests(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()
        self.handlers = sys.modules["lib.handlers"]
        self.AdtHttpError = sys.modules["lib.client"].AdtHttpError

        class Cfg:
            username = "DEVELOPER"
            profile_name = "dev"
            allow_write = False
            allow_transport = False
            environment = "dev"
            environment_source = "inferred"
            from_environment = False
            write_source = "global"
            transport_source = "global"
            env_write_requested = False
            env_transport_requested = False
            @property
            def is_production(self):
                return self.environment == "prd"

        self.cfg = Cfg()
        self.tmp = tempfile.NamedTemporaryFile("w", suffix=".abap", delete=False)
        self.tmp.write("report z.\n")
        self.tmp.close()

    def tearDown(self):
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_dml_rejected_is_tier_3_and_unsendable(self):
        with patch.object(self.cli, "load_config", return_value=self.cfg), \
                patch.object(self.handlers, "run_sql") as run_sql:
            r = CliRunner().invoke(
                self.cli.cli,
                ["run-sql", "UPDATE t001 SET waers = 'X'"],
            )
        self.assertEqual(r.exit_code, 3, r.output)
        env = _envelope(r)
        self.assertFalse(env["ok"])
        self.assertEqual(env["error"]["code"], "DML_REJECTED")
        run_sql.assert_not_called()

    def test_write_disabled_tier_3_even_with_yes(self):
        self.cfg.allow_write = False
        with patch.object(self.cli, "load_config", return_value=self.cfg):
            r = CliRunner().invoke(
                self.cli.cli,
                ["write-source", "class", "ZCL_X", "--file", self.tmp.name, "--yes"],
            )
        self.assertEqual(r.exit_code, 3, r.output)
        self.assertEqual(_envelope(r)["error"]["code"], "WRITE_DISABLED")

    def test_transport_disabled_tier_3(self):
        with patch.object(self.cli, "load_config", return_value=self.cfg):
            r = CliRunner().invoke(
                self.cli.cli,
                ["create-transport", "--package", "$TMP", "--description", "x", "--ref", "/sap/bc/adt/programs/programs/zx/source/main", "--yes"],
            )
        self.assertEqual(r.exit_code, 3, r.output)
        self.assertEqual(_envelope(r)["error"]["code"], "TRANSPORT_DISABLED")

    def test_confirm_required_when_not_a_tty_without_yes(self):
        self.cfg.allow_write = True
        with patch.object(self.cli, "load_config", return_value=self.cfg), \
                patch.object(self.cli, "_stdin_is_tty", return_value=False):
            r = CliRunner().invoke(
                self.cli.cli,
                ["write-source", "class", "ZCL_X", "--file", self.tmp.name],
            )
        self.assertEqual(r.exit_code, 3, r.output)
        self.assertEqual(_envelope(r)["error"]["code"], "CONFIRM_REQUIRED")

    def test_user_aborted_at_tty_prompt_is_tier_3_not_success(self):
        self.cfg.allow_write = True
        with patch.object(self.cli, "load_config", return_value=self.cfg), \
                patch.object(self.cli, "_stdin_is_tty", return_value=True):
            r = CliRunner().invoke(
                self.cli.cli,
                ["write-source", "class", "ZCL_X", "--file", self.tmp.name],
                input="n\n",
            )
        self.assertEqual(r.exit_code, 3, r.output)
        self.assertEqual(_envelope(r)["error"]["code"], "USER_ABORTED")

    def test_max_rows_validation_is_bad_request_tier_1(self):
        with patch.object(self.cli, "load_config", return_value=self.cfg):
            r = CliRunner().invoke(
                self.cli.cli,
                ["run-sql", "SELECT * FROM t001", "--max-rows", "99999"],
            )
        self.assertEqual(r.exit_code, 1, r.output)
        self.assertEqual(_envelope(r)["error"]["code"], "BAD_REQUEST")


class HandlerErrorTiersTests(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()
        self.handlers = sys.modules["lib.handlers"]
        self.AdtHttpError = sys.modules["lib.client"].AdtHttpError

        class FakeConfig:
            def base_url(self):
                return "https://sap-dev.example.com:8000"

        self._patches = [
            patch.object(self.handlers, "get_config", return_value=FakeConfig()),
        ]
        for p in self._patches:
            p.start()
        self.addCleanup(self._stop)

    def _stop(self):
        for p in self._patches:
            p.stop()

    def _http(self, status, body=""):
        def fake(url, method="GET", **kwargs):
            raise self.AdtHttpError(f"HTTP {status} for {method} {url}: {body}",
                                    status=status)
        return fake

    def test_object_not_found_is_tier_4(self):
        body = ("<?xml version=\"1.0\"?><exc:exception "
                "xmlns:exc=\"http://www.sap.com/abapxml/types/communicationframework\">"
                "<type id=\"com.sap.adt\">ExceptionResourceNotFound</type>"
                "<message>Resource CLASS ZCL_X does not exist.</message></exc:exception>")
        with patch.object(self.handlers, "make_adt_request",
                          side_effect=self._http(404, body)):
            r = CliRunner().invoke(self.cli.cli, ["get-class", "ZCL_X"])
        self.assertEqual(r.exit_code, 4, r.output)
        env = _envelope(r)
        self.assertEqual(env["error"]["code"], "OBJECT_NOT_FOUND")
        self.assertEqual(env["error"]["http_status"], 404)
        self.assertTrue(env["error"]["hint"])

    def test_404_unsupported_endpoint_is_bad_request_not_notfound(self):
        with patch.object(self.handlers, "make_adt_request",
                          side_effect=self._http(404, "No suitable resource found")):
            r = CliRunner().invoke(self.cli.cli, ["syntax-check", "class", "ZCL_X"])
        self.assertEqual(r.exit_code, 1, r.output)
        self.assertEqual(_envelope(r)["error"]["code"], "BAD_REQUEST")

    def test_500_is_server_error_tier_1(self):
        with patch.object(self.handlers, "make_adt_request",
                          side_effect=self._http(500, "ABAP dump")):
            r = CliRunner().invoke(self.cli.cli, ["get-class", "ZCL_X"])
        self.assertEqual(r.exit_code, 1, r.output)
        self.assertEqual(_envelope(r)["error"]["code"], "SERVER_ERROR")

    def test_423_locked_is_tier_1(self):
        with patch.object(self.handlers, "make_adt_request",
                          side_effect=self._http(423, "locked")):
            r = CliRunner().invoke(self.cli.cli, ["get-class", "ZCL_X"])
        self.assertEqual(r.exit_code, 1, r.output)
        self.assertEqual(_envelope(r)["error"]["code"], "LOCKED_BY_OTHER")

    def test_csrf_403_is_tier_1_auth_403_is_tier_2(self):
        with patch.object(self.handlers, "make_adt_request",
                          side_effect=self._http(403, "CSRF token validation failed")):
            r = CliRunner().invoke(self.cli.cli, ["get-class", "ZCL_X"])
        self.assertEqual(r.exit_code, 1, r.output)
        self.assertEqual(_envelope(r)["error"]["code"], "CSRF_EXPIRED")
        with patch.object(self.handlers, "make_adt_request",
                          side_effect=self._http(403, "forbidden")):
            r = CliRunner().invoke(self.cli.cli, ["get-class", "ZCL_X"])
        self.assertEqual(r.exit_code, 2, r.output)
        self.assertEqual(_envelope(r)["error"]["code"], "AUTH_FAILED")

    def test_bad_object_type_is_bad_request(self):
        r = CliRunner().invoke(
            self.cli.cli, ["where-used", "bogus", "ZCL_X"]
        )
        self.assertEqual(r.exit_code, 1, r.output)
        self.assertEqual(_envelope(r)["error"]["code"], "BAD_REQUEST")


class ConfigTier2Tests(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()

    def test_unconfigured_run_sql_is_config_missing_tier_2(self):
        with patch.object(self.cli, "load_config", return_value=None):
            r = CliRunner().invoke(
                self.cli.cli, ["run-sql", "SELECT * FROM t001"]
            )
        self.assertEqual(r.exit_code, 2, r.output)
        self.assertEqual(_envelope(r)["error"]["code"], "CONFIG_MISSING")

    def test_credentials_profile_not_found_tier_2(self):
        with patch.object(self.cli.config_module, "list_profiles", return_value=[]):
            r = CliRunner().invoke(
                self.cli.cli, ["credentials", "forget", "ghost"]
            )
        self.assertEqual(r.exit_code, 2, r.output)
        self.assertEqual(_envelope(r)["error"]["code"], "PROFILE_NOT_FOUND")


class NonInteractiveConfigureTests(unittest.TestCase):
    """5.0: flagged configure is an agent-facing path — errors are envelopes."""

    def setUp(self):
        self.cli, _ = load_cli_module()

    def test_missing_required_fields_is_config_missing_tier_2(self):
        def boom(**kwargs):
            raise self.cli.config_module.ConfigError(
                "Missing required fields for profile 'default': --url"
            )

        with patch.object(self.cli, "save_config_from_flags", side_effect=boom):
            r = CliRunner().invoke(
                self.cli.cli,
                ["configure", "--username", "u", "--client", "100"],
            )
        self.assertEqual(r.exit_code, 2, r.output)
        env = _envelope(r)
        self.assertEqual(env["error"]["code"], "CONFIG_MISSING")
        self.assertFalse(env["ok"])

    def test_invalid_profile_name_is_bad_request_tier_1(self):
        from click.exceptions import UsageError  # noqa: F401

        with patch.object(self.cli, "save_config_from_flags",
                          side_effect=ValueError("Invalid profile name")):
            r = CliRunner().invoke(
                self.cli.cli,
                ["configure", "--profile", "bad/name", "--url", "https://h",
                 "--username", "u", "--password", "p", "--client", "100"],
            )
        self.assertEqual(r.exit_code, 1, r.output)
        self.assertEqual(_envelope(r)["error"]["code"], "BAD_REQUEST")


if __name__ == "__main__":
    unittest.main()
