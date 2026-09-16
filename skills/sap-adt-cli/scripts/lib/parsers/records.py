"""kind=records: transport request lists.

Two wire shapes are accepted:

* transport organizer tree (new ``/cts/transportrequests`` resource,
  ``application/vnd.sap.adt.transportorganizertree.v1+xml``);
* the legacy CTS worklist document (``workitem|transport|request`` elements
  with ``attribute`` children) used by older releases.

Only an empty-tree fixture is available on the capture system (the service
user owns no transports); non-empty tree parsing therefore follows the
documented attribute layout and gains goldens once a populated fixture
exists.
"""
from __future__ import annotations

from .common import ParseError, attr, localname, parse_xml

# TRSTATUS codes callers should not have to memorize.
STATUS_TEXT = {
    "D": "modifiable",
    "R": "released",
    "L": "released (modifiable protected)",
    "N": "released (modifiable, repair protection)",
    "O": "released (protected start-up)",
    "K": "released (modifiable, temporary lock)",
    "Q": "released (modifiable, protected, temporary lock)",
}
_CONTAINERS = {"workitem", "transport", "request"}
_ATTR_NAMES = {
    "trkorr": "trkorr",
    "as4text": "description",
    "trstatus": "status",
    "as4user": "owner",
    "tarsystem": "target",
}


def _status_text(code):
    return STATUS_TEXT.get(code, code)


def _attributes(el) -> dict:
    out = {}
    for node in el.iter():
        if localname(node.tag) != "attribute":
            continue
        name = (attr(node, "name") or "").strip().lower()
        if name in _ATTR_NAMES:
            value = attr(node, "value")
            if value is not None:
                out[_ATTR_NAMES[name]] = value
    return out


def _record_from(element) -> dict | None:
    # Direct-attribute tree variants carry the number on @name/@number.
    values = _attributes(element)
    trkorr = values.get("trkorr") or attr(element, "number") or attr(element, "name")
    if not trkorr or not _looks_like_trkorr(trkorr):
        return None
    status = values.get("status")
    return {
        "trkorr": trkorr,
        "description": values.get("description") or attr(element, "description"),
        "status": status,
        "status_text": _status_text(status),
        "owner": values.get("owner") or attr(element, "owner"),
        "target": values.get("target"),
        # Task nesting in the tree resource awaits a non-empty fixture.
        "tasks": [],
    }


def _looks_like_trkorr(value) -> bool:
    return bool(value) and len(value) >= 6 and any(ch.isdigit() for ch in value[-6:])


def parse_single_request(payload: bytes) -> dict:
    """GET /cts/transportrequests/{trkorr}: one tm:request."""
    root = parse_xml(payload)
    request = next(
        (el for el in root.iter() if localname(el.tag) == "request"), None
    )
    if request is None:
        raise ParseError(f"not a transport request: {localname(root.tag)}")
    def _status_text(el):
        code = (attr(el, "status") or "").upper()
        # Prefer the server-provided localized text (status_text attribute),
        # fall back to the local code map for payloads that omit it.
        return attr(el, "status_text") or STATUS_TEXT.get(code, code or None)

    tasks = [
        {
            "trkorr": attr(t, "number"),
            "owner": attr(t, "owner"),
            "status": (attr(t, "status") or "").upper() or None,
            "status_text": _status_text(t),
        }
        for t in request.iter() if localname(t.tag) == "task"
    ]
    status = (attr(request, "status") or "").upper() or None
    return {
        "transport": {
            "trkorr": attr(request, "number"),
            "description": attr(request, "desc"),
            "status": status,
            "status_text": _status_text(request),
            "owner": attr(request, "owner"),
            "target": attr(request, "target") or None,
            "tasks": tasks,
        }
    }


def parse_release_report(payload: bytes) -> dict:
    """POST .../{trkorr}/newreleasejobs release check reports."""
    root = parse_xml(payload)
    reports = []
    for r in root.iter():
        if localname(r.tag) != "checkReport":
            continue
        messages = [
            {
                "severity": attr(m, "type"),
                "text": attr(m, "shortText") or attr(m, "text"),
            }
            for m in r.iter() if localname(m.tag) == "checkMessage"
        ]
        reports.append({
            "reporter": attr(r, "reporter"),
            "status": attr(r, "status"),
            "status_text": attr(r, "statusText"),
            "triggering_uri": attr(r, "triggeringUri"),
            "messages": messages,
        })
    return {"release_reports": reports}


def parse(payload: bytes) -> dict:
    root = parse_xml(payload)
    records = []
    for el in root.iter():
        if localname(el.tag) in _CONTAINERS and el is not root:
            rec = _record_from(el)
            if rec is not None:
                records.append(rec)
    return {"transports": records}
