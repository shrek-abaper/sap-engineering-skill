"""One-shot ADT execution and invocation-owned temporary Class lifecycle."""
from __future__ import annotations

import codecs
import hashlib
import json
import re
import secrets
import xml.etree.ElementTree as ET

from . import client, handlers, source_write
from .. import errors

_NAME = re.compile(r"(?:/[A-Z0-9_]+/)?[A-Z][A-Z0-9_]{0,29}", re.ASCII)
_CORE = "http://www.sap.com/adt/core"
_CLASS = "http://www.sap.com/adt/oo/classes"


def _hash(text):
    return source_write.sha256_text(source_write.canonical_source(text))


def prepare(kind, name, code, target, timeout, max_chars):
    if kind not in ("class", "report", "abap"):
        raise ValueError("execution type must be class, report or abap")
    if kind != "abap":
        name = name.upper()
        if not _NAME.fullmatch(name) or len(name) > 30:
            raise ValueError("invalid ABAP object name (maximum 30 characters)")
        typ = "program" if kind == "report" else "class"
        uri = handlers.get_object_uri(typ, name)
        baseline = handlers.read_source_main(uri, version="active")
        if baseline.is_error:
            return None, baseline
        code = baseline.text
    elif not code.strip():
        raise ValueError("ABAP snippet must not be empty")
    plan = {
        "mode": kind, "name": name, "target": target,
        "source_sha256": _hash(code), "timeout": timeout,
        "max_chars": max_chars,
        "package": "$TMP" if kind == "abap" else None,
        "lifecycle": (["create", "write", "activate", "execute", "delete"]
                      if kind == "abap" else ["execute"]),
        "source_binding": "snippet" if kind == "abap" else "observed-active-main-only",
        "wrapper_version": 1,
    }
    plan["plan_sha256"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True).encode("utf-8")).hexdigest()
    return plan, None


def build_class(name, code):
    return source_write.canonical_source(
        f"CLASS {name} DEFINITION PUBLIC FINAL CREATE PUBLIC.\n"
        "  PUBLIC SECTION.\n"
        "    INTERFACES if_oo_adt_classrun.\n"
        "ENDCLASS.\n"
        f"CLASS {name} IMPLEMENTATION.\n"
        "  METHOD if_oo_adt_classrun~main.\n"
        f"{code}\n"
        "  ENDMETHOD.\n"
        "ENDCLASS.")


def _metadata(uri):
    response = client.make_adt_request(
        f"{handlers._base()}{uri}", allow_redirects=False)
    if response.status_code != 200:
        raise ValueError("object metadata did not return HTTP 200")
    root = ET.fromstring(response.content)
    package = root.find(f"{{{_CORE}}}packageRef")
    return {
        "name": root.get(f"{{{_CORE}}}name"),
        "description": root.get(f"{{{_CORE}}}description"),
        "package": package.get(f"{{{_CORE}}}name") if package is not None else None,
    }


def _missing(exc):
    return errors.classify(exc).code == errors.OBJECT_NOT_FOUND


def _owns(uri, name, description):
    meta = _metadata(uri)
    return (meta["name"] == name and meta["description"] == description
            and (meta["package"] or "").upper() == "$TMP")


def _create(name, description):
    root = ET.Element(f"{{{_CLASS}}}abapClass", {
        f"{{{_CORE}}}type": "CLAS/OC",
        f"{{{_CORE}}}name": name,
        f"{{{_CORE}}}description": description,
        f"{{{_CORE}}}language": "EN",
        f"{{{_CORE}}}masterLanguage": "EN",
        f"{{{_CLASS}}}final": "true",
        f"{{{_CLASS}}}visibility": "public",
    })
    ET.SubElement(root, f"{{{_CORE}}}packageRef", {f"{{{_CORE}}}name": "$TMP"})
    response = client.make_adt_request(
        f"{handlers._base()}/sap/bc/adt/oo/classes", method="POST",
        data=ET.tostring(root, encoding="utf-8", xml_declaration=True),
        extra_headers={"Content-Type": "application/vnd.sap.adt.oo.classes.v2+xml"},
        retry_csrf=False, allow_redirects=False)
    if not 200 <= response.status_code < 300:
        raise ValueError("class creation returned an unexpected redirect/status")


def _delete(uri):
    root = ET.Element("{http://www.sap.com/adt/deletion}deletionRequest")
    obj = ET.SubElement(root, "{http://www.sap.com/adt/deletion}object",
                        {f"{{{_CORE}}}uri": uri})
    ET.SubElement(obj, "{http://www.sap.com/adt/deletion}transportNumber")
    response = client.make_adt_request(
        f"{handlers._base()}/sap/bc/adt/deletion/delete", method="POST",
        data=ET.tostring(root, encoding="utf-8", xml_declaration=True),
        extra_headers={"Content-Type": "application/vnd.sap.adt.deletion.request.v1+xml"},
        retry_csrf=False, allow_redirects=False)
    if not 200 <= response.status_code < 300:
        raise ValueError("deletion returned an unexpected redirect/status")
    try:
        _metadata(uri)
    except Exception as exc:
        if _missing(exc):
            return
        raise
    raise ValueError("temporary object still exists after deletion")


def _invoke(mode, name, timeout, max_chars, data):
    path = ("programs/programrun/" if mode == "report" else "oo/classrun/")
    # Do not replay execution, even for CSRF failures, and do not forward
    # credentials/code to a redirected endpoint.
    with client.isolated_session():
        client.prepare_csrf()
        data["execution"] = {"status": "unknown"}
        response = client.make_adt_request(
            f"{handlers._base()}/sap/bc/adt/{path}{handlers._enc(name)}",
            method="POST", timeout=timeout, retry_csrf=False,
            allow_redirects=False, stream=True,
            extra_headers={"Accept": "text/plain"})
        pieces = []
        try:
            data["execution"]["http_status"] = response.status_code
            media = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if response.status_code != 200 or media != "text/plain":
                raise ValueError(
                    f"unconfirmed execution response: HTTP {response.status_code}, "
                    f"content type {media!r}; expected 200 text/plain")
            decoder = codecs.getincrementaldecoder("utf-8")("strict")
            length, truncated = 0, False
            for block in response.iter_content(chunk_size=4096):
                text = decoder.decode(block)
                room = max_chars - length
                pieces.append(text[:room])
                length += min(len(text), room)
                if len(text) > room:
                    truncated = True
                    break
            if not truncated:
                tail = decoder.decode(b"", final=True)
                room = max_chars - length
                pieces.append(tail[:room])
                truncated = len(tail) > room
            data["output"] = {
                "format": "text", "text": "".join(pieces), "truncated": truncated}
            data["execution"] = {
                "status": "unknown" if truncated else "completed",
                "http_status": 200,
                "business_success": "not_evaluated",
            }
            if truncated:
                data["evidence_gaps"].append(
                    "Output truncated; execution completion and remaining output are unconfirmed.")
        finally:
            data["output"]["text"] = "".join(pieces)
            response.close()


def run(plan, code):
    data = {
        "plan": plan, "preparation": {"status": "not_required"},
        "execution": {"status": "not_started"},
        "output": {"format": "text", "text": "", "truncated": False},
        "cleanup": {"status": "not_required"}, "evidence_gaps": [],
    }
    name, uri, description, owned = plan["name"], None, None, False
    safe_hashes = set()
    code_error = None
    try:
        if plan["mode"] == "abap":
            name = "ZADT_RUN_" + secrets.token_hex(11)[:21].upper()
            description = f"sap-adt temporary {name}"
            uri = handlers.get_object_uri("class", name)
            data["temporary_object"] = {"name": name, "uri": uri, "package": "$TMP"}
            data["cleanup"] = {"status": "not_attempted"}
            data["preparation"] = {"status": "checking_absence"}
            try:
                _metadata(uri)
            except Exception as exc:
                if not _missing(exc):
                    raise
            else:
                raise ValueError("generated temporary class already exists; nothing overwritten")
            data["preparation"]["status"] = "creating"
            _create(name, description)
            if not _owns(uri, name, description):
                raise ValueError("created class ownership could not be verified")
            owned = True
            data["preparation"]["status"] = "created"
            baseline = handlers.read_source_main(uri)
            if baseline.is_error:
                raise RuntimeError(baseline.text)
            safe_hashes.add(_hash(baseline.text))
            generated = build_class(name, code)
            safe_hashes.add(_hash(generated))
            data["generated_source_sha256"] = _hash(generated)
            write_plan = source_write.WritePlan(
                object_type="class", object_name=name, group=None, object_uri=uri,
                transport=None, activate=True, target=plan["target"],
                baseline=source_write.canonical_source(baseline.text), content=generated)
            report = source_write.execute(
                write_plan, current_content_sha256=lambda: _hash(generated))
            data["preparation"] = report.to_data()
            if report.final_decision() is not None:
                raise RuntimeError(report.final_decision().message)
        else:
            typ = "program" if plan["mode"] == "report" else "class"
            current = handlers.read_source_main(
                handlers.get_object_uri(typ, name), version="active")
            if current.is_error:
                raise RuntimeError(current.text)
            if _hash(current.text) != plan["source_sha256"]:
                code_error = errors.BASELINE_CHANGED
                raise ValueError("active main source changed after confirmation; not executed")
        _invoke(plan["mode"], name, plan["timeout"], plan["max_chars"], data)
    except (Exception, KeyboardInterrupt) as exc:
        failure = handlers._err(exc) if isinstance(exc, Exception) else None
        data["failure"] = {
            "code": failure.error_code if failure else "INTERRUPTED",
            "message": failure.text if failure else "Interrupted; server execution may continue",
        }
        code_error = code_error or (
            errors.EXECUTION_INCOMPLETE if data["execution"]["status"] == "unknown"
            else errors.EXECUTION_FAILED)
    finally:
        if owned:
            # Never delete while execution may still be running, nor after an
            # unconfirmed write/unlock. Retain the identity for manual recovery.
            prep = data["preparation"]
            unlocked = (
                prep.get("unlock", {}).get("status") in (None, "accepted", "not_attempted")
                and prep.get("lock", {}).get("status") != "unknown"
                and prep.get("outcome") != "incomplete")
            if data["execution"]["status"] == "unknown" or not unlocked:
                data["cleanup"] = {"status": "retained",
                                   "reason": "execution or lock state is unconfirmed"}
            else:
                try:
                    if not _owns(uri, name, description):
                        raise ValueError("ownership changed; refusing deletion")
                    current = handlers.read_source_main(uri)
                    if current.is_error or _hash(current.text) not in safe_hashes:
                        raise ValueError("temporary source changed or unreadable; refusing deletion")
                    _delete(uri)
                    data["cleanup"] = {"status": "verified"}
                except (Exception, KeyboardInterrupt) as exc:
                    data["cleanup"] = {"status": "unknown",
                                       "reason": str(exc) if isinstance(exc, Exception) else "Interrupted"}
        elif uri:
            data["cleanup"] = {
                "status": "not_attempted",
                "reason": "creation/ownership not confirmed; no deletion authorized"}
            if data["preparation"].get("status") == "creating":
                data["evidence_gaps"].append("Creation outcome unknown; inspect temporary object.")

    incomplete = (data["execution"]["status"] == "unknown"
                  or data["cleanup"]["status"] not in ("verified", "not_required"))
    if incomplete:
        data["evidence_gaps"].append("Execution lifecycle incomplete; do not retry automatically.")
        code_error = code_error or errors.EXECUTION_INCOMPLETE
    return data, code_error
