"""kind=objects: search / package contents / where-used.

All three commands share one normalized shape:
``{objects: [{name, type, uri, package, description}]}``.

Accepted payloads:

* ``adtcore:objectReferences`` XML — quick-search results and the empty-result
  feed (``<objectReferences/>`` → empty list);
* ``usageReferences:usageReferenceResult`` XML — where-used results. These
  objects may additionally carry ``usage_line``/``usage_uri`` when the
  response points at a specific source position (search/package never emit
  these keys);
* abapxml nodestructure content — ``get-package`` tree, whose elements carry
  no namespace on modern systems even though the root declares ``asx``.
"""
from __future__ import annotations

import re

from .common import ParseError, attr, localname, parse_xml

OBJ_NODE = "SEU_ADT_REPOSITORY_OBJ_NODE"
_START_RE = re.compile(r"[#&]start=(\d+)(?:,\d+)?")


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


def _clean_name(value):
    """ADT encodes compound names with a leading slash ('/ASU/SSM')."""
    return value.lstrip("/") if isinstance(value, str) else value


def _parse_usage_result(root) -> list[dict]:
    objects = []
    for el in root.iter():
        if localname(el.tag) != "referencedObject":
            continue
        adt = None
        package_ref = None
        for child in el:
            if localname(child.tag) == "adtObject":
                adt = child
                package_ref = next(
                    (c for c in child if localname(c.tag) == "packageRef"), None
                )
        if adt is None:
            continue
        uri = attr(el, "uri")
        obj = {
            "name": _clean_name(attr(adt, "name")),
            "type": _norm_type(attr(adt, "type")),
            "uri": uri,
            "package": _clean_name(attr(package_ref, "name")) if package_ref is not None else None,
            "description": attr(adt, "description"),
        }
        if uri and "#" in uri:
            m = _START_RE.search(uri)
            obj["usage_uri"] = uri
            obj["usage_line"] = int(m.group(1)) if m else None
        objects.append(obj)
    return objects


def parse(payload: bytes) -> dict:
    root = parse_xml(payload)
    root_name = localname(root.tag)
    if root_name == "objectReferences":
        objects = _parse_references(root)
    elif root_name == "usageReferenceResult":
        objects = _parse_usage_result(root)
    elif any(localname(el.tag) == OBJ_NODE for el in root.iter()):
        objects = _parse_package_tree(root)
    else:
        raise ParseError(f"unrecognized objects payload (root <{root_name}>)")
    return {"objects": objects}
