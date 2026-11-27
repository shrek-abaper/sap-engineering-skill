"""Bounded transport impact evidence and transparent technical risk indicators."""
from __future__ import annotations

from .. import policy
from ..adt import client, comparison, handlers, object_evidence

TYPES = {
    "CLAS": "class", "INTF": "interface", "PROG": "program", "REPS": "include",
    "FUGR": "function-group", "TABL": "table", "DOMA": "domain", "DTEL": "data-element",
    "DDLS": "cds", "BDEF": "bdef", "SRVD": "srvd", "SRVB": "srvb",
    "MSAG": "message-class", "ENQU": "lock-object",
}


def objects(trkorr, limit):
    if not 1 <= limit <= 100:
        raise ValueError("Transport object limit must be between 1 and 100")
    queue, seen, found, gaps = [trkorr], set(), {}, []
    requests = []
    while queue and len(seen) < 50:
        number = queue.pop(0)
        if number in seen:
            continue
        seen.add(number)
        result = handlers.get_transport(number)
        if result.is_error:
            gaps.append({"code": result.error_code, "transport": number, "message": result.text})
            continue
        detail = result.data
        requests.append(detail["transport"])
        queue.extend(t["trkorr"] for t in detail["transport"].get("tasks", []) if t.get("trkorr"))
        for item in detail["objects"]:
            key = (item["pgmid"], item["type"], item["name"])
            if key not in found:
                if len(found) >= limit:
                    gaps.append({"code": "TRANSPORT_OBJECT_LIMIT_REACHED", "limit": limit})
                    queue.clear()
                    break
                found[key] = item
    if queue:
        gaps.append({"code": "TRANSPORT_TASK_LIMIT_REACHED"})
    return list(found.values()), requests, gaps


def analyze(config, trkorr, *, max_objects=20, depth=1, max_nodes=30):
    items, requests, gaps = objects(trkorr, max_objects)
    impacts, indicators = [], []
    for item in items:
        typ = item["type"]
        if typ in ("TABL", "DOMA", "DTEL", "ENQU"):
            indicators.append({"rule": "DDIC_CHANGE", "object": item, "weight": 20})
        if typ in ("AUTH", "SUSO", "SUSC"):
            indicators.append({"rule": "AUTHORIZATION_CHANGE", "object": item, "weight": 30})
        if typ in ("TABU", "VDAT"):
            indicators.append({"rule": "CUSTOMIZING_CHANGE", "object": item, "weight": 15})
            gaps.append({"code": "CUSTOMIZING_KEYS_NOT_COLLECTED", "object": item,
                         "message": "E071K/row contents are outside this source analysis."})
        kind = TYPES.get(typ)
        if not kind or item["pgmid"] != "R3TR":
            gaps.append({"code": "DEPENDENCY_OBJECT_UNSUPPORTED", "object": item})
            continue
        try:
            graph = object_evidence.references(kind, item["name"], depth=depth,
                                               max_nodes=max_nodes, per_node=20)
            impacts.append({"object": item, "graph": graph})
            gaps.extend({**g, "object": item} for g in graph["evidence_gaps"])
        except Exception as exc:
            gaps.append({"code": "DEPENDENCY_QUERY_UNAVAILABLE", "object": item, "message": str(exc)})
    score = min(100, min(40, len(items) * 2) + sum(i["weight"] for i in indicators))
    return {
        "target": policy.target(config), "transport": trkorr, "requests": requests,
        "objects": items, "impacts": impacts, "evidence_gaps": gaps,
        "dependency_scope": "bounded static reverse references; prerequisites/dynamic calls not proven complete",
        "risk": {"policy": "observed-technical-risk-v1", "score": score,
                 "score_kind": "observed-indicators-only", "indicators": indicators,
                 "object_count_contribution": min(40, len(items) * 2),
                 "evidence_complete_within_scope": not gaps, "release_approval": False},
    }


def compare_transport(trkorr, left, right, max_objects=20):
    configs = comparison.profiles(left, right)
    with client.connection_scope(configs[0]):
        items, requests, gaps = objects(trkorr, max_objects)
    comparisons = []
    for item in items:
        kind = TYPES.get(item["type"])
        if not kind or item["pgmid"] != "R3TR":
            gaps.append({"code": "COMPARISON_OBJECT_UNSUPPORTED", "object": item})
            continue
        result = comparison.compare(configs, kind, item["name"])
        comparisons.append({"object": item, **result})
        gaps.extend({**gap, "object": item} for gap in result["evidence_gaps"])
    return {"transport": trkorr, "requests": requests,
            "targets": [policy.target(c) for c in configs],
            "comparisons": comparisons, "evidence_gaps": gaps,
            "scope": "selected request object identities; current active versions, not an import prediction"}
