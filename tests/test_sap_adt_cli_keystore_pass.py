"""Tests for the GPG ``pass`` backend (headless Linux friendly)."""
import sys
import unittest
from pathlib import Path

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "sap-adt-cli" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from lib.keystore import pass_store  # noqa: E402
from lib.keystore.base import KeyStoreError  # noqa: E402


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class PassStoreTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.store = pass_store.PassStore()
        self.store._which = lambda: "/usr/bin/pass"

        def runner(args, stdin_text=None):
            self.calls.append({"args": args, "stdin": stdin_text})
            if args[:2] == ["pass", "ls"]:
                return FakeProc(0, "Password Store\n", "")
            if args[:2] == ["pass", "show"] and args[2] == "sap-adt-cli/dev":
                return FakeProc(0, "pass-secret\n", "")
            if args[:2] == ["pass", "show"]:
                return FakeProc(1, "", "gpg: decryption failed: No secret key")
            return FakeProc(0, "", "")

        self.store._run = runner

    def test_name_and_writable(self):
        self.assertEqual(self.store.name, "pass")
        self.assertTrue(self.store.writable)

    def test_unavailable_when_binary_missing(self):
        self.store._which = lambda: None
        ok, reason = self.store.available()
        self.assertFalse(ok)
        self.assertIn("pass", reason)

    def test_unavailable_when_pass_ls_fails(self):
        def runner(args, stdin_text=None):
            if args[:2] == ["pass", "ls"]:
                return FakeProc(1, "", "fatal: ...")
            return FakeProc(0)
        self.store._run = runner
        ok, reason = self.store.available()
        self.assertFalse(ok)
        self.assertIn("pass ls", reason)

    def test_available_when_ls_succeeds(self):
        ok, reason = self.store.available()
        self.assertTrue(ok)

    def test_get_roundtrip_uses_namespaced_path(self):
        self.assertEqual(self.store.get("dev"), "pass-secret")
        self.assertEqual(self.calls[-1]["args"], ["pass", "show", "sap-adt-cli/dev"])

    def test_get_unknown_error_raises_but_missing_path_returns_none(self):
        with self.assertRaises(KeyStoreError):
            self.store.get("broken")
        # The canonical pass "not in store" message means missing -> None.
        def runner(args, stdin_text=None):
            if args[:2] == ["pass", "ls"]:
                return FakeProc(0)
            return FakeProc(1, "", "sap-adt-cli/gone is not in the password store.")
        self.store._run = runner
        self.assertIsNone(self.store.get("gone"))

    def test_set_pipes_secret_via_stdin_with_force_and_multiline_flags(self):
        self.store.set("dev", "pass-secret")
        args = self.calls[-1]["args"]
        self.assertEqual(args[:2], ["pass", "insert"])
        self.assertIn("-m", args)
        self.assertIn("-f", args)
        self.assertIn("sap-adt-cli/dev", args)
        # secret must not appear in argv
        self.assertNotIn("pass-secret", args)
        self.assertEqual(self.calls[-1]["stdin"], "pass-secret")

    def test_delete_uses_force_and_swallows_missing(self):
        self.store.delete("dev")
        self.assertEqual(self.calls[-1]["args"], ["pass", "rm", "-f", "sap-adt-cli/dev"])
        self.store.delete("never-existed")  # idempotent


if __name__ == "__main__":
    unittest.main()
