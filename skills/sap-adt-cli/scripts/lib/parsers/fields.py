"""kind=fields: table/structure field lists.

S/4HANA-era ADT serves table/structure ``source/main`` as CDS-style DDL
(``define table/structure``), which carries field name, key flag, NOT NULL and
the referenced type — but no length/decimals/description. Those fields are
emitted as ``None``; older releases serving field-metadata XML will be added
to :func:`_parse_xml` when ECC fixtures exist.
"""
from __future__ import annotations

import re

from .common import ParseError, decode, parse_xml

# key NAME : TYPE [not null]   (TYPE is an element reference or abap.<b>(n[,d]))
_DECL_RE = re.compile(
    r"^\s*(?P<key>key\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*"
    r"(?P<type>\S+?)\s*(?P<notnull>not\s+null)?\s*$",
    re.IGNORECASE,
)
_BUILTIN_RE = re.compile(r"^abap\.[a-z]+\((\d+)(?:\s*,\s*(\d+))?\)$", re.IGNORECASE)
_DDL_RE = re.compile(r"\bdefine\s+(?:table|structure)\s+\S+\s*\{", re.IGNORECASE)
_BRACE_STRIP_RE = re.compile(r"\bdefine\s+(?:table|structure)\s+\S+\s*\{(.*)\}\s*$",
                             re.IGNORECASE | re.DOTALL)


def _split_length(type_token: str):
    m = _BUILTIN_RE.match(type_token)
    if not m:
        return type_token, None, None
    # Built-in types carry length inline; element references do not.
    return type_token, int(m.group(1)), (int(m.group(2)) if m.group(2) else None)


def _parse_ddl(text: str) -> list[dict]:
    m = _BRACE_STRIP_RE.search(text)
    if not m:
        raise ParseError("DDL body braces not found")
    body = m.group(1)

    fields: list[dict] = []
    for statement in body.split(";"):
        # Keep only the declaration part: "with foreign key/value help"
        # clauses continue after the type on the following lines.
        decl_lines = []
        for line in statement.splitlines():
            stripped = line.strip()
            if stripped.startswith("with "):
                break
            if stripped.startswith("@") or not stripped:
                continue
            decl_lines.append(stripped)
        decl = " ".join(decl_lines)
        dm = _DECL_RE.match(decl)
        if not dm:
            # include/association/other DDL constructs are not element fields
            continue
        type_token, length, decimals = _split_length(dm.group("type"))
        fields.append({
            "name": dm.group("name").lower(),
            "type": type_token,
            "length": length,
            "decimals": decimals,
            "is_key": bool(dm.group("key")),
            "not_null": bool(dm.group("notnull")),
            "description": None,
        })
    return fields


def _parse_xml(payload: bytes) -> list[dict]:
    root = parse_xml(payload)
    # Field-metadata XML (older releases) — extend with ECC fixtures in batch 3.
    raise ParseError(
        f"field metadata XML ({root.tag}) is not supported yet "
        "(waiting for an older-release fixture)"
    )


def parse(payload: bytes) -> dict:
    text = decode(payload)
    if _DDL_RE.search(text):
        return {"fields": _parse_ddl(text)}
    if text.lstrip().startswith("<?xml") or text.lstrip().startswith("<"):
        return {"fields": _parse_xml(payload)}
    raise ParseError("unrecognized table/structure payload (neither DDL nor XML)")
