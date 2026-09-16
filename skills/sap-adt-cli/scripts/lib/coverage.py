"""Command coverage against the connected system's discovery document.

Pure functions: given the parsed discovery ``collections`` and the
``COMMAND_CAPABILITIES`` map (command -> discovery hrefs it depends on),
split everything into three buckets. Local commands that do not talk to ADT
(configure/profile/credentials/status) are intentionally absent from the map
and counted separately by the CLI.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

# Commands that mutate/read SAP via ADT and the discovery hrefs they need.
# A command is "covered & available" when ANY listed href exists; a command
# spans object types (write/activate) when one of its object resources does.
_OO = ["/sap/bc/adt/oo/classes", "/sap/bc/adt/oo/interfaces"]
_PROG = ["/sap/bc/adt/programs/programs", "/sap/bc/adt/programs/includes"]
_FUGR = ["/sap/bc/adt/functions/groups"]
_DDL = ["/sap/bc/adt/ddic/ddl/sources"]

COMMAND_CAPABILITIES: "OrderedDict[str, list[str]]" = OrderedDict([
    ("get-program", _PROG),
    ("get-class", _OO),
    ("get-function-group", _FUGR),
    ("get-function", _FUGR),
    ("get-include", ["/sap/bc/adt/programs/includes"]),
    ("get-interface", ["/sap/bc/adt/oo/interfaces"]),
    ("get-cds-view", _DDL),
    ("get-type-group", ["/sap/bc/adt/ddic/typegroups"]),
    ("get-table", ["/sap/bc/adt/ddic/tables"]),
    ("get-structure", ["/sap/bc/adt/ddic/structures"]),
    ("get-type-info",
     ["/sap/bc/adt/ddic/domains", "/sap/bc/adt/ddic/dataelements"]),
    ("get-transaction",
     ["/sap/bc/adt/repository/informationsystem/objectproperties/values"]),
    ("search-object",
     ["/sap/bc/adt/repository/informationsystem/search"]),
    ("get-package", ["/sap/bc/adt/repository/nodestructure"]),
    ("where-used",
     ["/sap/bc/adt/repository/informationsystem/usageReferences"]),
    ("syntax-check", ["/sap/bc/adt/checkruns"]),
    ("run-sql", ["/sap/bc/adt/datapreview/freestyle"]),
    ("list-transports", ["/sap/bc/adt/cts/transportrequests"]),
    ("create-transport", ["/sap/bc/adt/cts/transports"]),
    ("release-transport", ["/sap/bc/adt/cts/transports"]),
    ("write-source", _OO + _PROG + _FUGR),
    ("activate", _OO + _PROG + _FUGR + _DDL +
     ["/sap/bc/adt/activation", "/sap/bc/adt/activation/runs"]),
])

# Commands not in the map by design (no ADT resource dependency).
LOCAL_COMMANDS = [
    "status", "configure", "profile list", "profile use", "profile remove",
    "credentials set", "credentials forget", "credentials status",
    "credentials doctor", "discovery",
]


def _available_hrefs(collections: Iterable[dict]) -> set[str]:
    return {c["href"] for c in collections if c.get("href")}


def _command_available(prefixes: list[str], hrefs: set[str]) -> bool:
    return any(p in hrefs for p in prefixes)


def _group_key(href: str) -> str:
    # Absolute entries are service roots (contain the host) — bucket them
    # without surfacing the hostname in examples.
    if href.startswith("http://") or href.startswith("https://"):
        return "(service root)"
    # /sap/bc/adt/ddic/tables -> /ddic ; /sap/bc/adt/oo/classes -> /oo
    marker = "/sap/bc/adt/"
    if marker in href:
        rest = href.split(marker, 1)[1].strip("/")
        return "/" + (rest.split("/", 1)[0] if rest else "adt")
    return href.split("/", 2)[-1].split("/", 1)[0] or "/"


def compute_coverage(collections: list[dict]) -> dict:
    hrefs = _available_hrefs(collections)
    by_href = {c["href"]: c for c in collections}

    available_commands = []
    unavailable_commands = []
    for command, prefixes in COMMAND_CAPABILITIES.items():
        (available_commands if _command_available(prefixes, hrefs)
         else unavailable_commands).append(command)

    referenced = {p for prefixes in COMMAND_CAPABILITIES.values() for p in prefixes}
    uncovered = [c for c in collections if c.get("href") not in referenced]

    groups: "OrderedDict[str, dict]" = OrderedDict()
    for c in sorted(uncovered, key=lambda x: x["href"] or ""):
        key = _group_key(c["href"])
        g = groups.setdefault(key, {"count": 0, "examples": []})
        g["count"] += 1
        if len(g["examples"]) < 4:
            # Never surface absolute (host-bearing) URLs in examples.
            g["examples"].append(
                "<system base URL>" if key == "(service root)" else c["href"]
            )

    return {
        "implemented_available": available_commands,
        "available_not_covered": {
            "total": len(uncovered),
            "groups": [{"prefix": k, **v} for k, v in groups.items()],
            "collections": [
                {"href": c["href"], "title": c.get("title"),
                 "content_types": c.get("content_types", [])}
                for c in uncovered
            ],
        },
        "covered_not_available": unavailable_commands,
        "local_commands": len(LOCAL_COMMANDS),
    }


def render_discovery_markdown(collections: list[dict]) -> str:
    """Render discovery collections to a generated endpoint table.

    Generated output only — the curated adt_api.md keeps human annotations
    (verified protocol facts, SICF, authorizations) that discovery lacks.
    """
    lines = [
        "<!-- GENERATED by `sap-adt-cli discovery --emit-markdown PATH`.",
        "     Do not merge over adt_api.md; its protocol notes are curated. -->",
        "",
        "# ADT discovery — exposed resources",
        "",
        "| Href | Title | Accept content types |",
        "|------|-------|----------------------|",
    ]
    for c in collections:
        types = ", ".join(c.get("content_types") or []) or "—"
        title = (c.get("title") or "").replace("|", "\\|")
        lines.append(f"| `{c.get('href')}` | {title} | {types} |")
    lines.append("")
    return "\n".join(lines)


def render_text(report: dict) -> str:
    """Text mode: per-segment counts; uncovered shown as path groups only."""
    lines = []
    avail = report["implemented_available"]
    lines.append(f"implemented & available : {len(avail)}")
    lines.append("  " + ", ".join(avail))
    unc = report["available_not_covered"]
    lines.append(f"available but NOT covered : {unc['total']}")
    for g in unc["groups"]:
        lines.append(f"  {g['prefix']}/*  {g['count']}")
        for ex in g["examples"]:
            lines.append(f"      {ex}")
    missing = report["covered_not_available"]
    lines.append(f"covered but NOT available : {len(missing)}")
    for cmd in missing:
        lines.append(f"  {cmd}")
    lines.append(f"local commands (no ADT resource) : {report['local_commands']}")
    return "\n".join(lines)
