"""Contract tests for the pluggable keystore backends.

Every concrete backend gets the same contract suite (set -> get ->
delete -> get is None) by mixing :class:`KeyStoreContract` into a TestCase
that implements :meth:`make_store`.
"""
import importlib
import os
import sys
import unittest
from pathlib import Path

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "sap-adt-cli" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

keystore_pkg = importlib.import_module("lib.keystore")


class MemoryStore:
    """In-memory test double used to validate the registry/contract harness."""

    def __init__(self, name="memory", writable=True, is_available=True, reason=""):
        self.name = name
        self.writable = writable
        self._is_available = is_available
        self._reason = reason
        self.data = {}

    def available(self):
        return self._is_available, self._reason

    def get(self, key):
        return self.data.get(key)

    def set(self, key, secret):
        if not self.writable:
            raise NotImplementedError
        self.data[key] = secret

    def delete(self, key):
        self.data.pop(key, None)


class RegistrySelectionTests(unittest.TestCase):
    def setUp(self):
        self._registered = []

    def tearDown(self):
        for store in self._registered:
            keystore_pkg.REGISTRY.remove(store)

    def register(self, store):
        keystore_pkg.REGISTRY.append(store)
        self._registered.append(store)
        return store

    def test_select_returns_first_available_in_registry_order(self):
        unavailable = MemoryStore(name="first", is_available=False, reason="broken")
        available = MemoryStore(name="second")
        self.register(unavailable)
        self.register(available)

        self.assertIs(keystore_pkg.select(), available)

    def test_select_without_any_available_backend_raises_fail_closed_error(self):
        self.register(MemoryStore(name="broken", is_available=False, reason="nope"))
        with self.assertRaises(keystore_pkg.BackendUnavailableError):
            keystore_pkg.select()

    def test_explicit_preferred_backend_must_be_known(self):
        with self.assertRaises(keystore_pkg.UnknownBackendError):
            keystore_pkg.select(preferred="does-not-exist")

    def test_explicit_preferred_unavailable_backend_raises_instead_of_falling_back(self):
        wanted = MemoryStore(name="wanted", is_available=False, reason="locked")
        other = MemoryStore(name="other")
        self.register(wanted)
        self.register(other)

        with self.assertRaises(keystore_pkg.BackendUnavailableError) as ctx:
            keystore_pkg.select(preferred="wanted")
        # The diagnostic reason must be surfaced for debugging.
        self.assertIn("locked", str(ctx.exception))

    def test_explicit_preferred_available_backend_is_used_even_when_unavailable_backends_come_first(self):
        first = MemoryStore(name="first", is_available=False, reason="broken")
        second = MemoryStore(name="second")
        self.register(first)
        self.register(second)

        self.assertIs(keystore_pkg.select(preferred="second"), second)

    def test_registry_contains_no_duplicate_names(self):
        names = [store.name for store in keystore_pkg.REGISTRY]
        self.assertEqual(sorted(names), sorted(set(names)))


class KeyStoreContract:
    """Mixin: backend contract. Concrete suites implement make_store()."""

    SECRET = "Sap-Pass-123"

    def make_store(self):
        raise NotImplementedError

    def test_set_get_roundtrip(self):
        store = self.make_store()
        store.set("dev", self.SECRET)
        try:
            self.assertEqual(store.get("dev"), self.SECRET)
        finally:
            store.delete("dev")

    def test_get_missing_key_returns_none(self):
        store = self.make_store()
        store.delete("no-such-profile-contract")
        self.assertIsNone(store.get("no-such-profile-contract"))

    def test_delete_removes_secret_and_is_idempotent(self):
        store = self.make_store()
        store.set("dev", self.SECRET)
        store.delete("dev")
        self.assertIsNone(store.get("dev"))
        store.delete("dev")  # deleting a missing key must not raise

    def test_overwrite_replaces_secret(self):
        store = self.make_store()
        try:
            store.set("dev", "first-secret")
            store.set("dev", self.SECRET)
            self.assertEqual(store.get("dev"), self.SECRET)
        finally:
            store.delete("dev")

    def test_unicode_secret_roundtrip(self):
        store = self.make_store()
        secret = "口令-Æ-🔐-x"
        try:
            store.set("dev", secret)
            self.assertEqual(store.get("dev"), secret)
        finally:
            store.delete("dev")


class MemoryStoreContractTests(KeyStoreContract, unittest.TestCase):
    """Validates the contract harness itself against the in-memory double."""

    def make_store(self):
        return MemoryStore()


if __name__ == "__main__":
    unittest.main()
