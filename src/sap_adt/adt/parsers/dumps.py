"""Dump metadata and chapter-based evidence, without language-specific labels."""
from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

from .common import ParseError, attr, localname, opt_int, parse_xml

_ROLES = {
    "kap0": "short_text", "kap1": "what_happened", "kap3": "error_analysis",
    "kap7": "termination", "kap8": "source", "kap9": "system_fields",
    "kap11": "stack", "kap10": "variables",
}


def parse(payload: bytes) -> dict:
    root = parse_xml(payload)
    if localname(root.tag) != "dump":
        raise ParseError("Expected an ADT runtime dump document")
    header = {
        key: attr(root, attribute)
        for key, attribute in {
            "error": "error", "exception": "exception", "program": "terminatedProgram",
            "user": "author", "datetime": "datetime", "system_date": "systemDate",
            "system_time": "systemTime", "title": "title",
        }.items()
    }
    links = []
    termination = {"uri": None, "line": None}
    for node in root.iter():
        if localname(node.tag) != "link":
            continue
        relation = attr(node, "relation") or attr(node, "rel") or ""
        uri = attr(node, "uri") or attr(node, "href")
        links.append({
            "rel": relation, "uri": uri,
            "content_type": attr(node, "contentType") or attr(node, "type"),
        })
        if relation.endswith("/runtime/dump/termination") and uri:
            target = urlsplit(uri)
            # adt://SID is SAP's navigation notation, not a network destination.
            if target.scheme in ("", "adt") and not target.query:
                termination["uri"] = urlunsplit(("", "", target.path, "", target.fragment))
                match = re.search(r"(?:^|&)start=(\d+)", target.fragment)
                termination["line"] = int(match[1]) if match else None
    chapters = []
    for node in root.iter():
        if localname(node.tag) == "chapter":
            identifier = attr(node, "name")
            chapters.append({
                "id": identifier, "title": attr(node, "title"),
                "start_line": opt_int(attr(node, "line")),
                "role": _ROLES.get(identifier),
            })
    return {
        "header": header, "termination": termination,
        "chapters": chapters, "links": links,
    }


def evidence(metadata: dict, formatted: str, max_chars: int) -> dict:
    """Keep relevant chapters within a shared budget; unknown layouts stay raw."""
    lines = formatted.splitlines()
    chapters = sorted(
        (c for c in metadata["chapters"] if c["start_line"] is not None
         and 1 <= c["start_line"] <= len(lines)),
        key=lambda c: c["start_line"],
    )
    sections = []
    remaining = max_chars
    truncated = False
    for i, chapter in enumerate(chapters):
        if not chapter["role"]:
            continue
        start = chapter["start_line"] - 1
        end = chapters[i + 1]["start_line"] - 1 if i + 1 < len(chapters) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        text = body[:remaining]
        remaining -= len(text)
        clipped = len(text) < len(body)
        truncated |= clipped
        sections.append({**chapter, "text": text, "truncated": clipped})
    raw_text = None
    if not sections:
        raw_text = formatted[:max_chars]
        truncated = len(formatted) > max_chars
    source = []
    stack = []
    for section in sections:
        for row in section["text"].splitlines():
            inner = row.strip().strip("|")
            if section["role"] == "source":
                match = re.match(r"\s*(\d+|>>>>>|====>)\s*\|(.*)", inner)
                if match:
                    number = int(match[1]) if match[1].isdigit() else metadata["termination"]["line"]
                    source.append({
                        "line": number, "text": match[2].rstrip(),
                        "is_termination": number is not None and number == metadata["termination"]["line"],
                    })
            elif section["role"] == "stack":
                match = re.match(r"\s*(\d+)\s+(.*\S)", inner)
                if match:
                    stack.append({"level": int(match[1]), "text": match[2].rstrip()})
    return {
        "sections": sections, "text": raw_text, "source": source, "stack": stack,
        "truncated": truncated, "chapter_layout_known": bool(sections),
        "unmapped_chapters": [
            c["id"] for c in metadata["chapters"] if c["role"] and c not in chapters
        ],
    }
