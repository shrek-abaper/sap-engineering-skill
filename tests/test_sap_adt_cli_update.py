"""Hermetic updater tests: no registry writes or user installation changes."""
import http.server
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from click.testing import CliRunner

from test_sap_adt_cli_config import load_cli_module


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.cli, self.config = load_cli_module()
        self.u = self.cli.updater
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.version = patch.object(self.u, "get_version", return_value="1.5.3")
        self.version.start()
        self.addCleanup(self.version.stop)
        self.proxy = patch.object(self.u, "_pip_proxy", return_value=None)
        self.proxy.start()
        self.addCleanup(self.proxy.stop)
        self.dist = Mock()
        self.dist.read_text.side_effect = {"INSTALLER": "pip\n"}.get
        self.dist.locate_file.return_value = str(self.root / "lib")
        for name, value in (("prefix", str(self.root)), ("base_prefix", "/base-python")):
            p = patch.object(self.u.sys, name, value)
            p.start()
            self.addCleanup(p.stop)

    def report(self, channel="pip", target="1.6.0"):
        return {
            "channel": channel, "current": "1.5.3", "target": target,
            "update_available": target != "1.5.3", "major": False,
            "guidance": "" if channel == "pip" else "Use the original installation.",
            "installation": self.u.Installation(
                channel, "Use the original installation.",
                (sys.executable, "-m", "pip"), str(self.root)),
        }

    def invoke(self, *args, **kwargs):
        # A check/update must never even read an existing config or keystore.
        with patch.object(self.config, "load_config", side_effect=AssertionError("SAP config read")), \
                patch.object(self.cli, "load_config", side_effect=AssertionError("SAP config read")), \
                patch.object(self.cli.credentials, "load",
                             side_effect=AssertionError("SAP password read")):
            return CliRunner().invoke(self.cli.cli, ["update", *args], **kwargs)

    def test_selects_latest_same_major_not_prerelease_or_downgrade(self):
        with patch.object(self.u, "detect_installation", return_value=self.u.Installation("pip")), \
                patch.object(self.u, "available_versions", return_value=[
                    "1.5.2", "1.6.0", "1.10.0", "2.0.0", "1.11.0rc1", "3.0.0-beta.1", "bad"]):
            self.assertEqual(self.u.check_update()["target"], "1.10.0")
            self.assertEqual(self.u.check_update(major=True)["target"], "2.0.0")
        with patch.object(self.u, "detect_installation", return_value=self.u.Installation("pip")), \
                patch.object(self.u, "available_versions", return_value=["1.5.2"]):
            self.assertFalse(self.u.check_update()["update_available"])

    def test_no_candidate_is_not_reported_as_up_to_date(self):
        with patch.object(self.u, "detect_installation", return_value=self.u.Installation("pip")), \
                patch.object(self.u, "available_versions", return_value=["2.0.0", "1.6.0-beta"]):
            with self.assertRaises(self.u.UpdateError):
                self.u.check_update()

    def test_pypi_excludes_yanked_and_empty_releases(self):
        response = Mock(status_code=200)
        response.json.return_value = {"releases": {
            "1.6.0": [{"yanked": False}], "1.7.0": [{"yanked": True}], "1.8.0": []}}
        with patch.object(self.u.requests, "get", return_value=response) as get:
            self.assertEqual(self.u.available_versions(self.u.Installation("pip")), ["1.6.0"])
        self.assertEqual(get.call_args.kwargs["allow_redirects"], False)
        self.assertEqual(get.call_args.kwargs["timeout"], (5, 20))

    def test_network_and_metadata_errors(self):
        for failure, code in (
            (self.u.requests.Timeout("not disclosed"), "NETWORK_ERROR"),
            (ValueError("not disclosed"), "PARSE_FAILED"),
        ):
            with self.subTest(code=code), patch.object(self.u.requests, "get", side_effect=failure):
                with self.assertRaises(self.u.UpdateError) as raised:
                    self.u.available_versions(self.u.Installation("pip"))
                self.assertEqual(raised.exception.code, code)

    def test_pip_proxy_environment_precedes_config_and_standard_proxy(self):
        self.proxy.stop()
        os.environ.update({"PIP_PROXY": "http://pip-proxy:8080",
                           "HTTPS_PROXY": "http://other-proxy:8080"})
        response = Mock(status_code=200)
        response.json.return_value = {"releases": {}}
        with patch.object(self.u.subprocess, "run") as run, \
                patch.object(self.u.requests, "get", return_value=response) as get:
            self.u.available_versions(self.u.Installation("pip"))
        run.assert_not_called()
        self.assertEqual(get.call_args.kwargs["proxies"], {
            "http": "http://pip-proxy:8080", "https": "http://pip-proxy:8080"})

    def test_pip_config_proxy_is_used_for_metadata(self):
        self.proxy.stop()
        response = Mock(status_code=200)
        response.json.return_value = {"releases": {}}
        for value in ("http://config-proxy:8080", ""):
            with self.subTest(proxy=bool(value)), \
                    patch.object(self.u.importlib.util, "find_spec", return_value=object()), \
                    patch.object(self.u.subprocess, "run", return_value=SimpleNamespace(
                        returncode=0, stdout=json.dumps(value), stderr="")) as run, \
                    patch.object(self.u.requests, "get", return_value=response) as get:
                self.u.available_versions(self.u.Installation("pip"))
                if value:
                    self.assertEqual(get.call_args.kwargs["proxies"],
                                     {"http": value, "https": value})
                else:
                    self.assertNotIn("proxies", get.call_args.kwargs)
            self.assertEqual(run.call_args.args[0][:2], [sys.executable, "-c"])
            self.assertEqual(run.call_args.kwargs["timeout"], 10)

    def test_no_pip_or_frozen_runtime_keeps_default_network_behavior(self):
        self.proxy.stop()
        for frozen, spec in ((False, None), (True, object())):
            with self.subTest(frozen=frozen), \
                    patch.object(self.u.sys, "frozen", frozen, create=True), \
                    patch.object(self.u.importlib.util, "find_spec", return_value=spec), \
                    patch.object(self.u.subprocess, "run") as run:
                self.assertIsNone(self.u._pip_proxy())
                run.assert_not_called()

    def test_pip_config_errors_are_bounded_and_do_not_disclose_output(self):
        self.proxy.stop()
        for outcome, code in (
            (self.u.subprocess.TimeoutExpired("pip", 10), "NETWORK_ERROR"),
            (OSError("private configuration"), "CONFIG_MISSING"),
            (SimpleNamespace(returncode=2, stdout="private configuration",
                             stderr="private configuration"), "CONFIG_MISSING"),
            (SimpleNamespace(returncode=0, stdout="private configuration",
                             stderr=""), "CONFIG_MISSING"),
        ):
            with self.subTest(code=code), \
                    patch.object(self.u.importlib.util, "find_spec", return_value=object()), \
                    patch.object(self.u.subprocess, "run") as run:
                if isinstance(outcome, Exception):
                    run.side_effect = outcome
                else:
                    run.return_value = outcome
                with self.assertRaises(self.u.UpdateError) as raised:
                    self.u.available_versions(self.u.Installation("pip"))
                self.assertEqual(raised.exception.code, code)
                self.assertNotIn("private configuration", str(raised.exception))

    def test_pip_config_reader_excludes_sap_environment(self):
        self.proxy.stop()
        os.environ.update({"SAP_PASSWORD": "fake-secret", "SAP_ADT_DOTENV": "/fake/path",
                           "PIP_CONFIG_FILE": "/chosen/pip.conf"})
        with patch.object(self.u.importlib.util, "find_spec", return_value=object()), \
                patch.object(self.u.subprocess, "run", return_value=SimpleNamespace(
                    returncode=0, stdout=json.dumps("http://proxy:8080"), stderr="")) as run:
            self.u._pip_proxy()
        environment = run.call_args.kwargs["env"]
        self.assertEqual(environment["PIP_CONFIG_FILE"], "/chosen/pip.conf")
        self.assertFalse(any(key.upper().startswith("SAP_") for key in environment))

    def test_real_pip_config_and_requests_use_the_same_local_proxy(self):
        if self.u.importlib.util.find_spec("pip") is None:
            self.skipTest("integration requires pip in the test interpreter")
        self.proxy.stop()
        seen = []

        class Proxy(http.server.BaseHTTPRequestHandler):
            def do_CONNECT(self):
                seen.append(self.path)
                self.send_response(407)
                self.end_headers()

            def log_message(self, *_):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
        self.addCleanup(server.server_close)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        proxy = f"http://127.0.0.1:{server.server_port}"
        config = self.root / "pip.conf"
        # A conflicting standard proxy must not override pip's explicit proxy.
        os.environ.update({"PIP_CONFIG_FILE": str(config),
                           "HTTPS_PROXY": "http://127.0.0.1:1",
                           "NO_PROXY": "pypi.org",
                           "HOME": str(self.root), "XDG_CONFIG_HOME": str(self.root)})
        send = self.u.requests.Session.send

        def guarded_send(session, request, **kwargs):
            self.assertEqual(
                self.u.requests.utils.select_proxy(request.url, kwargs.get("proxies") or {}),
                proxy,
            )
            return send(session, request, **kwargs)

        for content, variable in (
            ("[global]\n", proxy),
            (f"[global]\nproxy = {proxy}\n[install]\nproxy =\n", ""),
            (f"[global]\nproxy = http://127.0.0.1:1\n[install]\nproxy = {proxy}\n", ""),
        ):
            with self.subTest(config=content, environment=bool(variable)):
                config.write_text(content, encoding="utf-8")
                os.environ["PIP_PROXY"] = variable
                seen.clear()
                with patch.object(self.u.requests.Session, "send", guarded_send):
                    with self.assertRaises(self.u.UpdateError) as raised:
                        self.u.available_versions(self.u.Installation("pip"))
                self.assertEqual(raised.exception.code, "NETWORK_ERROR")
                self.assertEqual(seen, ["pypi.org:443"])

    def test_npm_queries_its_configured_registry(self):
        installation = self.u.Installation("npm-global", manager=("/node", "/npm-cli.js"))
        with patch.object(self.u, "_capture", return_value='["1.5.3","1.6.0"]') as run:
            self.assertEqual(self.u.available_versions(installation), ["1.5.3", "1.6.0"])
        self.assertEqual(run.call_args.args[0], [
            "/node", "/npm-cli.js", "view", "sap-adt-cli", "versions", "--json"])

    def test_detects_pip_and_refuses_editable_or_foreign_installer(self):
        with patch.object(self.u.importlib.metadata, "distribution", return_value=self.dist):
            self.assertEqual(self.u.detect_installation().channel, "pip")
            self.dist.read_text.side_effect = {
                "INSTALLER": "pip", "direct_url.json": '{"dir_info":{"editable":true}}'}.get
            self.assertEqual(self.u.detect_installation().channel, "source")
            self.dist.read_text.side_effect = {"INSTALLER": "uv"}.get
            self.assertEqual(self.u.detect_installation().channel, "unknown")

    def test_pipx_detection_requires_ownership_metadata(self):
        prefix = self.root / "custom-pipx-home" / "venvs" / "sap-adt-cli-suffix"
        prefix.mkdir(parents=True)
        self.dist.locate_file.return_value = str(prefix / "lib")
        (prefix / "pipx_metadata.json").write_text(json.dumps({
            "main_package": {"package": "sap-adt-cli"}}))
        with patch.object(self.u.importlib.metadata, "distribution", return_value=self.dist), \
                patch.object(self.u.sys, "prefix", str(prefix)), \
                patch.object(self.u.shutil, "which", return_value="/tools/pipx"):
            self.assertEqual(self.u.detect_installation().channel, "pipx")
        (prefix / "pipx_metadata.json").write_text(json.dumps({
            "main_package": {"package": "other-package"}}))
        with patch.object(self.u.importlib.metadata, "distribution", return_value=self.dist), \
                patch.object(self.u.sys, "prefix", str(prefix)):
            self.assertEqual(self.u.detect_installation().channel, "unknown")

    def test_pep668_is_not_bypassed(self):
        stdlib = self.root / "stdlib"
        stdlib.mkdir()
        (stdlib / "EXTERNALLY-MANAGED").touch()
        with patch.object(self.u.importlib.metadata, "distribution", return_value=self.dist), \
                patch.object(self.u.sys, "base_prefix", str(self.root)), \
                patch.object(self.u.sysconfig, "get_path", return_value=str(stdlib)):
            self.assertEqual(self.u.detect_installation().channel, "externally-managed")

    def test_user_install_and_foreign_python_location(self):
        user_site = self.root / "user-site"
        self.dist.locate_file.return_value = str(user_site)
        with patch.object(self.u.importlib.metadata, "distribution", return_value=self.dist), \
                patch.object(self.u.sys, "prefix", str(self.root / "venv")), \
                patch.object(self.u.site, "getusersitepackages", return_value=str(user_site)), \
                patch.object(self.u.site, "ENABLE_USER_SITE", True):
            self.assertEqual(self.u.detect_installation().channel, "pip-user")
        with patch.object(self.u.importlib.metadata, "distribution", return_value=self.dist), \
                patch.object(self.u.sys, "prefix", str(self.root / "venv")), \
                patch.object(self.u.site, "ENABLE_USER_SITE", False):
            self.assertEqual(self.u.detect_installation().channel, "unknown")

    def test_standalone_is_not_mistaken_for_pip(self):
        with patch.object(self.u.sys, "frozen", True, create=True):
            self.assertEqual(self.u.detect_installation().channel, "standalone")

    def test_npm_scope_and_mismatched_runtime(self):
        package_root = self.root / "global" / "sap-adt-cli"
        (package_root / "scripts").mkdir(parents=True)
        (package_root / "scripts" / "run.js").touch()
        (package_root / "package.json").write_text(json.dumps({
            "name": "sap-adt-cli", "version": "1.5.3"}))
        node = self.root / "node"
        npm = self.root / "npm-cli.js"
        node.touch()
        npm.touch()
        os.environ.update({
            "_SAP_ADT_NPM_ROOT": str(package_root), "_SAP_ADT_NPM_NODE": str(node),
            "_SAP_ADT_NPM_CLI": str(npm)})
        with patch.object(self.u.sys, "executable",
                          str(package_root / "runtime" / "windows-x86_64" / "sap-adt.exe")), \
                patch.object(self.u, "_capture", return_value=str(package_root.parent)):
            self.assertEqual(self.u.detect_installation().channel, "npm-global")
        with patch.object(self.u.sys, "executable", str(self.root / "unrelated")):
            self.assertEqual(self.u.detect_installation().channel, "unknown")
        with patch.object(self.u.sys, "executable", str(package_root / "runtime" / "sap-adt")), \
                patch.object(self.u, "_capture", side_effect=[str(self.root / "other"), str(self.root)]):
            self.assertEqual(self.u.detect_installation().channel, "npm-local")

    def test_check_is_read_only_without_sap_configuration(self):
        with patch.object(self.u, "check_update", return_value=self.report()), \
                patch.object(self.u, "apply_python_update") as apply:
            result = self.invoke("--check")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("1.6.0", result.stdout)
        apply.assert_not_called()

    def test_noninteractive_update_requires_explicit_yes(self):
        with patch.object(self.u, "check_update", return_value=self.report()), \
                patch.object(self.u, "apply_python_update") as apply:
            result = self.invoke()
        self.assertEqual(result.exit_code, 3, result.output)
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "CONFIRM_REQUIRED")
        apply.assert_not_called()

    def test_interactive_decline_does_not_update(self):
        with patch.object(self.u, "check_update", return_value=self.report()), \
                patch.object(self.u, "apply_python_update") as apply, \
                patch("click.testing._NamedTextIOWrapper.isatty", return_value=True):
            result = self.invoke(input="n\n")
        self.assertEqual(result.exit_code, 3, result.output)
        self.assertIn("USER_ABORTED", result.stderr)
        apply.assert_not_called()

    def test_yes_updates_and_verifies_exact_version_with_current_python(self):
        with patch.object(self.u, "check_update", return_value=self.report()), \
                patch.object(self.u, "_capture", side_effect=["", "sap-adt, version 1.6.0"]) as run:
            result = self.invoke("--yes")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(run.call_args_list[0].args[0], [
            sys.executable, "-m", "pip", "install", "--upgrade", "sap-adt-cli==1.6.0"])
        self.assertEqual(run.call_args_list[1].args[0], [
            sys.executable, "-m", "sap_adt.cli", "--version"])
        self.assertIn("verified", result.stdout)

    def test_version_mismatch_and_manager_failure_do_not_claim_success(self):
        with patch.object(self.u, "check_update", return_value=self.report()), \
                patch.object(self.u, "_capture", side_effect=["", "sap-adt, version 1.5.3"]):
            result = self.invoke("--yes")
        self.assertEqual(result.exit_code, 3, result.output)
        self.assertNotIn("Updated and verified", result.output)
        with patch.object(self.u.subprocess, "run",
                          return_value=SimpleNamespace(returncode=1, stdout="", stderr="SECRET")):
            with self.assertRaises(self.u.UpdateError) as raised:
                self.u._capture(["pip", "install"])
        self.assertNotIn("SECRET", str(raised.exception))

    def test_pipx_and_user_commands_preserve_scope(self):
        report = self.report("pipx")
        report["installation"].manager = ("/tools/pipx",)
        report["installation"].root = str(self.root / "pipx-home" / "venvs" / "sap-adt-cli-suffix")
        self.assertEqual(self.u.update_commands(report), [[
            "/tools/pipx", "upgrade", "sap-adt-cli-suffix", "--pip-args", "sap-adt-cli==1.6.0"]])
        with patch.object(self.u, "_capture", side_effect=["", "sap-adt, version 1.6.0"]) as run:
            self.u.apply_python_update(report, self.u.update_commands(report))
        self.assertEqual(run.call_args_list[0].kwargs["env"],
                         {"PIPX_HOME": str(self.root / "pipx-home")})
        report = self.report("pip-user")
        self.assertIn("--user", self.u.update_commands(report)[0])

    def test_unknown_channel_is_guidance_only_even_with_yes(self):
        with patch.object(self.u, "check_update", return_value=self.report("source")), \
                patch.object(self.u, "apply_python_update") as apply:
            result = self.invoke("--yes")
        self.assertEqual(result.exit_code, 3, result.output)
        apply.assert_not_called()

    def test_no_downgrade_or_reinstall_when_up_to_date(self):
        with patch.object(self.u, "check_update", return_value=self.report(target="1.5.3")), \
                patch.object(self.u, "apply_python_update") as apply:
            result = self.invoke("--yes")
        self.assertEqual(result.exit_code, 0, result.output)
        apply.assert_not_called()

    def test_npm_returns_plan_only_after_confirmation_and_never_runs_manager_in_runtime(self):
        os.environ["_SAP_ADT_UPDATE_LAUNCHER"] = "1"
        with patch.object(self.u, "check_update", return_value=self.report("npm-global")), \
                patch.object(self.u, "apply_python_update") as apply:
            result = self.invoke("--yes")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.stdout)["update_plan"]["target"], "1.6.0")
        apply.assert_not_called()
        with patch.object(self.u, "check_update", return_value=self.report("npm-global")):
            result = self.invoke("--check")
        self.assertIsNone(json.loads(result.stdout)["update_plan"])
        self.assertIn("1.6.0", json.loads(result.stdout)["message"])

    def test_errors_do_not_read_config_or_emit_sap_hints(self):
        with patch.object(self.u, "check_update",
                          side_effect=self.u.UpdateError("NETWORK_ERROR", "Registry unavailable.")):
            result = self.invoke("--check")
        self.assertEqual(result.exit_code, 1)
        self.assertNotIn("sap-adt configure", result.stderr)

    def test_package_manager_environment_excludes_sap_credentials(self):
        os.environ.update({"SAP_PASSWORD": "fake-secret", "SAP_ADT_DEV_PASSWORD": "fake-secret",
                           "SAP_ADT_DOTENV": "/fake/path", "HTTPS_PROXY": "http://proxy:8080"})
        with patch.object(self.u.subprocess, "run", return_value=SimpleNamespace(
                returncode=0, stdout="ok")) as run:
            self.u._capture(["npm", "view"])
        env = run.call_args.kwargs["env"]
        self.assertNotIn("SAP_PASSWORD", env)
        self.assertNotIn("SAP_ADT_DEV_PASSWORD", env)
        self.assertNotIn("SAP_ADT_DOTENV", env)
        self.assertEqual(env["HTTPS_PROXY"], "http://proxy:8080")


    def test_package_manager_errors_have_specific_redacted_recovery_hints(self):
        for detail, reason, hint in (
            ("407 proxy-user:fake-secret", "PROXY_AUTH", "URL-encoded"),
            ("certificate verify failed fake-secret", "TLS_CERTIFICATE", "PIP_CERT"),
            ("Permission denied fake-secret", "PERMISSION", "folder permissions"),
            ("ENOSPC fake-secret", "DISK_FULL", "Free space"),
            ("externally-managed-environment", "EXTERNALLY_MANAGED", "virtual environment"),
            ("No matching distribution found", "UNSUPPORTED_VERSION", "configured package index"),
        ):
            with self.subTest(reason=reason), \
                    patch.object(self.u.subprocess, "run", return_value=SimpleNamespace(
                        returncode=1, stdout="", stderr=detail)):
                with self.assertRaises(self.u.UpdateError) as raised:
                    self.u._capture([sys.executable, "-m", "pip", "install"])
                self.assertIn(reason, str(raised.exception))
                self.assertIn(hint, raised.exception.hint)
                self.assertNotIn("fake-secret", str(raised.exception) + raised.exception.hint)

    def test_metadata_tls_error_hint_reaches_cli_envelope(self):
        with patch.object(self.u, "detect_installation", return_value=self.u.Installation("pip")), \
                patch.object(self.u.requests, "get",
                             side_effect=self.u.requests.exceptions.SSLError("private certificate data")):
            result = self.invoke("--check")
        self.assertEqual(result.exit_code, 1)
        error = json.loads(result.stderr)["error"]
        self.assertIn("TLS_CERTIFICATE", error["message"])
        self.assertIn("REQUESTS_CA_BUNDLE", error["hint"])
        self.assertNotIn("private certificate data", result.stderr)

    def test_incomplete_update_has_exact_scoped_repair_and_verification(self):
        for channel in ("pip", "pip-user", "pipx"):
            report = self.report(channel)
            if channel == "pipx":
                report["installation"].root = str(self.root / "owner" / "venvs" / "sap-adt-suffix")
                report["installation"].manager = ("/tools/pipx",)
            with self.subTest(channel=channel), \
                    patch.object(self.u, "check_update", return_value=report), \
                    patch.object(self.u, "_capture", side_effect=self.u.UpdateError(
                        "SERVER_ERROR", "Package operation failed.", "Free disk space.")):
                result = self.invoke("--yes")
            self.assertEqual(result.exit_code, 3)
            hint = json.loads(result.stderr)["error"]["hint"]
            self.assertIn("--force-reinstall", hint)
            self.assertIn("sap-adt-cli==1.6.0", hint)
            self.assertIn("--version", hint)
            self.assertIn("Free disk space.", hint)
            if channel == "pip-user":
                self.assertIn("--user", hint)
            if channel in ("pip", "pip-user"):
                self.assertRegex(hint, r"install'?\s+'?--force-reinstall")
            if channel == "pipx":
                self.assertIn("PIPX_HOME", hint)
                self.assertIn(str(self.root / "owner"), hint)


if __name__ == "__main__":
    unittest.main()
