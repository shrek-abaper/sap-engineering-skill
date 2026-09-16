"""Stable error-code enum, exit-code tiers and the single classifier.

The mapping from failures (HTTP responses, network/parse exceptions, local
validation, safety gates) to an error code and an exit code exists ONLY in
this module. Handlers call :func:`classify`; they must not branch on HTTP
status themselves.

Exit tiers:

* 0 - success, including empty results;
* 1 - failure a caller may retry (transient/network/server/parse/request bug);
* 2 - configuration or credential problem;
* 3 - refused by safety policy, or an operation that did not happen and needs
      a human - callers must NOT retry automatically;
* 4 - the requested object does not exist.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ------------------------------- error codes -------------------------------

CONFIG_MISSING = "CONFIG_MISSING"
PROFILE_NOT_FOUND = "PROFILE_NOT_FOUND"
AUTH_FAILED = "AUTH_FAILED"
CSRF_EXPIRED = "CSRF_EXPIRED"
OBJECT_NOT_FOUND = "OBJECT_NOT_FOUND"
SERVICE_NOT_ACTIVE = "SERVICE_NOT_ACTIVE"
BAD_REQUEST = "BAD_REQUEST"
SERVER_ERROR = "SERVER_ERROR"
LOCKED_BY_OTHER = "LOCKED_BY_OTHER"
NETWORK_ERROR = "NETWORK_ERROR"
PARSE_FAILED = "PARSE_FAILED"
WRITE_DISABLED = "WRITE_DISABLED"
TRANSPORT_DISABLED = "TRANSPORT_DISABLED"
CONFIRM_REQUIRED = "CONFIRM_REQUIRED"
USER_ABORTED = "USER_ABORTED"
DML_REJECTED = "DML_REJECTED"
RELEASE_UNVERIFIED = "RELEASE_UNVERIFIED"
RELEASE_REJECTED = "RELEASE_REJECTED"

# Closed set. Every code here MUST appear in EXIT_CODE_MAP (enforced by test).
ALL_CODES = (
    CONFIG_MISSING,
    PROFILE_NOT_FOUND,
    AUTH_FAILED,
    CSRF_EXPIRED,
    OBJECT_NOT_FOUND,
    SERVICE_NOT_ACTIVE,
    BAD_REQUEST,
    SERVER_ERROR,
    LOCKED_BY_OTHER,
    NETWORK_ERROR,
    PARSE_FAILED,
    WRITE_DISABLED,
    TRANSPORT_DISABLED,
    CONFIRM_REQUIRED,
    USER_ABORTED,
    DML_REJECTED,
    RELEASE_UNVERIFIED,
    RELEASE_REJECTED,
)

EXIT_CODE_MAP = {
    # 2 - configuration / credentials
    CONFIG_MISSING: 2,
    PROFILE_NOT_FOUND: 2,
    AUTH_FAILED: 2,
    # 3 - policy refusal / operation did not happen, do not retry
    WRITE_DISABLED: 3,
    TRANSPORT_DISABLED: 3,
    CONFIRM_REQUIRED: 3,
    USER_ABORTED: 3,
    DML_REJECTED: 3,
    # 4 - object does not exist
    OBJECT_NOT_FOUND: 4,
    # 1 - everything else: retryable/operational failures
    CSRF_EXPIRED: 1,
    SERVICE_NOT_ACTIVE: 1,
    BAD_REQUEST: 1,
    SERVER_ERROR: 1,
    LOCKED_BY_OTHER: 1,
    NETWORK_ERROR: 1,
    PARSE_FAILED: 1,
    RELEASE_UNVERIFIED: 1,
    RELEASE_REJECTED: 1,
}

# Codes produced by the local safety gates rather than HTTP responses.
GATE_CODES = frozenset({
    WRITE_DISABLED,
    TRANSPORT_DISABLED,
    CONFIRM_REQUIRED,
    USER_ABORTED,
    DML_REJECTED,
})

DEFAULT_HINTS = {
    CONFIG_MISSING: "Run 'sap-adt-cli configure' or provide SAP_* environment variables.",
    PROFILE_NOT_FOUND: "List profiles with 'profile list' and create one with 'configure'.",
    AUTH_FAILED: "Check username/password and ADT authorizations (S_ADT, S_DEVELOP).",
    CSRF_EXPIRED: "CSRF token was rejected; retry the request (token is refreshed automatically).",
    OBJECT_NOT_FOUND: "The object name/type may be wrong, or it does not exist on this system.",
    SERVICE_NOT_ACTIVE: "Ask SAP Basis to activate the ADT service in transaction SICF.",
    BAD_REQUEST: "The request was rejected by SAP; check object type, parameters and ADT API version.",
    SERVER_ERROR: "The SAP server returned an unexpected error; retry later or check ST22.",
    LOCKED_BY_OTHER: "The object is locked in the transport organizer; release the foreign lock first.",
    NETWORK_ERROR: "The SAP server was unreachable or timed out; check connectivity and retry.",
    PARSE_FAILED: "The response could not be parsed; use --format xml for the raw payload.",
    WRITE_DISABLED: "Re-run 'configure' and enable write mode; the operation was not performed.",
    TRANSPORT_DISABLED: "Re-run 'configure' and enable transport write; the operation was not performed.",
    CONFIRM_REQUIRED: "Run in a terminal or pass --yes explicitly; the operation was not performed.",
    USER_ABORTED: "The confirmation prompt was declined; no changes were made.",
    DML_REJECTED: "Direct DML via run-sql is permanently disabled in this version.",
    RELEASE_UNVERIFIED: (
        "The release request was sent but the final status is unknown (readback "
        "timed out). Do NOT re-release; have a human verify in SE09/SE10."
    ),
    RELEASE_REJECTED: (
        "The transport is still modifiable (status D) after release; the release "
        "job failed or reported a check failure."
    ),
}


@dataclass
class ErrorDecision:
    code: str
    message: str
    http_status: Optional[int] = None
    hint: Optional[str] = None

    @property
    def exit_code(self) -> int:
        return EXIT_CODE_MAP[self.code]

    def to_envelope(self, command: str, profile: Optional[str] = None) -> dict:
        return {
            "ok": False,
            "format_version": 1,
            "command": command,
            **({"profile": profile} if profile else {}),
            "error": {
                "code": self.code,
                "message": self.message,
                "http_status": self.http_status,
                "hint": self.hint,
            },
        }


def exit_code_for(code: str) -> int:
    return EXIT_CODE_MAP[code]


def decision(
    code: str,
    message: str,
    *,
    http_status: Optional[int] = None,
    hint: Optional[str] = None,
) -> ErrorDecision:
    return ErrorDecision(
        code=code,
        message=message,
        http_status=http_status,
        hint=hint if hint is not None else DEFAULT_HINTS.get(code),
    )


# ------------------------------ classification ------------------------------

def _classify_http(status: Optional[int], body: str) -> str:
    """Map an HTTP status + body to an error code (no gate context)."""
    if status is None:
        # Wrapped transport-layer exception (connection refused, timeout...).
        return NETWORK_ERROR
    if status == 401:
        return AUTH_FAILED
    if status == 403:
        return CSRF_EXPIRED if "csrf" in body.lower() else AUTH_FAILED
    if status == 404:
        # Object lookup vs. unsupported endpoint differ in the error body:
        # a missing object carries ExceptionResourceNotFound / "does not
        # exist", while "No suitable resource found" means our URL is wrong.
        low = body.lower()
        if "resourcenotfound" in low or "does not exist" in low:
            return OBJECT_NOT_FOUND
        return BAD_REQUEST
    if status == 423:
        return LOCKED_BY_OTHER
    if status == 503:
        return SERVICE_NOT_ACTIVE
    if status in (400, 405, 406, 409, 415):
        return BAD_REQUEST
    if 400 <= status < 500:
        return BAD_REQUEST
    if status >= 500:
        return SERVER_ERROR
    return SERVER_ERROR


def classify(
    exc: Optional[Exception] = None,
    *,
    gate: Optional[str] = None,
    http_status: Optional[int] = None,
    body: str = "",
    message: str = "",
) -> ErrorDecision:
    """Single mapping point from any failure to an :class:`ErrorDecision`.

    Priority: explicit safety ``gate`` > exception/HTTP classification.
    Pass one of:

    * ``gate=`` for policy refusals (a code from GATE_CODES);
    * ``exc=`` an AdtHttpError / ParseError / ValueError / requests error;
    * ``http_status``+``body`` for raw responses;
    * ``message`` with nothing else yields SERVER_ERROR (unknown internal
      failure) rather than a misleading client-error code.
    """
    if gate is not None:
        if gate not in GATE_CODES:
            raise ValueError(f"unknown gate code: {gate!r}")
        return decision(gate, message or DEFAULT_HINTS[gate])

    if exc is not None:
        name = type(exc).__name__
        text = str(exc)
        status = getattr(exc, "status", None)
        # Name-based to avoid importing lib.config (layering).
        if name == "ProfileNotFoundError":
            return decision(PROFILE_NOT_FOUND, text)
        if name == "ConfigError":
            return decision(CONFIG_MISSING, text)
        if isinstance(exc, ValueError) and not status:
            # ParseError (bad payload) and local argument validation
            # (unknown object type, missing --group, ...) are distinct.
            if name == "ParseError":
                return decision(PARSE_FAILED, text)
            return decision(BAD_REQUEST, text)
        low = text.lower()
        if status is None and any(
            t in low for t in ("timeout", "connection", "dns", "ssl", "resolve")
        ):
            return decision(NETWORK_ERROR, text)
        code = _classify_http(status, body or text)
        return decision(code, text, http_status=status)

    if http_status is not None:
        code = _classify_http(http_status, body)
        return decision(code, message or body or f"HTTP {http_status}",
                        http_status=http_status)

    return decision(SERVER_ERROR, message or "unexpected internal error")
