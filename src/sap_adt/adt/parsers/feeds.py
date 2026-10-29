"""Atom feed catalog/schema and diagnostic entries."""
from __future__ import annotations

from .common import ParseError, attr, child_text, localname, parse_xml

ATOM = "{http://www.w3.org/2005/Atom}"


def links(element) -> list[dict]:
    return [
        {k: attr(n, k) for k in ("href", "rel", "type", "title")}
        for n in element.findall(f"{ATOM}link")
    ]


def parse(payload: bytes) -> dict:
    root = parse_xml(payload)
    if root.tag != f"{ATOM}feed":
        raise ParseError("Expected an Atom feed")
    entries = []
    for entry in root.findall(f"{ATOM}entry"):
        content = entry.find(f"{ATOM}content")
        summary = entry.find(f"{ATOM}summary")
        item = {
            "id": child_text(entry, "id"),
            "title": child_text(entry, "title"),
            "updated": child_text(entry, "updated"),
            "author": child_text(entry.find(f"{ATOM}author"), "name")
            if entry.find(f"{ATOM}author") is not None else None,
            "summary": "".join(summary.itertext()) if summary is not None else None,
            "content_uri": attr(content, "src") if content is not None else None,
            "content_type": attr(content, "type") if content is not None else None,
            "links": links(entry),
            "categories": [
                {"term": attr(n, "term"), "label": attr(n, "label")}
                for n in entry.findall(f"{ATOM}category")
            ],
        }
        extended = next(
            (n for n in entry if localname(n.tag) == "extendedData"), None
        )
        if extended is not None:
            item["schema"] = {
                "attributes": [
                    {
                        "id": attr(n, "id"),
                        "label": child_text(n, "label"),
                        "data_type": next(
                            (attr(c, "id") for c in n if localname(c.tag) == "dataType"),
                            None,
                        ),
                        "operators": [
                            attr(c, "id") for c in n.iter()
                            if localname(c.tag) == "operator"
                        ],
                    }
                    for n in extended.iter() if localname(n.tag) == "attribute"
                ],
                "query_required": child_text(extended, "queryIsObligatory") == "true",
                "query_variants": [
                    {
                        "query": attr(n, "queryString"),
                        "title": attr(n, "title"),
                        "default": attr(n, "isDefault") == "true",
                    }
                    for n in extended.iter() if localname(n.tag) == "queryVariant"
                ],
            }
        entries.append(item)
    return {
        "title": child_text(root, "title"),
        "entries": entries,
        "next_uri": next(
            (link["href"] for link in links(root) if link["rel"] == "next"), None
        ),
    }
