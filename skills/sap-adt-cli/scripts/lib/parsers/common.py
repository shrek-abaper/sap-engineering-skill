"""Shared helpers for the pure ADT payload parsers."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional


class ParseError(ValueError):
    """Raised when a payload cannot be normalized into the target kind."""


def decode(payload: bytes) -> str:
    """Decode ADT payload text (the services use UTF-8)."""
    if isinstance(payload, str):
        return payload
    return payload.decode("utf-8", errors="replace")


def parse_xml(payload: bytes) -> ET.Element:
    """Parse XML, raising ParseError instead of the stdlib exception types."""
    try:
        return ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ParseError(f"malformed XML: {exc}") from None


def localname(tag: str) -> str:
    """Element local name regardless of namespace (``{ns}name`` -> ``name``)."""
    return tag.rsplit("}", 1)[-1]


def attr(el: ET.Element, name: str) -> Optional[str]:
    """Namespace-insensitive attribute lookup by local name.

    ADT attributes are namespace-qualified (``adtcore:name``); checks the
    qualified form first, then any attribute whose local name matches.
    """
    if name in el.attrib:
        return el.attrib[name]
    suffix = "}" + name
    for key, value in el.attrib.items():
        if key == name or key.endswith(suffix):
            return value
    return None


def child_text(el: ET.Element, name: str) -> Optional[str]:
    """Text of the first direct/descendant child with the given local name."""
    for node in el.iter():
        if localname(node.tag) == name:
            return node.text
    return None


def opt_int(value: Optional[str]) -> Optional[int]:
    """Parse SAP zero-padded numeric strings like ``000010``; None stays None."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None
