"""Unified output contract for the sap-adt-cli commands.

Single rendering seam between handler results and stdout.

* ``kind="raw"`` results (legacy commands, error strings, human write/lock
  messages) are passed through unchanged.
* Structured results (kind in source/fields/objects/rows/records/findings/
  scalar) are rendered per the output envelope:

  - explicit ``--format`` / ``SAP_ADT_FORMAT`` wins;
  - ``source`` defaults to ``text`` (verbatim ABAP source, so shell
    redirection stays byte-stable); every other kind defaults to ``json``;
  - ``xml`` returns the original ADT payload kept on the result.

Only the Python standard library is used.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

FORMAT_VERSION = 1

VALID_FORMATS = ("json", "text", "xml")
FORMAT_ENVVAR = "SAP_ADT_FORMAT"

# Pseudo-kind meaning "handler still returns a preformatted string".
RAW_KIND = "raw"

STRUCTURED_KINDS = (
    "source", "fields", "objects", "rows", "records", "findings", "scalar",
    "capabilities",
)

# data key holding the list whose length is the row_count for that kind.
_LIST_KEY = {
    "fields": "fields",
    "objects": "objects",
    "rows": "rows",
    "records": "transports",
    "findings": "findings",
    "capabilities": "collections",
}

_format: Optional[str] = None


class FormatUnsupported(Exception):
    """Requested format cannot represent this result (e.g. xml without raw ADT)."""


def set_format(fmt: Optional[str]) -> None:
    global _format
    _format = fmt


def get_format() -> Optional[str]:
    return _format


@dataclass
class Envelope:
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


def default_format(kind: str) -> str:
    """Format used when the caller does not pass --format/SAP_ADT_FORMAT."""
    return "text" if kind == "source" else "json"


def _row_count(kind: str, data: Optional[dict]) -> Optional[int]:
    key = _LIST_KEY.get(kind)
    if key and isinstance(data, dict) and isinstance(data.get(key), list):
        return len(data[key])
    if kind == "source" and isinstance(data, dict):
        return data.get("line_count")
    return None


def _envelope_dict(result, command, profile) -> dict:
    kind = getattr(result, "kind", RAW_KIND)
    data = getattr(result, "data", None)
    meta = dict(getattr(result, "meta", None) or {})
    rc = _row_count(kind, data)
    if rc is not None:
        meta.setdefault("row_count", rc)
    env = Envelope(
        ok=True,
        command=command or getattr(result, "command", None) or "unknown",
        profile=profile,
        object=getattr(result, "object", None),
        kind=kind,
        data=data,
        meta=meta or None,
    )
    return env.to_dict()


# ----------------------------- text rendering -----------------------------

def _text_source(data: dict) -> str:
    # Verbatim; click.echo adds the trailing newline exactly like the old path.
    return data["source"]


def _text_fields(data: dict) -> str:
    lines = []
    for f in data.get("fields", []):
        prefix = "* " if f.get("is_key") else "  "
        line = f"{prefix}{f.get('name')} : {f.get('type')}"
        if f.get("not_null"):
            line += " not null"
        lines.append(line)
    return "\n".join(lines)


def _text_objects(data: dict) -> str:
    lines = []
    for o in data.get("objects", []):
        lines.append("\t".join([
            str(o.get("type") or ""),
            str(o.get("name") or ""),
            str(o.get("package") or ""),
            str(o.get("description") or ""),
        ]))
    return "\n".join(lines)


def _text_rows(data: dict) -> str:
    columns = [c.get("name", "") for c in data.get("columns", [])]
    lines = ["\t".join(columns)]
    for row in data.get("rows", []):
        lines.append("\t".join("" if v is None else str(v) for v in row))
    return "\n".join(lines)


def _text_records(data: dict) -> str:
    lines = []
    for t in data.get("transports", []):
        lines.append("\t".join([
            str(t.get("trkorr") or ""),
            str(t.get("status") or ""),
            str(t.get("status_text") or ""),
            str(t.get("owner") or ""),
            str(t.get("target") or ""),
            str(t.get("description") or ""),
        ]))
    return "\n".join(lines)


def _text_findings(data: dict) -> str:
    lines = []
    for f in data.get("findings", []):
        line = f"[{(f.get('severity') or '').upper():7}] line {f.get('line')}: {f.get('text') or ''}"
        lines.append(line)
    return "\n".join(lines)


def _text_scalar(data: dict) -> str:
    lines = []
    for key, value in data.items():
        if isinstance(value, (list, dict)):
            continue
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _text_capabilities(data: dict) -> str:
    return "\n".join(
        f"{c.get('href') or ''}\t{','.join(c.get('content_types') or [])}\t{c.get('title') or ''}"
        for c in data.get("collections", [])
    )


_TEXT_RENDERERS = {
    "source": _text_source,
    "fields": _text_fields,
    "objects": _text_objects,
    "rows": _text_rows,
    "records": _text_records,
    "findings": _text_findings,
    "scalar": _text_scalar,
    "capabilities": _text_capabilities,
}


def render(result: Any, fmt: Optional[str] = None,
           command: Optional[str] = None, profile: Optional[str] = None) -> str:
    """Render a handler result to the string written to stdout.

    Raises ``FormatUnsupported`` for combinations without a representation
    (e.g. ``--format xml`` on a result carrying no raw ADT payload).
    """
    kind = getattr(result, "kind", RAW_KIND)
    if kind == RAW_KIND:
        return result.text

    effective = fmt or default_format(kind)
    envelope = _envelope_dict(result, command, profile)

    if effective == "json":
        return json.dumps(envelope, indent=2, ensure_ascii=False)
    if effective == "text":
        renderer = _TEXT_RENDERERS.get(kind)
        if renderer is None:  # pragma: no cover - guarded by STRUCTURED_KINDS
            raise FormatUnsupported(f"no text renderer for kind {kind!r}")
        return renderer(envelope["data"])
    if effective == "xml":
        raw = getattr(result, "raw", None)
        if raw is None:
            raise FormatUnsupported(
                f"command {command!r} has no raw ADT XML payload to return"
            )
        return raw
    raise FormatUnsupported(f"unknown format {effective!r}")
