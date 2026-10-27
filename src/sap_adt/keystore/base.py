"""Keystore protocol, common types and exceptions."""
from typing import Optional, Tuple, Protocol, runtime_checkable


class KeyStoreError(Exception):
    """Base class for all keystore failures."""


class UnknownBackendError(KeyStoreError):
    """A ``--keystore`` / preferred name does not match any registered backend."""


class BackendUnavailableError(KeyStoreError):
    """The selected backend exists but cannot be used on this machine."""


class BackendNotWritableError(KeyStoreError):
    """A read-only backend (environment variables) was asked to set/delete."""


@runtime_checkable
class KeyStore(Protocol):
    """Storage backend for one secret string per key.

    Keys are SAP environment **profile names** as stored in config.json
    (e.g. ``dev``, ``qas-1``). They are matched case-sensitively and
    verbatim — profile names are user-chosen identifiers, not SAP SIDs —
    and are restricted by the profile validator to ``[A-Za-z0-9_-]+``.
    """

    #: Stable identifier used in config output and the ``--keystore`` option.
    name: str
    #: False for the read-only environment-variable backend.
    writable: bool

    def available(self) -> Tuple[bool, str]:
        """Probe real usability (not just importability).

        Returns ``(True, human-readable detail)`` or
        ``(False, one-line reason shown directly to the user)``.
        """
        ...

    def get(self, key: str) -> Optional[str]:
        """Return the secret, or ``None`` when the key does not exist."""
        ...

    def set(self, key: str, secret: str) -> None:
        """Store the secret (overwrite when present)."""
        ...

    def delete(self, key: str) -> None:
        """Remove the secret; deleting a missing key is a no-op."""
        ...
