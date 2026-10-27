"""Single-source CLI version.

The authority is pyproject.toml ([project] version); this module reads it via
importlib.metadata so no second hand-maintained constant exists. The static
fallback covers non-installed invocations (e.g. running from a source tree
without `pip install -e .`), which is a developer-only scenario — installed
and frozen distributions always have metadata (frozen builds embed it).
"""
from __future__ import annotations

import importlib.metadata

_DIST_NAME = "sap-adt"
_FALLBACK = "0.0.0+uninstalled"


def get_version() -> str:
    try:
        return importlib.metadata.version(_DIST_NAME)
    except importlib.metadata.PackageNotFoundError:
        return _FALLBACK


__version__ = get_version()
