"""Candidate-buffer checks and non-replaying, metadata-verified ADT creation."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote, unquote

from .. import errors
from . import client, handlers
from .parsers import findings
from .parsers.common import ParseError, attr, localname, parse_xml
from .source_parts import source_path

CORE = "http://www.sap.com/adt/core"
CHECK = "http://www.sap.com/adt/checkrun"
SPECS = {
    "class": ("oo/classes", "CLAS/OC", "oo/classes", "abapClass", "oo.classes.v2"),
    "interface": ("oo/interfaces", "INTF/OI", "oo/interfaces", "abapInterface", "oo.interfaces.v2"),
    "program": ("programs/programs", "PROG/P", "programs/programs", "abapProgram", "programs.programs.v2"),
    "package": ("packages", "DEVC/K", "packages", "package", "packages.v2"),
}
_NAME = re.compile(r"(?:[ZY][A-Z0-9_]{0,29}|/[A-Z0-9_]+/[A-Z0-9_]+)\Z")
_PACKAGE = re.compile(r"(?:\$[A-Z0-9_]+|[A-Z][A-Z0-9_]*|/[A-Z0-9_]+/[A-Z0-9_]+)\Z")


def _result(data, *, kind="scalar", code=None, text=""):
    return handlers.AdtResult(kind=kind, data=data, is_error=code is not None,
                              error_code=code, text=text)


def check_candidate(object_uri, content, *, part="main", stateful=False):
    """Check a supplied artifact, not the source currently stored in SAP."""
    from .source_write import canonical_source, sha256_text
    content = canonical_source(content)
    evidence = {"status": "unavailable", "source_uri": source_path(object_uri, part),
                "content_sha256": sha256_text(content), "findings": []}
    try:
        root = ET.Element(f"{{{CHECK}}}checkObjectList")
        obj = ET.SubElement(root, f"{{{CHECK}}}checkObject", {
            f"{{{CORE}}}uri": object_uri, f"{{{CHECK}}}version": "active"})
        artifacts = ET.SubElement(obj, f"{{{CHECK}}}artifacts")
        artifact = ET.SubElement(artifacts, f"{{{CHECK}}}artifact", {
            f"{{{CHECK}}}contentType": "text/plain; charset=utf-8",
            f"{{{CHECK}}}uri": evidence["source_uri"]})
        ET.SubElement(artifact, f"{{{CHECK}}}content").text = base64.b64encode(
            content.encode("utf-8")).decode("ascii")
        headers = {"Content-Type": "application/vnd.sap.adt.checkobjects+xml",
                   "Accept": "application/vnd.sap.adt.checkmessages+xml"}
        if stateful:
            headers["X-sap-adt-sessiontype"] = "stateful"
        response = client.make_adt_request(
            handlers._base() + "/sap/bc/adt/checkruns", method="POST",
            params={"reporters": "abapCheckRun"},
            data=ET.tostring(root, encoding="utf-8", xml_declaration=True),
            extra_headers=headers, allow_redirects=False)
        root = parse_xml(response.content)
        reports = [e for e in root.iter() if localname(e.tag) == "checkReport"]
        if localname(root.tag) != "checkRunReports" or not reports:
            raise ParseError("candidate check returned no check reports")
        evidence.update(findings.parse(response.content))
        evidence["reports"] = [
            {key: attr(e, key) for key in ("reporter", "triggeringUri", "status", "statusText")}
            for e in reports]
        if any(f["severity"] == "error" for f in evidence["findings"]):
            evidence["status"] = "failed"
        elif any(attr(e, "reporter") != "abapCheckRun"
                 or unquote(attr(e, "triggeringUri") or "").lower() != unquote(object_uri).lower()
                 or (attr(e, "status") or "").lower() not in ("processed", "ok", "success")
                 for e in reports):
            raise ParseError("candidate check did not confirm successful processing")
        elif any(f["severity"] not in ("error", "warning", "info")
                 for f in evidence["findings"]):
            raise ParseError("candidate check returned an unknown message severity")
        else:
            evidence["status"] = "passed"
        return _result(evidence, kind="findings",
                       code=errors.BAD_REQUEST if evidence["status"] == "failed" else None,
                       text="candidate source has syntax errors" if evidence["status"] == "failed" else "")
    except Exception as exc:
        decision = errors.classify(exc)
        evidence["error"] = {"code": decision.code, "message": decision.message}
        return _result(evidence, kind="findings", code=decision.code, text=decision.message)


def part_baseline(uri, part, *, allow_missing=False, stateful=False):
    """Resolve working/active include source; only explicit missing-part plans use empty."""
    result = handlers.read_source_main(uri, part=part, stateful=stateful)
    if not result.is_error or result.error_code != errors.OBJECT_NOT_FOUND:
        return result
    active = handlers.read_source_main(uri, part=part, version="active", stateful=stateful)
    if not active.is_error or active.error_code != errors.OBJECT_NOT_FOUND:
        return active
    if not allow_missing:
        return result
    try:
        response = client.make_adt_request(handlers._base() + uri,
            extra_headers={"X-sap-adt-sessiontype": "stateful"} if stateful else None,
            allow_redirects=False)
        root = parse_xml(response.content)
        if (attr(root, "type") != "CLAS/OC" or
                (attr(root, "name") or "").upper() != unquote(uri.rsplit("/", 1)[-1]).upper()):
            raise ParseError("missing include parent identity is unconfirmed")
        if any(attr(e, "includeType") == part for e in root):
            raise ParseError("class declares this include but source is unavailable")
        return handlers.AdtResult(text="", meta={"absent": True})
    except Exception as exc:
        return handlers._err(exc)


def generate_part(uri, part, handle, transport=None):
    """Create one missing include once, under the parent lock."""
    if part == "main":
        raise ValueError("main source cannot be generated as an include")
    source_path(uri, part)
    ns = "http://www.sap.com/adt/oo/classes"
    root = ET.Element(f"{{{ns}}}abapClassInclude",
                      {f"{{{CORE}}}name": "dummy", f"{{{ns}}}includeType": part})
    response = client.make_adt_request(handlers._base() + uri + "/includes",
        method="POST", params={"lockHandle": handle, **({"corrNr": transport} if transport else {})},
        extra_headers={"Content-Type": "application/vnd.sap.adt.oo.classincludes+xml",
                       "X-sap-adt-sessiontype": "stateful"},
        data=ET.tostring(root, encoding="utf-8", xml_declaration=True),
        retry_csrf=False, allow_redirects=False)
    if not 200 <= response.status_code < 300:
        raise ParseError("include generation returned an unexpected redirect/status")
    result = handlers.read_source_main(uri, part=part, stateful=True)
    if result.is_error:
        raise ParseError("include generation accepted but readback unavailable")
    return result.text


def object_uri(kind, name):
    return "/sap/bc/adt/" + SPECS[kind][0] + "/" + quote(name.lower(), safe="")


def metadata(uri):
    response = client.make_adt_request(handlers._base() + uri,
                                       allow_redirects=False)
    if response.status_code != 200:
        raise ParseError("object metadata did not return HTTP 200")
    root = parse_xml(response.content)
    package = next((attr(e, "name") for e in root
                    if localname(e.tag) == "packageRef"), None)
    data = {"name": attr(root, "name"), "type": attr(root, "type"),
            "description": attr(root, "description"), "package": package,
            "version": attr(root, "version")}
    if data["type"] == "PROG/P":
        data["program_type"] = attr(root, "programType")
    return data


def _absent(uri):
    try:
        metadata(uri)
    except Exception as exc:
        if errors.classify(exc).code == errors.OBJECT_NOT_FOUND:
            return
        raise
    raise ValueError("object already exists; creation never overwrites")


def _dependencies(kind, package, transport):
    parent = metadata(object_uri("package", package))
    if (parent["name"] or "").upper() != package or parent["type"] != "DEVC/K":
        raise ValueError("package metadata identity mismatch")
    request = None
    if transport:
        result, request = handlers.transport_preflight(transport)
        if result.is_error:
            raise ValueError("transport validation failed: " + result.text)
        if not request or request.get("status") != "D":
            raise ValueError("transport must be modifiable")
    return {"package": parent, "transport": request}


def creation_plan(kind, name, *, package, description, target, transport=None,
                  software_component=None, transport_layer=None):
    kind, name, package = kind.lower(), name.upper(), package.upper()
    local_package_name = kind == "package" and re.fullmatch(r"\$[ZY][A-Z0-9_]*", name)
    if kind not in SPECS or not (_NAME.fullmatch(name) or local_package_name) or len(name) > 30:
        raise ValueError("creation requires class/interface/program/package and a Z/Y or registered-namespace name (max 30)")
    if not _PACKAGE.fullmatch(package):
        raise ValueError("invalid package name")
    if not description.strip() or len(description) > 60:
        raise ValueError("description must contain 1-60 characters")
    local = package.startswith("$")
    if not local and not transport:
        raise ValueError("non-local creation requires an explicit transport")
    if local and transport:
        raise ValueError("local-package creation must not specify a transport")
    if kind == "package":
        if local != name.startswith("$"):
            raise ValueError("local packages require a $Z/$Y name and a local super-package")
        if not software_component or not _PACKAGE.fullmatch(software_component.upper()):
            raise ValueError("package creation requires an explicit software component")
        if not local and not transport_layer:
            raise ValueError("transportable package creation requires a transport layer")
        if local and (software_component.upper() != "LOCAL" or transport_layer):
            raise ValueError("local subpackages require component LOCAL and no transport layer")
    elif software_component or transport_layer:
        raise ValueError("software component and transport layer apply only to packages")
    uri = object_uri(kind, name)
    _absent(uri)
    dependencies = _dependencies(kind, package, transport)
    path, code, namespace, tag, mime = SPECS[kind]
    ns = "http://www.sap.com/adt/" + namespace
    root = ET.Element(f"{{{ns}}}{tag}", {
        f"{{{CORE}}}name": name, f"{{{CORE}}}type": code,
        f"{{{CORE}}}description": description,
        f"{{{CORE}}}language": "EN", f"{{{CORE}}}masterLanguage": "EN"})
    ET.SubElement(root, f"{{{CORE}}}packageRef",
                  {f"{{{CORE}}}name": name if kind == "package" else package})
    if kind == "class":
        root.set(f"{{{ns}}}final", "true")
        root.set(f"{{{ns}}}visibility", "public")
    elif kind == "program":
        root.set(f"{{{ns}}}programType", "1")
    elif kind == "package":
        if not target.get("user"):
            raise ValueError("package creation requires a resolved responsible user")
        root.set(f"{{{CORE}}}responsible", target["user"].upper())
        root.set(f"{{{CORE}}}version", "active")
        ET.SubElement(root, f"{{{ns}}}attributes", {
            f"{{{ns}}}packageType": "development",
            f"{{{ns}}}recordChanges": "false" if local else "true"})
        ET.SubElement(root, f"{{{ns}}}superPackage", {f"{{{CORE}}}name": package})
        node = ET.SubElement(root, f"{{{ns}}}transport")
        ET.SubElement(node, f"{{{ns}}}softwareComponent",
                      {f"{{{ns}}}name": software_component.upper()})
        ET.SubElement(node, f"{{{ns}}}transportLayer",
                      {f"{{{ns}}}name": (transport_layer or "").upper()})
        for child in ("useAccesses", "packageInterfaces", "subPackages"):
            ET.SubElement(root, f"{{{ns}}}{child}")
    body = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    data = {"target": target, "object": {"type": kind, "name": name, "uri": uri},
            "package": package, "description": description, "transport": transport,
            "software_component": software_component, "transport_layer": transport_layer,
            "dependencies": dependencies, "body": body,
            "collection": "/sap/bc/adt/" + path,
            "content_type": f"application/vnd.sap.adt.{mime}+xml",
            "source_write": "not_requested", "activation": "not_requested"}
    data["plan_sha256"] = hashlib.sha256(
        json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
    return data


def create(plan):
    """Revalidate the reviewed plan, then send exactly one POST; never delete."""
    data = {**plan, "create": {"status": "not_attempted"},
            "readback": {"status": "not_attempted"}, "outcome": "not_created"}
    try:
        obj = plan["object"]
        _absent(obj["uri"])
        if _dependencies(obj["type"], plan["package"], plan["transport"]) != plan["dependencies"]:
            return _result(data, code=errors.BASELINE_CHANGED,
                           text="creation dependencies changed after confirmation")
        client.prepare_csrf()
        # A concurrent creator is left to the server's create-only semantics.
        data["create"] = {"status": "unknown"}
        data["outcome"] = "incomplete"
        response = client.make_adt_request(
            handlers._base() + plan["collection"], method="POST",
            params={"corrNr": plan["transport"]} if plan["transport"] else None,
            data=plan["body"].encode("utf-8"),
            extra_headers={"Content-Type": plan["content_type"]},
            retry_csrf=False, allow_redirects=False)
        if not 200 <= response.status_code < 300:
            raise ParseError("creation returned an unexpected redirect/status")
        data["create"] = {"status": "accepted", "http_status": response.status_code}
        got = metadata(obj["uri"])
        data["readback"] = {"status": "unknown", "metadata": got}
        expected = {"name": obj["name"], "type": SPECS[obj["type"]][1],
                    "description": plan["description"]}
        if obj["type"] != "package":
            expected["package"] = plan["package"]
        if any(got.get(k) != v for k, v in expected.items()):
            raise ParseError("created object metadata does not match the confirmed plan")
        if obj["type"] == "program" and got.get("program_type") not in ("1", "executableProgram"):
            raise ParseError("created program is not an executable Report")
        if obj["type"] == "package":
            verify_package(plan)
        data["readback"]["status"] = "verified"
        data["outcome"] = "completed"
        return _result(data)
    except Exception as exc:
        dec = errors.classify(exc)
        data["error"] = {"code": dec.code, "message": dec.message}
        if data["create"]["status"] == "not_attempted":
            return _result(data, code=dec.code, text=dec.message)
        if data["create"]["status"] == "unknown" and dec.http_status and 400 <= dec.http_status < 500:
            data["create"]["status"] = "rejected"
            data["outcome"] = "not_created"
            return _result(data, code=dec.code, text=dec.message)
        return _result(data, code=errors.WRITE_INCOMPLETE,
                       text="creation not verified; do not retry or delete automatically: " + dec.message)


def verify_package(plan):
    response = client.make_adt_request(handlers._base() + plan["object"]["uri"],
                                       allow_redirects=False)
    root = parse_xml(response.content)
    expected = {"superPackage": plan["package"],
                "softwareComponent": plan["software_component"].upper()}
    if plan["transport_layer"]:
        expected["transportLayer"] = plan["transport_layer"].upper()
    for tag, value in expected.items():
        nodes = [e for e in root.iter() if localname(e.tag) == tag]
        if len(nodes) != 1 or attr(nodes[0], "name") != value:
            raise ParseError(f"created package {tag} differs from confirmed plan")
