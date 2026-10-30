"""Stateful debugger lifecycle and policy tests using synthetic HTTP only."""
from dataclasses import replace
import json
import os
from pathlib import Path
from queue import Queue
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from click.testing import CliRunner
import requests

from sap_adt import cli, errors
from sap_adt.adt import handlers
from sap_adt.config import SapConfig
from sap_adt.debugger.adapter import Adapter
from sap_adt.debugger.owner import Owner, descriptor, rpc
from debugger_fixture import debugger_fixture

SOURCE = "/sap/bc/adt/oo/classes/zcl_demo/includes/testclasses"
_proxy_patch = patch.dict(os.environ, {"NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"})


def setUpModule():
    _proxy_patch.start()


def tearDownModule():
    _proxy_patch.stop()


def config(url):
    return SapConfig(url, "OFFLINE", "offline-fixture", "000",
                     allow_write=True, environment="qas", profile_name="qas")


class AdapterTests(unittest.TestCase):
    def test_complete_sequence_keeps_context_and_only_deletes_owned_resources(self):
        with debugger_fixture() as (url, state):
            a = Adapter(config(url), "synthetic-terminal")
            try:
                a.breakpoint(SOURCE, 42)
                hit = a.listen(1)
                self.assertFalse(hit["timed_out"])
                a.attach(hit["debuggee"]["id"])
                self.assertEqual(a.stack()["stack"][0]["line"], "42")
                values = a.vars(["opaque-1"], None, 20, 500)
                self.assertEqual(values["variables"][0]["value"], "\u4e0a\u6d77")
                self.assertTrue(a.vars([], "@LOCALS", 20, 1)["truncated"])
                for action in ("stepInto", "stepOver", "stepReturn", "stepContinue"):
                    a.step(action)
                self.assertEqual(a.cleanup(), [])
                self.assertFalse(a.attached)
                calls = state.calls
                self.assertEqual(calls[-3]["method"], "detachDebugger")
                self.assertTrue(calls[-1]["path"].endswith("/SYNTHETIC_OWNED_BP"))
                self.assertFalse(any(c["method"] == "terminateDebuggee" for c in calls))
                for call in calls[1:]:
                    self.assertIn("synthetic-cookie", call["headers"].get("Cookie", ""))
                    self.assertEqual(call["headers"]["sap-contextid"], "synthetic-context")
            finally:
                a.close()

    def test_timeout_is_not_a_hit_or_attachment(self):
        with debugger_fixture("timeout") as (url, _):
            a = Adapter(config(url), "timeout")
            self.addCleanup(a.close)
            self.assertEqual(a.listen(1), {"timed_out": True, "debuggee": None})
            with self.assertRaises(ValueError):
                a.attach("invented")
            self.assertEqual(a.cleanup(), [])

    def test_foreign_debuggee_and_malformed_attachment_fail_closed(self):
        for scenario in ("foreign-user", "malformed-attach"):
            with self.subTest(scenario=scenario), debugger_fixture(scenario) as (url, state):
                a = Adapter(config(url), "synthetic")
                try:
                    with self.assertRaises(ValueError):
                        hit = a.listen(1)
                        a.attach(hit["debuggee"]["id"])
                    with self.assertRaises(ValueError):
                        a.stack()
                    a.cleanup()
                    if scenario == "malformed-attach":
                        self.assertTrue(any(c["method"] == "detachDebugger" for c in state.calls))
                finally:
                    a.close()

    def test_steps_are_not_replayed_or_treated_as_finished_on_http_500(self):
        with debugger_fixture("step-error") as (url, state):
            a = Adapter(config(url), "synthetic")
            try:
                hit = a.listen(1)
                a.attach(hit["debuggee"]["id"])
                with self.assertRaises(Exception):
                    a.step("stepContinue")
                self.assertTrue(a.uncertain)
                with self.assertRaises(ValueError):
                    a.step("stepContinue")
                self.assertEqual(sum(c["method"] == "stepContinue" for c in state.calls), 1)
                self.assertEqual(a.cleanup(), [])
            finally:
                a.close()

    def test_cleanup_attempts_all_phases_despite_failures(self):
        with debugger_fixture("cleanup-failure") as (url, state):
            a = Adapter(config(url), "synthetic")
            try:
                a.breakpoint(SOURCE, 42)
                a.attach(a.listen(1)["debuggee"]["id"])
                gaps = a.cleanup()
                self.assertEqual(len(gaps), 3)
                self.assertEqual(state.calls[-3]["method"], "detachDebugger")
                self.assertEqual(state.calls[-2]["verb"], "DELETE")
                self.assertEqual(state.calls[-1]["verb"], "DELETE")
            finally:
                a.close()

    def test_auth_failures_do_not_echo_backend_secrets_or_retry(self):
        with debugger_fixture("auth") as (url, state):
            a = Adapter(config(url), "synthetic")
            try:
                result = errors.classify(self.assertRaisesCapture(a))
                self.assertEqual(result.code, errors.AUTH_FAILED)
                self.assertNotIn("SAP_PASSWORD", result.message)
                self.assertEqual(len(state.calls), 2)
            finally:
                a.close()

    @staticmethod
    def assertRaisesCapture(adapter):
        try:
            adapter.listen(1)
        except Exception as exc:
            return exc
        raise AssertionError("Expected HTTP failure")

    def test_rejected_breakpoint_has_explicit_uncertain_scope(self):
        with debugger_fixture("refused-breakpoint") as (url, _):
            a = Adapter(config(url), "synthetic")
            try:
                with self.assertRaises(ValueError):
                    a.breakpoint(SOURCE, 42)
                self.assertTrue(any("BREAKPOINT_SCOPE_UNCONFIRMED" in g for g in a.cleanup()))
            finally:
                a.close()

    def test_invalid_breakpoint_and_variable_requests_send_no_http(self):
        a = Adapter(config("http://127.0.0.1:1"), "synthetic")
        try:
            with patch.object(a.http, "request") as request:
                for uri in ("https://evil.example" + SOURCE, "/sap/bc/adt/activation",
                            SOURCE + "?sap-client=999", SOURCE + "#start=42"):
                    with self.assertRaises(ValueError):
                        a.breakpoint(uri, 42)
                a.attached = True
                for ids, parent in (([], None), (["x"], "@ROOT"), (["x"] * 101, None)):
                    with self.assertRaises(ValueError):
                        a.vars(ids, parent, 20, 500)
                request.assert_not_called()
        finally:
            a.close()


class OwnerTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        self.patch = patch("sap_adt.debugger.owner.state_dir",
                           return_value=Path(self.home.name) / "debug")
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def start(self, cfg):
        owner = Owner(cfg)
        owner.open()
        thread = threading.Thread(target=owner.run)
        thread.start()
        owner.worker = thread
        def finish():
            owner.stop.set()
            thread.join(10)
            self.assertFalse(thread.is_alive())
        self.addCleanup(finish)
        return owner

    def test_private_ipc_profile_affinity_unknown_commands_and_cleanup(self):
        with debugger_fixture() as (url, _):
            cfg = config(url)
            o = self.start(cfg)
            path, record = descriptor(o.session)
            self.assertNotIn("offline-fixture", path.read_text())
            self.assertNotIn("synthetic-cookie", path.read_text())
            self.assertNotIn("token", rpc(cfg, o.session, "status", {}))
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                rpc(replace(cfg, client="100"), o.session, "status", {})
            with self.assertRaises(ValueError):
                rpc(cfg, o.session, "setVariableValue", {})
            denied = requests.post(f"http://127.0.0.1:{record['port']}/command",
                                   json={}, timeout=5)
            self.assertEqual(denied.status_code, 403)
            answer = rpc(cfg, o.session, "cleanup", {})
            self.assertEqual(answer["state"], "closed")
            self.assertTrue(answer["cleanup_requests_accepted"])
            self.assertFalse(answer["remote_cleanup_verified"])

    def test_busy_owner_rejects_second_operation_without_queue_or_http(self):
        with debugger_fixture("busy") as (url, state):
            cfg = config(url)
            o = self.start(cfg)
            hit = rpc(cfg, o.session, "listen", {"timeout": 1})
            rpc(cfg, o.session, "attach", {"debuggee": hit["debuggee"]["id"]})
            thread = threading.Thread(target=lambda: rpc(cfg, o.session, "stack", {}))
            thread.start()
            self.assertTrue(state.entered.wait(5))
            refused = rpc(cfg, o.session, "continue", {})
            self.assertIsInstance(refused, errors.ErrorDecision)
            self.assertIn("busy", refused.message)
            self.assertFalse(any(c["method"] == "stepContinue" for c in state.calls))
            state.release.set()
            thread.join(5)
            rpc(cfg, o.session, "cleanup", {})

    def test_ipc_control_error_hint_never_recommends_retry_or_raw_xml(self):
        with debugger_fixture("step-error") as (url, _):
            cfg = config(url)
            o = self.start(cfg)
            rpc(cfg, o.session, "attach", {
                "debuggee": rpc(cfg, o.session, "listen", {"timeout": 1})["debuggee"]["id"],
            })
            error = rpc(cfg, o.session, "continue", {})
            self.assertEqual(error.code, errors.SERVER_ERROR)
            self.assertIn("Do not replay", error.hint)
            self.assertNotIn("retry later", error.hint)
            self.assertEqual(rpc(cfg, o.session, "status", {})["state"], "uncertain")
            rpc(cfg, o.session, "cleanup", {})

    def test_dead_owner_is_not_recovered_by_pid_and_local_discard_is_partial(self):
        with debugger_fixture() as (url, _):
            cfg = config(url)
            o = Owner(cfg)
            o.open()
            o.server.server_close()
            o.adapter.close()
            result = rpc(cfg, o.session, "cleanup", {}, discard=True)
            self.assertEqual(result["state"], "discarded_local")
            self.assertTrue(result["evidence_gaps"])
            self.assertFalse(o.path.exists())

    def test_insecure_or_symlink_descriptors_are_rejected(self):
        if os.name == "nt":
            self.skipTest("POSIX mode/symlink fixture; Windows DACL checked in native smoke")
        with debugger_fixture() as (url, _):
            o = Owner(config(url))
            o.open()
            try:
                o.path.chmod(0o644)
                with self.assertRaises(Exception):
                    descriptor(o.session)
                o.path.chmod(0o600)
                actual = o.path.with_suffix(".saved")
                o.path.rename(actual)
                o.path.symlink_to(actual)
                with self.assertRaises(Exception):
                    descriptor(o.session)
                o.path.unlink()
                actual.rename(o.path)
            finally:
                o.finish()

    def test_unknown_step_and_incomplete_cleanup_block_later_controls(self):
        for scenario in ("step-error", "cleanup-failure"):
            with self.subTest(scenario=scenario), debugger_fixture(scenario) as (url, state):
                cfg = config(url)
                o = Owner(cfg)
                o.open()
                try:
                    o.execute("attach", {"debuggee": o.execute("listen", {"timeout": 1})["debuggee"]["id"]})
                    if scenario == "step-error":
                        with self.assertRaises(Exception):
                            o.execute("continue", {})
                    else:
                        self.assertTrue(o.execute("cleanup", {})["evidence_gaps"])
                    before = len(state.calls)
                    with self.assertRaises(ValueError):
                        o.execute("continue", {})
                    self.assertEqual(len(state.calls), before)
                finally:
                    o.finish()

    def test_context_switch_and_wrong_step_session_are_not_accepted(self):
        with debugger_fixture() as (url, _):
            a = Adapter(config(url), "synthetic")
            try:
                a.attach(a.listen(1)["debuggee"]["id"])
                with patch.object(a, "request", return_value=b'<step debugSessionId="OTHER"/>'):
                    with self.assertRaises(ValueError):
                        a.step("stepOver")
                self.assertTrue(a.uncertain)
                a.uncertain = False
                a.context = "wrong-context"
                with self.assertRaises(Exception):
                    a.stack()
                self.assertTrue(a.uncertain)
            finally:
                a.cleanup()
                a.close()

    def test_idle_expiry_performs_remote_cleanup(self):
        with debugger_fixture() as (url, state):
            o = self.start(config(url))
            o.adapter.attach(o.adapter.listen(1)["debuggee"]["id"])
            o.last_used -= 121
            o.stop.wait(3)
            o.worker.join(5)
            self.assertTrue(o.stop.is_set())
            self.assertTrue(any(c["method"] == "detachDebugger" for c in state.calls))


class DebugCliTests(unittest.TestCase):
    def test_mutating_commands_require_capability_nonprd_and_fresh_confirmation(self):
        arguments = [
            ["serve"], ["breakpoint", "--session", "a" * 32, "--uri", SOURCE, "--line", "42"],
            ["listen", "--session", "a" * 32],
            ["attach", "--session", "a" * 32, "--debuggee", "x"],
            ["step", "--session", "a" * 32], ["continue", "--session", "a" * 32],
        ]
        for args in arguments:
            for cfg, code in (
                (replace(config("http://offline"), allow_write=False), "WRITE_DISABLED"),
                (replace(config("http://offline"), environment="prd"), "WRITE_DISABLED"),
                (config("http://offline"), "CONFIRM_REQUIRED"),
            ):
                with self.subTest(args=args, code=code), patch.object(cli, "load_config", return_value=cfg), \
                        patch.object(handlers, "debug_operation") as request:
                    result = CliRunner().invoke(cli.cli, ["debug", *args])
                    self.assertEqual(result.exit_code, 3, result.output)
                    self.assertEqual(json.loads(result.stderr)["error"]["code"], code)
                    request.assert_not_called()

    def test_cleanup_allowed_when_writes_disabled_and_partial_exit_one(self):
        cfg = replace(config("http://offline"), allow_write=False)
        data = {"session": "a" * 32, "operation": "cleanup", "state": "discarded_local",
                "evidence_gaps": ["REMOTE_STATE_UNKNOWN"]}
        with patch.object(cli, "load_config", return_value=cfg), patch.object(
            handlers, "debug_operation", return_value=handlers.debug_result(data),
        ):
            result = CliRunner().invoke(cli.cli, ["debug", "cleanup", "--session", "a" * 32])
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertTrue(json.loads(result.stdout)["meta"]["partial"])


class ProcessLifecycleTests(unittest.TestCase):
    def exercise(self, abrupt):
        with debugger_fixture() as (url, state), tempfile.TemporaryDirectory() as home:
            env = {k: v for k, v in os.environ.items() if not k.startswith("SAP_")}
            env.update({
                "HOME": home, "USERPROFILE": home, "SAP_URL": url, "SAP_USERNAME": "OFFLINE",
                "SAP_PASSWORD": "offline-fixture", "SAP_CLIENT": "000",
                "SAP_ENVIRONMENT": "qas", "SAP_ALLOW_WRITE": "true", "SAP_ADT_FORMAT": "json",
                "PYTHONUTF8": "1",
            })
            command = [sys.executable, "-m", "sap_adt"]
            owner = subprocess.Popen([*command, "debug", "serve", "--yes", "--ttl", "30",
                                      "--idle", "20"], env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
            try:
                ready = Queue()
                reader = threading.Thread(target=lambda: ready.put(owner.stdout.readline()), daemon=True)
                reader.start()
                session = json.loads(ready.get(timeout=15))["data"]["session"]
                def invoke(operation, *args, expected=0):
                    result = subprocess.run([*command, "debug", operation, "--session", session, *args],
                                            env=env, capture_output=True, timeout=20)
                    self.assertEqual(result.returncode, expected, result.stderr.decode("utf-8", "replace"))
                    return json.loads(result.stdout)
                hit = invoke("listen", "--timeout", "1", "--yes")["data"]["debuggee"]
                invoke("attach", "--debuggee", hit["id"], "--yes")
                if abrupt:
                    owner.kill()
                    owner.communicate(timeout=10)
                    result = invoke("cleanup", "--discard-local", "--yes", expected=1)
                    self.assertTrue(result["meta"]["partial"])
                    self.assertIn("REMOTE_STATE_UNKNOWN", result["data"]["evidence_gaps"][0])
                    self.assertFalse(any(c["method"] == "detachDebugger" for c in state.calls))
                else:
                    owner.terminate()
                    tail, stderr = owner.communicate(timeout=20)
                    self.assertEqual(owner.returncode, 0, stderr.decode("utf-8", "replace"))
                    self.assertEqual(json.loads(tail)["data"]["state"], "closed")
                    self.assertTrue(any(c["method"] == "detachDebugger" for c in state.calls))
            finally:
                if owner.poll() is None:
                    owner.kill()
                    owner.communicate(timeout=10)
                owner.stdout.close()
                owner.stderr.close()

    def test_abrupt_owner_death_reports_remote_unknown(self):
        self.exercise(abrupt=True)

    @unittest.skipIf(os.name == "nt", "TerminateProcess is not a catchable POSIX SIGTERM")
    def test_sigterm_owner_attempts_nonterminating_remote_cleanup(self):
        self.exercise(abrupt=False)
