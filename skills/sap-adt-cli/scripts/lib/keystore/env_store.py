"""Read-only backend: per-profile password environment variables.

Variable naming: ``SAP_ADT_<PROFILE_UPPER>_PASSWORD`` where ``<PROFILE_UPPER>``
is the config.json profile name uppercased (e.g. profile ``qas-1`` ->
``SAP_ADT_QAS-1_PASSWORD``). Containers and CI set these instead of
installing a desktop keyring. Writing is impossible by design.
"""
import os
from typing import Optional

from . import register
from .base import BackendNotWritableError

ENV_PREFIX = "SAP_ADT_"
ENV_SUFFIX = "_PASSWORD"


def _env_var(key: str) -> str:
    return f"{ENV_PREFIX}{key.upper()}{ENV_SUFFIX}"


class EnvStore:
    name = "env"
    writable = False

    def available(self):
        set_vars = sorted(
            name
            for name in os.environ
            if name.startswith(ENV_PREFIX) and name.endswith(ENV_SUFFIX)
        )
        if set_vars:
            return True, ", ".join(set_vars) + " set"
        return False, f"{ENV_PREFIX}*_PASSWORD not set"

    def get(self, key: str) -> Optional[str]:
        return os.environ.get(_env_var(key))

    def set(self, key: str, secret: str) -> None:
        raise BackendNotWritableError(
            "the 'env' keystore is read-only; export "
            f"{_env_var(key)} in the shell instead"
        )

    def delete(self, key: str) -> None:
        raise BackendNotWritableError(
            "the 'env' keystore is read-only; unset "
            f"{_env_var(key)} in the shell instead"
        )


register(EnvStore())
