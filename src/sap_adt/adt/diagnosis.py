"""Bounded diagnostic evidence collection, without root-cause inference."""
from __future__ import annotations

import json

from .. import artifacts, policy
from . import handlers


def collect(config, *, dump_id=None, message=None, feed_uri=None, query="",
            max_entries=20, max_dumps=3, max_chars=20000):
    if bool(dump_id) == bool(message):
        raise ValueError("Choose exactly one --dump-id or --message")
    if not 1 <= max_entries <= 100 or not 1 <= max_dumps <= 10:
        raise ValueError("Diagnostic budgets exceed their supported range")
    if dump_id and (feed_uri or query):
        raise ValueError("Feed options apply only to message correlation")
    data = {"target": policy.target(config), "request": {
        "dump_id": dump_id, "message": message, "feed_uri": feed_uri, "query": query},
        "candidates": [], "dumps": [], "sources": [], "evidence_gaps": [],
        "interpretation": "evidence and candidate correlations only; not a root-cause conclusion"}
    assets = {}
    gaps = data["evidence_gaps"]

    def failed(stage, result):
        gaps.append({"code": result.error_code or "EVIDENCE_UNAVAILABLE",
                     "stage": stage, "message": result.text})

    identifiers = [dump_id] if dump_id else []
    if message:
        catalog = handlers.list_feeds()
        if catalog.is_error:
            failed("feed_catalog", catalog)
        else:
            entries = catalog.data["entries"]
            if feed_uri:
                chosen = [e for e in entries if e.get("content_uri") and
                          handlers._adt_uri(e["content_uri"]) == handlers._adt_uri(feed_uri)]
            else:
                chosen = [e for e in entries if "/runtime/dumps" in (e.get("content_uri") or "")]
            if len(chosen) != 1:
                gaps.append({"code": "FEED_SELECTION_REQUIRED",
                             "message": "Select one advertised --feed-uri; no feed was guessed."})
            else:
                selected = chosen[0]
                effective_query = query
                if not query and selected.get("schema", {}).get("query_required"):
                    effective_query = next((v["query"] for v in selected["schema"].get(
                        "query_variants", []) if v.get("default")), "")
                result = handlers.query_feed(selected["content_uri"], effective_query, max_entries)
                if result.is_error:
                    failed("feed_page", result)
                else:
                    assets["feed-page.json"] = {"data": result.data, "meta": result.meta}
                    if (result.meta or {}).get("has_more"):
                        gaps.append({"code": "FEED_SCOPE_LIMITED",
                                     "message": "Only the requested bounded page was inspected."})
                    for entry in result.data["entries"]:
                        if message.casefold() not in json.dumps(entry, ensure_ascii=False).casefold():
                            continue
                        data["candidates"].append({"entry": entry, "correlation": "literal-text-match"})
                        uri = entry.get("content_uri")
                        if uri:
                            try:
                                identifiers.append(handlers._dump_uri(uri))
                            except ValueError:
                                pass
                    if not data["candidates"]:
                        gaps.append({"code": "NO_CANDIDATE_IN_SCOPE",
                                     "message": "No literal match in this page; absence is not system-wide."})
    identifiers = list(dict.fromkeys(identifiers))
    if len(identifiers) > max_dumps:
        gaps.append({"code": "DUMP_LIMIT_REACHED", "omitted": len(identifiers) - max_dumps})
    for index, identifier in enumerate(identifiers[:max_dumps]):
        result = handlers.get_dump(identifier, max_chars)
        if result.is_error:
            failed("dump", result)
            continue
        data["dumps"].append(result.data)
        assets[f"dumps/{index}.json"] = result.data
        if result.raw:
            assets[f"dumps/{index}.xml"] = result.raw.encode("utf-8")
        gaps.extend({**gap, "dump": identifier} for gap in result.data["evidence_gaps"])
        termination = result.data.get("termination", {})
        uri, line = termination.get("uri"), termination.get("line")
        if uri:
            source = handlers.get_source(uri, max(1, (line or 1) - 15), (line or 1) + 15)
            if source.is_error:
                failed("termination_source", source)
            else:
                data["sources"].append(source.data)
                assets[f"sources/{index}.json"] = source.data
        else:
            gaps.append({"code": "TERMINATION_SOURCE_UNAVAILABLE", "dump": identifier})
    if message and data["candidates"] and not identifiers:
        gaps.append({"code": "NO_ATTRIBUTABLE_DUMP",
                     "message": "Feed candidates do not provide a readable dump URI."})
    assets["diagnosis.json"] = data
    return data, assets


def bundle(path, data, assets):
    return artifacts.write_package(path, "diagnosis", assets,
                                   context={"target": data["target"]}, gaps=data["evidence_gaps"])
