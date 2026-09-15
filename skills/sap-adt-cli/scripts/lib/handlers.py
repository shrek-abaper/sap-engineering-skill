import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import requests

from .client import AdtHttpError, make_adt_request
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
    # AdtHttpError messages are pre-sanitized (no Authorization headers).
    return AdtResult(text=str(exc), is_error=True)


def _xattr(s: str) -> str:
    """Escape a string for safe embedding inside a double-quoted XML attribute value."""
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def get_program(program_name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(f"{_base()}/sap/bc/adt/programs/programs/{_enc(program_name)}/source/main"))
    except Exception as e:
        return _err(e)


def get_class(class_name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(f"{_base()}/sap/bc/adt/oo/classes/{_enc(class_name)}/source/main"))
    except Exception as e:
        return _err(e)


def get_function_group(function_group: str) -> AdtResult:
    try:
        return _ok(make_adt_request(f"{_base()}/sap/bc/adt/functions/groups/{_enc(function_group)}/source/main"))
    except Exception as e:
        return _err(e)


def get_function(function_name: str, function_group: str) -> AdtResult:
    try:
        url = (
            f"{_base()}/sap/bc/adt/functions/groups/{_enc(function_group)}"
            f"/fmodules/{_enc(function_name)}/source/main"
        )
        return _ok(make_adt_request(url))
    except Exception as e:
        return _err(e)


def get_structure(structure_name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(f"{_base()}/sap/bc/adt/ddic/structures/{_enc(structure_name)}/source/main"))
    except Exception as e:
        return _err(e)


def get_table(table_name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(f"{_base()}/sap/bc/adt/ddic/tables/{_enc(table_name)}/source/main"))
    except Exception as e:
        return _err(e)


def get_package(package_name: str) -> AdtResult:
    try:
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/repository/nodestructure",
            method="POST",
            params={
                "parent_type": "DEVC/K",
                "parent_name": _enc(package_name),
                "withShortDescriptions": "true",
            },
        )
        root = ET.fromstring(resp.text)
        ns_obj = "{http://www.sap.com/abapxml}"
        items = []
        for node in root.findall(f".//{ns_obj}SEU_ADT_REPOSITORY_OBJ_NODE"):
            name_el = node.find(f"{ns_obj}OBJECT_NAME")
            uri_el = node.find(f"{ns_obj}OBJECT_URI")
            if name_el is None or uri_el is None:
                continue
            type_el = node.find(f"{ns_obj}OBJECT_TYPE")
            desc_el = node.find(f"{ns_obj}DESCRIPTION")
            items.append({
                "OBJECT_TYPE": type_el.text if type_el is not None else "",
                "OBJECT_NAME": name_el.text,
                "OBJECT_DESCRIPTION": desc_el.text if desc_el is not None else "",
                "OBJECT_URI": uri_el.text,
            })
        return AdtResult(text=json.dumps(items, indent=2))
    except Exception as e:
        return _err(e)


def get_type_info(type_name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(f"{_base()}/sap/bc/adt/ddic/domains/{_enc(type_name)}/source/main"))
    except Exception:
        pass
    try:
        return _ok(make_adt_request(f"{_base()}/sap/bc/adt/ddic/dataelements/{_enc(type_name)}"))
    except Exception as e:
        return _err(e)


def get_include(include_name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(f"{_base()}/sap/bc/adt/programs/includes/{_enc(include_name)}/source/main"))
    except Exception as e:
        return _err(e)


def get_interface(interface_name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(f"{_base()}/sap/bc/adt/oo/interfaces/{_enc(interface_name)}/source/main"))
    except Exception as e:
        return _err(e)


def get_transaction(transaction_name: str) -> AdtResult:
    try:
        url = (
            f"{_base()}/sap/bc/adt/repository/informationsystem/objectproperties/values"
            f"?uri=%2Fsap%2Fbc%2Fadt%2Fvit%2Fwb%2Fobject_type%2Ftrant%2Fobject_name%2F{_enc(transaction_name)}"
            f"&facet=package&facet=appl"
        )
        return _ok(make_adt_request(url))
    except Exception as e:
        return _err(e)


def search_object(query: str, max_results: int = 100) -> AdtResult:
    try:
        url = (
            f"{_base()}/sap/bc/adt/repository/informationsystem/search"
            f"?operation=quickSearch&query={_enc(query)}&maxResults={max_results}"
        )
        return _ok(make_adt_request(url))
    except Exception as e:
        return _err(e)


def get_object_uri(object_type: str, object_name: str, group: Optional[str] = None) -> str:
    t = object_type.lower()
    if t == "program":
        return f"/sap/bc/adt/programs/programs/{_enc(object_name)}"
    elif t == "class":
        return f"/sap/bc/adt/oo/classes/{_enc(object_name)}"
    elif t == "interface":
        return f"/sap/bc/adt/oo/interfaces/{_enc(object_name)}"
    elif t == "include":
        return f"/sap/bc/adt/programs/includes/{_enc(object_name)}"
    elif t == "function":
        if not group:
            raise ValueError("--group is required for object type 'function'")
        return f"/sap/bc/adt/functions/groups/{_enc(group)}/fmodules/{_enc(object_name)}"
    else:
        raise ValueError(
            f"Unknown object type: {object_type!r}. "
            "Supported types: program, class, interface, include, function"
        )


def _flat_attribs(elem) -> dict:
    return {(k.split("}")[-1] if "}" in k else k): v for k, v in elem.attrib.items()}


def _tag_local(elem) -> str:
    return elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag


def _extract_lock_handle(resp: requests.Response) -> str:
    handle = resp.headers.get("com.sap.adt.lock.handle", "")
    if handle:
        return handle
    if resp.text:
        try:
            root = ET.fromstring(resp.text)
            for elem in root.iter():
                for k, v in elem.attrib.items():
                    kl = k.split("}")[-1] if "}" in k else k
                    if kl in ("handle", "lockHandle", "lock"):
                        return v
                tl = _tag_local(elem)
                if tl in ("handle", "lockHandle") and elem.text:
                    return elem.text.strip()
        except ET.ParseError:
            return resp.text.strip()
    return ""


def _parse_syntax_check(xml_text: str) -> str:
    if not xml_text or not xml_text.strip():
        return "Syntax OK — no issues found."
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return xml_text

    messages = []
    for elem in root.iter():
        flat = _flat_attribs(elem)
        severity = flat.get("severity", "")
        text = flat.get("text", "") or flat.get("description", "")
        line = flat.get("line", "") or flat.get("offset", "")
        if not severity or not text:
            continue
        tag = severity.upper()
        if tag not in ("ERROR", "WARNING", "INFO"):
            continue
        line_str = f" line {line}:" if line and line != "0" else ""
        messages.append(f"[{tag}]{line_str} {text}")

    return "\n".join(messages) if messages else "Syntax OK — no issues found."


def _parse_activation_errors(xml_text: str) -> list:
    if not xml_text or not xml_text.strip():
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    errors = []
    for elem in root.iter():
        flat = _flat_attribs(elem)
        tl = _tag_local(elem)
        severity = flat.get("severity", "")
        text = flat.get("text", "") or flat.get("description", "") or flat.get("shortText", "")
        if tl in ("error", "message", "checkResult") and text:
            prefix = f"[{severity.upper()}] " if severity else ""
            errors.append(f"{prefix}{text}")
    return errors


def _parse_where_used(xml_text: str) -> list:
    if not xml_text or not xml_text.strip():
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    ns_core = "http://www.sap.com/adt/core"
    items = []
    for ref in root.iter(f"{{{ns_core}}}objectReference"):
        name = ref.get(f"{{{ns_core}}}name") or ref.get("name", "")
        type_ = ref.get(f"{{{ns_core}}}type") or ref.get("type", "")
        uri = ref.get(f"{{{ns_core}}}uri") or ref.get("uri", "")
        if name:
            items.append({"type": type_, "name": name, "uri": uri})
    if not items:
        for elem in root.iter():
            if _tag_local(elem) == "objectReference":
                flat = _flat_attribs(elem)
                name = flat.get("name", "")
                if name:
                    items.append({
                        "type": flat.get("type", ""),
                        "name": name,
                        "uri": flat.get("uri", ""),
                    })
    return items


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
        for elem in root.iter():
            if _tag_local(elem) != "column":
                continue
            flat = _flat_attribs(elem)
            col_name = flat.get("name", "")
            if not col_name:
                continue
            rows = []
            for child in elem:
                cl = _tag_local(child)
                if cl in ("row", "cell", "value"):
                    rows.append(child.text or "")
            if not rows:
                for rows_elem in elem.iter():
                    if _tag_local(rows_elem) == "rows":
                        for row_elem in rows_elem:
                            rows.append(row_elem.text or "")
                        break
            columns_ordered.append((col_name, rows))

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


def _parse_transports(xml_text: str, status_filter: str = "") -> list:
    if not xml_text or not xml_text.strip():
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items = []
    for elem in root.iter():
        tl = _tag_local(elem)
        if tl not in ("workitem", "transport", "request"):
            continue
        flat = _flat_attribs(elem)
        attr_map = {}
        for child in elem.iter():
            if _tag_local(child) == "attribute":
                cf = _flat_attribs(child)
                aname = cf.get("name", "")
                avalue = cf.get("value", "")
                if aname:
                    attr_map[aname] = avalue

        trkorr = attr_map.get("TRKORR") or flat.get("number") or flat.get("TRKORR", "")
        desc = attr_map.get("AS4TEXT") or flat.get("description") or flat.get("AS4TEXT", "")
        status = attr_map.get("TRSTATUS") or flat.get("status") or flat.get("TRSTATUS", "")
        owner = attr_map.get("AS4USER") or flat.get("owner") or flat.get("AS4USER", "")

        if not trkorr:
            continue
        if status_filter and status.upper() != status_filter.upper():
            continue
        items.append({
            "trkorr": trkorr,
            "description": desc,
            "status": status,
            "owner": owner,
        })
    return items


def syntax_check(
    object_type: str,
    object_name: str,
    group: Optional[str] = None,
) -> AdtResult:
    try:
        uri = get_object_uri(object_type, object_name, group=group)
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<adtcore:objectReferences xmlns:adtcore="http://www.sap.com/adt/core">'
            f'<adtcore:objectReference adtcore:uri="{_xattr(uri)}" adtcore:name="{_xattr(object_name.upper())}"/>'
            '</adtcore:objectReferences>'
        ).encode("utf-8")
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/abapsource/syntaxcheck",
            method="POST",
            data=body,
            extra_headers={
                "Content-Type": (
                    "application/vnd.sap.adt.abapsource.syntaxcheckresult+xml; charset=utf-8"
                )
            },
        )
        return AdtResult(text=_parse_syntax_check(resp.text))
    except ValueError as e:
        return AdtResult(text=str(e), is_error=True)
    except Exception as e:
        return _err(e)


def get_cds_view(name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(
            f"{_base()}/sap/bc/adt/ddic/ddl/sources/{_enc(name)}/source/main"
        ))
    except Exception as e:
        return _err(e)


def get_type_group(name: str) -> AdtResult:
    try:
        return _ok(make_adt_request(
            f"{_base()}/sap/bc/adt/typegroups/groups/{_enc(name)}/source/main"
        ))
    except Exception as e:
        return _err(e)


def where_used(
    object_type: str,
    object_name: str,
    max_results: int = 50,
    group: Optional[str] = None,
) -> AdtResult:
    try:
        uri = get_object_uri(object_type, object_name, group=group)
        full_uri = f"{_base()}{uri}"
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/repository/informationsystem/whereused",
            params={"uri": full_uri, "maxResults": max_results},
            extra_headers={
                "Accept": (
                    "application/vnd.sap.adt.repository.informationsystem.whereused+xml"
                )
            },
        )
        items = _parse_where_used(resp.text)
        return AdtResult(text=json.dumps(items, indent=2))
    except ValueError as e:
        return AdtResult(text=str(e), is_error=True)
    except Exception as e:
        return _err(e)


def run_sql(sql: str, max_rows: int = 100) -> AdtResult:
    url = f"{_base()}/sap/bc/adt/datapreview/freestyle"
    try:
        try:
            resp = make_adt_request(
                url,
                params={"rowNumber": max_rows, "sqlCommand": sql},
                extra_headers={"Accept": "application/vnd.sap.adt.datapreview.table.v1+xml"},
            )
        except AdtHttpError as e:
            if e.status != 405:
                raise
            resp = make_adt_request(
                url,
                method="POST",
                params={"rowNumber": max_rows},
                data=sql.encode("utf-8"),
                extra_headers={
                    "Content-Type": "text/plain",
                    "Accept": "application/vnd.sap.adt.datapreview.table.v1+xml",
                },
                timeout=60,
            )
        rows = _parse_sql_result(resp.text)
        return AdtResult(text=json.dumps(rows, indent=2))
    except Exception as e:
        return _err(e)


def list_transports(user: str, status: str = "D") -> AdtResult:
    try:
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/cts/transports",
            params={"user": user, "target": "", "category": "Workbench"},
            extra_headers={
                "Accept": "application/vnd.sap.cts.transport.worklist+xml; charset=utf-8"
            },
        )
        items = _parse_transports(resp.text, status_filter=status)
        return AdtResult(text=json.dumps(items, indent=2))
    except Exception as e:
        return _err(e)


def lock_object(object_uri: str) -> AdtResult:
    try:
        resp = make_adt_request(
            f"{_base()}{object_uri}?method=lock",
            method="POST",
            extra_headers={"X-sap-adt-sessiontype": "stateful"},
        )
        handle = _extract_lock_handle(resp)
        if not handle:
            return AdtResult(text="Lock succeeded but no handle returned by SAP — cannot proceed with write.", is_error=True)
        return AdtResult(text=handle)
    except Exception as e:
        return _err(e)


def put_source(
    object_uri: str,
    content: str,
    lock_handle: str,
    transport: Optional[str] = None,
) -> AdtResult:
    try:
        extra: dict = {
            "Content-Type": "text/plain; charset=utf-8",
            "X-sap-adt-lock-handle": lock_handle,
        }
        params: Optional[dict] = None
        if transport:
            params = {"sap-cts-request": transport}
        make_adt_request(
            f"{_base()}{object_uri}/source/main",
            method="PUT",
            data=content.encode("utf-8"),
            params=params,
            extra_headers=extra,
        )
        return AdtResult(text="OK")
    except Exception as e:
        return _err(e)


def unlock_object(object_uri: str, lock_handle: str) -> AdtResult:
    try:
        make_adt_request(
            f"{_base()}{object_uri}?method=unlock",
            method="POST",
            extra_headers={"X-sap-adt-lock-handle": lock_handle},
        )
        return AdtResult(text="OK")
    except Exception:
        return AdtResult(text="unlock error (ignored)", is_error=False)


def activate_object(
    object_type: str,
    object_name: str,
    group: Optional[str] = None,
) -> AdtResult:
    try:
        uri = get_object_uri(object_type, object_name, group=group)
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<adtcore:objectReferences xmlns:adtcore="http://www.sap.com/adt/core">'
            f'<adtcore:objectReference adtcore:uri="{_xattr(uri)}" adtcore:name="{_xattr(object_name.upper())}"/>'
            '</adtcore:objectReferences>'
        ).encode("utf-8")
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/activation",
            method="POST",
            data=body,
            extra_headers={
                "Content-Type": (
                    "application/vnd.sap.adt.activation.request+xml; charset=utf-8"
                )
            },
        )
        if resp.text and resp.text.strip():
            errors = _parse_activation_errors(resp.text)
            if errors:
                return AdtResult(text="\n".join(errors), is_error=True)
        return AdtResult(text=f"Activated {object_type.upper()} {object_name.upper()}.")
    except ValueError as e:
        return AdtResult(text=str(e), is_error=True)
    except Exception as e:
        return _err(e)


def create_transport(
    description: str,
    category: str = "Workbench",
    username: str = "",
) -> AdtResult:
    try:
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<cts:transportRequest xmlns:cts="http://www.sap.com/cts">'
            "<cts:attributes>"
            f'<cts:attribute name="category"    value="{_xattr(category)}"/>'
            f'<cts:attribute name="owner"       value="{_xattr(username)}"/>'
            f'<cts:attribute name="description" value="{_xattr(description)}"/>'
            '<cts:attribute name="target"      value=""/>'
            "</cts:attributes>"
            "</cts:transportRequest>"
        ).encode("utf-8")
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/cts/transports",
            method="POST",
            data=body,
            extra_headers={
                "Content-Type": (
                    "application/vnd.sap.cts.transport.request+xml; charset=utf-8"
                )
            },
        )
        location = resp.headers.get("Location", "")
        trkorr = location.rstrip("/").rsplit("/", 1)[-1] if location else ""
        if not trkorr:
            trkorr = resp.text.strip() or "(unknown)"
        return AdtResult(text=f"Created transport: {trkorr}")
    except Exception as e:
        return _err(e)


def release_transport(trkorr: str) -> AdtResult:
    try:
        make_adt_request(
            f"{_base()}/sap/bc/adt/cts/transports/{_enc(trkorr)}?action=release",
            method="POST",
        )
        return AdtResult(text=f"Released transport: {trkorr}")
    except Exception as e:
        return _err(e)
