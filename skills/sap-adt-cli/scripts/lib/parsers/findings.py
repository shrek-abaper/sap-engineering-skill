"""kind=findings: syntax/ATC check results.

Primary shape is the checkrun resource (``/checkruns``,
``application/vnd.sap.adt.checkmessages+xml``):

``chkrun:checkMessage`` elements carry ``chkrun:type`` (E/W/I/S),
``chkrun:shortText`` and a ``chkrun:uri`` whose fragment encodes
``#start=LINE,COLUMN``. A report without a ``checkMessageList`` means the
object is clean.
"""
from __future__ import annotations

import re

from .common import attr, localname, parse_xml

_SEVERITY = {
    "E": "error",
    "W": "warning",
    "I": "info",
    "S": "info",
    "1": "info",
    "2": "warning",
    "3": "error",
}
_START_RE = re.compile(r"[#&]start=(\d+)(?:,(\d+))?")


def _line_from_uri(uri: str | None):
    if not uri:
        return None
    m = _START_RE.search(uri)
    return int(m.group(1)) if m else None


def _finding(el) -> dict:
    code = (attr(el, "type") or attr(el, "severity") or "").strip()
    text = attr(el, "shortText") or attr(el, "text") or attr(el, "description")
    uri = attr(el, "uri")
    line = _line_from_uri(uri)
    if line is None:
        raw_line = attr(el, "line")
        line = int(raw_line) if raw_line and raw_line.isdigit() else None
    return {
        "severity": _SEVERITY.get(code.upper(), code.lower() or "info"),
        "text": text,
        "line": line,
        "uri": uri,
    }


def parse(payload: bytes) -> dict:
    root = parse_xml(payload)
    findings = []
    for el in root.iter():
        if localname(el.tag) in ("checkMessage", "message") and (
            attr(el, "type") or attr(el, "severity")
        ):
            findings.append(_finding(el))
    return {"findings": findings}
