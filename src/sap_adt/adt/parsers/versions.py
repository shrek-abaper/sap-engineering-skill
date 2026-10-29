"""Historical version lists; content URIs are opaque server identifiers."""
from __future__ import annotations

from .common import ParseError, attr, parse_xml
from .feeds import parse as parse_feed


def parse(payload: bytes) -> dict:
    data = parse_feed(payload)
    versions = []
    # Keep the SAP feed order, not a lexical or date-based reordering.
    # Version 00000 is the current active source, not a frozen TR snapshot.
    names = {}
    for node in parse_xml(payload).iter():
        if attr(node, "rel") == "http://www.sap.com/adt/relations/transport/request":
            names[attr(node, "href")] = attr(node, "name")
    for entry in data["entries"]:
        if not entry["id"] or not entry["content_uri"]:
            raise ParseError("Historical version lacks id or content URI")
        transports = list(dict.fromkeys(
            names[link["href"]] for link in entry["links"]
            if names.get(link["href"])
        ))
        versions.append({
            "version": entry["id"],
            "is_active": entry["id"] == "00000",
            "author": entry["author"],
            "updated": entry["updated"],
            "title": entry["title"],
            "content_uri": entry["content_uri"],
            "transports": transports,
        })
    return {"versions": versions, "next_uri": data["next_uri"]}
