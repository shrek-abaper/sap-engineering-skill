"""Operation annotations and explicit target binding; never grants permission."""
from __future__ import annotations

import hashlib
import json
from urllib.parse import urlsplit


def target(config):
    parsed = urlsplit(config.base_url())
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    identity = {
        "origin": f"{parsed.scheme.lower()}://{parsed.hostname.lower()}:{port}",
        "client": str(config.client),
        "environment": config.environment,
    }
    fingerprint = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        **identity, "profile": config.profile_name,
        "connection_source": "environment" if config.from_environment else "profile",
        "fingerprint": fingerprint,
        "identity_verification": "configured-target-not-server-attested",
    }


def validate_target(config, *, environment=None, client=None, fingerprint=None):
    actual = target(config)
    for key, expected in (("environment", environment), ("client", client),
                          ("fingerprint", fingerprint)):
        if expected is not None and actual[key] != expected:
            raise ValueError(f"Target {key} differs from the explicitly expected value; no operation performed")
    return actual


def operation(command, params=None):
    params = params or {}
    approval = "not_required"
    if command in ("run-class", "run-report", "run-abap", "run-function"):
        kind, risk, approval = "execution", "high", "fresh_confirmation_or_bound_plan"
    elif command == "run-unit-test":
        risks = set(params.get("risk_level", ("harmless",)))
        kind, risk = "execution", "medium"
        if risks - {"harmless"}:
            risk, approval = "high", "fresh_confirmation_or_bound_plan"
    elif command in ("write-source", "write-definition", "create-object",
                     "delete-object", "activate", "apply-change-set"):
        kind, risk, approval = "source_write", "high", "fresh_confirmation"
    elif command in ("create-transport", "release-transport"):
        kind, risk, approval = "transport_write", "high", "fresh_confirmation"
    elif command.startswith("debug "):
        read = command in ("debug status", "debug stack", "debug vars")
        kind, risk = ("read", "low") if read else ("debug_control", "high")
        if not read:
            approval = "session_scoped_consent"
    elif command in ("unit skeleton", "diagnose", "git export", "delivery pack") or (
            command in ("config-data read", "quality-check") and params.get("output_file")):
        kind, risk = "local_write", "low"
    elif command.startswith(("profile ", "credentials ")) or command in ("configure", "update"):
        kind, risk = "local_maintenance", "medium"
    else:
        kind, risk = "read", "low"
    return {
        "type": kind, "risk_level": risk, "approval_required": approval != "not_required",
        "approval_mechanism": approval, "approval_identity": "not_attested_by_cli",
        "dry_run": bool(params.get("dry_run")),
    }


def error_category(code):
    from . import errors
    if code in (errors.CONFIG_MISSING, errors.PROFILE_NOT_FOUND):
        return "configuration"
    if code == errors.AUTH_FAILED:
        return "authentication_or_authorization"
    if code in errors.GATE_CODES or code in (errors.BASELINE_CHANGED, errors.CONTENT_CHANGED):
        return "policy_or_precondition"
    if code in (errors.WRITE_INCOMPLETE, errors.EXECUTION_INCOMPLETE, errors.RELEASE_UNVERIFIED):
        return "outcome_unknown"
    if code == errors.OBJECT_NOT_FOUND:
        return "not_found"
    if code == errors.SERVICE_NOT_ACTIVE:
        return "capability_unavailable"
    if code in (errors.NETWORK_ERROR, errors.SERVER_ERROR, errors.CSRF_EXPIRED):
        return "transport"
    if code == errors.PARSE_FAILED:
        return "invalid_evidence"
    return "operation"
