"""Conservative source-derived function interfaces and typed local invocation."""
from __future__ import annotations

import json
import re

from . import handlers, source_write

NAME = re.compile(r"(?:/[A-Z0-9_]+/)?[A-Z][A-Z0-9_]{0,29}\Z", re.ASCII)
TYPE = re.compile(r"(?:/[A-Z0-9_]+/)?[A-Z][A-Z0-9_]*(?:-[A-Z][A-Z0-9_]*)?\Z", re.ASCII)
GENERIC = {"ANY", "DATA", "SIMPLE", "CLIKE", "CSEQUENCE", "XSEQUENCE", "NUMERIC",
           "ANY TABLE", "INDEX TABLE", "STANDARD TABLE", "OBJECT", "C", "N", "X", "P"}
TOKEN = re.compile(r"'(?:''|[^'])*'|[A-Za-z0-9_/]+(?:-[A-Za-z0-9_]+)*|[().]|[^\s]")
DIRECTIONS = ("IMPORTING", "EXPORTING", "CHANGING", "TABLES", "EXCEPTIONS")


def parse_signature(source, name):
    """Read an explicit modern interface or the generated Local Interface header."""
    name = name.upper()
    if not NAME.fullmatch(name):
        raise ValueError("invalid function name")
    header = re.search(r"(?im)^FUNCTION\s+([A-Z0-9_/]+)(?=\s|\.)", source)
    if not header or header[1].upper() != name:
        raise ValueError("function declaration does not match the selected identity")
    legacy = re.search(r'(?im)^\*"(?:\*")?\s*(?:Local Interface|Lokale Schnittstelle)\s*:', source)
    if legacy:
        lines = []
        for line in source[legacy.end():].splitlines()[1:]:
            if not line.startswith('*"'):
                break
            text = line[2:].strip()
            if text and not set(text) <= {"-"}:
                lines.append(text)
        declaration = " ".join(lines)
    else:
        # Strip comments without treating periods/quotes inside literals as syntax.
        lines = [line for line in source.splitlines() if not line.startswith("*")]
        tokens = TOKEN.findall("\n".join(lines))
        if len(tokens) < 3 or tokens[0].upper() != "FUNCTION" or tokens[1].upper() != name:
            raise ValueError("function declaration does not match the selected identity")
        try:
            end = tokens.index(".")
        except ValueError:
            raise ValueError("function declaration is incomplete") from None
        declaration = " ".join(tokens[2:end])
    tokens = TOKEN.findall(declaration)
    params, exceptions, section, i = [], [], None, 0
    while i < len(tokens):
        token = tokens[i].upper()
        if token in DIRECTIONS:
            section, i = token, i + 1
            continue
        if section is None:
            raise ValueError("no unambiguous explicit function interface found")
        if section == "EXCEPTIONS":
            if not NAME.fullmatch(token):
                raise ValueError("unsupported exception declaration")
            exceptions.append(token)
            i += 1
            continue
        if token in ("VALUE", "REFERENCE"):
            if i + 3 >= len(tokens) or tokens[i + 1] != "(" or tokens[i + 3] != ")":
                raise ValueError("invalid parameter declaration")
            parameter, i = tokens[i + 2].upper(), i + 4
        else:
            parameter, i = token, i + 1
        if not NAME.fullmatch(parameter) or any(p["name"] == parameter for p in params):
            raise ValueError("invalid or duplicate parameter")
        if i + 1 >= len(tokens) or tokens[i].upper() not in ("TYPE", "LIKE", "STRUCTURE"):
            raise ValueError("only explicit TYPE/LIKE/STRUCTURE parameters are supported")
        typing, typename = tokens[i].upper(), tokens[i + 1].upper()
        i += 2
        if not TYPE.fullmatch(typename) or typename in GENERIC or typename in ("REF", "STANDARD", "SORTED", "HASHED"):
            raise ValueError("generic, reference and anonymous table types are not supported")
        if typing == "STRUCTURE" and section != "TABLES":
            raise ValueError("STRUCTURE requires a TABLES parameter")
        optional = section in ("EXPORTING", "TABLES")
        default = None
        if i < len(tokens) and tokens[i].upper() == "OPTIONAL":
            optional, i = True, i + 1
        elif i < len(tokens) and tokens[i].upper() == "DEFAULT":
            if i + 1 >= len(tokens):
                raise ValueError("missing default value")
            default, optional, i = tokens[i + 1], True, i + 2
        params.append({"name": parameter, "direction": section, "typing": typing,
                       "type": typename, "optional": optional, "default": default})
    if not params and not declaration.strip() and not legacy:
        raise ValueError("empty/unavailable interface cannot prove a parameterless function")
    return {"name": name, "parameters": params, "exceptions": exceptions,
            "source": "observed-active-function-source",
            "source_sha256": source_write.sha256_text(source_write.canonical_source(source))}


def signature(name, group):
    if not group or not NAME.fullmatch(group.upper()):
        raise ValueError("an explicit valid --group is required")
    uri = handlers.get_object_uri("function", name, group=group)
    result = handlers.read_source_main(uri, version="active")
    if result.is_error:
        raise ValueError("function source unavailable: " + result.text)
    data = parse_signature(result.text, name)
    data.update({"group": group.upper(), "uri": uri})
    return data


def literal(value):
    if len(value) > 120:
        return " &&\n".join("`" + value[i:i + 120].replace("`", "``") + "`"
                           for i in range(0, len(value), 120))
    return "'" + value.replace("'", "''") + "'"


def build(sig, inputs, marker):
    if not isinstance(inputs, dict) or set(inputs) - {"importing", "changing", "tables"}:
        raise ValueError("input must contain only importing/changing/tables objects")
    supplied = {}
    for direction, values in inputs.items():
        if not isinstance(values, dict):
            raise ValueError("each input direction must be a JSON object")
        for key, value in values.items():
            upper = key.upper()
            if upper in supplied:
                raise ValueError("duplicate case-insensitive input parameter")
            supplied[upper] = (direction.upper(), value)
    known = {p["name"]: p for p in sig["parameters"]}
    if any(p["name"] == "SUBRC" and p["direction"] != "IMPORTING"
           for p in sig["parameters"]):
        raise ValueError("output parameter SUBRC conflicts with the wrapper result status field")
    if set(supplied) - set(known):
        raise ValueError("input contains unknown parameters")
    for key, (direction, value) in supplied.items():
        if known[key]["direction"] != direction or direction == "EXPORTING":
            raise ValueError("input direction differs from the observed function signature")
        if direction == "TABLES" and not isinstance(value, list):
            raise ValueError("TABLES inputs must be JSON arrays")
    declarations, loads, call, outputs = [], [], [], []
    for index, p in enumerate(sig["parameters"]):
        key, direction = p["name"], p["direction"]
        if direction in ("IMPORTING", "CHANGING") and key not in supplied and not p["optional"]:
            raise ValueError("missing required input: " + key)
        # Omitting optional input preserves the function's own default semantics.
        if direction == "IMPORTING" and key not in supplied:
            continue
        variable = f"lv_p{index}"
        typing = (f"TYPE STANDARD TABLE OF {p['type']} WITH DEFAULT KEY"
                  if direction == "TABLES" else f"{p['typing']} {p['type']}")
        declarations.append(f"DATA {variable} {typing}.")
        if key in supplied:
            encoded = json.dumps({key: supplied[key][1]}, ensure_ascii=True,
                                 separators=(",", ":"), allow_nan=False)
            loads += [f"lv_json = {literal(encoded)}.",
                      f"DATA(lo_reader{index}) = cl_sxml_string_reader=>create( "
                      "input = cl_abap_codepage=>convert_to( lv_json ) ).",
                      f"CALL TRANSFORMATION id SOURCE XML lo_reader{index} RESULT {key.lower()} = {variable}."]
        call.append(({"IMPORTING": "EXPORTING", "EXPORTING": "IMPORTING",
                      "CHANGING": "CHANGING", "TABLES": "TABLES"}[direction],
                     f"  {key} = {variable}"))
        if direction != "IMPORTING":
            outputs.append(f"{key.lower()} = {variable}")
    lines = declarations + ["DATA lv_json TYPE string.", "DATA lv_subrc TYPE sysubrc."] + loads
    lines.append(f"CALL FUNCTION {literal(sig['name'])}")
    for direction in ("EXPORTING", "IMPORTING", "TABLES", "CHANGING"):
        entries = [line for d, line in call if d == direction]
        if entries:
            lines += [direction] + entries
    lines += ["EXCEPTIONS"]
    lines += [f"  {name} = {i}" for i, name in enumerate(sig["exceptions"], 1)]
    lines += [f"  OTHERS = {len(sig['exceptions']) + 1}.", "lv_subrc = sy-subrc.",
              "DATA(lo_writer) = cl_sxml_string_writer=>create( type = if_sxml=>co_xt_json ).",
              "CALL TRANSFORMATION id SOURCE subrc = lv_subrc " + " ".join(outputs) +
              " RESULT XML lo_writer.",
              "DATA(lv_result) = cl_abap_codepage=>convert_from( lo_writer->get_output( ) ).",
              f"out->write( {literal(marker + ':BEGIN')} ).", "out->write( lv_result ).",
              f"out->write( {literal(marker + ':END')} )."]
    return "\n".join(lines)


def marker(binding):
    from .lifecycle import digest
    return "SAP_ADT_RESULT_" + digest(binding)[:24].upper()


def extract(data, token):
    output = data.get("output", {})
    if data.get("execution", {}).get("status") != "completed" or output.get("truncated"):
        raise ValueError("execution result is incomplete; structured output is unconfirmed")
    text = output.get("text", "")
    begin, end = token + ":BEGIN", token + ":END"
    if text.count(begin) != 1 or text.count(end) != 1:
        raise ValueError("missing or duplicate structured result markers")
    prefix, result = text.split(begin)
    payload, suffix = result.split(end)
    if prefix.strip() or suffix.strip():
        raise ValueError("unexpected output outside the structured result")
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("duplicate JSON result key")
            obj[key] = value
        return obj
    parsed = json.loads(payload.strip(), object_pairs_hook=unique,
                        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    if not isinstance(parsed, dict) or type(parsed.get("SUBRC")) is not int:
        raise ValueError("structured result has no confirmed numeric SUBRC")
    return parsed
