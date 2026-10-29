#!/usr/bin/env python3
"""Exercise an installed CLI against offline HTTP fixtures, never a real SAP."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "sap_adt_cli"


def check_cli(command: list[str], extra_env: dict | None = None) -> None:
    unit = (FIXTURES / "synthetic" / "unit.methods.synthetic.xml").read_bytes()
    dump = (FIXTURES / "synthetic" / "dump.detail.synthetic.xml").read_bytes()
    formatted = (FIXTURES / "synthetic" / "dump.formatted.synthetic.txt").read_bytes()
    empty = (FIXTURES / "unit.empty.xml").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def answer(self, body, content_type="application/xml"):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("x-csrf-token", "offline-token")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/sap/bc/adt/runtime/dump/DEMO":
                self.answer(dump)
            elif path == "/sap/bc/adt/runtime/dump/DEMO/formatted":
                self.answer(formatted, "text/plain; charset=utf-8")
            elif path in (
                "/sap/bc/adt/oo/classes/zcl_demo/includes/testclasses",
                "/sap/bc/adt/oo/classes/%2Fdemo%2Fzcl_example/includes/testclasses",
            ):
                self.answer("line one\nline two \u4e0a\u6d77\nline three\n".encode("utf-8"),
                            "text/plain; charset=utf-8")
            elif path == "/sap/bc/adt/abapunit/testruns":
                self.answer(b"")
            else:
                self.send_error(404)

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if self.path.split("?", 1)[0] != "/sap/bc/adt/abapunit/testruns":
                self.send_error(404)
            elif b'dangerous="true"' in body or b'critical="true"' in body:
                self.send_error(403)
            else:
                self.answer(empty if b"zcl_empty" in body else unit)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="sap-adt-offline-smoke-") as home:
            env = {k: v for k, v in os.environ.items() if not k.startswith("SAP_")}
            env.update(extra_env or {})
            env.update({
                "SAP_URL": f"http://127.0.0.1:{server.server_port}",
                "SAP_USERNAME": "OFFLINE", "SAP_PASSWORD": "offline-fixture",
                "SAP_CLIENT": "000", "SAP_ENVIRONMENT": "qas",
                "SAP_ADT_FORMAT": "json", "NO_PROXY": "127.0.0.1",
                "no_proxy": "127.0.0.1", "PYTHONUTF8": "1",
                "HOME": home, "USERPROFILE": home,
            })

            def invoke(args, expected):
                result = subprocess.run(
                    [*command, *args], env=env, cwd=home, capture_output=True,
                    timeout=60,
                )
                stderr = result.stderr.decode("utf-8", errors="replace")
                if result.returncode != expected:
                    raise AssertionError(f"{args[0]}: exit {result.returncode}: {stderr}")
                try:
                    envelope = json.loads(result.stdout)
                except (ValueError, UnicodeDecodeError) as exc:
                    raise AssertionError(f"{args[0]}: invalid JSON stdout: {stderr}") from exc
                assert envelope["ok"] and envelope["format_version"] == 1
                return envelope

            result = invoke(["run-unit-test", "ZCL_DEMO", "--require-tests"], 1)
            assert result["data"]["summary"]["failed"] == 1
            assert result["data"]["test_classes"][0]["methods"][1]["alerts"][0]["stack"][0]["line"] == 18
            result = invoke(["run-unit-test", "ZCL_EMPTY", "--require-tests"], 1)
            assert result["data"]["summary"]["status"] == "not_run"
            result = invoke(["get-source",
                             "/sap/bc/adt/oo/classes/zcl_demo/includes/testclasses#start=2",
                             "--start-line", "2", "--end-line", "2"], 0)
            assert result["data"]["source"] == "line two \u4e0a\u6d77\n"
            result = invoke(["get-source",
                             "/sap/bc/adt/oo/classes/%2Fdemo%2Fzcl_example/includes/testclasses",
                             "--start-line", "2", "--end-line", "2"], 0)
            assert result["data"]["source"] == "line two \u4e0a\u6d77\n"
            result = invoke(["get-dump", "DEMO"], 0)
            assert result["data"]["detail_available"]
            assert result["data"]["source"][1]["is_termination"]
            result = invoke(["get-dump", "DEMO", "--max-chars", "40"], 1)
            assert result["meta"]["partial"]
            result = invoke(["get-dump", "UNAVAILABLE"], 1)
            assert result["data"]["fallback"] == "ST22"
            assert not result["data"]["detail_available"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs=argparse.REMAINDER,
                        help="CLI argv, e.g. python -m sap_adt")
    args = parser.parse_args()
    if not args.command:
        parser.error("Provide the installed CLI command")
    check_cli(args.command)
    print("[smoke_diagnostics] OK: Unit, empty-run gate, source window, dump and partial evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
