import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import requests

from . import errors
from .client import AdtHttpError, make_adt_request
from .config import get_config
from .parsers import fields as parse_fields
from .parsers import findings as parse_findings
from .parsers import objects as parse_objects
from .parsers import records as parse_records
from .parsers import rows as parse_rows
from .parsers import scalar as parse_scalar
from .parsers import source as parse_source
from .parsers.common import ParseError


@dataclass
class AdtResult:
    text: str = ""
    is_error: bool = False
    # Structured-output fields (kind != "raw" when the command is normalized).
    kind: str = "raw"
    data: Optional[dict] = None
    object: Optional[dict] = None
    meta: Optional[dict] = None
    # Original ADT payload kept for --format xml passthrough.
    raw: Optional[str] = None
    # Classified error fields (is_error=True), produced via lib.errors.
    error_code: Optional[str] = None
    http_status: Optional[int] = None
    hint: Optional[str] = None


def _base() -> str:
    return get_config().base_url()


def _enc(name: str) -> str:
    return quote(name, safe="")


def _err(exc: Exception) -> AdtResult:
    # Single classification point lives in lib.errors; AdtHttpError
    # messages are pre-sanitized (no Authorization headers).
    d = errors.classify(exc)
    return AdtResult(
        text=d.message,
        is_error=True,
        error_code=d.code,
        http_status=d.http_status,
        hint=d.hint,
    )


def _obj(obj_type: str, name: str) -> dict:
    return {"type": obj_type, "name": (name or "").upper()}


def _structured(kind: str, data: dict, obj: dict, raw: Optional[str] = None,
                meta: Optional[dict] = None) -> AdtResult:
    return AdtResult(kind=kind, data=data, object=obj, raw=raw, meta=meta)


def _source_result(resp: requests.Response, obj_type: str, name: str) -> AdtResult:
    data = parse_source.parse(resp.content)
    return _structured("source", data, _obj(obj_type, name), raw=None)


def _xattr(s: str) -> str:
    """Escape a string for safe embedding inside a double-quoted XML attribute value."""
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def get_program(program_name: str) -> AdtResult:
    try:
        resp = make_adt_request(f"{_base()}/sap/bc/adt/programs/programs/{_enc(program_name)}/source/main")
        return _source_result(resp, "program", program_name)
    except Exception as e:
        return _err(e)


def get_class(class_name: str) -> AdtResult:
    try:
        resp = make_adt_request(f"{_base()}/sap/bc/adt/oo/classes/{_enc(class_name)}/source/main")
        return _source_result(resp, "class", class_name)
    except Exception as e:
        return _err(e)


def get_function_group(function_group: str) -> AdtResult:
    try:
        resp = make_adt_request(f"{_base()}/sap/bc/adt/functions/groups/{_enc(function_group)}/source/main")
        return _source_result(resp, "function-group", function_group)
    except Exception as e:
        return _err(e)


def get_function(function_name: str, function_group: str) -> AdtResult:
    try:
        url = (
            f"{_base()}/sap/bc/adt/functions/groups/{_enc(function_group)}"
            f"/fmodules/{_enc(function_name)}/source/main"
        )
        return _source_result(make_adt_request(url), "function", function_name)
    except Exception as e:
        return _err(e)


def _fields_result(resp: requests.Response, obj_type: str, name: str) -> AdtResult:
    parsed = parse_fields.parse(resp.content)
    unparsed = parsed.pop("unparsed_types", [])
    meta = {"unparsed_types": unparsed} if unparsed else None
    return _structured("fields", parsed, _obj(obj_type, name), raw=resp.text, meta=meta)


def get_structure(structure_name: str) -> AdtResult:
    try:
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/ddic/structures/{_enc(structure_name)}/source/main"
        )
        return _fields_result(resp, "structure", structure_name)
    except Exception as e:
        return _err(e)


def get_table(table_name: str) -> AdtResult:
    try:
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/ddic/tables/{_enc(table_name)}/source/main"
        )
        return _fields_result(resp, "table", table_name)
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
        data = parse_objects.parse(resp.content)
        return _structured("objects", data, _obj("package", package_name), raw=resp.text)
    except Exception as e:
        return _err(e)


def get_type_info(type_name: str) -> AdtResult:
    # Domain metadata resource is /ddic/domains/{name} (v2); the old
    # .../source/main path 404s on modern releases. Fall back to the data
    # element only for a genuine 404; the parser reports resolved_as.
    try:
        resp = make_adt_request(f"{_base()}/sap/bc/adt/ddic/domains/{_enc(type_name)}")
        data = parse_scalar.parse(resp.content)
        return _structured("scalar", data, _obj("type", type_name), raw=resp.text)
    except AdtHttpError as e:
        if e.status != 404:
            return _err(e)
    except Exception as e:
        return _err(e)
    try:
        resp = make_adt_request(f"{_base()}/sap/bc/adt/ddic/dataelements/{_enc(type_name)}")
        data = parse_scalar.parse(resp.content)
        return _structured("scalar", data, _obj("type", type_name), raw=resp.text)
    except Exception as e:
        return _err(e)


def get_include(include_name: str) -> AdtResult:
    try:
        resp = make_adt_request(f"{_base()}/sap/bc/adt/programs/includes/{_enc(include_name)}/source/main")
        return _source_result(resp, "include", include_name)
    except Exception as e:
        return _err(e)


def get_interface(interface_name: str) -> AdtResult:
    try:
        resp = make_adt_request(f"{_base()}/sap/bc/adt/oo/interfaces/{_enc(interface_name)}/source/main")
        return _source_result(resp, "interface", interface_name)
    except Exception as e:
        return _err(e)


def get_transaction(transaction_name: str) -> AdtResult:
    try:
        url = (
            f"{_base()}/sap/bc/adt/repository/informationsystem/objectproperties/values"
            f"?uri=%2Fsap%2Fbc%2Fadt%2Fvit%2Fwb%2Fobject_type%2Ftrant%2Fobject_name%2F{_enc(transaction_name)}"
            f"&facet=package&facet=appl"
        )
        resp = make_adt_request(url)
        data = parse_scalar.parse(resp.content)
        return _structured("scalar", data, _obj("transaction", transaction_name), raw=resp.text)
    except Exception as e:
        return _err(e)


def search_object(query: str, max_results: int = 100) -> AdtResult:
    try:
        url = (
            f"{_base()}/sap/bc/adt/repository/informationsystem/search"
            f"?operation=quickSearch&query={_enc(query)}&maxResults={max_results}"
        )
        resp = make_adt_request(url)
        data = parse_objects.parse(resp.content)
        return _structured("objects", data, _obj("search", query), raw=resp.text)
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



def syntax_check(
    object_type: str,
    object_name: str,
    group: Optional[str] = None,
) -> AdtResult:
    try:
        uri = get_object_uri(object_type, object_name, group=group)
        name = _xattr(object_name.upper())
        # New check-run resource (the legacy /abapsource/syntaxcheck returns
        # 404 on modern releases): checkObjectList request, checkmessages reply.
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<chk:checkObjectList xmlns:chk="http://www.sap.com/adt/checkrun" '
            'xmlns:adtcore="http://www.sap.com/adt/core">'
            f'<chk:checkObject adtcore:uri="{_xattr(uri)}" adtcore:name="{name}">'
            '<chk:reporter chk:name="abapCheckRun"/>'
            '</chk:checkObject>'
            '</chk:checkObjectList>'
        ).encode("utf-8")
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/checkruns",
            method="POST",
            data=body,
            extra_headers={
                "Content-Type": "application/vnd.sap.adt.checkobjects+xml",
                "Accept": "application/vnd.sap.adt.checkmessages+xml",
            },
        )
        data = parse_findings.parse(resp.content)
        return _structured("findings", data, _obj(object_type, object_name), raw=resp.text)
    except ValueError as e:
        return _err(e)
    except Exception as e:
        return _err(e)


def get_cds_view(name: str) -> AdtResult:
    try:
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/ddic/ddl/sources/{_enc(name)}/source/main"
        )
        return _source_result(resp, "cds-view", name)
    except Exception as e:
        return _err(e)


def get_type_group(name: str) -> AdtResult:
    try:
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/typegroups/groups/{_enc(name)}/source/main"
        )
        return _source_result(resp, "type-group", name)
    except Exception as e:
        return _err(e)


def where_used(
    object_type: str,
    object_name: str,
    max_results: int = 50,
    group: Optional[str] = None,
) -> AdtResult:
    # New POST-only usageReferences resource. Per the abap-adt-api reference
    # implementation the uri query parameter is the RELATIVE, lower-case
    # object URI and both content types are application/*.
    usage_body = (
        '<?xml version="1.0" encoding="ASCII"?>'
        '<usagereferences:usageReferenceRequest '
        'xmlns:usagereferences="http://www.sap.com/adt/ris/usageReferences">'
        '<usagereferences:affectedObjects/>'
        '</usagereferences:usageReferenceRequest>'
    ).encode("utf-8")
    try:
        uri = get_object_uri(object_type, object_name, group=group).lower()
        try:
            resp = make_adt_request(
                f"{_base()}/sap/bc/adt/repository/informationsystem/usageReferences",
                method="POST",
                params={"uri": uri},
                data=usage_body,
                extra_headers={"Content-Type": "application/*", "Accept": "application/*"},
                timeout=120,
            )
        except AdtHttpError as e:
            # Older releases: the legacy GET whereused resource.
            if e.status not in (404, 405):
                raise
            resp = make_adt_request(
                f"{_base()}/sap/bc/adt/repository/informationsystem/whereused",
                params={"uri": f"{_base()}{uri}", "maxResults": max_results},
                extra_headers={
                    "Accept": (
                        "application/vnd.sap.adt.repository.informationsystem.whereused+xml"
                    )
                },
            )
        data = parse_objects.parse(resp.content)
        data["objects"] = data["objects"][:max_results]
        return _structured("objects", data, _obj(object_type, object_name), raw=resp.text)
    except ValueError as e:
        return _err(e)
    except Exception as e:
        return _err(e)


def run_sql(sql: str, max_rows: int = 100) -> AdtResult:
    url = f"{_base()}/sap/bc/adt/datapreview/freestyle"
    # Modern releases accept the SQL only as a POST body (GET -> 405);
    # older releases took sqlCommand as a GET query parameter. Try POST
    # first and fall back to GET on 405 for those systems. DML is rejected
    # earlier, in the CLI before any request is sent.
    try:
        try:
            resp = make_adt_request(
                url,
                method="POST",
                params={"rowNumber": max_rows},
                data=sql.encode("utf-8"),
                extra_headers={
                    "Content-Type": "text/plain; charset=utf-8",
                    "Accept": "application/vnd.sap.adt.datapreview.table.v1+xml",
                },
                timeout=60,
            )
        except AdtHttpError as e:
            if e.status != 405:
                raise
            resp = make_adt_request(
                url,
                params={"rowNumber": max_rows, "sqlCommand": sql},
                extra_headers={
                    "Accept": "application/vnd.sap.adt.datapreview.table.v1+xml"
                },
            )
        data = parse_rows.parse(resp.content)
        return _structured("rows", data, {"type": "run-sql", "name": None}, raw=resp.text)
    except Exception as e:
        return _err(e)


def list_transports(user: str = "", status: str = "D") -> AdtResult:
    # New transport-organizer tree resource (the legacy /cts/transports
    # worklist document returns 406 on modern releases).
    try:
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/cts/transportrequests",
            extra_headers={
                "Accept": "application/vnd.sap.adt.transportorganizertree.v1+xml"
            },
        )
        data = parse_records.parse(resp.content)
        records = data["transports"]
        # --user/--status stay supported via client-side filtering.
        if user:
            records = [t for t in records if (t.get("owner") or "").upper() == user.upper()]
        if status:
            records = [t for t in records if (t.get("status") or "").upper() == status.upper()]
        return _structured("records", {"transports": records}, None, raw=resp.text)
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
        return _err(e)
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
