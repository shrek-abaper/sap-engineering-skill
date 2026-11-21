"""Discovery-negotiated repository definitions and explicit, bounded deletion."""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

from .. import errors
from . import client, development, handlers
from .parsers.common import ParseError, attr, localname, parse_xml

XML_TYPES = ("domain", "data-element", "srvb")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def negotiate_mime(kind):
    spec = development.SPECS[kind]
    primary = "application/vnd.sap.adt." + spec[4] + "+xml"
    alternatives = {
        "function-group": ["functions.groups.v2"],
        "function": ["functions.fmodules.v2"],
        "function-include": ["functions.fincludes"],
        "data-element": ["dataelements.v1"],
        "srvb": ["businessservices.servicebinding.v1"],
        "cds": ["ddlSource.v2"],
    }
    known = [primary] + ["application/vnd.sap.adt." + v + "+xml"
                         for v in alternatives.get(kind, [])]
    result = handlers.discovery()
    if result.is_error:
        raise ValueError("discovery unavailable: " + result.text)
    path = "/sap/bc/adt/" + spec[0]
    offered = set()
    collections = result.data["collections"]
    resources = collections + [t for c in collections for t in c.get("templates", [])]
    for collection in resources:
        href = urlsplit(collection.get("href") or "").path.rstrip("/")
        normalized = re.sub(r"\{[^}]+\}", "{group}", href)
        if normalized == path:
            offered.update(t.split(";")[0].strip() for t in collection.get("content_types", []))
    for mime in known:
        if mime in offered:
            return mime
    raise ValueError(f"{kind}: discovery does not advertise a supported creation/definition MIME")


def _read(uri, *, stateful=False, version=None):
    response = client.make_adt_request(handlers._base() + uri,
        params={"version": version} if version else None,
        extra_headers={"X-sap-adt-sessiontype": "stateful"} if stateful else None,
        allow_redirects=False)
    if response.status_code != 200:
        raise ParseError("definition read did not return HTTP 200")
    return parse_xml(response.content)


def verify_creation(plan):
    root = _read(plan["object"]["uri"])
    if plan.get("group"):
        nodes = [e for e in root if localname(e.tag) == "containerRef"]
        if len(nodes) != 1 or (attr(nodes[0], "name") or "").upper() != plan["group"].upper():
            raise ParseError("created function parent differs from reviewed group")
    if plan["object"]["type"] == "srvb":
        bindings = [e for e in root.iter() if localname(e.tag) == "binding"]
        services = [e for e in root.iter() if localname(e.tag) == "serviceDefinition"]
        if (len(bindings) != 1 or attr(bindings[0], "version") != plan["binding_protocol"]
                or attr(bindings[0], "category") != plan["binding_category"]
                or len(services) != 1
                or attr(services[0], "name") != plan["service_definition"].upper()):
            raise ParseError("created binding differs from reviewed definition/protocol/category")
        _unpublished(root)


def _unpublished(root):
    flags = [value.lower() for e in root.iter() for key, value in e.attrib.items()
             if localname(key) == "published"]
    if not flags or any(v != "false" for v in flags):
        raise ValueError("published or unconfirmed service binding cannot be deleted/accepted")


def _identity(root, kind, name):
    spec = development.SPECS[kind]
    ns = spec[2] if spec[2].startswith("http:") else "http://www.sap.com/adt/" + spec[2]
    if (root.tag != f"{{{ns}}}{spec[3]}" or attr(root, "name") != name.upper()
            or attr(root, "type") != spec[1]):
        raise ValueError("XML definition identity/type does not match the selected object")


def _tree(root):
    return [root.tag, sorted(root.attrib.items()), (root.text or "").strip(),
            [_tree(e) for e in root]]


def _content(root):
    return [_tree(e) for e in root
            if localname(e.tag) not in ("link", "packageRef", "containerRef")]


def definition(kind, name, group=None):
    if kind not in XML_TYPES:
        raise ValueError("XML definition reads support domain, data-element and srvb")
    root = _read(development.object_uri(kind, name, group))
    _identity(root, kind, name)
    return {"object": {"type": kind, "name": name.upper()},
            "xml": ET.tostring(root, encoding="unicode"), "sha256": digest(_tree(root)),
            "editable": kind != "srvb"}


def plan(kind, name, *, target, transport=None, group=None, content=None, delete=False):
    uri = development.object_uri(kind, name, group)
    root = _read(uri)
    _identity(root, kind, name)
    meta = development.metadata(uri)
    package = meta["package"]
    if not package:
        raise ValueError("object package is unconfirmed")
    development._dependencies(kind, package, transport)
    if not package.startswith("$") and not transport:
        raise ValueError("non-local mutation requires an explicit transport")
    if package.startswith("$") and transport:
        raise ValueError("local objects must not specify a transport")
    if delete:
        if not development.customer_name(kind, name.upper(), group):
            raise ValueError("deletion requires an explicit customer-namespace object")
        if kind in ("table", "package", "function-group"):
            raise ValueError("table deletion and container/cascade deletion are excluded")
        if kind == "srvb":
            _unpublished(root)
    else:
        if kind not in ("domain", "data-element"):
            raise ValueError("XML updates support domain/data-element only; SRVB update is unproven")
        candidate = parse_xml(content.encode("utf-8"))
        _identity(candidate, kind, name)
        if [(e.tag, sorted(e.attrib.items())) for e in candidate if localname(e.tag) == "packageRef"] != [
                (e.tag, sorted(e.attrib.items())) for e in root if localname(e.tag) == "packageRef"]:
            raise ValueError("definition updates cannot change the package")
        # Existing domains may back populated tables; changing their storage type
        # requires conversion evidence that this workflow deliberately cannot infer.
        storage = ({"typeInformation"} if kind == "domain" else {
            "typeKind", "typeName", "dataType", "dataTypeLength", "dataTypeDecimals"})
        before = [_tree(e) for e in root.iter() if localname(e.tag) in storage]
        after = [_tree(e) for e in candidate.iter() if localname(e.tag) in storage]
        if before != after:
            try:
                active = _read(uri, version="active")
            except Exception as exc:
                if errors.classify(exc).code != errors.OBJECT_NOT_FOUND:
                    raise ValueError("unconfirmed active definition; storage-type change refused") from exc
            else:
                _identity(active, kind, name)
                if attr(root, "version") != "new" or attr(active, "version") != "new":
                    raise ValueError("DDIC storage-type changes require a separate conversion assessment")
    data = {"action": "delete" if delete else "write-definition", "target": target,
            "object": {"type": kind, "name": name.upper(), "group": group, "uri": uri},
            "transport": transport, "baseline_sha256": digest(_tree(root)),
            "content": content, "metadata": meta,
            "content_type": None if delete else negotiate_mime(kind)}
    data["plan_sha256"] = digest(data)
    return data


def execute(plan):
    data = {"plan": plan, "mutation": "not_attempted", "readback": "not_attempted",
            "lock": "not_required", "unlock": "not_required", "outcome": "not_changed"}
    uri, handle = plan["object"]["uri"], None
    primary = None
    uncertain_codes = (None, errors.NETWORK_ERROR, errors.SERVER_ERROR,
                       errors.PARSE_FAILED, errors.WRITE_INCOMPLETE)
    try:
        if digest(_tree(_read(uri))) != plan["baseline_sha256"]:
            primary = errors.decision(errors.BASELINE_CHANGED, "definition changed after confirmation")
            raise ValueError(primary.message)
        client.prepare_csrf()
        if plan["action"] == "delete":
            ns = "http://www.sap.com/adt/deletion"
            body = ET.Element(f"{{{ns}}}deletionRequest")
            obj = ET.SubElement(body, f"{{{ns}}}object", {f"{{{development.CORE}}}uri": uri})
            ET.SubElement(obj, f"{{{ns}}}transportNumber").text = plan["transport"] or ""
            data["mutation"], data["outcome"] = "unknown", "incomplete"
            response = client.make_adt_request(handlers._base() + "/sap/bc/adt/deletion/delete",
                method="POST", data=ET.tostring(body, encoding="utf-8", xml_declaration=True),
                extra_headers={"Content-Type": "application/vnd.sap.adt.deletion.request.v1+xml"},
                retry_csrf=False, allow_redirects=False)
            if not 200 <= response.status_code < 300:
                raise ParseError("unexpected deletion response")
            result = parse_xml(response.content)
            if localname(result.tag) != "deletionResult":
                raise ParseError("unrecognized deletion evidence")
            if any(attr(e, "isDeleted") == "false" or attr(e, "type") in ("E", "A", "X")
                   for e in result.iter()):
                raise ParseError("SAP rejected deletion")
            data["mutation"] = "accepted"
            try:
                _read(uri)
            except Exception as exc:
                if errors.classify(exc).code != errors.OBJECT_NOT_FOUND:
                    raise
            else:
                raise ParseError("object still exists after deletion")
        else:
            data["lock"], data["outcome"] = "unknown", "incomplete"
            lock = handlers.lock_object(uri)
            if lock.is_error:
                unknown = lock.error_code in uncertain_codes
                data["lock"] = "unknown" if unknown else "failed"
                data["outcome"] = "incomplete" if unknown else "not_changed"
                primary = errors.decision(errors.WRITE_INCOMPLETE if unknown else lock.error_code,
                                          lock.text)
                raise ValueError(primary.message)
            handle = lock.text
            data["lock"], data["outcome"] = "acquired", "not_changed"
            data["unlock"] = "not_attempted"
            if digest(_tree(_read(uri, stateful=True))) != plan["baseline_sha256"]:
                primary = errors.decision(errors.BASELINE_CHANGED, "in-lock definition baseline changed")
                raise ValueError(primary.message)
            params = {"lockHandle": handle}
            if plan["transport"]:
                params["corrNr"] = plan["transport"]
            data["mutation"], data["outcome"] = "unknown", "incomplete"
            response = client.make_adt_request(handlers._base() + uri, method="PUT",
                params=params, data=plan["content"].encode("utf-8"),
                extra_headers={"Content-Type": plan["content_type"],
                               "X-sap-adt-sessiontype": "stateful"},
                retry_csrf=False, allow_redirects=False)
            if not 200 <= response.status_code < 300:
                raise ParseError("unexpected definition update response")
            data["mutation"] = "accepted"
            readback = _read(uri, stateful=True)
            _identity(readback, plan["object"]["type"], plan["object"]["name"])
            if _content(readback) != _content(parse_xml(plan["content"].encode("utf-8"))):
                raise ParseError("definition readback differs; do not retry automatically")
        data["readback"], data["outcome"] = "verified", "completed"
    except (Exception, KeyboardInterrupt) as exc:
        primary = primary or (errors.classify(exc) if isinstance(exc, Exception) else
                   errors.decision(errors.WRITE_INCOMPLETE, "Interrupted; inspect remote state before retrying"))
    finally:
        if handle:
            try:
                unlocked = handlers.unlock_object(uri, handle)
                data["unlock"] = ("unknown" if unlocked.error_code in uncertain_codes else "failed"
                                  ) if unlocked.is_error else "accepted"
                if unlocked.is_error:
                    primary = primary or errors.decision(errors.WRITE_INCOMPLETE, unlocked.text)
                    data["outcome"] = "incomplete"
            except (Exception, KeyboardInterrupt):
                data["unlock"] = "unknown"
                primary = primary or errors.decision(
                    errors.WRITE_INCOMPLETE, "Unlock outcome unknown; inspect remote state before retrying")
                data["outcome"] = "incomplete"
    return handlers.AdtResult(kind="scalar", data=data, is_error=primary is not None,
        error_code=(errors.WRITE_INCOMPLETE if data["mutation"] != "not_attempted" or data["outcome"] == "incomplete"
                    else primary.code) if primary else None,
        text=primary.message if primary else "")
