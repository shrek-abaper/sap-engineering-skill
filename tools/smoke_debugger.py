#!/usr/bin/env python3
"""Installed CLI debugger smoke: distinct clients, synthetic local ADT only."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from queue import Queue
import subprocess
import sys
import tempfile
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from debugger_fixture import debugger_fixture  # noqa: E402


def check_cli(command, extra_env=None):
    with debugger_fixture() as (url, state), tempfile.TemporaryDirectory(
        prefix="sap-adt-debug-smoke-",
    ) as home:
        env = {k: v for k, v in os.environ.items() if not k.startswith("SAP_")}
        env.update(extra_env or {})
        env.update({
            "SAP_URL": url, "SAP_USERNAME": "OFFLINE", "SAP_PASSWORD": "offline-fixture",
            "SAP_CLIENT": "000", "SAP_ENVIRONMENT": "qas", "SAP_ALLOW_WRITE": "true",
            "SAP_ADT_FORMAT": "json", "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1",
            "HOME": home, "USERPROFILE": home, "PYTHONUTF8": "1",
        })
        with tempfile.TemporaryFile() as log:
            owner = subprocess.Popen(
                [*command, "debug", "serve", "--ttl", "120", "--idle", "60", "--yes"],
                cwd=home, env=env, stdout=subprocess.PIPE, stderr=log,
            )
            try:
                ready_lines = Queue()
                reader = Thread(target=lambda: ready_lines.put(owner.stdout.readline()), daemon=True)
                reader.start()
                ready = json.loads(ready_lines.get(timeout=40))
                assert ready["ok"] and ready["kind"] == "debug", ready
                session = ready["data"]["session"]
                assert owner.poll() is None

                def invoke(operation, *arguments, expected=0, allow_write=True):
                    environment = dict(env)
                    environment["SAP_ALLOW_WRITE"] = "true" if allow_write else "false"
                    result = subprocess.run(
                        [*command, "debug", operation, "--session", session, *arguments],
                        cwd=home, env=environment, capture_output=True, timeout=100,
                    )
                    assert result.returncode == expected, (
                        operation, result.returncode, result.stderr.decode("utf-8", "replace")
                    )
                    answer = json.loads(result.stdout)
                    assert answer["ok"] and answer["kind"] == "debug"
                    assert answer["format_version"] == 1
                    assert answer["data"]["session"] == session
                    return answer["data"]

                assert invoke("status")["pid"] == ready["data"]["pid"]
                invoke("breakpoint", "--uri",
                       "/sap/bc/adt/oo/classes/zcl_demo/includes/testclasses", "--line", "42", "--yes")
                hit = invoke("listen", "--timeout", "1", "--yes")
                assert not hit["timed_out"]
                invoke("attach", "--debuggee", hit["debuggee"]["id"], "--yes")
                assert invoke("stack")["stack"][0]["line"] == "42"
                assert invoke("vars", "--id", "opaque-1")["variables"][0]["value"] == "\u4e0a\u6d77"
                assert invoke("vars", "--parent", "@LOCALS", "--max-chars", "1", expected=1)["truncated"]
                for action in ("into", "over", "return"):
                    invoke("step", "--action", action, "--yes")
                invoke("continue", "--yes")
                descriptor = Path(home) / ".sap-adt-cli" / "debug" / (session + ".json")
                contents = descriptor.read_text(encoding="utf-8")
                for forbidden in ("offline-fixture", "synthetic-cookie", "synthetic-context", "\u4e0a\u6d77"):
                    assert forbidden not in contents
                # Cleanup remains possible even after disabling new writes.
                assert invoke("cleanup", allow_write=False)["state"] == "closed"
                tail, _ = owner.communicate(timeout=40)
                assert owner.returncode == 0
                assert json.loads(tail)["data"]["state"] == "closed"
                assert not descriptor.exists()
                assert any(c["method"] == "detachDebugger" for c in state.calls)
                assert not any(c["method"] == "terminateDebuggee" for c in state.calls)
                assert sum(c["method"] == "stepContinue" for c in state.calls) == 1
            finally:
                if owner.poll() is None:
                    owner.terminate()
                    try:
                        owner.communicate(timeout=40)
                    except subprocess.TimeoutExpired:
                        owner.kill()
                        owner.communicate(timeout=10)
                owner.stdout.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error("Provide the installed CLI command")
    check_cli(args.command)
    print("[smoke_debugger] OK: owner, cross-process controls, UTF-8 and scoped cleanup (synthetic)")


if __name__ == "__main__":
    main()
