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


# ---------------------------------------------------------------------------
# ABAP Unit (aunit:runResult)
#
# NOTE: the alert/class-level mapping below is verified against real S/4
# responses, but the testMethod path (pass/fail/skipped counts, failed
# assertion text) is NOT: the capture DEV system exposes no healthy test
# class, so that shape follows the abap-adt-api client. Unknown node shapes
# are collected in meta.unparsed_nodes rather than dropped.
# ---------------------------------------------------------------------------

_AUNIT = "http://www.sap.com/adt/aunit"
_UNIT_ALERT_SEVERITY = {
    "failedAssertion": "error",
    "exception": "error",
    "warning": "warning",
}
_UNIT_KNOWN_TAGS = {
    "runResult", "program", "testClasses", "testClass", "testMethods",
    "testMethod", "alerts", "alert", "title", "details", "detail", "stack",
    "stackEntry",
}


def _unit_alert(el, *, context_uri=None, source_severity=True) -> dict:
    kind = (attr(el, "kind") or "").strip()
    sev_attr = attr(el, "severity")
    title = None
    title_el = next((c for c in el if localname(c.tag) == "title"), None)
    if title_el is not None:
        title = (title_el.text or "").strip()
    details = []
    for d in el.iter():
        if localname(d.tag) != "detail":
            continue
        value = (d.text or attr(d, "text") or "").strip()
        if value:
            details.append(value)
    text = " — ".join([t for t in ([title] + details) if t]) or None
    uri = context_uri
    line = _line_from_uri(uri)
    finding = {
        "severity": _UNIT_ALERT_SEVERITY.get(kind, "info"),
        "text": text,
        "line": line,
        "uri": uri,
    }
    if source_severity and sev_attr:
        # kind is the result category; severity is the (possibly critical)
        # alert severity — keep it visible without conflating the two.
        finding["source_severity"] = sev_attr
    return finding


def parse_unit(payload: bytes) -> dict:
    root = parse_xml(payload)
    findings: list[dict] = []
    total = failed = skipped = 0
    duration_ms: int | None = None
    duration_category = None
    unparsed: list[str] = []

    programs = [el for el in root.iter() if localname(el.tag) == "program"]
    classes = [el for el in root.iter() if localname(el.tag) == "testClass"]
    methods = [el for el in root.iter() if localname(el.tag) == "testMethod"]

    for c in classes:
        if not duration_category:
            duration_category = attr(c, "durationCategory")

    # Class-level alerts are alerts NOT nested inside a testMethod (the real
    # alert-only fixture shape: a defective test class emits one here).
    method_alert_ids = set()
    for m in methods:
        for a in m.iter():
            if localname(a.tag) == "alert":
                method_alert_ids.add(id(a))
    for a in root.iter():
        if localname(a.tag) == "alert" and id(a) not in method_alert_ids:
            stack_entry = next(
                (s for s in a.iter() if localname(s.tag) == "stackEntry"), None
            )
            findings.append(_unit_alert(
                a, context_uri=attr(stack_entry, "uri") if stack_entry is not None else None
            ))

    # method-level results (structure per abap-adt-api; unverified on DEV)
    have_method_time = False
    for m in methods:
        total += 1
        unit_state = (attr(m, "unit") or "").lower()
        if unit_state in ("skipped", "not_executed", "no_test"):
            skipped += 1
        method_alerts_list = [a for a in m.iter() if localname(a.tag) == "alert"]
        is_failed = bool(method_alerts_list) or unit_state in (
            "failed", "error", "fatal"
        )
        if is_failed:
            failed += 1
        for a in method_alerts_list:
            stack_entry = next(
                (s for s in a.iter() if localname(s.tag) == "stackEntry"), None
            )
            findings.append(_unit_alert(
                a,
                context_uri=(attr(stack_entry, "uri") if stack_entry is not None else None)
                or attr(m, "navigationUri") or attr(m, "uri"),
            ))
        t = attr(m, "executionTime")
        if t and t.replace(".", "", 1).isdigit():
            have_method_time = True
            duration_ms = (duration_ms or 0) + int(float(t))

    # unknown shapes surface instead of being silently dropped
    known = _UNIT_KNOWN_TAGS
    for el in root.iter():
        if localname(el.tag) not in known and isinstance(el.tag, str):
            unparsed.append(el.tag.split("}")[-1])

    # Empty shell or only non-executed classes: no test method ran.
    no_tests = total == 0
    meta = {
        "total": total,
        "failed": failed,
        "skipped": skipped,
        "duration_ms": duration_ms if have_method_time else None,
        "duration_category": duration_category,
        "no_tests_found": no_tests,
    }
    if unparsed:
        meta["unparsed_nodes"] = sorted(set(unparsed))
    return {"findings": findings, "_meta": meta}

