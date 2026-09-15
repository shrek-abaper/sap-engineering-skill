"""Single entry point for loading/saving SAP passwords.

All password access in the CLI goes through :func:`load` / :func:`save`
/ :func:`forget`; callers never touch a concrete keystore backend. The
keystore is chosen by capability probing (REGISTRY priority), never by
``platform.system()`` branches. Explicit ``keystore=`` / ``--keystore``
selection is fail-closed: unavailable backends raise instead of silently
falling back.
"""
from dataclasses import dataclass
from typing import List, Optional

from .keystore import REGISTRY, select
from .keystore.base import (
    BackendNotWritableError,
    KeyStore,
    KeyStoreError,
)


class NoCredentialError(KeyStoreError):
    """No password could be obtained for the requested profile."""


# Global --keystore override set by the CLI group callback.
_preferred: Optional[str] = None
# In-process cache: (backend name, profile) -> password. DPAPI/pass shells
# out per call (~300ms) and file-store scrypt is deliberately expensive;
# each secret is decrypted at most once per process.
_cache: dict = {}


def set_preferred(name: Optional[str]) -> None:
    global _preferred
    _preferred = name or None


def reset_cache() -> None:
    _cache.clear()


@dataclass(frozen=True)
class Credentials:
    user: str
    password: str

    def __repr__(self) -> str:
        # Hard requirement: tracebacks printing a Credentials object must
        # not leak the password.
        return f"Credentials(user={self.user!r}, password='***')"

    def __str__(self) -> str:
        return self.__repr__()


def _resolved_preference(keystore: Optional[str]) -> Optional[str]:
    return keystore if keystore is not None else _preferred


def _apply_interactive(store: KeyStore, interactive: bool) -> None:
    # Only prompting-capable backends carry an 'interactive' attribute.
    if hasattr(store, "interactive"):
        store.interactive = interactive


def load(
    profile: str,
    user: str,
    *,
    interactive: bool = True,
    keystore: Optional[str] = None,
    registry: Optional[List[KeyStore]] = None,
) -> Credentials:
    """Return the password for ``profile`` or raise :class:`NoCredentialError`.

    Without a preferred backend, backends are tried in REGISTRY order and
    the first non-None hit wins (e.g. an env override can coexist with a
    DPAPI entry for another profile). With an explicit preference only
    that backend is consulted. Missing credentials always raise rather
    than prompting or hanging when ``interactive=False``.
    """
    candidates = registry if registry is not None else REGISTRY
    preferred = _resolved_preference(keystore)

    if preferred is not None:
        store = select(preferred, candidates=candidates)
        _apply_interactive(store, interactive)
        cache_key = (store.name, profile)
        if cache_key in _cache:
            return Credentials(user, _cache[cache_key])
        secret = store.get(profile)
        if secret is None:
            raise NoCredentialError(
                f"no password for profile '{profile}' in keystore '{preferred}'. "
                f"Run `credentials set {profile}` or check {preferred}."
            )
        _cache[cache_key] = secret
        return Credentials(user, secret)

    for store in candidates:
        ok, _reason = store.available()
        if not ok:
            continue
        cache_key = (store.name, profile)
        if cache_key in _cache:
            return Credentials(user, _cache[cache_key])
        _apply_interactive(store, interactive)
        secret = store.get(profile)
        if secret is not None:
            _cache[cache_key] = secret
            return Credentials(user, secret)

    raise NoCredentialError(
        f"no password found for profile '{profile}' in any available keystore. "
        f"Run `credentials set {profile}`, set SAP_ADT_{profile.upper()}_PASSWORD, "
        "or run `credentials doctor` to diagnose."
    )


def save(
    profile: str,
    user: str,
    password: str,
    *,
    keystore: Optional[str] = None,
    registry: Optional[List[KeyStore]] = None,
) -> str:
    """Store the password in the selected (writable) backend; return its name."""
    candidates = registry if registry is not None else REGISTRY
    preferred = _resolved_preference(keystore)

    if preferred is not None:
        store = select(preferred, candidates=candidates)
        if not store.writable:
            raise BackendNotWritableError(
                f"keystore '{preferred}' is read-only; set the password there "
                "yourself (e.g. export the environment variable)"
            )
        store.set(profile, password)
        _cache[(store.name, profile)] = password
        return store.name

    for store in candidates:
        if not store.writable:
            continue
        ok, _reason = store.available()
        if not ok:
            continue
        store.set(profile, password)
        _cache[(store.name, profile)] = password
        return store.name

    raise KeyStoreError(
        "no writable keystore backend is available; run `credentials doctor`"
    )


def forget(
    profile: str,
    *,
    keystore: Optional[str] = None,
    registry: Optional[List[KeyStore]] = None,
) -> List[str]:
    """Delete the password. Without a preference, purge all writable backends.

    Returns the names of the backends the entry was removed from. A
    read-only env entry, if present, is left for the user to unset.
    """
    candidates = registry if registry is not None else REGISTRY
    preferred = _resolved_preference(keystore)

    if preferred is not None:
        store = select(preferred, candidates=candidates)
        if not store.writable:
            raise BackendNotWritableError(
                f"keystore '{preferred}' is read-only; unset the environment "
                "variable yourself"
            )
        store.delete(profile)
        _cache.pop((store.name, profile), None)
        return [store.name]

    removed = []
    for store in candidates:
        if not store.writable:
            continue
        ok, _reason = store.available()
        if not ok:
            continue
        store.delete(profile)
        _cache.pop((store.name, profile), None)
        removed.append(store.name)
    return removed
