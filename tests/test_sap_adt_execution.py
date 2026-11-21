"""Controlled execution gates, one-shot output and temporary-object ownership."""
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from click.testing import CliRunner

from test_sap_adt_cli_config import load_cli_module, MemoryKeystore


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.cli, self.cfg = load_cli_module()
        self.e = __import__("sap_adt.adt.execution", fromlist=["execution"])
        self.h = sys.modules["sap_adt.adt.handlers"]
        self.client = sys.modules["sap_adt.adt.client"]
        preflight = patch.object(self.client, "prepare_csrf")
        preflight.start()
        self.addCleanup(preflight.stop)
        self.errors = sys.modules["sap_adt.errors"]
        self.config = self.cfg.SapConfig(
            "https://sap.example.invalid", "TESTER", "secret", "400",
            allow_execute=True, profile_name="dev", environment_source="explicit")
        self.plan = {
            "mode": "class", "name": "ZCL_TEST", "target": {},
            "source_sha256": self.e._hash("source"), "timeout": 3, "max_chars": 100,
        }

    def response(self, text="hello", media="text/plain", status=200):
        response = Mock()
        response.status_code = status
        response.headers = {"Content-Type": media}
        response.iter_content.return_value = [text.encode("utf-8")]
        return response

    def invoke_execution(self, response=None, mode="class", max_chars=100):
        data = {"evidence_gaps": [], "output": {}}
        with patch.object(self.client, "make_adt_request",
                          return_value=response or self.response()) as request, \
             patch.object(self.h, "_base", return_value=self.config.url):
            self.e._invoke(mode, "ZTEST", 3, max_chars, data)
        return data, request

    def test_class_and_report_one_shot_text_output(self):
        for mode, path in (("class", "oo/classrun/"), ("report", "programs/programrun/")):
            with self.subTest(mode=mode):
                data, request = self.invoke_execution(mode=mode)
                self.assertEqual(data["execution"]["status"], "completed")
                self.assertEqual(data["output"]["text"], "hello")
                self.assertEqual(request.call_count, 1)
                self.assertIn(path, request.call_args.args[0])
                self.assertFalse(request.call_args.kwargs["retry_csrf"])
                self.assertFalse(request.call_args.kwargs["allow_redirects"])

    def test_truncation_does_not_claim_completed_execution(self):
        data, _ = self.invoke_execution(self.response("abcdef"), max_chars=3)
        self.assertEqual(data["output"], {"format": "text", "text": "abc", "truncated": True})
        self.assertEqual(data["execution"]["status"], "unknown")
        self.assertTrue(data["evidence_gaps"])

    def test_html_or_redirect_is_not_success(self):
        for response in (self.response("<html/>", "text/html"), self.response(status=302)):
            with self.subTest(status=response.status_code), self.assertRaises(ValueError):
                self.invoke_execution(response)
            response.close.assert_called_once()

    def test_partial_utf8_output_survives_read_failure(self):
        response = self.response()

        def blocks():
            yield "输出".encode("utf-8")
            raise requests.ReadTimeout("interrupted")

        response.iter_content.side_effect = lambda **_: blocks()
        data = {"evidence_gaps": [], "output": {}}
        with patch.object(self.client, "make_adt_request", return_value=response), \
             patch.object(self.h, "_base", return_value=self.config.url), \
             self.assertRaises(requests.ReadTimeout):
            self.e._invoke("class", "ZTEST", 3, 100, data)
        self.assertEqual(data["output"]["text"], "输出")
        self.assertEqual(data["execution"]["status"], "unknown")

    def test_session_isolation_restores_existing_cookie_and_csrf_context(self):
        original = Mock()
        self.client._session = original
        self.client._csrf_token = "old-csrf"
        self.client._session_cookies = {"old": "cookie"}
        fresh = Mock()
        with self.client.isolated_session():
            self.assertIsNone(self.client._csrf_token)
            self.client._session = fresh
        fresh.close.assert_called_once()
        original.close.assert_not_called()
        self.assertIs(self.client._session, original)
        self.assertEqual(self.client._csrf_token, "old-csrf")
        self.assertEqual(self.client._session_cookies, {"old": "cookie"})

    def test_active_source_change_prevents_execution(self):
        with patch.object(self.h, "read_source_main",
                          return_value=self.h.AdtResult(text="changed")), \
             patch.object(self.e, "_invoke") as invoke:
            data, code = self.e.run(self.plan, None)
        self.assertEqual(code, "BASELINE_CHANGED")
        self.assertEqual(data["execution"]["status"], "not_started")
        invoke.assert_not_called()

    def test_timeout_is_unknown_and_never_replayed(self):
        with patch.object(self.h, "read_source_main", return_value=self.h.AdtResult(text="source")), \
             patch.object(self.client, "make_adt_request", side_effect=requests.ReadTimeout("lost")) as request, \
             patch.object(self.h, "_base", return_value=self.config.url):
            data, code = self.e.run(self.plan, None)
        self.assertEqual(code, "EXECUTION_INCOMPLETE")
        self.assertEqual(data["execution"]["status"], "unknown")
        self.assertEqual(request.call_count, 1)

    def temporary_patches(self, *, invoke=None, write_error=False):
        plan = {**self.plan, "mode": "abap", "name": None}
        write = Mock()
        write.to_data.return_value = {"unlock": {"status": "accepted"}}
        write.final_decision.return_value = (
            self.errors.decision("ACTIVATION_FAILED", "syntax rejected") if write_error else None)
        stack = ExitStack()
        stack.enter_context(patch.object(self.e, "_metadata",
                                        side_effect=self.client.AdtHttpError(
                                            "ExceptionResourceNotFound", status=404)))
        create = stack.enter_context(patch.object(self.e, "_create"))
        owns = stack.enter_context(patch.object(self.e, "_owns", return_value=True))
        stack.enter_context(patch.object(self.h, "read_source_main",
                                        return_value=self.h.AdtResult(text="skeleton")))
        stack.enter_context(patch.object(self.e.source_write, "execute", return_value=write))
        delete = stack.enter_context(patch.object(self.e, "_delete"))
        call = stack.enter_context(patch.object(self.e, "_invoke", side_effect=invoke))
        return stack, plan, create, owns, delete, call

    def test_success_and_activation_failure_clean_up_only_owned_class(self):
        for write_error in (False, True):
            with self.subTest(write_error=write_error):
                stack, plan, _, owns, delete, invoke = self.temporary_patches(write_error=write_error)
                with stack:
                    data, code = self.e.run(plan, "out->write( 'hello' ).")
                self.assertEqual(data["cleanup"]["status"], "verified")
                delete.assert_called_once()
                self.assertEqual(owns.call_count, 2)
                self.assertEqual(invoke.call_count, 0 if write_error else 1)
                self.assertEqual(code, "EXECUTION_FAILED" if write_error else None)

    def test_unknown_execution_retains_object_and_does_not_delete(self):
        def unknown(_mode, _name, _timeout, _max_chars, data):
            data["execution"]["status"] = "unknown"
            raise requests.ReadTimeout("lost")

        stack, plan, _, _, delete, _ = self.temporary_patches(invoke=unknown)
        with stack:
            data, code = self.e.run(plan, "WRITE 'x'.")
        self.assertEqual(code, "EXECUTION_INCOMPLETE")
        self.assertEqual(data["cleanup"]["status"], "retained")
        delete.assert_not_called()

    def test_create_timeout_never_deletes_unconfirmed_object(self):
        stack, plan, create, _, delete, invoke = self.temporary_patches()
        create.side_effect = requests.ReadTimeout("lost create response")
        with stack:
            data, code = self.e.run(plan, "WRITE 'x'.")
        self.assertTrue(code)
        self.assertEqual(data["cleanup"]["status"], "not_attempted")
        delete.assert_not_called()
        invoke.assert_not_called()

    def test_changed_ownership_prevents_delete(self):
        stack, plan, _, owns, delete, _ = self.temporary_patches()
        owns.side_effect = [True, False]
        with stack:
            data, code = self.e.run(plan, "WRITE 'x'.")
        self.assertEqual(code, "EXECUTION_INCOMPLETE")
        self.assertEqual(data["cleanup"]["status"], "unknown")
        delete.assert_not_called()

    def test_independent_execute_gate_and_production_refusal(self):
        for changes, expected in (
            ({"allow_execute": False, "allow_write": True, "allow_debug": True}, "EXECUTE_DISABLED"),
            ({"environment": "prd"}, "EXECUTE_DISABLED"),
            ({"from_environment": True, "environment_source": "default"}, "CONFIG_MISSING"),
        ):
            config = self.cfg.SapConfig(self.config.url, "U", "secret", "400", allow_execute=True)
            for key, value in changes.items():
                setattr(config, key, value)
            with self.subTest(changes=changes), patch.object(self.cli, "_load_config", return_value=config), \
                 patch.object(self.h, "prepare_execution") as prepare:
                result = CliRunner().invoke(self.cli.cli, ["run-class", "ZTEST", "--dry-run"])
                self.assertEqual(result.exit_code, 3, result.output)
                self.assertEqual(json.loads(result.stderr)["error"]["code"], expected)
                prepare.assert_not_called()

    def test_noninteractive_execution_needs_hash_and_snippet_write_permission(self):
        with patch.object(self.cli, "_load_config", return_value=self.config):
            result = CliRunner().invoke(self.cli.cli, ["run-class", "ZTEST", "--yes"])
            self.assertEqual(result.exit_code, 3)
            self.assertEqual(json.loads(result.stderr)["error"]["code"], "CONFIRM_REQUIRED")
            result = CliRunner().invoke(self.cli.cli, ["run-abap", "--file", "-", "--dry-run"])
            self.assertEqual(json.loads(result.stderr)["error"]["code"], "WRITE_DISABLED")

    def test_dry_run_and_reviewed_plan_only_execute_once(self):
        self.config.allow_write = True
        with patch.object(self.cli, "_load_config", return_value=self.config), \
             patch.object(self.h, "execute_prepared", return_value=self.h.AdtResult(
                 kind="execution", data={"execution": {"status": "completed"}})) as execute:
            runner = CliRunner()
            dry = runner.invoke(self.cli.cli, ["run-abap", "--file", "-", "--dry-run"],
                                input="out->write( 'hello' ).")
            self.assertEqual(dry.exit_code, 0, dry.output)
            digest = json.loads(dry.stdout)["data"]["plan"]["plan_sha256"]
            execute.assert_not_called()
            result = runner.invoke(
                self.cli.cli, ["run-abap", "--file", "-", "--yes", "--expect-plan-sha256", digest],
                input="out->write( 'changed' ).")
            self.assertEqual(result.exit_code, 3)
            execute.assert_not_called()
            result = runner.invoke(
                self.cli.cli, ["run-abap", "--file", "-", "--yes", "--expect-plan-sha256", digest],
                input="out->write( 'hello' ).")
            self.assertEqual(result.exit_code, 0, result.output)
            execute.assert_called_once()

    def test_execute_capability_is_strict_profile_only(self):
        capability = self.cfg.effective_execute_capability
        self.assertEqual(capability({}, "dev"), (False, "default"))
        self.assertEqual(capability({"allow_execute": "false"}, "dev"), (False, "profile"))
        self.assertEqual(capability({"allow_execute": True}, "dev"), (True, "profile"))
        self.assertEqual(capability({"allow_execute": True}, "prd"), (False, "hard-refused"))

    def test_configure_execute_only_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.cfg.CONFIG_DIR = root
            self.cfg.CONFIG_FILE = root / "config.json"
            self.cfg._OLD_CONFIG_FILE = root / "absent.json"
            self.cfg.credentials.set_registry_override([MemoryKeystore()])
            self.cfg.save_profile(
                name="dev", url=self.config.url, username="TESTER", password="fixture",
                client="400", verify_ssl=False, allow_write=True, allow_transport=True)
            result = CliRunner().invoke(
                self.cli.cli, ["configure", "--profile", "dev", "--allow-execute"])
            self.assertEqual(result.exit_code, 0, result.output)
            saved = json.loads(self.cfg.CONFIG_FILE.read_text())["profiles"]["dev"]
            self.assertTrue(saved["allow_execute"])
            self.assertTrue(saved["allow_write"])
            self.assertTrue(saved["allow_transport"])
            self.assertFalse(saved["verify_ssl"])
            self.assertNotIn("password", saved)

    def test_csrf_rejection_is_not_replayed(self):
        self.client.set_config(self.config)
        self.client._csrf_token = "fixture"
        response = requests.Response()
        response.status_code = 403
        response._content = b"CSRF token rejected"
        with patch.object(self.client, "_request", return_value=response) as request, \
             patch.object(self.client, "_fetch_csrf_token") as fetch, \
             self.assertRaises(self.client.AdtHttpError):
            self.client.make_adt_request(
                self.config.url + "/sap/bc/adt/oo/classrun/ZTEST",
                method="POST", retry_csrf=False, allow_redirects=False)
        request.assert_called_once()
        fetch.assert_not_called()
        self.assertFalse(request.call_args.kwargs["allow_redirects"])

    def test_unknown_preparation_lock_does_not_authorize_delete(self):
        stack, plan, _, _, delete, _ = self.temporary_patches(write_error=True)
        with stack:
            self.e.source_write.execute.return_value.to_data.return_value = {
                "lock": {"status": "unknown"}, "unlock": {"status": "not_attempted"},
                "outcome": "incomplete"}
            data, code = self.e.run(plan, "WRITE 'x'.")
        delete.assert_not_called()
        self.assertEqual(data["cleanup"]["status"], "retained")
        self.assertIsNotNone(code)

    def test_preflight_failure_is_not_an_execution_attempt(self):
        with patch.object(self.client, "prepare_csrf", side_effect=requests.ConnectTimeout("offline")), \
             patch.object(self.h, "_base", return_value=self.config.url), \
             patch.object(self.h, "read_source_main", return_value=self.h.AdtResult(text="source")), \
             patch.object(self.client, "make_adt_request") as request:
            data, code = self.e.run(self.plan, None)
        self.assertEqual(data["execution"]["status"], "not_started")
        self.assertEqual(code, "EXECUTION_FAILED")
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
