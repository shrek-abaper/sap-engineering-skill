"""Stateful ADT debugger transport; owned by exactly one local process."""
from __future__ import annotations

import copy
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlsplit

import requests

from ..adt.client import AdtHttpError
from ..adt.parsers.common import ParseError, attr, localname, parse_xml

DEBUG = "/sap/bc/adt/debugger"
ASX = "http://www.sap.com/abapxml"
MAX_BYTES = 2 * 1024 * 1024


def bounded_int(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"Expected an integer between {minimum} and {maximum}")
    return value


def identifier(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 1024 or any(
        ord(c) < 32 for c in value
    ):
        raise ValueError("Expected a bounded debugger identifier")
    return value


def document(payload, name):
    root = parse_xml(payload)
    if localname(root.tag) != name:
        raise ParseError(f"Expected debugger {name} document")
    return root


def abap_data(payload):
    root = document(payload, "abap")
    data = next((e for e in root.iter() if localname(e.tag) == "DATA"), None)
    if data is None:
        raise ParseError("Missing debugger DATA")
    if any(localname(e.tag) in ("exception", "ERROR", "ERROR_INFO") for e in root.iter()):
        raise ParseError("Debugger returned an error document")
    return data


def fields(node):
    return {localname(c.tag): "".join(c.itertext()) for c in node}


def variables(payload, limit, max_chars):
    data = abap_data(payload)
    rows = []
    clipped = False
    for node in data.iter():
        if localname(node.tag) != "STPDA_ADT_VARIABLE":
            continue
        item = fields(node)
        if not item.get("ID"):
            raise ParseError("Debugger variable is missing its ID")
        value = item.get("VALUE", "")
        truncated = len(value) > max_chars or item.get("IS_VALUE_INCOMPLETE") == "X"
        rows.append({
            "id": item["ID"], "name": item.get("NAME"),
            "type": item.get("ACTUAL_TYPE_NAME") or item.get("DECLARED_TYPE_NAME"),
            "meta_type": item.get("META_TYPE"), "value": value[:max_chars],
            "truncated": truncated,
        })
        clipped |= truncated
    return rows[:limit], clipped or len(rows) > limit


def variable_body(ids, children):
    root = ET.Element(f"{{{ASX}}}abap", version="1.0")
    data = ET.SubElement(ET.SubElement(root, f"{{{ASX}}}values"), "DATA")
    if children:
        data = ET.SubElement(data, "HIERARCHIES")
    for value in ids:
        row = ET.SubElement(data, "STPDA_ADT_VARIABLE_HIERARCHY" if children else "STPDA_ADT_VARIABLE")
        ET.SubElement(row, "PARENT_ID" if children else "ID").text = identifier(value)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


class Adapter:
    def __init__(self, config, terminal):
        self.config = config
        self.terminal = terminal
        self.http = requests.Session()
        self.token = None
        self.context = None
        self.pinned = None
        self.attached = False
        self.attach_attempted = False
        self.listener_attempted = False
        self.breakpoint_attempted = False
        self.breakpoint_ids = []
        self._breakpoint_known = False
        self.candidate = None
        self.uncertain = False
        self.debug_session = None
        self.stepping_possible = True

    def params(self):
        return {
            "debuggingMode": "user", "requestUser": self.config.username,
            "terminalId": self.terminal, "ideId": "sap-adt-cli",
        }

    def request(self, path=DEBUG, method="GET", params=None, body=None,
                content_type="application/xml", timeout=30):
        if path not in (DEBUG, "/sap/bc/adt/discovery") and not path.startswith(DEBUG + "/"):
            raise ValueError("Invalid debugger resource")
        if not self.token and method != "GET":
            self.request("/sap/bc/adt/discovery")
            if not self.token:
                raise AdtHttpError("Debugger CSRF preflight did not return a token")
        if self.pinned is not None:
            for cookie in self.pinned:
                self.http.cookies.set_cookie(copy.copy(cookie))
        headers = {
            "X-sap-adt-sessiontype": "stateful", "Accept": content_type,
            "Content-Type": content_type, "X-SAP-Client": self.config.client,
        }
        if self.context:
            headers["sap-contextid"] = self.context
        if self.token:
            headers["x-csrf-token"] = self.token
        else:
            headers["x-csrf-token"] = "fetch"
        started = time.monotonic()
        try:
            with self.http.request(
                method, self.config.base_url() + path,
                params={**(params or {}), "sap-client": self.config.client},
                headers=headers, data=body, auth=(self.config.username, self.config.password),
                verify=self.config.verify_ssl, timeout=(5, timeout),
                allow_redirects=False, stream=True,
            ) as response:
                if not 200 <= response.status_code < 300:
                    # Backend bodies and response headers can contain session credentials.
                    self.uncertain |= self.attached
                    raise AdtHttpError("Debugger HTTP request rejected; no automatic replay",
                                       status=response.status_code)
                self.token = response.headers.get("x-csrf-token", self.token)
                context = response.headers.get("sap-contextid")
                if self.attached and self.context and context and context != self.context:
                    self.uncertain = True
                    raise AdtHttpError("Debugger context changed; cleanup and verify in ADT")
                self.context = context or self.context
                chunks = []
                length = 0
                # Check wall time per byte: chunk buffering lets a trickling peer
                # keep a large read alive indefinitely despite a socket timeout.
                for chunk in response.iter_content(1):
                    length += len(chunk)
                    if length > MAX_BYTES or time.monotonic() - started > timeout:
                        raise ParseError("Debugger response exceeded its evidence budget")
                    chunks.append(chunk)
                return b"".join(chunks)
        except requests.RequestException:
            self.uncertain |= self.attached
            raise AdtHttpError("Debugger connection failed or timed out; do not replay control actions") from None

    def breakpoint(self, uri, line):
        if self.breakpoint_attempted or self.attach_attempted or self.listener_attempted:
            raise ValueError("Set one owned breakpoint before listening; start another owner for another scope")
        identifier(uri)
        parsed = urlsplit(uri)
        # Reuse the repository source allowlist without performing a source read.
        from ..adt.handlers import source_uri
        uri = source_uri(uri, self.config.base_url())
        if parsed.fragment:
            raise ValueError("Pass --line separately from the source URI")
        bounded_int(line, 1, 10000000)
        root = ET.Element("{http://www.sap.com/adt/debugger}breakpoints", {
            **self.params(), "scope": "external", "systemDebugging": "false",
        })
        ET.SubElement(root, "breakpoint", {
            "kind": "line", "enabled": "true", "clientId": self.terminal,
            "{http://www.sap.com/adt/core}uri": f"{uri}#start={line}",
        })
        self.breakpoint_attempted = True
        payload = self.request(DEBUG + "/breakpoints", "POST",
                               body=ET.tostring(root, encoding="utf-8"))
        root = document(payload, "breakpoints")
        rows = [n for n in root.iter() if localname(n.tag) == "breakpoint"]
        self.breakpoint_ids = [attr(n, "id") for n in rows if attr(n, "id")]
        if any(not re.fullmatch(r"[A-Za-z0-9_:~.+=-]{1,256}", bp)
               or bp in (".", "..") for bp in self.breakpoint_ids):
            self.breakpoint_ids = []
            raise ParseError("Breakpoint ID is not a safe opaque path component")
        self._breakpoint_known = bool(self.breakpoint_ids)
        if not self.breakpoint_ids or any(attr(n, "errorMessage") for n in rows):
            raise ParseError("Breakpoint was refused or its ownership could not be established")
        return {"breakpoints": [
            {"id": attr(n, "id"), "uri": attr(n, "uri")} for n in rows
        ]}

    def listen(self, timeout):
        bounded_int(timeout, 1, 30)
        if self.attach_attempted:
            raise ValueError("This owner already attempted attachment")
        if self.candidate:
            raise ValueError("Attach or clean up the existing candidate before listening again")
        self.listener_attempted = True
        payload = self.request(DEBUG + "/listeners", "POST", {
            **self.params(), "timeout": timeout, "checkConflict": "true",
            "isNotifiedOnConflict": "true",
        }, timeout=timeout + 5)
        if not payload.strip():
            return {"timed_out": True, "debuggee": None}
        data = abap_data(payload)
        node = next((e for e in data.iter() if localname(e.tag) == "STPDA_DEBUGGEE"), None)
        if node is None:
            raise ParseError("Listener returned no recognizable debuggee; possible listener conflict")
        item = fields(node)
        candidate = item.get("DEBUGGEE_ID")
        if not candidate:
            raise ParseError("Listener debuggee has no identifier")
        if item.get("DEBUGGEE_USER", "").upper() != self.config.username.upper():
            raise ValueError("Listener returned another user's debuggee; refusing attachment")
        if item.get("IS_ATTACH_IMPOSSIBLE") == "X":
            raise ValueError("Listener reports this debuggee cannot be attached")
        self.candidate = identifier(candidate)
        return {"timed_out": False, "debuggee": {
            "id": candidate, "program": item.get("PRG_CURR"), "include": item.get("INCL_CURR"),
            "line": item.get("LINE_CURR"), "user": item.get("DEBUGGEE_USER"),
        }}

    def attach(self, debuggee):
        if self.attach_attempted or not self.candidate or debuggee != self.candidate:
            raise ValueError("Attach requires this owner's returned debuggee ID, exactly once")
        self.attach_attempted = True
        payload = self.request(method="POST", params={
            "method": "attach", "debuggeeId": identifier(debuggee),
            "dynproDebugging": "false", "debuggingMode": "user",
            "requestUser": self.config.username,
        })
        root = document(payload, "attach")
        if not attr(root, "debugSessionId"):
            raise ParseError("Attach response has no debugSessionId")
        self.attached = True
        self.debug_session = attr(root, "debugSessionId")
        self.stepping_possible = attr(root, "isSteppingPossible") != "false"
        self.pinned = [
            copy.copy(c) for c in self.http.cookies
            if c.name.lower().startswith("sap_sessionid") or c.name.lower() == "sap-contextid"
        ]
        return {"attached": True}

    def require_attached(self):
        if not self.attached or self.uncertain:
            raise ValueError("No verified attached context; cleanup instead of replaying")

    def stack(self):
        self.require_attached()
        root = document(self.request(DEBUG + "/stack", params={
            "method": "getStack", "emode": "_", "semanticURIs": "true",
        }), "stack")
        rows = []
        for node in root.iter():
            if localname(node.tag) == "stackEntry":
                rows.append({key: attr(node, key) for key in (
                    "stackPosition", "stackUri", "programName", "includeName",
                    "line", "eventName", "uri",
                )})
        if not rows:
            raise ParseError("Attached stack contains no frames")
        return {"stack": rows[:100], "truncated": len(rows) > 100}

    def vars(self, ids, parent, limit, max_chars):
        self.require_attached()
        bounded_int(limit, 1, 100)
        bounded_int(max_chars, 1, 4000)
        children = parent is not None
        if children:
            if ids:
                raise ValueError("Choose variable IDs or one parent, not both")
            ids = [identifier(parent)]
        if not isinstance(ids, list) or not 1 <= len(ids) <= 100:
            raise ValueError("Provide 1 to 100 variable IDs, or one parent")
        name = "ChildVariables" if children else "Variables"
        content_type = "application/vnd.sap.as+xml;charset=UTF-8;dataname=com.sap.adt.debugger." + name
        payload = self.request(method="POST", params={"method": "get" + name},
                               body=variable_body(ids, children), content_type=content_type)
        rows, partial = variables(payload, limit, max_chars)
        data = abap_data(payload)
        hierarchy = [fields(e) for e in data.iter()
                     if localname(e.tag) == "STPDA_ADT_VARIABLE_HIERARCHY"]
        if not rows and not hierarchy:
            raise ParseError("Variable response contains neither variables nor hierarchy evidence")
        return {"variables": rows, "hierarchies": hierarchy[:limit],
                "truncated": partial or len(hierarchy) > limit}

    def step(self, action):
        self.require_attached()
        if not self.stepping_possible:
            raise ValueError("Backend no longer permits stepping; clean up this owner")
        if action not in ("stepInto", "stepOver", "stepReturn", "stepContinue"):
            raise ValueError("Unsupported debugger action")
        self.uncertain = True
        payload = self.request(method="POST", params={"method": action})
        root = document(payload, "step")
        # No successful HTTP response alone proves where execution stopped.
        if attr(root, "debugSessionId") != self.debug_session:
            raise ParseError("Step outcome is unknown; inspect in ADT, do not replay")
        self.uncertain = False
        self.stepping_possible = attr(root, "isSteppingPossible") != "false"
        return {"action": action, "outcome": "response_received",
                "stepping_possible": attr(root, "isSteppingPossible")}

    def cleanup(self):
        gaps = []
        if self.attach_attempted:
            try:
                self.request(method="POST", params={"method": "detachDebugger"}, timeout=5)
                self.attached = False
                self.attach_attempted = False
            except Exception:
                gaps.append("DETACH_UNCONFIRMED: inspect the target session in ADT; never terminate blindly")
        if self.listener_attempted:
            try:
                self.request(DEBUG + "/listeners", "DELETE", self.params(), timeout=5)
                self.listener_attempted = False
            except Exception:
                gaps.append("LISTENER_CLEANUP_UNCONFIRMED: inspect this terminal's listener in ADT")
        for bp in list(self.breakpoint_ids):
            try:
                self.request(DEBUG + "/breakpoints/" + quote(bp, safe=""), "DELETE", {
                    **self.params(), "scope": "external",
                }, timeout=5)
                self.breakpoint_ids.remove(bp)
            except Exception:
                gaps.append("BREAKPOINT_CLEANUP_UNCONFIRMED: remove the owned breakpoint in ADT")
        if self.breakpoint_attempted and not self.breakpoint_ids:
            # A POST without an ID-bearing response may have changed remote state.
            if not getattr(self, "_breakpoint_known", False):
                gaps.append("BREAKPOINT_SCOPE_UNCONFIRMED: inspect the owner's terminal scope in ADT")
        return gaps

    def close(self):
        self.http.close()
