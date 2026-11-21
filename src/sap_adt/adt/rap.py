"""Read-only RAP evidence and bounded, same-origin OData runtime inspection."""
from __future__ import annotations

import json
import re
from urllib.parse import quote, unquote, urljoin, urlsplit

from . import client, handlers
from .parsers.common import ParseError, attr, localname, parse_xml

RESOURCES = {
    "cds": ("ddic/ddl/sources", "DDLS/DF", None),
    "bdef": ("bo/behaviordefinitions", "BDEF/BDO", None),
    "srvd": ("ddic/srvd/sources", "SRVD/SRV", None),
    "srvb": ("businessservices/bindings", "SRVB/SVB",
             "application/vnd.sap.adt.businessservices.servicebinding.v2+xml"),
}
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def _attributes(node):
    return {localname(k): v for k, v in node.attrib.items()}


def get_object(kind, name):
    """Fetch explicit object evidence; do not infer a complete dependency graph."""
    try:
        path, code, media = RESOURCES[kind]
        uri = "/sap/bc/adt/" + path + "/" + quote(name.lower(), safe="")
        if kind != "srvb":
            response = client.make_adt_request(handlers._base() + uri + "/source/main",
                                               allow_redirects=False)
            if response.status_code != 200:
                raise ParseError("RAP source did not return HTTP 200")
            return handlers._source_result(response, kind, name)
        response = client.make_adt_request(
            handlers._base() + uri, extra_headers={"Accept": media}, allow_redirects=False)
        if response.status_code != 200:
            raise ParseError("service binding did not return HTTP 200")
        root = parse_xml(response.content)
        if (localname(root.tag) != "serviceBinding" or
                (attr(root, "name") or "").upper() != name.upper() or attr(root, "type") != code):
            raise ParseError("service binding metadata identity mismatch")
        data = {"binding": _attributes(root), "uri": uri, "services": [], "evidence_gaps": []}
        data["status"] = {key: attr(root, key) for key in
                          ("published", "releaseSupported", "bindingCreated")
                          if attr(root, key) is not None}
        data["status"].update({localname(e.tag): (e.text or "").strip() for e in root
                          if localname(e.tag) in ("published", "releaseSupported", "bindingCreated")})
        binding = next((e for e in root if localname(e.tag) == "binding"), None)
        if binding is None:
            data["evidence_gaps"].append("binding protocol/version missing")
        else:
            data["protocol"] = _attributes(binding)
        version = attr(binding, "version") if binding is not None else None
        supported = binding is not None and attr(binding, "type") == "ODATA" and version in ("V2", "V4")
        services = [e for e in root if localname(e.tag) == "services"]
        if not services:
            data["evidence_gaps"].append("no service definitions declared")
        if len(services) > 10:
            data["evidence_gaps"].append("service discovery limited to first 10 definitions")
        for node in services[:10]:
            content = next((e for e in node if localname(e.tag) == "content"), None)
            definition = next((e for e in node.iter() if localname(e.tag) == "serviceDefinition"), None)
            service_name = attr(node, "name") or next(
                ((e.text or "").strip() for e in node if localname(e.tag) == "name"), None)
            record = {"name": service_name,
                      "content": _attributes(content) if content is not None else {},
                      "definition": _attributes(definition) if definition is not None else {},
                      "runtime": [], "evidence_gaps": []}
            data["services"].append(record)
            if sum(localname(e.tag) == "content" for e in node) > 1:
                record["evidence_gaps"].append("only the first service content/version was inspected")
            if not supported or not service_name or content is None or definition is None:
                record["evidence_gaps"].append("unsupported or incomplete OData binding/service declaration")
                continue
            service_version, definition_name = attr(content, "version"), attr(definition, "name")
            if not service_version or not definition_name:
                record["evidence_gaps"].append("service version/definition name missing")
                continue
            try:
                prefix = "application/vnd.sap.adt.businessservices.odata" + version[1]
                accepts = (f"{prefix}.v3+xml, {prefix}.v2+xml" if version == "V2"
                           else f"{prefix}.v2+xml, {prefix}.v1+xml")
                group = client.make_adt_request(
                    handlers._base() + "/sap/bc/adt/businessservices/odata" +
                    version[1] + "/" + quote(name.lower(), safe=""),
                    params={"servicename": service_name, "serviceversion": service_version,
                            "srvdname": definition_name},
                    extra_headers={"Accept": accepts}, allow_redirects=False)
                if group.status_code != 200:
                    raise ParseError("service group did not return HTTP 200")
                tree = parse_xml(group.content)
                if localname(tree.tag) != ("serviceList" if version == "V2" else "serviceGroup"):
                    raise ParseError("unrecognized OData service group document")
                record["group"] = _attributes(tree)
                for e in tree.iter():
                    if attr(e, "serviceUrl"):
                        record["runtime"].append(_attributes(e))
                if not record["runtime"]:
                    record["evidence_gaps"].append("no runtime service URL returned; publication/availability unconfirmed")
            except Exception as exc:
                error = handlers._err(exc)
                record["evidence_gaps"].append(
                    {"code": error.error_code, "message": error.text})
        partial = bool(data["evidence_gaps"] or any(
            s["evidence_gaps"] for s in data["services"]))
        return handlers.AdtResult(kind="scalar", data=data, object=handlers._obj(kind, name),
                                  raw=response.text, meta={"partial": partial})
    except Exception as exc:
        return handlers._err(exc)


def runtime_url(value):
    """Allow only SAP OData service roots on the configured origin."""
    if (any(ord(c) < 33 or ord(c) == 127 for c in value) or
            any(s in (".", "..") for s in unquote(urlsplit(value).path).split("/"))):
        raise ValueError("OData URL must not contain controls or dot segments")
    base = urlsplit(handlers._base())
    parsed = urlsplit(urljoin(handlers._base() + "/", value))

    def origin(url):
        return (url.scheme.lower(), url.hostname,
                url.port or {"http": 80, "https": 443}.get(url.scheme.lower()))

    if origin(parsed) != origin(base):
        raise ValueError("OData URL must use the configured SAP origin")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("OData service root must not contain credentials, query or fragment")
    decoded = unquote(parsed.path)
    if ("%" in decoded or "\\" in decoded or
            any(ord(c) < 33 or ord(c) == 127 for c in value + decoded) or
            any(s in (".", "..") for s in decoded.split("/")) or
            not decoded.startswith(("/sap/opu/odata/", "/sap/opu/odata4/")) or
            any(c in decoded for c in ("(", ")", "$", "?", "#"))):
        raise ValueError("expected a plain SAP OData service root, not an operation/entity/query URL")
    if re.search(r"%2f|%5c", parsed.path, re.I):
        raise ValueError("encoded path separators are not allowed")
    return parsed._replace(path=parsed.path.rstrip("/") + "/").geturl()


def _read(url, *, accept, max_bytes, params=None):
    response = client.make_adt_request(
        url, extra_headers={"Accept": accept}, params=params, timeout=30,
        retry_csrf=False, allow_redirects=False, stream=True)
    try:
        if response.status_code != 200:
            raise ParseError("OData read did not return HTTP 200 (redirects are not followed)")
        payload = bytearray()
        for chunk in response.iter_content(chunk_size=16384):
            payload.extend(chunk)
            if len(payload) > max_bytes:
                raise ParseError(f"OData response exceeds {max_bytes} byte budget")
        return bytes(payload)
    finally:
        response.close()


def read_odata(service_url, *, entity_set=None, top=20, max_bytes=2 * 1024 * 1024):
    """Inspect metadata, or GET one declared entity set; never follow next links."""
    try:
        if not 1 <= top <= 100 or not 1024 <= max_bytes <= 2 * 1024 * 1024:
            raise ValueError("OData budgets: top 1-100 and max-bytes 1024-2097152")
        if entity_set and not _IDENTIFIER.fullmatch(entity_set):
            raise ValueError("entity set must be a plain metadata-declared identifier")
        root_url = runtime_url(service_url)
        payload = _read(root_url + "$metadata", accept="application/xml", max_bytes=max_bytes)
        root = parse_xml(payload)
        if root.tag != "{http://docs.oasis-open.org/odata/ns/edmx}Edmx" and root.tag != "{http://schemas.microsoft.com/ado/2007/06/edmx}Edmx":
            raise ParseError("OData metadata is not an EDMX document")
        edm_namespaces = {
            "http://docs.oasis-open.org/odata/ns/edm",
            "http://schemas.microsoft.com/ado/2006/04/edm",
            "http://schemas.microsoft.com/ado/2007/05/edm",
            "http://schemas.microsoft.com/ado/2008/01/edm",
            "http://schemas.microsoft.com/ado/2008/09/edm",
            "http://schemas.microsoft.com/ado/2009/08/edm",
            "http://schemas.microsoft.com/ado/2009/11/edm",
        }
        sets = sorted({e.get("Name") for e in root.iter()
                       if any(e.tag == f"{{{ns}}}EntitySet" for ns in edm_namespaces)
                       and e.get("Name")})
        data = {"service_url": root_url, "entity_sets": sets,
                "metadata_bytes": len(payload), "evidence_gaps": [],
                "runtime_endpoint": True, "pagination": "not_followed"}
        if entity_set is None:
            return handlers.AdtResult(kind="scalar", data=data,
                                      raw=payload.decode("utf-8"))
        if entity_set not in sets:
            raise ValueError("entity set is not declared in service metadata; operations are not allowed")
        remaining = max_bytes - len(payload)
        rows_payload = _read(root_url + entity_set, accept="application/json",
                             params={"$top": top}, max_bytes=remaining)
        document = json.loads(rows_payload)
        container = document.get("d", document) if isinstance(document, dict) else None
        if not isinstance(container, dict):
            raise ParseError("OData response is not a collection object")
        rows = container.get("results", container.get("value"))
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ParseError("OData response contains no entity collection")
        next_page = bool(container.get("__next") or container.get("@odata.nextLink"))
        over_limit = len(rows) > top
        rows = rows[:top]
        columns = sorted({key for row in rows for key in row})
        data.update({"columns": [{"name": key, "type": None} for key in columns],
                     "rows": [[row.get(key) for key in columns] for row in rows],
                     "entity_set": entity_set, "requested_top": top,
                     "returned": len(rows), "truncated": over_limit or next_page,
                     "limit_reached": len(rows) == top, "scope": "bounded_preview",
                     "next_link_present": next_page, "response_bytes": len(rows_payload)})
        return handlers.AdtResult(kind="rows", data=data)
    except Exception as exc:
        return handlers._err(exc)
