"""Verified write-source workflow on top of the existing ADT handlers.

Flow: baseline read -> (caller: diff + confirmation) -> content re-check ->
LOCK -> in-lock baseline re-check -> PUT -> in-lock readback -> UNLOCK
(``finally``) -> optional activation + active-version readback.

Canonical source / hash rule (measured on S/4HANA 2021, Basis 7.56: ADT
returns CRLF without a final newline, drops trailing blanks of each line and
trailing empty lines, keeps tabs):

1. local bytes must be valid UTF-8; one leading BOM is removed;
2. CRLF and lone CR become LF;
3. trailing U+0020 blanks of every line are removed (tabs are kept);
4. trailing empty lines are removed (no final newline).

``sha256`` is taken over the UTF-8 bytes of the canonical text, which is
also exactly the uploaded body. Every other difference (case, tabs, inner
blanks, leading lines, ...) is substantive and fails verification.

Stage statuses: ``accepted`` (2xx only), ``verified`` (independent readback
matches), ``failed`` (definitely rejected or read back different),
``unknown`` (outcome cannot be determined), ``not_attempted``, ``skipped``.
Nothing is retried and the old source is never written back as a rollback.
"""
from __future__ import annotations

import difflib
import hashlib
import json
from dataclasses import dataclass, field
from typing import Callable, Optional

from .. import errors
from . import handlers

ACCEPTED = "accepted"
VERIFIED = "verified"
FAILED = "failed"
UNKNOWN = "unknown"
NOT_ATTEMPTED = "not_attempted"
SKIPPED = "skipped"


def decode_local(data: bytes) -> str:
    """Strict UTF-8 decode of a local source file (one leading BOM removed)."""
    text = data.decode("utf-8")  # UnicodeDecodeError is a ValueError
    return text[1:] if text.startswith("\ufeff") else text


def canonical_source(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip(" ") for line in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def sha256_text(canonical: str) -> str:
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def unified_diff(before: str, after: str, label: str) -> list[str]:
    return list(difflib.unified_diff(
        before.split("\n") if before else [],
        after.split("\n") if after else [],
        fromfile=f"{label} (SAP baseline)", tofile=f"{label} (upload)",
        lineterm="",
    ))


def _line_count(canonical: str) -> int:
    return len(canonical.split("\n")) if canonical else 0


@dataclass
class WritePlan:
    object_type: str
    object_name: str
    group: Optional[str]
    object_uri: str
    transport: Optional[str]
    activate: bool
    target: dict
    baseline: str
    content: str
    expected_baseline_sha256: Optional[str] = None
    expected_content_sha256: Optional[str] = None

    @property
    def baseline_sha256(self) -> str:
        return sha256_text(self.baseline)

    @property
    def content_sha256(self) -> str:
        return sha256_text(self.content)

    @property
    def unchanged(self) -> bool:
        return self.baseline == self.content

    @property
    def plan_sha256(self) -> str:
        binding = {
            "url": self.target.get("url"), "client": self.target.get("client"),
            "user": self.target.get("user"), "object_uri": self.object_uri,
            "transport": self.transport, "activate": self.activate,
            "baseline_sha256": self.baseline_sha256,
            "content_sha256": self.content_sha256,
        }
        return hashlib.sha256(
            json.dumps(binding, sort_keys=True).encode("utf-8")).hexdigest()

    def describe(self) -> dict:
        return {
            "target": self.target,
            "object": {"type": self.object_type.upper(),
                       "name": self.object_name.upper(),
                       "group": self.group.upper() if self.group else None,
                       "uri": self.object_uri},
            "transport": {"requested": self.transport},
            "baseline": {"sha256": self.baseline_sha256,
                         "lines": _line_count(self.baseline),
                         "expected_sha256": self.expected_baseline_sha256},
            "content": {"sha256": self.content_sha256,
                        "bytes": len(self.content.encode("utf-8")),
                        "lines": _line_count(self.content),
                        "expected_sha256": self.expected_content_sha256},
            "unchanged": self.unchanged,
            "activate_requested": self.activate,
            "plan_sha256": self.plan_sha256,
        }


def precheck(plan: WritePlan) -> Optional[errors.ErrorDecision]:
    """Validate caller expectations before anything is confirmed or sent."""
    if (plan.expected_baseline_sha256
            and plan.expected_baseline_sha256.lower() != plan.baseline_sha256):
        return errors.decision(
            errors.BASELINE_CHANGED,
            f"remote baseline sha256 {plan.baseline_sha256} != expected "
            f"{plan.expected_baseline_sha256}; nothing was written")
    if (plan.expected_content_sha256
            and plan.expected_content_sha256.lower() != plan.content_sha256):
        return errors.decision(
            errors.CONTENT_CHANGED,
            f"upload sha256 {plan.content_sha256} != expected "
            f"{plan.expected_content_sha256}; nothing was written")
    return None


def _err(result) -> dict:
    return {"code": result.error_code or errors.SERVER_ERROR,
            "message": result.text, "http_status": result.http_status}


def _outcome_unknown(result) -> bool:
    """True when a failed request may still have been processed by SAP.

    A request that never connected (ConnectTimeout) definitely did not
    arrive; other transport-level failures (read timeout, reset) and 5xx
    replies leave the server-side outcome open.
    """
    if result.http_status is None:
        return result.error_code == errors.NETWORK_ERROR and \
            not result.text.startswith("ConnectTimeout")
    return result.http_status >= 500


@dataclass
class WriteReport:
    plan: WritePlan
    lock: dict = field(default_factory=lambda: {"status": NOT_ATTEMPTED})
    baseline_recheck: dict = field(default_factory=lambda: {"status": NOT_ATTEMPTED})
    write: dict = field(default_factory=lambda: {"status": NOT_ATTEMPTED})
    unlock: dict = field(default_factory=lambda: {"status": NOT_ATTEMPTED})
    activation: dict = field(default_factory=lambda: {"status": NOT_ATTEMPTED})
    primary: Optional[errors.ErrorDecision] = None
    primary_stage: Optional[str] = None

    def fail(self, stage: str, code: str, message: str,
             http_status: Optional[int] = None) -> None:
        # The first failure is the primary error; later (cleanup) failures
        # never overwrite it and are reported in their own stage.
        if self.primary is None:
            self.primary = errors.decision(code, message, http_status=http_status)
            self.primary_stage = stage

    @property
    def outcome(self) -> str:
        """completed | not_written | partial | incomplete."""
        if self.primary is None:
            return "completed"
        clean = (self.lock["status"] != UNKNOWN
                 and self.unlock["status"] in (NOT_ATTEMPTED, ACCEPTED))
        w = self.write
        nothing_written = w["status"] in (NOT_ATTEMPTED, SKIPPED) or (
            w["status"] == FAILED and w.get("request") != ACCEPTED)
        if clean and nothing_written and self.activation["status"] != UNKNOWN:
            return "not_written"
        if clean and w["status"] == VERIFIED and self.activation["status"] == FAILED:
            return "partial"
        return "incomplete"

    def to_data(self) -> dict:
        data = self.plan.describe()
        data["baseline"]["recheck"] = self.baseline_recheck
        data["transport"]["lock_corrnr"] = self.lock.get("corrnr")
        data.update({
            "lock": self.lock, "write": self.write,
            "activation": self.activation, "unlock": self.unlock,
            "outcome": self.outcome,
        })
        return data

    def final_decision(self) -> Optional[errors.ErrorDecision]:
        if self.primary is None:
            return None
        message = self.primary.message
        if self.unlock["status"] in (FAILED, UNKNOWN) and self.primary_stage != "unlock":
            message += (f"; cleanup: unlock {self.unlock['status']} "
                        f"({self.unlock.get('error', {}).get('message', '')})")
        return errors.decision(self.primary.code, message,
                               http_status=self.primary.http_status,
                               data=self.to_data())


def _readback_matches(plan: WritePlan, *, stateful: bool,
                      version: Optional[str] = None) -> tuple[Optional[bool], dict]:
    r = handlers.read_source_main(plan.object_uri, stateful=stateful, version=version)
    if r.is_error:
        return None, {"error": _err(r)}
    got = sha256_text(canonical_source(r.text))
    return got == plan.content_sha256, {"readback_sha256": got}


def execute(plan: WritePlan, *, current_content_sha256: Callable[[], str],
            progress: Callable[[str], None] = lambda _m: None) -> WriteReport:
    """Run the confirmed plan; never raises for SAP-side failures."""
    rep = WriteReport(plan)

    now = current_content_sha256()
    if now != plan.content_sha256:
        rep.fail("content", errors.CONTENT_CHANGED,
                 f"upload content changed after confirmation (sha256 {now} != "
                 f"confirmed {plan.content_sha256}); nothing was written")
        return rep

    if plan.unchanged:
        rep.write = {"status": SKIPPED, "detail": "baseline already equals upload"}
        progress("Source unchanged; lock/write skipped.")
    else:
        _locked_write(plan, rep, progress)

    if plan.activate:
        if rep.primary is None and rep.write["status"] in (VERIFIED, SKIPPED):
            _activate(plan, rep, progress)
        else:
            rep.activation = {"status": NOT_ATTEMPTED,
                              "detail": "write not verified or unlock not confirmed"}
    else:
        rep.activation = {"status": SKIPPED, "detail": "not requested"}
    return rep


def _locked_write(plan: WritePlan, rep: WriteReport, progress) -> None:
    progress("Locking ...")
    lk = handlers.lock_object(plan.object_uri)
    if lk.is_error:
        if _outcome_unknown(lk):
            rep.lock = {"status": UNKNOWN, "error": _err(lk)}
            rep.fail("lock", errors.WRITE_INCOMPLETE,
                     f"lock outcome unknown, no handle to release: {lk.text}")
        else:
            rep.lock = {"status": FAILED, "error": _err(lk)}
            rep.fail("lock", lk.error_code or errors.SERVER_ERROR, f"lock: {lk.text}",
                     lk.http_status)
        return
    handle = lk.text
    corrnr = (lk.meta or {}).get("corrnr") or None
    rep.lock = {"status": "acquired", "corrnr": corrnr,
                "handle_sha256_8": hashlib.sha256(handle.encode()).hexdigest()[:8]}
    try:
        if plan.transport and corrnr and corrnr.upper() != plan.transport.upper():
            rep.fail("transport", errors.BAD_REQUEST,
                     f"object is already recorded in transport {corrnr}, not the "
                     f"confirmed {plan.transport}; nothing was written")
            return
        progress("Re-checking baseline under lock ...")
        cur = handlers.read_source_main(plan.object_uri, stateful=True)
        if cur.is_error:
            rep.baseline_recheck = {"status": FAILED, "error": _err(cur)}
            rep.fail("baseline", cur.error_code or errors.SERVER_ERROR,
                     f"baseline re-check: {cur.text}", cur.http_status)
            return
        cur_sha = sha256_text(canonical_source(cur.text))
        if cur_sha != plan.baseline_sha256:
            rep.baseline_recheck = {"status": "changed", "sha256": cur_sha}
            rep.fail("baseline", errors.BASELINE_CHANGED,
                     f"remote source changed after confirmation (sha256 {cur_sha} "
                     f"!= confirmed {plan.baseline_sha256}); nothing was written")
            return
        rep.baseline_recheck = {"status": "matched", "sha256": cur_sha}

        body = plan.content.encode("utf-8")
        if hashlib.sha256(body).hexdigest() != plan.content_sha256:
            rep.fail("content", errors.CONTENT_CHANGED, "upload body does not match the confirmed hash")
            return
        progress(f"Writing source ({len(body)} bytes) ...")
        put = handlers.put_source(plan.object_uri, plan.content, handle,
                                  transport=plan.transport)
        if put.is_error and not _outcome_unknown(put):
            rep.write = {"status": FAILED, "error": _err(put)}
            rep.fail("write", put.error_code or errors.SERVER_ERROR, f"write: {put.text}",
                     put.http_status)
            return

        progress("Reading back ...")
        match, evidence = _readback_matches(plan, stateful=True)
        if put.is_error:
            # Outcome unknown: only a matching readback resolves it.
            status = VERIFIED if match else UNKNOWN
            rep.write = {"status": status, "request": UNKNOWN,
                         "error": _err(put), **evidence}
            if status == UNKNOWN:
                rep.fail("write", errors.WRITE_INCOMPLETE,
                         f"write outcome unknown ({put.text}); readback "
                         + ("unavailable" if match is None else "does not match upload"))
            return
        if match is None:
            rep.write = {"status": UNKNOWN, "request": ACCEPTED, **evidence}
            rep.fail("write", errors.WRITE_INCOMPLETE,
                     "write accepted but readback unavailable: "
                     + evidence["error"]["message"])
        elif not match:
            rep.write = {"status": FAILED, "request": ACCEPTED,
                         "detail": "readback differs from upload", **evidence}
            rep.fail("write", errors.WRITE_INCOMPLETE,
                     f"write accepted but readback sha256 {evidence['readback_sha256']} "
                     f"!= upload {plan.content_sha256}")
        else:
            rep.write = {"status": VERIFIED, "request": ACCEPTED, **evidence}
    finally:
        progress("Unlocking ...")
        un = handlers.unlock_object(plan.object_uri, handle)
        if un.is_error:
            status = UNKNOWN if _outcome_unknown(un) else FAILED
            rep.unlock = {"status": status, "error": _err(un)}
            rep.fail("unlock", errors.WRITE_INCOMPLETE,
                     f"unlock {status}: {un.text}; check SM12 for a remaining lock")
        else:
            # 200 inside the owning stateful session: measured to release the
            # enqueue, but not independently re-checked here.
            rep.unlock = {"status": ACCEPTED}


def _activate(plan: WritePlan, rep: WriteReport, progress) -> None:
    progress("Activating ...")
    act = handlers.activate_object(plan.object_type, plan.object_name, group=plan.group)
    meta = act.meta or {}
    if act.is_error:
        if _outcome_unknown(act):
            rep.activation = {"status": UNKNOWN, "error": _err(act)}
        else:
            rep.activation = {"status": FAILED, "error": _err(act),
                              "messages": meta.get("messages", [])}
            rep.fail("activation", act.error_code or errors.SERVER_ERROR,
                     f"activation: {act.text}", act.http_status)
            return
    else:
        rep.activation = {"status": ACCEPTED, "messages": meta.get("messages", []),
                          "inactive_objects": meta.get("inactive_objects", [])}

    progress("Verifying active version ...")
    ver = handlers.object_version(plan.object_uri)
    match, evidence = _readback_matches(plan, stateful=False, version="active")
    evidence["object_version"] = None if ver.is_error else ver.text
    if ver.is_error:
        evidence["version_error"] = _err(ver)
    if match and evidence["object_version"] == "active":
        rep.activation.update({"status": VERIFIED, **evidence})
        return
    if match is False or evidence["object_version"] == "inactive":
        rep.activation.update({"status": FAILED, **evidence})
        rep.fail("activation", errors.ACTIVATION_FAILED,
                 "activation not effective: active source/version does not match upload")
        return
    rep.activation.update({"status": UNKNOWN, **evidence})
    rep.fail("activation", errors.WRITE_INCOMPLETE,
             "activation result unknown: active version could not be read back")
