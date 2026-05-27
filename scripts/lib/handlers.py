import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import requests

from .client import make_adt_request
from .config import get_config


@dataclass
class AdtResult:
    text: str
    is_error: bool = False


def _base() -> str:
    return get_config().base_url()


def _enc(name: str) -> str:
    return quote(name, safe="")


def _ok(resp: requests.Response) -> AdtResult:
    return AdtResult(text=resp.text)


def _err(exc: Exception) -> AdtResult:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return AdtResult(
            text=f"HTTP {exc.response.status_code}: {exc.response.text or str(exc)}",
            is_error=True,
        )
    return AdtResult(text=str(exc), is_error=True)


def _tag_local(elem) -> str:
    return elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag


def _flat_attribs(elem) -> dict:
    return {(k.split("}")[-1] if "}" in k else k): v for k, v in elem.attrib.items()}


def _parse_sql_result(xml_text: str) -> list:
    if not xml_text or not xml_text.strip():
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    columns_ordered = []
    for elem in root.iter():
        if _tag_local(elem) != "columns":
            continue
        meta = next((c for c in elem if _tag_local(c) == "metadata"), None)
        if meta is None:
            continue
        col_name = _flat_attribs(meta).get("name", "")
        if not col_name:
            continue
        dataset = next((c for c in elem if _tag_local(c) == "dataSet"), None)
        values = []
        if dataset is not None:
            values = [d.text or "" for d in dataset if _tag_local(d) == "data"]
        columns_ordered.append((col_name, values))

    if not columns_ordered:
        return []
    n_rows = max(len(v) for _, v in columns_ordered)
    result = []
    for i in range(n_rows):
        row = {}
        for col_name, values in columns_ordered:
            row[col_name] = values[i] if i < len(values) else ""
        result.append(row)
    return result


def _run_e071_sql(tr_id: str) -> list:
    url = f"{_base()}/sap/bc/adt/datapreview/freestyle"
    sql = f"SELECT PGMID, OBJECT, OBJ_NAME, LOCKFLAG, ACTIVITY FROM E071 WHERE TRKORR = '{tr_id}'"
    try:
        try:
            resp = make_adt_request(
                url,
                params={"rowNumber": 500, "sqlCommand": sql},
                extra_headers={"Accept": "application/vnd.sap.adt.datapreview.table.v1+xml"},
            )
        except requests.HTTPError as e2:
            if e2.response is None or e2.response.status_code != 405:
                raise
            resp = make_adt_request(
                url,
                method="POST",
                params={"rowNumber": 500},
                data=sql.encode("utf-8"),
                extra_headers={
                    "Content-Type": "text/plain",
                    "Accept": "application/vnd.sap.adt.datapreview.table.v1+xml",
                },
                timeout=60,
            )
        return _parse_sql_result(resp.text)
    except Exception:
        return []


def get_transport_objects(tr_id: str) -> AdtResult:
    try:
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/cts/transports/{_enc(tr_id)}/objects",
            extra_headers={
                "Accept": "application/vnd.sap.cts.transport.objects+xml; charset=utf-8"
            },
        )
        return AdtResult(text=resp.text)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            rows = _run_e071_sql(tr_id)
            seen: set = set()
            objects = []
            for row in rows:
                pgmid = row.get("PGMID", "").strip()
                obj_type = row.get("OBJECT", "").strip()
                obj_name = row.get("OBJ_NAME", "").strip()
                if not pgmid or not obj_type or not obj_name:
                    continue
                key = (obj_type, obj_name)
                if key in seen:
                    continue
                seen.add(key)
                objects.append({
                    "pgmid": pgmid,
                    "object_type": obj_type,
                    "object_name": obj_name,
                    "lockflag": row.get("LOCKFLAG", "").strip(),
                    "activity": row.get("ACTIVITY", "").strip(),
                })
            if objects:
                return AdtResult(text=json.dumps(objects))
        return _err(e)
    except Exception as e:
        return _err(e)


def parse_transport_objects(xml_text: str) -> list:
    if not xml_text or not xml_text.strip():
        return []

    stripped = xml_text.strip()
    if stripped.startswith("["):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return []

    try:
        root = ET.fromstring(stripped)
    except ET.ParseError:
        return []

    objects = []
    for elem in root.iter():
        flat = _flat_attribs(elem)

        # SAP ADT XML format varies by release: some use XML attributes (PGMID=, OBJECT=, OBJ_NAME=),
        # others use child elements (<PGMID>, <OBJECT>, <OBJ_NAME>). Try both.
        pgmid = flat.get("PGMID") or flat.get("pgmid", "")
        obj_type = flat.get("OBJECT") or flat.get("object") or flat.get("type", "")
        obj_name = flat.get("OBJ_NAME") or flat.get("obj_name") or flat.get("name", "")

        if not pgmid and not obj_type:
            pgmid_el = elem.find("PGMID")
            obj_el = elem.find("OBJECT")
            name_el = elem.find("OBJ_NAME")
            if pgmid_el is not None and obj_el is not None and name_el is not None:
                pgmid = (pgmid_el.text or "").strip()
                obj_type = (obj_el.text or "").strip()
                obj_name = (name_el.text or "").strip()

        if not pgmid or not obj_type or not obj_name:
            continue

        lockflag_el = elem.find("LOCKFLAG")
        activity_el = elem.find("ACTIVITY")
        objects.append({
            "pgmid": pgmid,
            "object_type": obj_type,
            "object_name": obj_name,
            "lockflag": (lockflag_el.text or "").strip() if lockflag_el is not None else flat.get("LOCKFLAG", ""),
            "activity": (activity_el.text or "").strip() if activity_el is not None else flat.get("ACTIVITY", ""),
        })

    seen = set()
    unique = []
    for obj in objects:
        key = (obj["object_type"], obj["object_name"])
        if key not in seen:
            seen.add(key)
            unique.append(obj)
    return unique


def get_program(name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(
            f"{_base()}/sap/bc/adt/programs/programs/{_enc(name)}/source/main"
        ))
    except Exception as e:
        return _err(e)


def get_include(name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(
            f"{_base()}/sap/bc/adt/programs/includes/{_enc(name)}/source/main"
        ))
    except Exception as e:
        return _err(e)


def get_class(name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(
            f"{_base()}/sap/bc/adt/oo/classes/{_enc(name)}/source/main"
        ))
    except Exception as e:
        return _err(e)


def get_interface(name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(
            f"{_base()}/sap/bc/adt/oo/interfaces/{_enc(name)}/source/main"
        ))
    except Exception as e:
        return _err(e)


def get_function_group(name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(
            f"{_base()}/sap/bc/adt/functions/groups/{_enc(name)}/source/main"
        ))
    except Exception as e:
        return _err(e)


def get_function_module(group: str, name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(
            f"{_base()}/sap/bc/adt/functions/groups/{_enc(group)}/fmodules/{_enc(name)}/source/main"
        ))
    except Exception as e:
        return _err(e)


def get_table(name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(
            f"{_base()}/sap/bc/adt/ddic/tables/{_enc(name)}/source/main"
        ))
    except Exception as e:
        return _err(e)


def get_structure(name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(
            f"{_base()}/sap/bc/adt/ddic/structures/{_enc(name)}/source/main"
        ))
    except Exception as e:
        return _err(e)


def get_cds_view(name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(
            f"{_base()}/sap/bc/adt/ddic/ddl/sources/{_enc(name)}/source/main"
        ))
    except Exception as e:
        return _err(e)


def get_data_element(name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(
            f"{_base()}/sap/bc/adt/ddic/dataelements/{_enc(name)}"
        ))
    except Exception as e:
        return _err(e)


def get_domain(name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(
            f"{_base()}/sap/bc/adt/ddic/domains/{_enc(name)}/source/main"
        ))
    except Exception as e:
        return _err(e)


# Each entry: (handler_fn, needs_group). "FUNC" needs_group=True → special dispatch below.
# SAP object type codes: PROG=report, REPS=program include, CINC=class include,
# CLAS=global class, INTF=interface, FUGR=function group, FUNC=function module,
# TABL=transparent table, STRU=structure, DTEL=data element, DOMA=domain, DDLS=CDS view.
_SOURCE_HANDLERS = {
    "PROG": (get_program, False),
    "REPS": (get_include, False),
    "CINC": (get_include, False),
    "CLAS": (get_class, False),
    "INTF": (get_interface, False),
    "FUGR": (get_function_group, False),
    "FUNC": (None, True),
    "TABL": (get_table, False),
    "STRU": (get_structure, False),
    "DTEL": (get_data_element, False),
    "DOMA": (get_domain, False),
    "DDLS": (get_cds_view, False),
}

_NO_SOURCE_TYPES = {
    "DEVC", "SICF", "SMIM", "NROB", "MSAG",
    "TRAN", "AUTH", "SUSC", "SUSO", "SRFC",
    "ENHO", "ENHS", "ENHC",
}


def fetch_source_for_object(pgmid: str, object_type: str, object_name: str) -> AdtResult:
    if object_type in _NO_SOURCE_TYPES:
        return AdtResult(text=f"[NO_SOURCE] Object type {object_type} has no source endpoint.", is_error=False)

    handler_info = _SOURCE_HANDLERS.get(object_type)
    if handler_info is None:
        return AdtResult(text=f"[UNSUPPORTED] Object type {object_type} not mapped to a source handler.", is_error=True)

    handler_fn, needs_group = handler_info

    if object_type == "FUNC":
        # SAP FMs require their containing function group. Callers can pass "GROUP/FUNCNAME"
        # as object_name. Without a slash, best-effort: derive group from name prefix.
        if "/" in object_name:
            group, name = object_name.split("/", 1)
        else:
            parts = object_name.rsplit("_", 1)
            group = parts[0] if len(parts) > 1 else object_name
            name = object_name
        return get_function_module(group, name)

    return handler_fn(object_name)


def ping() -> AdtResult:
    try:
        config = get_config()
        resp = make_adt_request(f"{_base()}/sap/bc/adt/")
        return AdtResult(text=f"OK — connected to {config.url} (HTTP {resp.status_code})")
    except Exception as e:
        return _err(e)
