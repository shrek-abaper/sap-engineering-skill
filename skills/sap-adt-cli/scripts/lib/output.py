"""Unified output contract for the sap-adt-cli commands.

This module is the single rendering seam between handler results and stdout.
It is introduced incrementally:

* Batch 1 (current): every ``AdtResult`` is treated as ``kind="raw"`` and
  ``render`` returns its ``.text`` byte-for-byte, so external behavior is
  unchanged. The ``Envelope`` dataclass and the ``--format`` plumbing already
  exist but no command produces a structured envelope yet.
* Later batches attach a ``kind``/``data`` to results and render the JSON
  envelope, plain text, or the original ADT XML.

Only the Python standard library is used.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

FORMAT_VERSION = 1

VALID_FORMATS = ("json", "text", "xml")
FORMAT_ENVVAR = "SAP_ADT_FORMAT"

# Pseudo-kind meaning "handler still returns a preformatted string"; render
# passes it through unchanged regardless of the requested format.
RAW_KIND = "raw"

_format: Optional[str] = None


def set_format(fmt: Optional[str]) -> None:
    """Set the output format chosen via ``--format`` / ``SAP_ADT_FORMAT``.

    Mirrors the module-global override pattern used for profiles in
    ``config.set_profile_override``.
    """
    global _format
    _format = fmt


def get_format() -> Optional[str]:
    return _format


@dataclass
class Envelope:
    """Structured output envelope shared by success and error results."""

    ok: bool
    command: str
    format_version: int = FORMAT_VERSION
    profile: Optional[str] = None
    object: Optional[dict] = None
    kind: str = RAW_KIND
    data: Optional[dict] = None
    meta: Optional[dict] = None
    error: Optional[dict] = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ok": self.ok,
            "format_version": self.format_version,
            "command": self.command,
        }
        if self.profile is not None:
            out["profile"] = self.profile
        if self.object is not None:
            out["object"] = self.object
        if self.error is not None:
            out["error"] = self.error
            return out
        out["kind"] = self.kind
        if self.data is not None:
            out["data"] = self.data
        if self.meta is not None:
            out["meta"] = self.meta
        return out


def render(result: Any, fmt: Optional[str] = None) -> str:
    """Render a handler result to the string written to stdout.

    Batch 1 behavior: results carry no structured kind yet, so their existing
    ``.text`` is returned unchanged for every format. Error handling (stderr
    and exit codes) stays the caller's responsibility until the error-code
    batch.
    """
    kind = getattr(result, "kind", RAW_KIND)
    if kind == RAW_KIND:
        return result.text
    raise NotImplementedError(
        "structured envelope rendering lands with the per-command parser batch"
    )
