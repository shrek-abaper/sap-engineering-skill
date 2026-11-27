"""Bounded read-only metadata and static reference graphs."""
from __future__ import annotations

import re
from urllib.parse import quote

from . import handlers
from .parsers.common import ParseError, attr, localname, parse_xml

RESOURCES = {
    "message-class": ("messageclass", "application/*"),
    "lock-object": ("ddic/lockobjects/sources", "application/vnd.sap.adt.lockobjects.v1+xml"),
    "enhancement-spot": ("enhancements/enhsxs", "application/vnd.sap.adt.enh.enhs.v1+xml"),
    "badi": ("enhancements/enhsxsb", "application/vnd.sap.adt.enh.enhs.v2+xml"),
    "badi-implementation": ("enhancements/enhoxhb", "application/vnd.sap.adt.enh.enhoxhb.v3+xml"),
    "enhancement-implementation": ("enhancements/enhoxh", "application/vnd.sap.adt.enh.enho.v1+xml"),
    "source-enhancement": ("enhancements/enhoxhh", "application/vnd.sap.adt.enh.enhoxhh.v3+xml"),
}
NAME = re.compile(r"(?:/[A-Za-z0-9_]+/)?[A-Za-z0-9_$]+\Z", re.ASCII)


def object_uri(kind, name):
    if not NAME.fullmatch(name) or len(name) > 80:
        raise ValueError("Invalid repository object name")
    return "/sap/bc/adt/" + RESOURCES[kind][0] + "/" + quote(name.lower(), safe="")


def read(kind, name, max_nodes=5000):
    try:
        if kind == "enhancement-point":
            result = handlers.get_program(name)
            if result.is_error:
                return result
            source = result.data["source"]
            points = [{
                "kind": m[1].upper(), "name": m[2].upper(),
                "line": source[:m.start()].count("\n") + 1,
                "statement": m[0],
            } for m in re.finditer(
                r"(?im)^[ \t]*ENHANCEMENT-(POINT|SECTION)\s+([/\w]+)[^\n.]*\.",
                source)]
            data = {"owner_program": name.upper(), "points": points,
                    "scope": "lexical declarations in the explicitly named program; no include expansion",
                    "evidence_gaps": []}
            return handlers.AdtResult(kind="scalar", data=data)
        uri = object_uri(kind, name)
        response = handlers._read_adt(
            uri, extra_headers={"Accept": RESOURCES[kind][1]}, allow_redirects=False)
        if len(response.content) > 4 * 1024 * 1024:
            raise ParseError("Metadata exceeds 4 MiB")
        root = parse_xml(response.content)
        if (attr(root, "name") or "").upper() != name.upper():
            raise ParseError("Metadata does not confirm the requested object identity")
        remaining = max_nodes
        truncated = False

        def tree(node, depth=0):
            nonlocal remaining, truncated
            if remaining <= 0 or depth > 30:
                truncated = True
                return None
            remaining -= 1
            children = []
            for child in node:
                value = tree(child, depth + 1)
                if value is not None:
                    children.append(value)
                if remaining <= 0:
                    if child is not node[-1]:
                        truncated = True
                    break
            return {"tag": localname(node.tag),
                    "attributes": {localname(k): v for k, v in node.attrib.items()},
                    "text": node.text.strip() if node.text and node.text.strip() else None,
                    "children": children}

        representation = tree(root)
        gaps = ([{"code": "METADATA_TRUNCATED", "limit": max_nodes}] if truncated else [])
        data = {"uri": uri, "metadata": representation, "evidence_gaps": gaps,
                "scope": "BAdI definitions declared by the named enhancement spot"
                if kind == "badi" else "explicit object metadata"}
        return handlers.AdtResult(kind="scalar", data=data, raw=response.text,
                                  object=handlers._obj(kind, name), meta={"partial": bool(gaps)})
    except Exception as exc:
        return handlers._err(exc)


def references(kind, name, *, group=None, depth=2, max_nodes=100, per_node=50):
    if not 1 <= depth <= 5 or not 1 <= max_nodes <= 500 or not 1 <= per_node <= 500:
        raise ValueError("Reference budgets: depth 1..5, nodes/per-node 1..500")
    uri = (object_uri(kind, name) if kind in RESOURCES else
           handlers.get_object_uri(kind, name, group)).lower()
    root = {"uri": uri, "type": kind, "name": name.upper(), "depth": 0}
    nodes, edges, gaps = {uri.lower(): root}, [], []
    frontier = [root]
    while frontier:
        node = frontier.pop(0)
        if node["depth"] >= depth:
            continue
        result = handlers.where_used(kind, name, per_node, group, object_uri=node["uri"])
        if result.is_error:
            gaps.append({"code": result.error_code, "uri": node["uri"], "message": result.text})
            continue
        if (result.meta or {}).get("limit_reached"):
            gaps.append({"code": "REFERENCE_LIMIT_REACHED", "uri": node["uri"]})
        for item in result.data["objects"]:
            value = item.get("uri")
            if not value:
                gaps.append({"code": "REFERENCE_URI_MISSING", "object": item})
                continue
            try:
                target = handlers._adt_uri(value).split("#", 1)[0]
            except ValueError:
                gaps.append({"code": "REFERENCE_URI_UNSUPPORTED", "uri": value})
                continue
            key = target.lower()
            if key not in nodes:
                if len(nodes) >= max_nodes:
                    gaps.append({"code": "GRAPH_NODE_LIMIT_REACHED", "limit": max_nodes})
                    frontier.clear()
                    break
                nodes[key] = {**item, "uri": target, "depth": node["depth"] + 1}
                frontier.append(nodes[key])
            edge = {"from": node["uri"], "to": nodes[key]["uri"], "relation": "referenced_by"}
            if edge not in edges:
                edges.append(edge)
    return {"root": root, "nodes": list(nodes.values()), "edges": edges,
            "scope": {"kind": "static-where-used", "max_depth": depth,
                      "max_nodes": max_nodes, "per_node": per_node},
            "dynamic_dependencies_complete": False, "evidence_gaps": gaps}
