"""Tests for the credentials facade (load/save/forget, caching, masking)."""
import sys
import unittest
from pathlib import Path

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "sap-adt-cli" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

from lib import credentials  # noqa: E402
from lib.keystore.base import (  # noqa: E402
    BackendNotWritableError,
    BackendUnavailableError,
    UnknownBackendError,
)


class FakeStore:
    def __init__(self, name, writable=True, available=True, data=None):
        self.name = name
        self.writable = writable
        self._available = available
        self.data = data if data is not None else {}
        self.get_calls = []

    def available(self):
        if self._available:
            return True, f"{self.name} ok"
        return False, f"{self.name} broken"

    def get(self, key):
        self.get_calls.append(key)
        return self.data.get(key)

    def set(self, key, secret):
        if not self.writable:
            raise BackendNotWritableError(f"{self.name} is read-only")
        self.data[key] = secret

    def delete(self, key):
        if not self.writable:
            raise BackendNotWritableError(f"{self.name} is read-only")
        self.data.pop(key, None)


class InteractiveRecorder(FakeStore):
    def __init__(self):
        super().__init__(name="file")
        self.interactive = None


class CredentialsFacadeTests(unittest.TestCase):
    def setUp(self):
        credentials.reset_cache()
        self.env = FakeStore("env", writable=False, data={})
        self.dpapi = FakeStore("dpapi", data={"dev": "dpapi-secret"})
        self.file = FakeStore("file", available=False)
        self.registry = [self.env, self.dpapi, self.file]

    def test_credentials_repr_and_str_never_contain_password(self):
        cred = credentials.Credentials(user="DEVUSER", password="top-secret")
        self.assertNotIn("top-secret", repr(cred))
        self.assertNotIn("top-secret", str(cred))
        self.assertIn("DEVUSER", repr(cred))
        self.assertIn("***", repr(cred))

    def test_load_walks_registry_priority_and_returns_first_hit(self):
        cred = credentials.load("dev", "DEVUSER", registry=self.registry)
        self.assertEqual(cred.password, "dpapi-secret")
        self.assertEqual(cred.user, "DEVUSER")
        # Lower-priority backends are not consulted once a secret is found.
        self.assertEqual(self.file.get_calls, [])

    def test_load_readonly_env_backend_wins_over_lower_priority(self):
        self.env.data["dev"] = "env-secret"
        cred = credentials.load("dev", "DEVUSER", registry=self.registry)
        self.assertEqual(cred.password, "env-secret")

    def test_load_skips_unavailable_backends(self):
        self.dpapi._available = False
        self.file._available = True
        self.file.data["dev"] = "file-secret"
        cred = credentials.load("dev", "DEVUSER", registry=self.registry)
        self.assertEqual(cred.password, "file-secret")

    def test_load_without_any_secret_fails_closed_with_clear_error(self):
        self.dpapi.data.clear()
        with self.assertRaises(credentials.NoCredentialError) as ctx:
            credentials.load("dev", "DEVUSER", registry=self.registry, interactive=False)
        self.assertIn("dev", str(ctx.exception))

    def test_explicit_preferred_backend_is_used_exclusively(self):
        # 'file' has no secret, but 'dpapi' (lower priority) does: still fail.
        self.file._available = True
        with self.assertRaises(credentials.NoCredentialError):
            credentials.load("dev", "DEVUSER", keystore="file", registry=self.registry)
        cred = credentials.load("dev", "DEVUSER", keystore="dpapi", registry=self.registry)
        self.assertEqual(cred.password, "dpapi-secret")

    def test_unknown_preferred_backend_raises(self):
        with self.assertRaises(UnknownBackendError):
            credentials.load("dev", "DEVUSER", keystore="nope", registry=self.registry)

    def test_unavailable_preferred_backend_raises(self):
        with self.assertRaises(BackendUnavailableError):
            credentials.load("dev", "DEVUSER", keystore="file", registry=self.registry)

    def test_save_uses_first_available_writable_backend_skipping_readonly(self):
        credentials.save("qas", "DEVUSER", "new-secret", registry=self.registry)
        self.assertEqual(self.dpapi.data["qas"], "new-secret")
        self.assertEqual(self.env.data, {})

    def test_save_to_readonly_preferred_backend_raises(self):
        with self.assertRaises(BackendNotWritableError):
            credentials.save("dev", "DEVUSER", "x", keystore="env", registry=self.registry)

    def test_save_updates_cache(self):
        credentials.save("dev", "DEVUSER", "fresh", registry=self.registry)
        cred = credentials.load("dev", "DEVUSER", registry=self.registry)
        self.assertEqual(cred.password, "fresh")
        # Served from cache: the underlying backend still has the value,
        # but a second load does not add another get call.
        calls_before = len(self.dpapi.get_calls)
        credentials.load("dev", "DEVUSER", registry=self.registry)
        self.assertEqual(len(self.dpapi.get_calls), calls_before)

    def test_load_caches_decrypted_secret_within_one_process(self):
        credentials.load("dev", "DEVUSER", registry=self.registry)
        credentials.load("dev", "DEVUSER", registry=self.registry)
        self.assertEqual(self.dpapi.get_calls.count("dev"), 1)

    def test_forget_without_preference_deletes_from_all_writable_backends(self):
        self.env.data["dev"] = "env-secret"  # read-only; must not raise
        credentials.forget("dev", registry=self.registry)
        self.assertNotIn("dev", self.dpapi.data)

    def test_forget_with_preference_only_touches_that_backend(self):
        self.file._available = True
        self.file.data["dev"] = "file-secret"
        credentials.forget("dev", keystore="file", registry=self.registry)
        self.assertEqual(self.dpapi.data["dev"], "dpapi-secret")

    def test_forget_invalidates_cache(self):
        credentials.load("dev", "DEVUSER", registry=self.registry)
        credentials.forget("dev", registry=self.registry)
        with self.assertRaises(credentials.NoCredentialError):
            credentials.load("dev", "DEVUSER", registry=self.registry)

    def test_interactive_flag_is_propagated_to_file_backend(self):
        recorder = InteractiveRecorder()
        with self.assertRaises(credentials.NoCredentialError):
            credentials.load(
                "dev", "DEVUSER", registry=[recorder], interactive=False
            )
        self.assertFalse(recorder.interactive)


if __name__ == "__main__":
    unittest.main()
