"""Explicit SUBMIT wrapper; native ADT Report execution remains unchanged."""
from __future__ import annotations

import re

from . import function_call, handlers, source_write


def prepare(name, variant, selections):
    name = name.upper()
    if not function_call.NAME.fullmatch(name):
        raise ValueError("invalid Report name")
    if variant and not re.fullmatch(r"[A-Za-z0-9_/-]{1,14}", variant):
        raise ValueError("variant must contain 1-14 safe SAP variant characters")
    if not isinstance(selections, list) or len(selections) > 500:
        raise ValueError("selections must be an array of at most 500 RSPARAMS rows")
    rows = []
    for row in selections:
        if not isinstance(row, dict) or set(row) - {"name", "kind", "sign", "option", "low", "high"}:
            raise ValueError("unknown selection row fields")
        normalized = {"name": str(row.get("name", "")).upper(),
                      "kind": row.get("kind", "P"), "sign": row.get("sign", "I"),
                      "option": row.get("option", "EQ"),
                      "low": row.get("low", ""), "high": row.get("high", "")}
        if (not re.fullmatch(r"[A-Z][A-Z0-9_]{0,7}", normalized["name"])
                or normalized["kind"] not in ("P", "S")
                or normalized["sign"] not in ("I", "E")
                or normalized["option"] not in ("EQ", "NE", "BT", "NB", "CP", "NP", "GE", "GT", "LE", "LT")
                or any(not isinstance(normalized[k], str) or len(normalized[k]) > 45
                       for k in ("low", "high"))):
            raise ValueError("invalid RSPARAMS row (selection name max 8; LOW/HIGH max 45)")
        if normalized["kind"] == "P" and (normalized["sign"] != "I" or normalized["option"] != "EQ"
                                        or normalized["high"]):
            raise ValueError("parameters require I/EQ and no HIGH value")
        rows.append(normalized)
    if len({r["name"] for r in rows if r["kind"] == "P"}) != sum(r["kind"] == "P" for r in rows):
        raise ValueError("duplicate Report parameter")
    uri = handlers.get_object_uri("program", name)
    source = handlers.read_source_main(uri, version="active")
    if source.is_error:
        raise ValueError("Report source unavailable: " + source.text)
    return {"mode": "submit-wrapper", "name": name, "uri": uri, "variant": variant,
            "selections": rows, "source_binding": "observed-active-main-only",
            "source_sha256": source_write.sha256_text(source_write.canonical_source(source.text)),
            "capture": "classic ABAP List only; no GUI/ALV-control/Spool capture"}


def build(binding, marker):
    lit = function_call.literal
    lines = ["DATA lt_selection TYPE STANDARD TABLE OF rsparams WITH DEFAULT KEY.",
             "DATA ls_selection TYPE rsparams.",
             "DATA lt_list TYPE STANDARD TABLE OF abaplist WITH DEFAULT KEY.",
             "DATA lt_ascii TYPE STANDARD TABLE OF char255 WITH DEFAULT KEY.",
             "DATA lv_subrc TYPE sysubrc."]
    for row in binding["selections"]:
        lines += ["CLEAR ls_selection."]
        for field, key in (("selname", "name"), ("kind", "kind"), ("sign", "sign"),
                           ("option", "option"), ("low", "low"), ("high", "high")):
            lines.append(f"ls_selection-{field} = {lit(row[key])}.")
        lines.append("APPEND ls_selection TO lt_selection.")
    lines.append(f"SUBMIT {binding['name']}")
    if binding["variant"]:
        lines.append("USING SELECTION-SET " + lit(binding["variant"]))
    lines += ["WITH SELECTION-TABLE lt_selection EXPORTING LIST TO MEMORY AND RETURN.",
              "CALL FUNCTION 'LIST_FROM_MEMORY' TABLES listobject = lt_list",
              "  EXCEPTIONS not_found = 1 OTHERS = 2.",
              "lv_subrc = sy-subrc.",
              "IF lv_subrc = 0.",
              "  CALL FUNCTION 'LIST_TO_ASCI' TABLES listasci = lt_ascii listobject = lt_list",
              "    EXCEPTIONS empty_list = 1 list_index_invalid = 2 OTHERS = 3.",
              "  lv_subrc = sy-subrc.",
              "ENDIF.",
              "DATA(lo_writer) = cl_sxml_string_writer=>create( type = if_sxml=>co_xt_json ).",
              "CALL TRANSFORMATION id SOURCE subrc = lv_subrc list = lt_ascii RESULT XML lo_writer.",
              "DATA(lv_result) = cl_abap_codepage=>convert_from( lo_writer->get_output( ) ).",
              f"out->write( {lit(marker + ':BEGIN')} ).", "out->write( lv_result ).",
              f"out->write( {lit(marker + ':END')} )."]
    return "\n".join(lines)
