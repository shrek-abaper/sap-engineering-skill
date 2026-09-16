"""kind=fields: table/structure field lists.

S/4HANA-era ADT serves table/structure ``source/main`` as CDS-style DDL
(``define table/structure``). Element fields reference a data element
(``vbeln_va``) whose length/decimals are not in the DDL; a field can instead
use a built-in type inline (``abap.char(18)``, ``abap.dec(13,2)``).

The parser returns ``{"fields": [...], "unparsed_types": [...]}``:

* built-in types populate ``type``/``length``/``decimals``
  (``abap.char(18)`` -> ``CHAR``/18/``None``; ``abap.dec(13,2)`` ->
  ``DEC``/13/2; ``abap.rawstring(0)`` -> ``RAWSTRING``/0/``None``);
* data-element references keep ``type`` as the element name with
  ``length``/``decimals`` null and are listed (distinct, first-seen order)
  in ``unparsed_types`` for the caller to surface in ``meta``.

Field ``description`` is not part of the DDL response (no objectstructure
resource exists on modern releases), so field objects intentionally omit
the key rather than emitting a permanently-null value.
"""
from __future__ import annotations

import re

from .common import ParseError, parse_xml

# key NAME : TYPE[(n[,d])] [not null]
_DECL_RE = re.compile(
    r"^\s*(?P<key>key\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*"
    r"(?P<type>abap\.\w+(?:\([^)]*\))?|\S+?)\s*(?P<notnull>not\s+null)?\s*$",
    re.IGNORECASE,
)
_BUILTIN_RE = re.compile(
    r"^abap\.(?P<kind>[a-z0-9]+)(?:\((\d+)(?:\s*,\s*(\d+))?\))?$",
    re.IGNORECASE,
)
_DDL_HEAD_RE = re.compile(r"\bdefine\s+(?:table|structure)\s+\S+\s*\{",
                          re.IGNORECASE)
_BRACE_STRIP_RE = re.compile(r"\bdefine\s+(?:table|structure)\s+\S+\s*\{(.*)\}\s*$",
                             re.IGNORECASE | re.DOTALL)


def _split_type(type_token: str):
    m = _BUILTIN_RE.match(type_token)
    if not m:
        return type_token, None, None, False
    length = int(m.group(2)) if m.group(2) is not None else None
    decimals = int(m.group(3)) if m.group(3) is not None else None
    return m.group("kind").upper(), length, decimals, True


def _parse_ddl(text: str) -> dict:
    m = _BRACE_STRIP_RE.search(text)
    if not m:
        raise ParseError("DDL body braces not found")
    body = m.group(1)

    fields: list[dict] = []
    unparsed: list[str] = []
    for statement in body.split(";"):
        # Keep the declaration only: "with foreign key/value help" clauses
        # follow the type on subsequent lines.
        decl_lines = []
        for line in statement.splitlines():
            stripped = line.strip()
            if stripped.startswith("with "):
                break
            if stripped.startswith("@") or not stripped:
                continue
            decl_lines.append(stripped)
        dm = _DECL_RE.match(" ".join(decl_lines))
        if not dm:
            # include/association/other DDL constructs are not element fields
            continue
        type_name, length, decimals, is_builtin = _split_type(dm.group("type"))
        field = {
            "name": dm.group("name").lower(),
            "type": type_name,
            "length": length,
            "decimals": decimals,
            "is_key": bool(dm.group("key")),
            "not_null": bool(dm.group("notnull")),
        }
        fields.append(field)
        if not is_builtin and type_name not in unparsed:
            unparsed.append(type_name)
    return {"fields": fields, "unparsed_types": unparsed}


def _parse_xml(payload: bytes) -> dict:
    root = parse_xml(payload)
    # Field-metadata XML (older releases) — extend with ECC fixtures in
    # a later pass; descriptions may be reintroduced from that shape.
    raise ParseError(
        f"field metadata XML ({root.tag}) is not supported yet "
        "(waiting for an older-release fixture)"
    )


def parse(payload: bytes) -> dict:
    text = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else payload
    if _DDL_HEAD_RE.search(text):
        return _parse_ddl(text)
    if text.lstrip().startswith("<?xml") or text.lstrip().startswith("<"):
        return _parse_xml(payload)
    raise ParseError("unrecognized table/structure payload (neither DDL nor XML)")
