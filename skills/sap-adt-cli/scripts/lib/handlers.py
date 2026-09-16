import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import requests

from . import coverage as coverage_lib
from . import errors
from .client import AdtHttpError, make_adt_request
from .config import get_config
from .parsers import capabilities as parse_capabilities
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


def discovery() -> AdtResult:
    try:
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/discovery",
            extra_headers={"Accept": "application/atomsvc+xml, application/*"},
        )
        data = parse_capabilities.parse(resp.content)
        return _structured("capabilities", data,
                           {"type": "discovery", "name": None}, raw=resp.text)
    except Exception as e:
        return _err(e)


def coverage() -> AdtResult:
    """Coverage report (raw text for the CLI; structured data in .data)."""
    result = discovery()
    if result.is_error:
        return result
    report = coverage_lib.compute_coverage(result.data["collections"])
    return AdtResult(
        kind="raw",
        data=report,
        text=coverage_lib.render_text(report),
    )


AUNIT_VERSIONS = ("v4", "v3", "v2", "v1")


def _unit_uri(object_type: str, object_name: str, group: Optional[str]) -> str:
    """Semantic, lower-case object URI for AUnit (class tested directly)."""
    t = object_type.lower()
    name = (object_name or "").lower()
    if t == "class":
        return f"/sap/bc/adt/oo/classes/{_enc(name)}"
    if t == "interface":
        return f"/sap/bc/adt/oo/interfaces/{_enc(name)}"
    if t == "include":
        return f"/sap/bc/adt/programs/includes/{_enc(name)}"
    if t == "program":
        return f"/sap/bc/adt/programs/programs/{_enc(name)}"
    if t == "function":
        if not group:
            raise ValueError("--group is required when OBJECT_TYPE is 'function'")
        return f"/sap/bc/adt/functions/groups/{_enc(group.lower())}/fmodules/{_enc(name)}"
    raise ValueError(
        f"Unsupported type: {object_type!r}. "
        "program / class / interface / include / function"
    )


def _unit_body(uri: str, *, harmless: bool, dangerous: bool, critical: bool,
               duration: str) -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<aunit:runConfiguration xmlns:aunit="http://www.sap.com/adt/aunit">
<options>
<uriType value="semantic"/>
<testDeterminationStrategy sameProgram="true" assignedTests="false"/>
<testRiskLevels harmless="{str(harmless).lower()}" dangerous="{str(dangerous).lower()}" critical="{str(critical).lower()}"/>
<testDurations short="{str(duration=='short').lower()}" medium="{str(duration=='medium').lower()}" long="{str(duration=='long').lower()}"/>
<withNavigationUri enabled="true"/>
</options>
<adtcore:objectSets xmlns:adtcore="http://www.sap.com/adt/core">
<objectSet kind="inclusive"><adtcore:objectReferences>
<adtcore:objectReference adtcore:uri="{uri}"/>
</adtcore:objectReferences></objectSet>
</adtcore:objectSets>
</aunit:runConfiguration>'''.encode("utf-8")


AUNIT_CONFIG_V4 = "application/vnd.sap.adt.abapunit.testruns.config.v4+xml"
AUNIT_ACCEPT = (
    "application/vnd.sap.adt.abapunit.testruns.result.v2+xml, application/*"
)


def run_unit_test(object_type: str, object_name: str, group: Optional[str] = None,
                  risk_level: str = "harmless", duration: str = "short") -> AdtResult:
    if risk_level not in ("harmless", "dangerous", "critical"):
        return _err(ValueError(
            "risk-level must be harmless, dangerous or critical"
        ))
    if duration not in ("short", "medium", "long"):
        return _err(ValueError("duration must be short, medium or long"))
    try:
        uri = _unit_uri(object_type, object_name, group)
        risks = {
            "harmless": (True, False, False),
            "dangerous": (False, True, False),
            "critical": (False, False, True),
        }[risk_level]
        body = _unit_body(uri, harmless=risks[0], dangerous=risks[1],
                          critical=risks[2], duration=duration)
        url = f"{_base()}/sap/bc/adt/abapunit/testruns"
        config_version = "v4"
        fallback = False
        try:
            resp = make_adt_request(
                url, method="POST", data=body, timeout=300,
                extra_headers={"Content-Type": AUNIT_CONFIG_V4,
                               "Accept": AUNIT_ACCEPT},
            )
        except AdtHttpError as e:
            if e.status not in (400, 406, 415):
                raise
            resp = make_adt_request(
                url, method="POST", data=body, timeout=300,
                extra_headers={"Content-Type": "application/*",
                               "Accept": "application/*"},
            )
            config_version = "application/*"
            fallback = True
        parsed = parse_findings.parse_unit(resp.content)
        meta = parsed.pop("_meta")
        meta["risk_level"] = risk_level
        meta["config_version"] = config_version
        if fallback:
            meta["config_version_fallback"] = True
        return _structured("findings", parsed, _obj(object_type, object_name),
                           raw=resp.text, meta=meta)
    except ValueError as e:
        return _err(e)
    except Exception as e:
        return _err(e)


def run_atc(object_type: str, object_name: str, group: Optional[str] = None,
            variant: str = "STANDARD", max_results: int = 100) -> AdtResult:
    """Run ATC checks (static, no gate): worklist -> run -> worklist GET."""
    try:
        uri = _unit_uri(object_type, object_name, group)
        # 1) create a worklist for the variant -> plain-text GUID
        wl = make_adt_request(
            f"{_base()}/sap/bc/adt/atc/worklists",
            method="POST",
            params={"checkVariant": variant},
            extra_headers={"Accept": "text/plain"},
            timeout=120,
        )
        worklist_id = wl.text.strip()
        # 2) trigger the run (synchronous on this release; returns worklistRun)
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<atc:run maximumVerdicts="{max_results}" xmlns:atc="http://www.sap.com/adt/atc">'
            '<objectSets xmlns:adtcore="http://www.sap.com/adt/core">'
            '<objectSet kind="inclusive"><adtcore:objectReferences>'
            f'<adtcore:objectReference adtcore:uri="{uri}"/>'
            '</adtcore:objectReferences></objectSet>'
            '</objectSets></atc:run>'
        ).encode("utf-8")
        make_adt_request(
            f"{_base()}/sap/bc/adt/atc/runs",
            method="POST",
            params={"worklistId": worklist_id},
            data=body,
            extra_headers={"Accept": "application/xml",
                           "Content-Type": "application/xml"},
            timeout=300,
        )
        # 3) fetch the populated worklist
        def fetch():
            return make_adt_request(
                f"{_base()}/sap/bc/adt/atc/worklists/{worklist_id}",
                extra_headers={"Accept": "application/atc.worklist.v1+xml"},
                timeout=120,
            )
        resp = fetch()
        parsed = parse_findings.parse_atc(resp.content)
        meta = parsed.pop("_meta")
        if meta.get("result_incomplete"):
            # Object set not fully evaluated yet: re-fetch exactly once (no
            # poll loop); if still incomplete the flag stays in meta and the
            # caller sees result_incomplete:true plus the smaller-set advice.
            resp = fetch()
            parsed = parse_findings.parse_atc(resp.content)
            meta = parsed.pop("_meta")
        return _structured("findings", parsed, _obj(object_type, object_name),
                           raw=resp.text, meta=meta)
    except ValueError as e:
        return _err(e)
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
    # Modern protocol (verified S/4HANA 2021 / Basis 7.56, 2026-09-16):
    # POST ?_action=LOCK returns an ABAP-serialized payload
    # (application/vnd.sap.as+xml; dataname=com.sap.adt.lock.result):
    # asx:abap/asx:values/DATA/LOCK_HANDLE.
    if resp.text:
        try:
            root = ET.fromstring(resp.text)
            for elem in root.iter():
                if _tag_local(elem) == "LOCK_HANDLE" and elem.text:
                    return elem.text.strip()
        except ET.ParseError:
            pass
    # Legacy shape: handle in response header, or <handle>/<lockHandle> XML.
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
        # The Data Preview rowNumber parameter (--max-rows) is the hard cap;
        # verified 2026-09-16: an SQL "UP TO N ROWS" clause is IGNORED when
        # rowNumber is present (tests: UP TO 5/100 -> 100 rows, UP TO 200/10
        # -> 10 rows, no UP TO/7 -> 7 rows). Surface this instead of letting
        # the SQL clause silently mislead callers.
        meta = {"row_limit_applied": max_rows, "row_limit_source": "rowNumber"}
        m = re.search(r"\bUP\s+TO\s+(\d+)\s+ROWS?\b", sql, re.IGNORECASE)
        if m:
            meta["sql_up_to"] = int(m.group(1))
            if m and meta["sql_up_to"] != max_rows:
                meta["row_limit_conflict"] = True
        return _structured("rows", data, {"type": "run-sql", "name": None},
                           raw=resp.text, meta=meta)
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
    # Verified 2026-09-16 on S/4HANA 2021 / Basis 7.56: enqueue is
    # POST <object>?_action=LOCK&accessMode=MODIFY with the stateful session
    # header and the lock.result ASX accept type; the handle comes back as
    # LOCK_HANDLE in the ASX body (the legacy ?method=lock form is rejected
    # with 400 "Content type missing" / 415 on this release).
    try:
        resp = make_adt_request(
            f"{_base()}{object_uri}",
            method="POST",
            params={"_action": "LOCK", "accessMode": "MODIFY"},
            extra_headers={
                "X-sap-adt-sessiontype": "stateful",
                "Accept": (
                    "application/*,application/vnd.sap.as+xml;charset=UTF-8;"
                    "dataname=com.sap.adt.lock.result"
                ),
            },
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
    # Verified 2026-09-16 on Basis 7.56: the lock handle travels as the
    # ?lockHandle= QUERY parameter (not the X-sap-adt-lock-handle header),
    # and a chosen transport is ?corrNr= (legacy name sap-cts-request is
    # ignored). The PUT is part of the stateful session that owns the lock.
    try:
        params: dict = {"lockHandle": lock_handle}
        if transport:
            params["corrNr"] = transport
        make_adt_request(
            f"{_base()}{object_uri}/source/main",
            method="PUT",
            data=content.encode("utf-8"),
            params=params,
            extra_headers={
                "Content-Type": "text/plain; charset=utf-8",
                "X-sap-adt-sessiontype": "stateful",
            },
        )
        return AdtResult(text="OK")
    except Exception as e:
        return _err(e)


def unlock_object(object_uri: str, lock_handle: str) -> AdtResult:
    # Verified 2026-09-16/17 on Basis 7.56: dequeue is
    # POST <object>?_action=UNLOCK&lockHandle=<handle>. A 200 empty body is
    # NOT proof of release: from a foreign stateful context (no original
    # cookie) it is a measured silent no-op. The normal write-source flow
    # calls this in `finally` within the owning session, and real release
    # was confirmed by an independent fresh-process re-lock 200.
    try:
        make_adt_request(
            f"{_base()}{object_uri}",
            method="POST",
            params={"_action": "UNLOCK", "lockHandle": lock_handle},
            extra_headers={"X-sap-adt-sessiontype": "stateful"},
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
        # Verified 2026-09-16 on Basis 7.56: activation REQUIRES the
        # ?method=activate query parameter (bare POST /activation -> 400
        # ExceptionParameterNotFound "Parameter method could not be found").
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/activation",
            method="POST",
            params={"method": "activate", "preauditRequested": "true"},
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
    package: str,
    description: str,
    ref: str,
) -> AdtResult:
    # Verified 2026-09-17 on S/4HANA 2021 / Basis 7.56: request creation is
    # the ABAP-serialized CreateCorrectionRequest (ASX body of
    # DEVCLASS/REQUEST_TEXT/REF/OPERATION), not a CTS resource document.
    # The legacy cts:transportRequest+xml shape returns 400
    # ExceptionDataTypeNotFound ("No data type found in content type").
    # DEVCLASS + REF is the only measured working combination (both
    # required); "$TMP" creates a local, non-releasable request; the body
    # is text/plain "/com.sap.cts/object_record/<TRKORR>".
    try:
        package = (package or "").strip()
        description = (description or "").strip()
        ref = (ref or "").strip()
        if not package or not description or not ref:
            raise ValueError(
                "create-transport requires --package, --description and --ref"
            )
        if not ref.startswith("/sap/bc/adt/"):
            raise ValueError(
                f"--ref must be a relative ADT object URI (got {ref!r})"
            )
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<asx:abap xmlns:asx="http://www.sap.com/abapxml" version="1.0">'
            "<asx:values><DATA>"
            f"<DEVCLASS>{_xattr(package)}</DEVCLASS>"
            f"<REQUEST_TEXT>{_xattr(description)}</REQUEST_TEXT>"
            f"<REF>{_xattr(ref)}</REF>"
            "<OPERATION>I</OPERATION>"
            "</DATA></asx:values>"
            "</asx:abap>"
        ).encode("utf-8")
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/cts/transports",
            method="POST",
            data=body,
            extra_headers={
                "Accept": "text/plain",
                "Content-Type": (
                    "application/vnd.sap.as+xml; charset=UTF-8; "
                    "dataname=com.sap.adt.CreateCorrectionRequest"
                ),
            },
        )
        trkorr = (resp.text or "").strip().rstrip("/").rsplit("/", 1)[-1]
        if not _valid_trkorr(trkorr):
            return _err(ValueError(
                f"Transport creation returned an unreadable TRKORR: "
                f"{(resp.text or '').strip()[:120]!r}"
            ))
        return AdtResult(text=f"Created transport: {trkorr}")
    except Exception as e:
        return _err(e)


def _valid_trkorr(trkorr: str) -> bool:
    t = (trkorr or "").upper()
    return len(t) == 10 and t[0].isalpha() and t[1:].isalnum()


def transport_preflight(trkorr: str) -> tuple[AdtResult, dict | None]:
    """Read a single request: existence, owner, current status."""
    if not _valid_trkorr(trkorr):
        return _err(ValueError(f"Invalid transport number: {trkorr}")), None
    try:
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/cts/transportrequests/{_enc(trkorr.upper())}",
            extra_headers={"Accept":
                           "application/vnd.sap.adt.transportorganizer.v1+xml"},
        )
        parsed = parse_records.parse_single_request(resp.content)
        return _structured("records", parsed, {"type": "transport", "name": trkorr.upper()},
                           raw=resp.text), parsed["transport"]
    except AdtHttpError as e:
        # The transport organizer reports a missing request as HTTP 400
        # ADT_TM_COMMON_EXCEPTION "... does not exist in system".
        if e.status == 400 and "does not exist in system" in str(e).lower():
            return AdtResult(text=str(e), is_error=True,
                             error_code=errors.OBJECT_NOT_FOUND,
                             http_status=404, hint=errors.DEFAULT_HINTS[errors.OBJECT_NOT_FOUND]), None
        return _err(e), None
    except Exception as e:
        return _err(e), None


def release_transport(trkorr: str, *, dry_run: bool = False, progress=None,
                      poll_interval: float = 2.0, timeout: float = 120.0,
                      sleep=None) -> AdtResult:
    """Release a request (newreleasejobs) and verify TRSTATUS readback.

    Preflight → POST release jobs → poll the single-request resource until
    status R. D after the timeout is a definite rejection; an unknown final
    state is UNVERIFIED (never re-release automatically).
    """
    import time as _time
    sleep = sleep or _time.sleep
    pre, request = transport_preflight(trkorr)
    if pre.is_error:
        return pre
    if dry_run:
        pre.meta = {
            "dry_run": True,
            "release_possible": request["status"] == "D",
            "checks": {
                "exists": True,
                "owner": request["owner"],
                "status": request["status"],
                "modifiable": request["status"] == "D",
            },
        }
        return pre

    if request["status"] == "R":
        pre.meta = {"released": True, "already_released": True}
        return pre

    try:
        resp = make_adt_request(
            f"{_base()}/sap/bc/adt/cts/transportrequests/"
            f"{_enc(trkorr.upper())}/newreleasejobs",
            method="POST",
            extra_headers={"Accept": "application/*"},
            timeout=300,
        )
        report = parse_records.parse_release_report(resp.content)
        failed_reports = [
            r for r in report["release_reports"]
            if (r.get("status") or "").lower() in ("abortrelapifail", "aborted")
            or any((m.get("severity") or "").upper() == "E" for m in r.get("messages", []))
        ]
        if failed_reports:
            msgs = "; ".join(
                m["text"] for r in failed_reports for m in r["messages"] if m.get("text")
            )
            return AdtResult(
                text=f"Transport {trkorr.upper()} release rejected: {msgs or 'check failure'}",
                is_error=True, error_code=errors.RELEASE_REJECTED,
            )
    except Exception as e:
        return _err(e)

    # Release jobs run asynchronously: read back TRSTATUS with a hard timeout.
    deadline = _time.monotonic() + timeout
    attempt = 0
    last_status = request["status"]
    while _time.monotonic() < deadline:
        attempt += 1
        if progress:
            progress(f"Release job submitted; reading status (attempt {attempt})…")
        sleep(poll_interval)
        check, current = transport_preflight(trkorr)
        if check.is_error:
            # Readback failed: the release itself may still be running.
            return AdtResult(
                text=(f"Transport {trkorr.upper()} release requested, but status "
                      f"readback failed after {attempt} attempts; status unknown."),
                is_error=True, error_code=errors.RELEASE_UNVERIFIED,
            )
        last_status = current["status"]
        if last_status == "R":
            check.meta = {"released": True, "poll_attempts": attempt}
            return check
    if last_status == "D":
        return AdtResult(
            text=f"Transport {trkorr.upper()} is still modifiable (D) after {timeout:.0f}s.",
            is_error=True, error_code=errors.RELEASE_REJECTED,
        )
    return AdtResult(
        text=(f"Transport {trkorr.upper()} release requested; final status "
              f"{last_status or 'unknown'} after {timeout:.0f}s."),
        is_error=True, error_code=errors.RELEASE_UNVERIFIED,
    )
