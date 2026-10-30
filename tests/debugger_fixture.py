"""Synthetic ADT debugger, not a recording or a live-SAP substitute."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from urllib.parse import parse_qs, urlsplit


@contextmanager
def debugger_fixture(scenario="normal"):
    class State:
        calls = None
        entered = None
        release = None

    state = State()
    state.calls = []
    state.entered = threading.Event()
    state.release = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def answer(self, body=b"", status=200, cookie=False):
            self.send_response(status)
            self.send_header("x-csrf-token", "synthetic-token")
            self.send_header("sap-contextid", "synthetic-context")
            if cookie:
                self.send_header("Set-Cookie", "sap-contextid=synthetic-cookie; Path=/")
            self.send_header("Content-Type", "application/xml; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def handle_request(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            method = query.get("method", [""])[0]
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            state.calls.append({
                "verb": self.command, "path": parsed.path, "method": method,
                "params": query, "body": body, "headers": dict(self.headers),
            })
            if parsed.path == "/sap/bc/adt/discovery":
                self.answer(b"<service/>", cookie=True)
                return
            if (self.headers.get("X-sap-adt-sessiontype") != "stateful"
                or "synthetic-cookie" not in self.headers.get("Cookie", "")
                or self.headers.get("sap-contextid") != "synthetic-context"
                or self.headers.get("x-csrf-token") != "synthetic-token"):
                self.answer(status=403)
                return
            if scenario == "auth":
                self.answer(b"SAP_PASSWORD=synthetic-do-not-echo", status=403)
            elif self.command == "DELETE":
                self.answer(status=500 if scenario == "cleanup-failure" else 204)
            elif parsed.path.endswith("/breakpoints"):
                if scenario == "refused-breakpoint":
                    self.answer(b'<breakpoints><breakpoint errorMessage="No executable line"/></breakpoints>')
                else:
                    self.answer(b'<breakpoints><breakpoint id="SYNTHETIC_OWNED_BP" uri="/sap/bc/adt/oo/classes/zcl_demo/includes/testclasses#start=42"/></breakpoints>')
            elif parsed.path.endswith("/listeners"):
                if scenario == "timeout":
                    self.answer()
                else:
                    user = b"OTHER" if scenario == "foreign-user" else b"OFFLINE"
                    self.answer(b'<asx:abap xmlns:asx="http://www.sap.com/abapxml"><asx:values><DATA>'
                                b'<STPDA_DEBUGGEE><DEBUGGEE_ID>SYNTHETIC_DEBUGGEE</DEBUGGEE_ID>'
                                b'<DEBUGGEE_USER>' + user + b'</DEBUGGEE_USER><PRG_CURR>ZDEMO</PRG_CURR>'
                                b'<LINE_CURR>42</LINE_CURR></STPDA_DEBUGGEE></DATA></asx:values></asx:abap>')
            elif method == "attach":
                self.answer(b"<html>not an attachment</html>" if scenario == "malformed-attach"
                            else b'<attach debugSessionId="SYNTHETIC_SESSION" isSteppingPossible="true"/>')
            elif method == "getStack":
                if scenario == "busy":
                    state.entered.set()
                    state.release.wait(timeout=10)
                self.answer(b'<stack><stackEntry stackPosition="1" programName="ZDEMO" includeName="LTC_DEMO"'
                            b' line="42" uri="/sap/bc/adt/oo/classes/zcl_demo/includes/testclasses#start=42"/></stack>')
            elif method in ("getVariables", "getChildVariables"):
                hierarchy = (b"<HIERARCHIES><STPDA_ADT_VARIABLE_HIERARCHY><PARENT_ID>@LOCALS</PARENT_ID>"
                             b"<CHILD_ID>opaque-1</CHILD_ID><CHILD_NAME>LV_TEXT</CHILD_NAME>"
                             b"</STPDA_ADT_VARIABLE_HIERARCHY></HIERARCHIES>") if method == "getChildVariables" else b""
                self.answer(b'<asx:abap xmlns:asx="http://www.sap.com/abapxml"><asx:values><DATA>' + hierarchy +
                            b'<STPDA_ADT_VARIABLE><ID>opaque-1</ID><NAME>LV_TEXT</NAME><VALUE>'
                            + "\u4e0a\u6d77".encode("utf-8") +
                            b'</VALUE><ACTUAL_TYPE_NAME>STRING</ACTUAL_TYPE_NAME></STPDA_ADT_VARIABLE>'
                            b'</DATA></asx:values></asx:abap>')
            elif method == "detachDebugger":
                self.answer(status=500 if scenario == "cleanup-failure" else 200)
            elif method.startswith("step"):
                self.answer(b"not a successful step", status=500) if scenario == "step-error" else self.answer(
                    b'<step debugSessionId="SYNTHETIC_SESSION" isSteppingPossible="true"/>')
            else:
                self.answer(status=404)

        do_GET = handle_request
        do_POST = handle_request
        do_DELETE = handle_request

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        state.release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
