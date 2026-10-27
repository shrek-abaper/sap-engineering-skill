"""kind=source: plain ABAP source text."""
from __future__ import annotations

from .common import decode


def parse(payload: bytes) -> dict:
    """Return the verbatim source and its line count.

    ``source`` preserves bytes/text exactly (byte-level text-mode output
    depends on this); ``line_count`` counts editor lines.
    """
    text = decode(payload)
    return {"source": text, "line_count": len(text.splitlines())}
