"""Tests for the WSL DPAPI keystore backend.

The real backend shells out to Windows powershell.exe (one ~300ms
process per call). Tests replace the PowerShell runner seam; real-machine
verification is a manual checklist in CONTRIBUTING.md.
"""
import base64
import json
import os
import stat
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "sap-adt-cli" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from lib.keystore import dpapi_store  # noqa: E402
from lib.keystore.base import KeyStoreError  # noqa: E402


class FakePowershell:
    """Simulates the two DPAPI scripts via reversible base64 transforms."""

    def __init__(self, fail_stderr=None):
        self.calls = []
        self.fail_stderr = fail_stderr

    def __call__(self, store, script, payload):
        self.calls.append({"script": script, "payload": payload})
        if self.fail_stderr is not None:
            raise KeyStoreError(f"powershell.exe failed: {self.fail_stderr}")
        if "ConvertFrom-SecureString" in script:
            # encrypt path: stdin carries the plaintext secret
            return "ENC:" + base64.b64encode(payload["secret"].encode("utf-8")).decode()
        if "ConvertTo-SecureString" in script:
            # decrypt path: stdin carries the ciphertext blob
            blob = payload["cipher"]
            return base64.b64decode(blob[4:]).decode("utf-8")
        raise AssertionError("unknown DPAPI script")


def make_store(tmp_path, fake_ps, *, is_wsl=True, powershell_path="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"):
    store = dpapi_store.DpapiStore(secrets_file=tmp_path / ".sap-adt-cli" / "secrets.json")
    store._is_wsl = lambda: is_wsl
    store._find_powershell = lambda: powershell_path
    store._run_powershell = lambda script, payload: fake_ps(store, script, payload)
    return store


class DpapiAvailabilityTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def store(self, **kw):
        return make_store(self.tmp, FakePowershell(), **kw)

    def test_name_and_writable(self):
        store = self.store()
        self.assertEqual(store.name, "dpapi")
        self.assertTrue(store.writable)

    def test_unavailable_outside_wsl(self):
        store = self.store(is_wsl=False)
        ok, reason = store.available()
        self.assertFalse(ok)
        self.assertIn("WSL", reason)

    def test_unavailable_when_powershell_exe_missing(self):
        store = self.store(powershell_path=None)
        ok, reason = store.available()
        self.assertFalse(ok)
        self.assertIn("powershell.exe", reason)
        self.assertIn("wsl.conf", reason)

    def test_available_in_wsl_with_powershell(self):
        store = self.store()
        ok, reason = store.available()
        self.assertTrue(ok)
        self.assertIn("DPAPI", reason)


class DpapiWslDetectionTests(unittest.TestCase):
    def test_detects_wsl_from_distribution_env_var(self):
        store = object.__new__(dpapi_store.DpapiStore)
        with patch.dict(os.environ, {"WSL_DISTRO_NAME": "Ubuntu-24.04"}):
            self.assertTrue(store._is_wsl())

    def test_detects_wsl_from_proc_version(self):
        store = object.__new__(dpapi_store.DpapiStore)
        proc_version = "Linux version 6.6.87.2-microsoft-standard-WSL2 ..."
        with patch.dict(os.environ, {}, clear=True), \
             patch("builtins.open", unittest.mock.mock_open(read_data=proc_version)):
            self.assertTrue(store._is_wsl())

    def test_not_wsl_on_plain_linux(self):
        store = object.__new__(dpapi_store.DpapiStore)
        proc_version = "Linux version 6.6.0-generic ..."
        with patch.dict(os.environ, {}, clear=True), \
             patch("builtins.open", unittest.mock.mock_open(read_data=proc_version)):
            self.assertFalse(store._is_wsl())


class DpapiContractTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.fake_ps = FakePowershell()
        self.store = make_store(self.tmp, self.fake_ps)

    def tearDown(self):
        self._td.cleanup()

    def read_secrets_file(self):
        return json.loads((self.tmp / ".sap-adt-cli" / "secrets.json").read_text())

    def test_set_writes_only_ciphertext_to_disk_with_0600(self):
        self.store.set("dev", "Sap-Pass-123")
        raw = (self.tmp / ".sap-adt-cli" / "secrets.json").read_text()
        self.assertNotIn("Sap-Pass-123", raw)  # only the DPAPI blob on disk
        data = json.loads(raw)
        self.assertIn("dev", data["entries"])
        if os.name == "posix":  # Windows does not model unix permission bits
            mode = stat.S_IMODE((self.tmp / ".sap-adt-cli" / "secrets.json").stat().st_mode)
            self.assertEqual(mode, 0o600)

    def test_set_get_roundtrip(self):
        self.store.set("dev", "Sap-Pass-123")
        self.assertEqual(self.store.get("dev"), "Sap-Pass-123")

    def test_get_missing_key_returns_none_without_calling_powershell(self):
        before = len(self.fake_ps.calls)
        self.assertIsNone(self.store.get("never-set"))
        self.assertEqual(len(self.fake_ps.calls), before)

    def test_delete_removes_secret_and_is_idempotent(self):
        self.store.set("dev", "Sap-Pass-123")
        self.store.delete("dev")
        self.assertIsNone(self.store.get("dev"))
        self.store.delete("dev")

    def test_overwrite_replaces_secret(self):
        self.store.set("dev", "first-secret")
        self.store.set("dev", "second-secret")
        self.assertEqual(self.store.get("dev"), "second-secret")

    def test_unicode_secret_roundtrip(self):
        secret = "口令-Æ-🔐"
        self.store.set("dev", secret)
        self.assertEqual(self.store.get("dev"), secret)

    def test_secret_is_passed_via_stdin_payload_never_argv(self):
        self.store.set("dev", "Sap-Pass-123")
        encrypt_call = self.fake_ps.calls[0]
        self.assertEqual(encrypt_call["payload"]["secret"], "Sap-Pass-123")
        self.assertNotIn("Sap-Pass-123", encrypt_call["script"])

    def test_powershell_failure_surfaces_as_keystore_error(self):
        broken = make_store(self.tmp, FakePowershell(fail_stderr="DPAPI failed for current user"))
        with self.assertRaises(KeyStoreError):
            broken.set("dev", "Sap-Pass-123")

    @unittest.skipUnless(os.name == "posix", "unix mode bits only")
    def test_dir_permissions_are_0700(self):
        self.store.set("dev", "x")
        mode = stat.S_IMODE((self.tmp / ".sap-adt-cli").stat().st_mode)
        self.assertEqual(mode, 0o700)


class DpapiRealRunnerTests(unittest.TestCase):
    """The subprocess seam: argv flags, stdin payload, .exe requirement."""

    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.store = dpapi_store.DpapiStore(secrets_file=self.tmp / "secrets.json")

    def tearDown(self):
        self._td.cleanup()

    def test_runner_invokes_windows_powershell_with_profile_disabled_and_stdin_payload(self):
        completed = unittest.mock.Mock(returncode=0, stdout="ENC:blob\n", stderr="")
        with patch("lib.keystore.dpapi_store.subprocess.run", return_value=completed) as run:
            out = self.store._run_powershell("SCRIPT", {"secret": "Sap-Pass-123"})

        self.assertEqual(out, "ENC:blob")
        args, kwargs = run.call_args
        argv = args[0]
        self.assertTrue(argv[0].endswith("powershell.exe"))
        self.assertIn("-NoProfile", argv)
        self.assertIn("-NonInteractive", argv)
        joined_argv = " ".join(argv)
        self.assertNotIn("Sap-Pass-123", joined_argv)  # never on the command line
        self.assertIn("Sap-Pass-123", kwargs["input"])  # but present on stdin

    def test_runner_nonzero_exit_raises_keystore_error(self):
        completed = unittest.mock.Mock(returncode=1, stdout="", stderr="boom")
        with patch("lib.keystore.dpapi_store.subprocess.run", return_value=completed):
            with self.assertRaises(KeyStoreError):
                self.store._run_powershell("SCRIPT", {"secret": "x"})


if __name__ == "__main__":
    unittest.main()
