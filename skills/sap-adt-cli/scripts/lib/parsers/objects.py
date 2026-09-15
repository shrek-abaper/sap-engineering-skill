"""kind=objects: search / package contents / where-used.

All three commands share one normalized shape:
``{objects: [{name, type, uri, package, description}]}``.

Accepted payloads:

* ``adtcore:objectReferences`` XML — quick-search results, where-used results
  and the empty-result feed (``<objectReferences/>`` → empty list);
* abapxml nodestructure content — ``get-package`` tree, whose elements carry
  no namespace on modern systems even though the root declares ``asx``.
"""
from __future__ import annotations

from .common import ParseError, attr, localname, parse_xml

OBJ_NODE = "SEU_ADT_REPOSITORY_OBJ_NODE"


def _norm_type(raw_type: str | None) -> str | None:
    """Normalize ADT VIT types (``CLAS/OC`` -> ``CLAS``); passthrough if plain."""
    if raw_type is None:
        return None
    return raw_type.split("/", 1)[0] if "/" in raw_type else raw_type


def _parse_references(root) -> list[dict]:
    objects = []
    for el in root.iter():
        if localname(el.tag) != "objectReference":
            continue
        objects.append({
            "name": attr(el, "name"),
            "type": _norm_type(attr(el, "type")),
            "uri": attr(el, "uri"),
            "package": attr(el, "packageName"),
            "description": attr(el, "description"),
        })
    return objects


def _child(el, name):
    for node in el:
        if localname(node.tag) == name:
            return node
    return None


def _parse_package_tree(root) -> list[dict]:
    objects = []
    for el in root.iter():
        if localname(el.tag) != OBJ_NODE:
            continue
        name_el = _child(el, "OBJECT_NAME")
        uri_el = _child(el, "OBJECT_URI")
        name = (name_el.text or "").strip() if name_el is not None else ""
        if not name:
            # Pseudo nodes (package header, structure nodes) have empty names.
            continue
        type_el = _child(el, "OBJECT_TYPE")
        desc_el = _child(el, "DESCRIPTION")
        objects.append({
            "name": name,
            "type": (type_el.text or "").strip() if type_el is not None else None,
            "uri": (uri_el.text or "").strip() if uri_el is not None else None,
            # The nodestructure response does not repeat the parent package.
            "package": None,
            "description": ((desc_el.text or "").strip() or None)
            if desc_el is not None else None,
        })
    return objects


def parse(payload: bytes) -> dict:
    root = parse_xml(payload)
    root_name = localname(root.tag)
    if root_name == "objectReferences":
        objects = _parse_references(root)
    elif any(localname(el.tag) == OBJ_NODE for el in root.iter()):
        objects = _parse_package_tree(root)
    else:
        raise ParseError(f"unrecognized objects payload (root <{root_name}>)")
    return {"objects": objects}
