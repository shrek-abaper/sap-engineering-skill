"""Pluggable secret storage backends.

REGISTRY order is the lookup priority (highest first). Backends register
an instance at import time; :func:`select` resolves the active backend.
"""
from typing import List, Optional

from .base import (
    BackendNotWritableError,
    BackendUnavailableError,
    KeyStore,
    KeyStoreError,
    UnknownBackendError,
)

# Populated by the backend modules imported below. Order = priority.
REGISTRY: List[KeyStore] = []


def register(store: KeyStore) -> KeyStore:
    if any(existing.name == store.name for existing in REGISTRY):
        raise KeyStoreError(f"keystore backend '{store.name}' already registered")
    REGISTRY.append(store)
    return store


def select(preferred: Optional[str] = None, candidates: Optional[List[KeyStore]] = None) -> KeyStore:
    """Return a usable keystore.

    When ``preferred`` is given, that backend must exist AND be usable;
    a missing name raises :class:`UnknownBackendError`, an unusable one
    raises :class:`BackendUnavailableError` — never a silent fallback, so
    tests and troubleshooting stay deterministic.

    Without a preference, the first available backend in REGISTRY order
    wins. If none are available, :class:`BackendUnavailableError` is
    raised (fail-closed). ``candidates`` overrides REGISTRY (test seam).
    """
    registry = candidates if candidates is not None else REGISTRY
    if preferred is not None:
        for store in registry:
            if store.name == preferred:
                ok, reason = store.available()
                if not ok:
                    raise BackendUnavailableError(
                        f"keystore backend '{preferred}' is not available: {reason}"
                    )
                return store
        known = ", ".join(store.name for store in registry) or "(none registered)"
        raise UnknownBackendError(
            f"unknown keystore backend '{preferred}'. Known backends: {known}"
        )

    for store in registry:
        ok, _reason = store.available()
        if ok:
            return store

    available_lines = "\n".join(
        f"  {store.name:<8} {'✗' if not store.available()[0] else '✓'}  {store.available()[1]}"
        for store in registry
    )
    raise BackendUnavailableError(
        "no usable keystore backend found:\n"
        + (available_lines or "  (no backends registered)")
    )


# Import for registration side effects. Order = lookup priority.
from . import (  # noqa: E402,F401
    env_store,
    keyring_store,
    dpapi_store,
    pass_store,
    file_store,
)

__all__ = [
    "REGISTRY",
    "register",
    "select",
    "KeyStore",
    "KeyStoreError",
    "UnknownBackendError",
    "BackendUnavailableError",
    "BackendNotWritableError",
]
