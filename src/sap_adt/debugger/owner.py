"""Private loopback JSON IPC; SAP session material never leaves the owner."""
from __future__ import annotations

import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import threading
import time

import requests

from .. import errors
from ..config import ConfigError
from .adapter import Adapter, bounded_int

MAX_IPC = 3 * 1024 * 1024
MUTATING = {"breakpoint", "listen", "attach", "step", "continue"}
ARGUMENTS = {
    "status": set(), "breakpoint": {"uri", "line"}, "listen": {"timeout"},
    "attach": {"debuggee"}, "stack": set(),
    "vars": {"ids", "parent", "limit", "max_chars"}, "step": {"action"},
    "continue": set(), "detach": set(), "cleanup": set(),
}


def identity(config):
    value = [config.base_url(), config.client, config.username, config.profile_name]
    return hashlib.sha256(json.dumps(value).encode("utf-8")).hexdigest()


def state_dir():
    return Path.home() / ".sap-adt-cli" / "debug"


def secure(path, directory=False):
    if path.is_symlink():
        raise ConfigError("Debugger state path must not be a symlink")
    if os.name == "nt":
        from .permissions import windows_private
        windows_private(path, directory=directory, create=True)
    else:
        os.chmod(path, 0o700 if directory else 0o600)


def descriptor(session):
    if not isinstance(session, str) or not re.fullmatch(r"[a-f0-9]{32}", session):
        raise ValueError("Expected the session handle returned by debug serve")
    directory = state_dir()
    if directory.is_symlink():
        raise ConfigError("Debugger directory must not be a symlink")
    path = directory / (session + ".json")
    if path.is_symlink():
        raise ConfigError("Debugger descriptor must not be a symlink")
    if os.name == "nt":
        from .permissions import windows_private
        windows_private(directory, directory=True)
        windows_private(path)
    else:
        for item in (directory, path):
            info = item.stat()
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise ConfigError("Debugger state is not private to this user")
    if path.stat().st_size > 8192:
        raise ConfigError("Invalid debugger descriptor")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        if (record["session"] != session or record["version"] != 1
                or not re.fullmatch(r"[a-f0-9]{64}", record["token"])
                or not re.fullmatch(r"[a-f0-9]{64}", record["identity"])):
            raise ValueError()
        bounded_int(record["port"], 1, 65535)
    except (ValueError, KeyError, TypeError):
        raise ConfigError("Invalid debugger descriptor; no request sent") from None
    return path, record


def rpc(config, session, operation, arguments, discard=False):
    path, record = descriptor(session)
    if record["identity"] != identity(config):
        raise ValueError("Debugger profile/system/client/user differs from its owner")
    if operation not in ARGUMENTS or set(arguments) != ARGUMENTS[operation]:
        raise ValueError("Invalid debugger operation arguments")
    try:
        with requests.Session() as connection:
            connection.trust_env = False
            response = connection.post(
                f"http://127.0.0.1:{record['port']}/command",
                headers={"Authorization": "Bearer " + record["token"],
                         "Content-Type": "application/json"},
                json={"session": session, "identity": record["identity"],
                      "operation": operation, "arguments": arguments},
                timeout=(3, 110), allow_redirects=False, stream=True,
            )
            with response:
                if response.status_code != 200:
                    raise ValueError("Debugger owner rejected local IPC")
                body = response.raw.read(MAX_IPC + 1)
                if len(body) > MAX_IPC:
                    raise ValueError("Debugger IPC response exceeds its budget")
                answer = json.loads(body)
    except requests.ConnectionError:
        if operation == "cleanup" and discard:
            path.unlink()
            return {
                "session": session, "state": "discarded_local",
                "operation": operation,
                "remote_cleanup_verified": False, "cleanup_requests_accepted": False,
                "evidence_gaps": [
                    "REMOTE_STATE_UNKNOWN: owner unreachable; local state discarded only. "
                    "Inspect debugger/listener/breakpoints in ADT or ask Basis."
                ],
            }
        raise ValueError(
            "Debugger owner unreachable; do not reattach or kill a recorded PID. "
            "Use cleanup --discard-local only after inspecting remote state."
        ) from None
    except requests.RequestException:
        raise ValueError("Debugger IPC outcome unknown; do not replay control actions") from None
    if not isinstance(answer, dict) or set(answer) != {"data", "error"}:
        raise ValueError("Invalid debugger IPC response")
    if answer["error"]:
        error = answer["error"]
        if not isinstance(error, dict) or error.get("code") not in errors.ALL_CODES:
            raise ValueError("Invalid debugger IPC error")
        return errors.decision(error["code"], error["message"], hint=error.get("hint"),
                               http_status=error.get("http_status"))
    return answer["data"]


class Owner:
    def __init__(self, config, ttl=900, idle=120, adapter=None):
        bounded_int(ttl, 10, 1800)
        bounded_int(idle, 5, ttl)
        if config.is_production or not config.allow_write:
            raise ConfigError("Debugger owner requires a non-production write-enabled profile")
        self.config = config
        self.session = secrets.token_hex(16)
        self.token = secrets.token_hex(32)
        self.adapter = adapter or Adapter(config, "sap-adt-" + self.session)
        self.terminal = self.adapter.terminal
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.started = self.last_used = time.monotonic()
        self.ttl, self.idle = ttl, idle
        self.state = "ready"
        self.closed = False
        self.path = None
        self.server = None

    def data(self, operation, **extra):
        return {"session": self.session, "operation": operation, "state": self.state,
                "evidence_gaps": [], **extra}

    def execute(self, operation, arguments):
        if operation not in ARGUMENTS or set(arguments) != ARGUMENTS[operation]:
            raise ValueError("Invalid debugger operation arguments")
        if not self.lock.acquire(blocking=False):
            raise ValueError("Debugger owner is busy; no command was queued or sent")
        try:
            if self.closed:
                raise ValueError("Debugger owner has ended")
            if operation not in ("cleanup", "detach", "status") and (
                time.monotonic() - self.started >= self.ttl
                or time.monotonic() - self.last_used >= self.idle
            ):
                raise ValueError("Debugger owner expired; clean up this session")
            if self.state in ("uncertain", "cleanup_incomplete") and operation not in ("cleanup", "detach", "status"):
                raise ValueError("Debugger outcome uncertain; cleanup, never replay automatically")
            self.last_used = time.monotonic()
            if operation == "status":
                return self.data(operation, terminal=self.terminal, pid=os.getpid(),
                                 attached=self.adapter.attached)
            if operation in ("cleanup", "detach"):
                gaps = self.adapter.cleanup()
                self.state = "cleanup_incomplete" if gaps else "closed"
                if not gaps:
                    self.closed = True
                    self.stop.set()
                return self.data(operation, evidence_gaps=gaps,
                                 cleanup_requests_accepted=not gaps, remote_cleanup_verified=False)
            if operation == "continue":
                result = self.adapter.step("stepContinue")
            elif operation == "vars":
                result = self.adapter.vars(**arguments)
            else:
                result = getattr(self.adapter, operation)(**arguments)
            if operation == "listen":
                self.state = "ready" if result["timed_out"] else "candidate"
            elif operation == "attach":
                self.state = "attached"
            return self.data(operation, **result)
        except Exception:
            if operation in MUTATING or self.adapter.uncertain:
                self.state = "uncertain"
                self.adapter.uncertain = True
            raise
        finally:
            self.lock.release()

    def open(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(3)

            def log_message(self, *_):
                pass

            def do_POST(self):
                if (self.path != "/command"
                    or not hmac.compare_digest(self.headers.get("Authorization", "").encode("utf-8"),
                                               ("Bearer " + owner.token).encode("ascii"))
                    or self.headers.get("Origin") or self.headers.get("Transfer-Encoding")):
                    self.send_error(403)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 16384:
                        raise ValueError("Invalid debugger IPC size")
                    body = json.loads(self.rfile.read(length))
                    if (not isinstance(body, dict)
                        or set(body) != {"session", "identity", "operation", "arguments"}
                        or body["session"] != owner.session
                        or body["identity"] != identity(owner.config)
                        or not isinstance(body["arguments"], dict)):
                        raise ValueError("Invalid debugger IPC identity")
                    data = owner.execute(body["operation"], body["arguments"])
                    answer = {"data": data, "error": None}
                except Exception as exc:
                    decision = errors.classify(exc)
                    answer = {"data": None, "error": {
                        "code": decision.code, "message": decision.message,
                        "http_status": decision.http_status,
                        "hint": "Do not replay debugger control actions or use raw XML fallback. "
                                "Inspect debug status/cleanup for this session; "
                                "use ADT/Basis when remote state remains unknown.",
                    }}
                payload = json.dumps(answer, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                try:
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = False
        self.server.timeout = 0.25
        directory = state_dir()
        if directory.is_symlink():
            raise ConfigError("Debugger directory must not be a symlink")
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        secure(directory, directory=True)
        self.path = directory / (self.session + ".json")
        record = {
            "version": 1, "session": self.session, "identity": identity(self.config),
            "port": self.server.server_port, "token": self.token, "pid": os.getpid(),
            "terminal": self.terminal,
        }
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            secure(self.path)
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                fd = None
                json.dump(record, file)
        finally:
            if fd is not None:
                os.close(fd)
        return self.data("serve", terminal=self.terminal, pid=os.getpid(),
                         ttl_seconds=self.ttl, idle_seconds=self.idle)

    def run(self):
        previous = {}
        if threading.current_thread() is threading.main_thread():
            for name in ("SIGINT", "SIGTERM"):
                number = getattr(signal, name, None)
                if number is not None:
                    previous[number] = signal.signal(number, lambda *_: self.stop.set())
        try:
            while not self.stop.is_set():
                self.server.handle_request()
                now = time.monotonic()
                if now - self.started >= self.ttl or now - self.last_used >= self.idle:
                    self.stop.set()
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)
        return self.finish()

    def finish(self):
        with self.lock:
            gaps = [] if self.closed else self.adapter.cleanup()
            self.closed = True
            self.state = "cleanup_incomplete" if gaps else "closed"
            self.adapter.close()
        if self.server:
            self.server.server_close()
        # Keep the capability descriptor when cleanup failed: never imply remote release.
        if self.path and not gaps:
            self.path.unlink(missing_ok=True)
        return self.data("cleanup", evidence_gaps=gaps,
                         cleanup_requests_accepted=not gaps, remote_cleanup_verified=False)
