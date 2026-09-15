"""Backend for the OS-native vaults via the ``keyring`` package.

Covers Windows Credential Manager, macOS Keychain and Linux Secret
Service. ``keyring`` is an OPTIONAL dependency imported lazily: merely
being importable is not enough (a D-Bus session may exist while the
keyring is locked, or only the fail backend may be resolved), so
``available()`` performs a real probe handshake and reports the actual
backend class name for ``credentials doctor``.
"""
from typing import Optional

from . import register

SERVICE = "sap-adt-cli"
PROBE_KEY = "__probe__"


class KeyringStore:
    name = "keyring"
    writable = True

    def _load_keyring(self):
        """Import seam so tests can inject a fake keyring module."""
        import keyring  # noqa: PLC0415 (lazy optional dependency)

        return keyring

    def available(self):
        try:
            kr = self._load_keyring()
        except ImportError:
            return False, "keyring package not installed (pip install keyring)"

        backend = kr.get_keyring()
        backend_module = type(backend).__module__
        class_name = type(backend).__name__

        # The fail backend means no usable OS vault was resolved.
        if backend_module == "keyring.backends.fail":
            return False, "no usable keyring backend (fail.Keyring)"
        # keyrings.alt ships a PlaintextKeyring (an unencrypted file) and
        # other non-OS backends; accepting it would defeat the whole
        # migration away from plain text.
        if backend_module.startswith("keyrings.alt."):
            return (
                False,
                f"insecure keyring backend {class_name} (keyrings.alt); configure a "
                "native vault (Credential Manager / Keychain / Secret Service)",
            )
        # The chainer may itself fall through to PlaintextKeyring.
        if class_name == "ChainerBackend":
            return (
                False,
                "chainer keyring may fall back to the insecure PlaintextKeyring; "
                "configure a native OS keyring",
            )

        class_name = type(backend).__name__
        try:
            kr.get_password(SERVICE, PROBE_KEY)
        except Exception as e:  # locked keyring / missing D-Bus service / ...
            return False, f"{class_name} probe failed: {e}"
        return True, f"{class_name} ({SERVICE})"

    def list_keys(self):
        # keyring has no portable API to enumerate entries of a service.
        return None

    def get(self, key: str) -> Optional[str]:
        kr = self._load_keyring()
        return kr.get_password(SERVICE, key)

    def set(self, key: str, secret: str) -> None:
        kr = self._load_keyring()
        kr.set_password(SERVICE, key, secret)

    def delete(self, key: str) -> None:
        kr = self._load_keyring()
        try:
            kr.delete_password(SERVICE, key)
        except Exception:
            # keyring raises PasswordDeleteError for missing entries;
            # delete must be idempotent per the KeyStore contract.
            pass


register(KeyringStore())
