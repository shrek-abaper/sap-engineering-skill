"""kind=scalar: single-object dictionaries (type info, transaction).

``get-type-info`` payloads:

* ``blue:wbobj`` with ``adtcore:type="DTEL/DE"`` — data element metadata;
* ``doma:domain`` with ``adtcore:type="DOMA/DD"`` — domain metadata.

The resolved branch is reported explicitly as ``resolved_as`` so callers no
longer have to infer the handler's internal domain→data-element fallback.

``get-transaction`` payloads are ``opr:objectProperties`` facet documents.
"""
from __future__ import annotations

from .common import ParseError, attr, child_text, localname, opt_int, parse_xml


def _package_ref(root):
    for el in root.iter():
        if localname(el.tag) == "packageRef":
            return attr(el, "name")
    return None


def _type_info(root) -> dict:
    adt_type = attr(root, "type") or ""
    data = {
        "name": attr(root, "name"),
        "adt_type": adt_type,
        "description": attr(root, "description"),
        "package": _package_ref(root),
        "responsible": attr(root, "responsible"),
    }
    if adt_type == "DOMA/DD":
        data.update({
            "resolved_as": "domain",
            "data_type": child_text(root, "datatype"),
            "length": opt_int(child_text(root, "length")),
            "decimals": opt_int(child_text(root, "decimals")),
            "referenced_type": None,
        })
    else:
        data.update({
            "resolved_as": "dataelement",
            "data_type": child_text(root, "dataType"),
            "length": opt_int(child_text(root, "dataTypeLength")),
            "decimals": opt_int(child_text(root, "dataTypeDecimals")),
            "referenced_type": child_text(root, "typeName"),
            "type_kind": child_text(root, "typeKind"),
        })
    return data


def _transaction(root) -> dict:
    obj = None
    for el in root.iter():
        if localname(el.tag) == "object":
            obj = el
            break
    facets = []
    for el in root.iter():
        if localname(el.tag) != "property":
            continue
        facets.append({
            "facet": attr(el, "facet"),
            "name": attr(el, "name"),
            "text": attr(el, "text") or None,
        })
    data = {
        "name": attr(root, "name") or (attr(obj, "name") if obj is not None else None),
        "description": attr(obj, "text") if obj is not None else None,
        "package": attr(obj, "package") if obj is not None else None,
        "type": attr(obj, "type") if obj is not None else None,
        "facets": facets,
    }
    application = [f["name"] for f in facets if f["facet"] == "APPL"]
    if application:
        data["application"] = application
    return data


def parse(payload: bytes) -> dict:
    root = parse_xml(payload)
    tag = localname(root.tag)
    if tag == "wbobj" or tag == "domain":
        return _type_info(root)
    if tag == "objectProperties":
        return _transaction(root)
    raise ParseError(f"unrecognized scalar payload (root <{tag}>)")
