#!/usr/bin/env python3
"""Sanitize real-machine ADT responses in ``raw/`` into commit-safe fixtures.

Raw captures live in ``tests/fixtures/raw/`` (git-ignored, never committed).
Running this script copies a curated allow-list of them into
``tests/fixtures/`` with sensitive identifiers replaced by placeholders:

* internal host/URL  -> https://sap-dev.example.com:8000
* username           -> DEVELOPER
* transport numbers  -> DEVK9XXXXX
* run-sql business data -> fully synthetic rows (same shape/row count)

The real values are NOT hardcoded here. They are read from a local,
git-ignored mapping file ``raw/sanitize.map.json`` (see
``sanitize.map.example.json``), so this script can be committed safely.

Stdlib-only; no project imports. Re-run after every new raw capture::

    python3 sanitize.py            # write sanitized fixtures
    python3 sanitize.py --check    # fail if fixtures are stale/leaking
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
MAP_FILE = RAW / "sanitize.map.json"

TR_RE = re.compile(r"\b[A-Z][A-Z0-9]{2}K[0-9]{7}\b")

# Explicit allow-list: raw file -> committed fixture name.
# Anything not listed stays in raw/ and is never copied.
# The synthetic/ directory (hand-built *.synthetic.xml fixtures) is NEVER
# mapped: it is inferred structure, not a real capture, and must stay out
# of both sanitization and the golden/byte-level regression set.
FILE_MAP = {
    # source / DDL
    "get-table.VBAK.xml": "get-table.VBAK.s4hana.xml",
    "get-table.T001.xml": "get-table.T001.s4hana.xml",
    "get-table.REPOSRC.xml": "get-table.REPOSRC.s4hana.xml",
    "get-structure.VBAKKOM.xml": "get-structure.VBAKKOM.s4hana.xml",
    "get-class.source.abap": "get-class.CL_GUI_FRONTEND_SERVICES.abap",
    # type info (current-CLI dataelement outputs + true domain v2 payload)
    "get-type-info.dataelement.xml": "get-type-info.MATNR.dtel.xml",
    "get-type-info.domain.xml": "get-type-info.MATNR18.dtel.xml",
    "get-type-info.domain.CHAR10.raw.xml": "get-type-info.CHAR10.domain.xml",
    # scalar
    "get-transaction.VA01.xml": "get-transaction.VA01.xml",
    # objects
    "search-object.wildcard.xml": "search-object.CL_GUI_WILDCARD.xml",
    "search-object.empty.xml": "search-object.empty.xml",
    "get-package.json": "get-package.SABP_UNIT.cli-current.json",
    "get-package.SABP_UNIT.raw.xml": "get-package.SABP_UNIT.asxml.xml",
    # records
    "list-transports.empty.raw.xml": "list-transports.empty.xml",
    "list-transports.searchconfig.raw.xml": "list-transports.searchconfig.xml",
    "list-transports.xml.stderr": "error.406-list-transports.txt",
    # findings (new checkrun API + legacy-404 evidence)
    "syntax-check.class.raw.xml": "syntax-check.CL_GUI.clean.xml",
    "syntax-check.warnings.raw.xml": "syntax-check.SAPMV45A.warnings.xml",
    "syntax-check.clean.xml.stderr": "error.404-syntaxcheck.txt",
    # ABAP Unit real captures: empty shell + alert-only (no testMethod)
    "unit.empty.raw.xml": "unit.empty.xml",
    "unit.zcl_ci_test_ddic_naming.raw.xml": "unit.alert-only.xml",
    # where-used new usageReferences API (hits are trimmed SAP-only nodes)
    "where-used.hits.raw.xml": "where-used.CL_GUI_FRONTEND_SERVICES.xml",
    "where-used.empty.raw.xml": "where-used.empty.xml",
    "where-used.hits.xml.stderr": "error.405-whereused-legacy.txt",
    "where-used.usageReferences.GET.raw.xml": "error.405-usageReferences.raw.xml",
    # rows — JSON with real business data, rebuilt synthetically
    "run-sql.t001.xml": "run-sql.t001.json",
    # rows — raw dataPreview XML from SAP-standard table T100 (no customer data)
    "datapreview.t100.xml": "run-sql.t100.raw.xml",
    "datapreview.t001.post.xml": "run-sql.t001.post.raw.xml",
    # error branches
    "error.404.txt.stderr": "error.404.txt",
    "error.404.raw.xml": "error.404.xml",
    "error.dml-rejected.txt.stderr": "error.dml-rejected.txt",
    "error.403-csrf.raw.xml": "error.403-csrf.txt",
    # CLI baseline exit codes
    "_exit_codes.txt": "baseline-exit-codes.tsv",
}

# Brand-name checks (ASCII only) beyond the values in the local map.
# Non-ASCII business names (e.g. CJK company names) go into the local map's
# "extra_leaks" list, so this committed file never contains those literals.
EXTRA_LEAK_PATTERNS = [
    re.compile(r"(?i)\bnio\b"),
    re.compile(r"(?i)nextev"),
]


def load_map() -> dict:
    if not MAP_FILE.exists():
        sys.exit(
            f"Missing local map {MAP_FILE}. Copy sanitize.map.example.json "
            f"to {MAP_FILE} and fill in the real values (the file stays git-ignored)."
        )
    return json.loads(MAP_FILE.read_text(encoding="utf-8"))


def build_replacements(m: dict) -> list[tuple[str, str]]:
    # Longest first so full URLs are replaced before bare host/IP.
    return [
        (m["host_url"], m.get("placeholder_url", "https://sap-dev.example.com:8000")),
        (m["host_with_port"], m.get("placeholder_host", "sap-dev.example.com:8000")),
        (m["host"], m.get("placeholder_host_ip", "sap-dev.example.com")),
        (m["username"], m.get("placeholder_user", "DEVELOPER")),
        (m.get("profile", ""), m.get("placeholder_profile", "dev")),
    ]


def scrub_text(text: str, repls: list[tuple[str, str]]) -> str:
    for old, new in repls:
        if old:
            text = text.replace(old, new)
    return TR_RE.sub("DEVK9XXXXX", text)


def sanitize_rows_json(raw_text: str) -> str:
    """Rebuild run-sql JSON rows with fully synthetic values.

    Column names/order, row count and JSON shape are preserved; every company
    code/description is replaced (currency codes are standard SAP codes, not
    customer data, and stay intact for realistic type variety).
    """
    rows = json.loads(raw_text)
    synth = []
    for i, row in enumerate(rows):
        item = {}
        for key in row:
            if key == "BUKRS":
                item[key] = f"{1000 + i:04d}"
            elif key == "BUTXT":
                item[key] = f"Sample Company {i + 1:03d}"
            else:
                item[key] = row[key]
        synth.append(item)
    return json.dumps(synth, indent=2, ensure_ascii=False) + "\n"


def trim_where_used(raw_text: str) -> str:
    """Reduce a usageReferences tree to a small SAP-only, system-ID-free fixture.

    Real where-used responses are large trees (~2k nodes) whose paths contain
    customer Z/Y objects and a resultDescription with the SAP system ID. The
    committed fixture keeps only the first non-customer nodes while retaining
    every structural variety (parent group, isResult leaf, #start fragment).
    """
    import xml.etree.ElementTree as ET

    ET.register_namespace("usageReferences", "http://www.sap.com/adt/ris/usageReferences")
    ET.register_namespace("adtcore", "http://www.sap.com/adt/core")
    root = ET.fromstring(raw_text)
    U = "{http://www.sap.com/adt/ris/usageReferences}"

    def is_customer(node) -> bool:
        uri = (node.get("uri") or "").lower()
        for seg in re.split(r"/|%2f", uri):
            if len(seg) > 1 and seg[:1] in ("z", "y"):
                return True
        return False

    # Two passes: reserve the informative leaves (actual isResult hits, and
    # at least two #start fragments), then fill with hierarchy parents.
    leaves, starts, picked = [], [], []
    for node in root.iter(f"{U}referencedObject"):
        if is_customer(node):
            continue
        uri = node.get("uri") or ""
        if node.get("isResult") == "true" and len(leaves) < 6:
            leaves.append(node)
        elif "#start=" in uri and len(starts) < 2:
            starts.append(node)
    for node in root.iter(f"{U}referencedObject"):
        if is_customer(node) or len(picked) >= 6:
            continue
        if node not in leaves and node not in starts:
            picked.append(node)
    kept = (leaves + starts + picked)[:14]

    root.set("numberOfResults", str(len(kept)))
    root.set("resultDescription",
             "References for: CL_GUI_FRONTEND_SERVICES (Class)")
    container = root.find(f"{U}referencedObjects")
    if container is None:
        container = ET.SubElement(root, f"{U}referencedObjects")
    for child in list(container):
        container.remove(child)
    for node in kept:
        container.append(node)
    return '<?xml version="1.0" encoding="utf-8"?>' + ET.tostring(root, encoding="unicode")


def render(raw_name: str, raw_bytes: bytes, repls: list[tuple[str, str]]) -> bytes:
    if raw_name == "run-sql.t001.xml":
        return sanitize_rows_json(raw_bytes.decode("utf-8")).encode("utf-8")
    if raw_name == "where-used.hits.raw.xml":
        return trim_where_used(raw_bytes.decode("utf-8")).encode("utf-8")
    if raw_name == "where-used.empty.raw.xml":
        # resultDescription carries the SAP system ID ("... [ECD]").
        text = re.sub(r"\s*\[[A-Z0-9]{3}\]", "", raw_bytes.decode("utf-8"))
        return text.encode("utf-8")
    return scrub_text(raw_bytes.decode("utf-8"), repls).encode("utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify fixtures are up to date and leak-free")
    args = ap.parse_args()

    if not RAW.is_dir():
        print(f"raw/ directory not found: {RAW}", file=sys.stderr)
        return 2
    mapping = load_map()
    repls = build_replacements(mapping)
    leak_patterns = [re.compile(re.escape(v)) for v in
                     (mapping["host"], mapping["host_with_port"],
                      mapping["username"], mapping.get("profile", "")) if v]
    leak_patterns.extend(
        re.compile(re.escape(v)) for v in mapping.get("extra_leaks", []) if v
    )
    leak_patterns.extend(EXTRA_LEAK_PATTERNS)

    failures = []
    for raw_name, out_name in sorted(FILE_MAP.items()):
        src = RAW / raw_name
        if not src.exists():
            failures.append(f"missing raw capture: {raw_name}")
            continue
        content = render(raw_name, src.read_bytes(), repls)
        text = content.decode("utf-8", errors="replace")
        for pat in leak_patterns:
            if pat.search(text):
                failures.append(f"{out_name}: leaked pattern /{pat.pattern}/")
        dst = HERE / out_name
        if args.check:
            if not dst.exists() or dst.read_bytes() != content:
                failures.append(f"stale fixture: {out_name} (rerun sanitize.py)")
        else:
            dst.write_bytes(content)
            print(f"{raw_name} -> {out_name} ({len(content)} bytes)")

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    if args.check:
        print(f"OK: {len(FILE_MAP)} fixtures up to date, no leaks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
