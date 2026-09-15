"""Tests for the keyring backend.

The real ``keyring`` package talks to the OS vault (Credential Manager /
Keychain / Secret Service). Tests inject a fake module via the store's
import seam; the Windows/macOS CI jobs exercise the real backends.
"""
import sys
import types
import unittest
from pathlib import Path

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "sap-adt-cli" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from lib.keystore import keyring_store  # noqa: E402


class FailKeyring:
    """Stand-in for keyring.backends.fail.Keyring."""


# Production detection keys off the real class module path.
FailKeyring.__module__ = "keyring.backends.fail"


class MemoryBackend:
    name = "memory fake"

    def __init__(self):
        self.store = {}

    def get_password(self, service, user):
        return self.store.get((service, user))

    def set_password(self, service, user, password):
        self.store[(service, user)] = password

    def delete_password(self, service, user):
        self.store.pop((service, user), None)


def fake_keyring_lib(backend, probe_error=None, store=None):
    """Build a fake keyring *module*.

    Mirrors the real package: get_password/set_password/delete_password
    are module-level functions backed by ``store``; ``get_keyring()`` is
    separate and may return the fail backend.
    """
    store = {} if store is None else store
    lib = types.SimpleNamespace()

    def get_password(service, user):
        if user == "__probe__":
            if probe_error:
                raise probe_error
            return None
        return store.get((service, user))

    def set_password(service, user, password):
        store[(service, user)] = password

    def delete_password(service, user):
        store.pop((service, user), None)

    lib.get_keyring = lambda: backend
    lib.get_password = get_password
    lib.set_password = set_password
    lib.delete_password = delete_password
    lib.backends = types.SimpleNamespace(fail=types.SimpleNamespace(Keyring=FailKeyring))
    return lib


class KeyringStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = keyring_store.KeyringStore()

    def test_name_and_writable(self):
        self.assertEqual(self.store.name, "keyring")
        self.assertTrue(self.store.writable)

    def test_unavailable_when_package_not_installed(self):
        def boom():
            raise ImportError("No module named keyring")

        self.store._load_keyring = boom
        ok, reason = self.store.available()
        self.assertFalse(ok)
        self.assertIn("keyring", reason)

    def test_unavailable_when_only_the_fail_backend_is_resolved(self):
        self.store._load_keyring = lambda: fake_keyring_lib(FailKeyring())
        ok, reason = self.store.available()
        self.assertFalse(ok)
        self.assertIn("fail", reason)

    def test_unavailable_when_probe_handshake_raises_locked_keyring_error(self):
        backend = MemoryBackend()
        err = RuntimeError("org.freedesktop.DBus.Error.ServiceUnknown: keyring locked")
        self.store._load_keyring = lambda: fake_keyring_lib(backend, probe_error=err)
        ok, reason = self.store.available()
        self.assertFalse(ok)
        self.assertIn("locked", reason.lower() + reason)

    def test_available_reports_backend_class_name(self):
        self.store._load_keyring = lambda: fake_keyring_lib(MemoryBackend())
        ok, reason = self.store.available()
        self.assertTrue(ok)
        self.assertIn("MemoryBackend", reason)

    def test_get_returns_none_on_missing_key(self):
        self.store._load_keyring = lambda: fake_keyring_lib(MemoryBackend())
        self.assertIsNone(self.store.get("no-such-profile"))

    def test_service_name_is_stable(self):
        # The service label must never change silently: stored secrets are
        # looked up under exactly this OS-vault entry.
        self.assertEqual(keyring_store.SERVICE, "sap-adt-cli")


class KeyringStoreContractTests(unittest.TestCase):
    """Contract suite with the fake OS backend (real roundtrip semantics)."""

    def setUp(self):
        backend = MemoryBackend()
        self.store_data = backend.store
        self.store = keyring_store.KeyringStore()
        self.store._load_keyring = lambda: fake_keyring_lib(backend, store=backend.store)

    def test_set_get_roundtrip_under_service_and_profile_key(self):
        self.store.set("dev", "kr-secret")
        self.assertEqual(self.store.get("dev"), "kr-secret")
        self.assertEqual(self.store_data[("sap-adt-cli", "dev")], "kr-secret")

    def test_delete_removes_secret_and_is_idempotent(self):
        self.store.set("dev", "kr-secret")
        self.store.delete("dev")
        self.assertIsNone(self.store.get("dev"))
        self.store.delete("dev")

    def test_overwrite_replaces_secret(self):
        self.store.set("dev", "first")
        self.store.set("dev", "second")
        self.assertEqual(self.store.get("dev"), "second")
        self.store.delete("dev")

    def test_unicode_secret_roundtrip(self):
        secret = "口令-Æ-🔐"
        self.store.set("dev", secret)
        self.assertEqual(self.store.get("dev"), secret)
        self.store.delete("dev")


if __name__ == "__main__":
    unittest.main()
