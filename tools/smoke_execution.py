#!/usr/bin/env python3
"""Verify an installed CLI's execution lifecycle using loopback-only fixtures."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
from threading import Thread
from urllib.parse import parse_qs, unquote, urlsplit
import xml.etree.ElementTree as ET

CORE = "http://www.sap.com/adt/core"


def check_cli(command: list[str]) -> None:
    objects = {
        "ZCL_DEMO": {"source": "class source", "description": "demo", "package": "$TMP"},
        "ZREPORT": {"source": "report source", "description": "demo", "package": "$TMP"},
    }
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def answer(self, body=b"", media="application/xml", status=200):
            if isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", media)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("x-csrf-token", "fixture-csrf")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            if path == "/sap/bc/adt/discovery":
                self.answer('<app:service xmlns:app="http://www.w3.org/2007/app"/>',
                            "application/atomsvc+xml")
                return
            parts = path.split("/")
            name = parts[-3].upper() if path.endswith("/source/main") else parts[-1].upper()
            obj = objects.get(name)
            if obj is None:
                self.answer("<exception><type>ExceptionResourceNotFound</type></exception>", status=404)
            elif path.endswith("/source/main"):
                self.answer(obj["source"], "text/plain")
            else:
                self.answer(
                    f'<class:abapClass xmlns:class="http://www.sap.com/adt/oo/classes" '
                    f'xmlns:adtcore="{CORE}" adtcore:name="{name}" adtcore:version="active" '
                    f'adtcore:description="{obj["description"]}">'
                    f'<adtcore:packageRef adtcore:name="$TMP"/></class:abapClass>')

        def do_PUT(self):
            name = unquote(urlsplit(self.path).path).split("/")[-3].upper()
            body = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8")
            objects[name]["source"] = body
            self.answer()

        def do_POST(self):
            parsed = urlsplit(self.path)
            path = unquote(parsed.path)
            query = parse_qs(parsed.query)
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if "classrun/" in path or "programrun/" in path:
                calls.append(path)
                self.answer("RESULT \u4e0a\u6d77\n", "text/plain; charset=utf-8")
            elif path == "/sap/bc/adt/oo/classes":
                root = ET.fromstring(body)
                name = root.get(f"{{{CORE}}}name").upper()
                assert name not in objects
                objects[name] = {
                    "source": "skeleton", "package": "$TMP",
                    "description": root.get(f"{{{CORE}}}description"),
                }
                self.answer(status=201)
            elif query.get("_action") == ["LOCK"]:
                self.answer("<abap><DATA><LOCK_HANDLE>fixture-handle</LOCK_HANDLE></DATA></abap>")
            elif query.get("_action") == ["UNLOCK"] or path == "/sap/bc/adt/activation":
                self.answer()
            elif path == "/sap/bc/adt/deletion/delete":
                root = ET.fromstring(body)
                uri = list(root)[0].get(f"{{{CORE}}}uri")
                del objects[uri.split("/")[-1].upper()]
                self.answer()
            else:
                self.answer(status=404)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="sap-adt-execution-smoke-") as home:
            env = {k: v for k, v in os.environ.items() if not k.startswith("SAP_")}
            env.update({
                "SAP_URL": f"http://127.0.0.1:{server.server_port}",
                "SAP_USERNAME": "FIXTURE", "SAP_PASSWORD": "fixture",
                "SAP_CLIENT": "000", "SAP_ENVIRONMENT": "dev",
                "SAP_ALLOW_EXECUTE": "true", "SAP_ALLOW_WRITE": "true",
                "SAP_ADT_FORMAT": "json", "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1",
                "HOME": home, "USERPROFILE": home, "PYTHONUTF8": "1",
            })
            snippet = Path(home) / "probe.abap"
            snippet.write_text("out->write( 'RESULT' ).", encoding="utf-8")

            def invoke(args, expected=0, overrides=None):
                result = subprocess.run(
                    [*command, *args], env={**env, **(overrides or {})}, cwd=home,
                    capture_output=True, timeout=60)
                stderr = result.stderr.decode("utf-8", errors="replace")
                assert result.returncode == expected, (args, result.returncode, stderr)
                raw = result.stdout.decode("utf-8") if expected == 0 else stderr
                return json.loads(raw[raw.index('{\n  "ok"'):])

            for args in (["run-class", "ZCL_DEMO"], ["run-report", "ZREPORT"],
                         ["run-abap", "--file", str(snippet)]):
                count = len(calls)
                dry = invoke([*args, "--dry-run"])
                assert len(calls) == count
                digest = dry["data"]["plan"]["plan_sha256"]
                result = invoke([*args, "--yes", "--expect-plan-sha256", digest])
                assert result["kind"] == "execution"
                assert result["data"]["execution"]["status"] == "completed"
                assert result["data"]["output"]["text"] == "RESULT \u4e0a\u6d77\n"
                assert len(calls) == count + 1
                if args[0] == "run-abap":
                    assert result["data"]["cleanup"]["status"] == "verified"
                    assert len(objects) == 2
            denied = invoke(["run-class", "ZCL_DEMO", "--dry-run"], 3,
                            {"SAP_ALLOW_EXECUTE": "false"})
            assert denied["error"]["code"] == "EXECUTE_DISABLED"
            dry = invoke(["run-class", "ZCL_DEMO", "--max-chars", "3", "--dry-run"])
            result = invoke(
                ["run-class", "ZCL_DEMO", "--max-chars", "3", "--yes",
                 "--expect-plan-sha256", dry["data"]["plan"]["plan_sha256"]], 3)
            assert result["error"]["code"] == "EXECUTION_INCOMPLETE"
            assert result["data"]["output"]["text"] == "RES"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error("Provide the installed CLI command")
    check_cli(args.command)
    print("[smoke_execution] OK: Class, Report, snippet, cleanup, gate and bounded output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
