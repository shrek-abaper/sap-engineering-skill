"""Pure XML/text parsers normalizing ADT payloads into the output contract.

Every parser is a pure function ``parse(payload: bytes) -> dict``:

* no HTTP, no config/keystore access, no clock/network;
* stdlib ``xml.etree.ElementTree`` only;
* raises ``ParseError`` on payloads it cannot understand.

The returned dict is the envelope ``data`` section for that kind:

================== =======================================================
kind               data shape
================== =======================================================
source             ``{source, line_count}``
fields             ``{fields: [{name, type, length, decimals, is_key,
                       not_null, description}]}``
objects            ``{objects: [{name, type, uri, package, description}]}``
rows               ``{columns: [{name, type}], rows: [[...]]}``
records            ``{transports: [{trkorr, description, status,
                       status_text, owner, target, tasks: []}]}``
findings           ``{findings: [{severity, text, line, uri}]}``
scalar             object dictionary (command-specific keys)
================== =======================================================
"""
from __future__ import annotations

from . import (
    capabilities,
    fields,
    findings,
    objects,
    records,
    rows,
    scalar,
    source,
)

__all__ = [
    "capabilities",
    "fields",
    "findings",
    "objects",
    "records",
    "rows",
    "scalar",
    "source",
]
