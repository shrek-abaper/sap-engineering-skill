"""Explicit two-profile, sequential active-representation comparisons."""
from __future__ import annotations

import difflib
import hashlib

from .. import config, policy
from . import client, development, handlers, object_evidence, source_write
from .source_parts import source_path


def profiles(left, right):
    a, b = config.load_profile_connection(left), config.load_profile_connection(right)
    identities = [policy.target(c) for c in (a, b)]
    if (identities[0]["origin"], identities[0]["client"]) == (
            identities[1]["origin"], identities[1]["client"]):
        raise ValueError("Comparison profiles resolve to the same SAP origin/client")
    return a, b


def snapshot(kind, name, *, part="main", group=None):
    kind = {"cds-view": "cds"}.get(kind, kind)
    if kind in object_evidence.RESOURCES:
        result = object_evidence.read(kind, name)
        if result.is_error or (result.meta or {}).get("partial"):
            raise ValueError("Metadata snapshot unavailable or partial: " + result.text)
        import json
        text = json.dumps(result.data["metadata"], sort_keys=True, ensure_ascii=False, indent=2)
        uri = result.data["uri"]
        representation = "metadata"
    else:
        uri = development.object_uri(kind, name, group)
        if kind in ("domain", "data-element", "srvb"):
            if part != "main":
                raise ValueError("Metadata objects do not expose class source parts")
            response = handlers._read_adt(uri, extra_headers={"Accept": "application/*"},
                                          allow_redirects=False)
            from .parsers.common import attr, parse_xml
            if (response.status_code != 200
                    or (attr(parse_xml(response.content), "name") or "").upper() != name.upper()):
                raise ValueError("Metadata snapshot identity is unconfirmed")
            text = response.text
            representation = "metadata-xml"
        else:
            uri = source_path(uri, part)
            result = handlers.get_source(uri)
            if result.is_error:
                raise ValueError("Source snapshot unavailable: " + result.text)
            text = source_write.canonical_source(result.data["source"])
            representation = "source"
    if len(text.encode("utf-8")) > 2 * 1024 * 1024:
        raise ValueError("Object representation exceeds 2 MiB")
    return {"type": kind, "name": name.upper(), "part": part, "uri": uri,
            "representation": representation, "source": text,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "version": "active-at-read-time"}


def compare(configs, kind, name, *, part="main", group=None):
    sides, gaps = [], []
    for label, cfg in zip(("from", "to"), configs):
        with client.connection_scope(cfg):
            try:
                sides.append({"target": policy.target(cfg),
                              "snapshot": snapshot(kind, name, part=part, group=group)})
            except Exception as exc:
                gaps.append({"side": label, "code": "OBJECT_SNAPSHOT_UNAVAILABLE", "message": str(exc)})
                sides.append({"target": policy.target(cfg), "snapshot": None})
    a, b = (s["snapshot"] for s in sides)
    changed = a["sha256"] != b["sha256"] if a and b else None
    return {"from": sides[0], "to": sides[1], "changed": changed,
            "diff": "".join(difflib.unified_diff(
                a["source"].splitlines(keepends=True), b["source"].splitlines(keepends=True),
                fromfile=f"{configs[0].profile_name}/{a['uri']}",
                tofile=f"{configs[1].profile_name}/{b['uri']}")) if a and b else None,
            "comparison": "active-representations-not-release-snapshots",
            "evidence_gaps": gaps}
