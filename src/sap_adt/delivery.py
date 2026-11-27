"""Verify and aggregate declared delivery evidence, without replay or orchestration."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from io import BytesIO
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from zipfile import ZipFile, is_zipfile

from . import artifacts

KINDS = ("transport", "source", "diff", "unit", "quality", "configuration",
         "diagnosis", "git", "attachment")
PRIMARY = {"unit": "results.json", "quality": "quality.json", "diagnosis": "diagnosis.json",
           "git": "mapping.json", "transport": "transport.json", "source": "source.json",
           "configuration": "configuration.json", "diff": "diff.json"}
DEFAULT_REQUIRED = ("transport", "source", "unit", "quality", "git")


def _package(raw, kind):
    with ZipFile(BytesIO(raw)) as archive:
        infos = archive.infolist()
        names = [i.filename for i in infos]
        if len(names) != len(set(names)) or len(names) > 501 or "manifest.json" not in names:
            raise ValueError("Evidence archive needs a unique manifest and at most 500 assets")
        total = 0
        for info in infos:
            name = info.filename
            if (info.is_dir() or PurePosixPath(name).is_absolute() or "\\" in name
                    or ":" in name or any(p in ("", ".", "..") for p in name.split("/"))
                    or (info.external_attr >> 16) & 0o170000 == 0o120000
                    or info.flag_bits & 1):
                raise ValueError("Unsafe or encrypted evidence archive member")
            total += info.file_size
            if info.file_size > 20 * 1024 * 1024 or total > 100 * 1024 * 1024:
                raise ValueError("Expanded evidence archive exceeds byte budgets")
        manifest = artifacts.parse_json(archive.read("manifest.json"))
        if not isinstance(manifest, dict):
            raise ValueError("Evidence manifest must be a JSON object")
        declared_kind = {"git-change-set": "git"}.get(manifest.get("kind"), manifest.get("kind"))
        if manifest.get("schema_version") != 1 or declared_kind != kind:
            raise ValueError("Evidence archive schema or kind differs from --asset")
        entries = manifest.get("assets")
        if not isinstance(entries, list):
            raise ValueError("Evidence manifest has no assets array")
        expected = [entry["path"] for entry in entries]
        if len(expected) != len(set(expected)) or set(expected) != set(names) - {"manifest.json"}:
            raise ValueError("Evidence manifest and archive member sets differ")
        primary = None
        for entry in entries:
            content = archive.read(entry["path"])
            if (type(entry.get("bytes")) is not int or len(content) != entry["bytes"]
                    or hashlib.sha256(content).hexdigest() != entry.get("sha256")):
                raise ValueError("Evidence archive asset hash/size mismatch")
            if entry["path"] == PRIMARY[kind]:
                primary = artifacts.parse_json(content)
        if primary is None:
            raise ValueError("Evidence archive lacks its primary structured report")
        return primary, manifest


def _target(value, expected):
    if not isinstance(value, dict):
        return False
    if value.get("fingerprint") is not None and value["fingerprint"] != expected:
        raise ValueError("Delivery evidence belongs to a different SAP target")
    if all(value.get(k) is not None for k in ("origin", "client", "environment")):
        identity = {k: value[k] for k in ("origin", "client", "environment")}
    elif all(value.get(k) is not None for k in ("url", "client", "environment")):
        parsed = urlsplit(value["url"])
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        identity = {"origin": f"{parsed.scheme.lower()}://{parsed.hostname.lower()}:{port}",
                    "client": str(value["client"]), "environment": value["environment"]}
    else:
        return False
    fingerprint = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if value.get("fingerprint", fingerprint) != fingerprint or fingerprint != expected:
        raise ValueError("Delivery evidence belongs to a different or inconsistent SAP target")
    return True


def _inspect(kind, document, manifest, fingerprint, transports, now, max_age_hours):
    if not isinstance(document, dict):
        raise ValueError("Evidence primary report must be a JSON object")
    gaps = list(manifest.get("evidence_gaps") or [])
    captured = manifest.get("created_at")
    if "format_version" in document:
        if not document.get("ok"):
            gaps.append({"code": "IMPORTED_COMMAND_FAILED"})
        if document.get("meta", {}).get("partial"):
            gaps.append({"code": "IMPORTED_COMMAND_PARTIAL"})
        document = document.get("data") or {}
    if not isinstance(document, dict):
        raise ValueError("Structured evidence data must be an object")
    gaps.extend(document.get("evidence_gaps") or [])
    context = manifest.get("context") or {}
    bound = _target(context.get("target"), fingerprint)
    own_target = document.get("target") or document.get("plan", {}).get("target")
    if own_target:
        own_bound = _target(own_target, fingerprint)
        if not own_bound:
            gaps.append({"code": "ARTIFACT_REPORT_TARGET_UNBOUND"})
        bound = own_bound or bound
    if kind in ("configuration", "diff") and isinstance(document.get("from"), dict):
        bound = _target(document["from"].get("target"), fingerprint) or bound
    if not bound:
        gaps.append({"code": "ARTIFACT_TARGET_UNBOUND"})
    timestamps = [t for t in (captured, document.get("captured_at"),
        document.get("collector", {}).get("meta", {}).get("collected_at")) if t]
    if not timestamps:
        gaps.append({"code": "ARTIFACT_CAPTURE_TIME_UNKNOWN"})
    for captured in timestamps:
        try:
            stamp = datetime.fromisoformat(captured)
            if stamp.tzinfo is None:
                raise ValueError("Evidence timestamp must include its timezone")
            age = now - stamp
            if age > timedelta(hours=max_age_hours) or age < -timedelta(minutes=5):
                gaps.append({"code": "ARTIFACT_STALE_OR_FUTURE_DATED", "captured_at": captured})
        except (TypeError, ValueError):
            gaps.append({"code": "ARTIFACT_CAPTURE_TIME_UNKNOWN"})
    if manifest.get("partial") and not gaps:
        gaps.append({"code": "IMPORTED_ARCHIVE_PARTIAL"})
    if kind in ("unit", "quality") and document.get("gate", {}).get("status") != "passed":
        gaps.append({"code": "CHECK_GATE_NOT_PASSED", "status": document.get("gate", {}).get("status")})
    if kind == "unit" and (document.get("summary", {}).get("status") != "passed"
                          or document.get("summary", {}).get("executed", 0) <= 0):
        gaps.append({"code": "UNIT_EXECUTION_NOT_PROVEN"})
    if kind == "quality" and (not document.get("engines") or any(
            e.get("status") != "passed" or e.get("meta", {}).get("result_incomplete")
            or e.get("meta", {}).get("partial") for e in document["engines"])):
        gaps.append({"code": "QUALITY_ENGINES_NOT_PASSED"})
    if kind == "git" and document.get("transport_verified") is not True:
        gaps.append({"code": "GIT_TRANSPORT_ASSOCIATION_UNVERIFIED"})
    if kind == "configuration" and (document.get("complete_within_selection") is False
                                    or document.get("observed_only") is True):
        gaps.append({"code": "CONFIGURATION_SELECTION_INCOMPLETE"})
    number = document.get("transport") or context.get("transport")
    if isinstance(number, dict):
        number = number.get("trkorr")
    if number is not None and number not in transports:
        raise ValueError("Artifact transport is outside the declared requirement transports")
    if kind in ("transport", "git") and number is None:
        gaps.append({"code": "ARTIFACT_TRANSPORT_UNBOUND"})
    if kind == "transport":
        paths = {e["path"] for e in manifest.get("assets", [])}
        for obj in document.get("objects", []):
            if "source_fetched" in obj and (not obj["source_fetched"] or obj.get("source_file") not in paths):
                gaps.append({"code": "TRANSPORT_DECLARED_SOURCE_UNAVAILABLE", "object": obj})
    return gaps, number


def pack(requirement, transports, assets, fingerprint, output_file, *,
         required=DEFAULT_REQUIRED, max_age_hours=168):
    from .adt import handlers
    if (not isinstance(requirement, str) or not requirement.strip() or len(requirement) > 128
            or any(ord(c) < 32 for c in requirement)):
        raise ValueError("Requirement ID must contain 1..128 non-control characters")
    transports = list(dict.fromkeys(t.upper() for t in transports))
    if not 1 <= len(transports) <= 20 or not all(handlers._valid_trkorr(t) for t in transports):
        raise ValueError("Declare 1..20 valid transport numbers")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", fingerprint):
        raise ValueError("Delivery requires an explicit configured target SHA-256 fingerprint")
    fingerprint = fingerprint.lower()
    if not 1 <= len(assets) <= 50 or not 1 <= max_age_hours <= 8760:
        raise ValueError("Declare 1..50 assets and a maximum age of 1..8760 hours")
    required = list(dict.fromkeys(("transport", *required)))
    if set(required) - (set(KINDS) - {"attachment"}):
        raise ValueError("Unknown required evidence kind")
    records, members, gaps, observed, covered, seen = [], {}, [], set(), set(), set()
    now = datetime.now(timezone.utc)
    total_bytes = 0
    for index, selection in enumerate(assets, 1):
        kind, sep, path = selection.partition("=")
        if not sep or kind not in KINDS or not path:
            raise ValueError("--asset must be KIND=PATH")
        with open(path, "rb") as stream:
            raw = stream.read(20 * 1024 * 1024 + 1)
        if len(raw) > 20 * 1024 * 1024:
            raise ValueError("Imported asset exceeds 20 MiB")
        total_bytes += len(raw)
        if total_bytes > 100 * 1024 * 1024:
            raise ValueError("Delivery input assets exceed 100 MiB")
        digest = hashlib.sha256(raw).hexdigest()
        if digest in seen:
            raise ValueError("The same artifact cannot satisfy multiple evidence categories")
        seen.add(digest)
        local_gaps, number, manifest = [], None, {}
        archive = is_zipfile(BytesIO(raw))
        if kind != "attachment":
            document, manifest = (_package(raw, kind) if archive else (artifacts.parse_json(raw), {}))
            local_gaps, number = _inspect(kind, document, manifest, fingerprint,
                                         transports, now, max_age_hours)
            observed.add(kind)
            if kind == "transport" and number:
                covered.add(number)
                if any(e["path"].startswith("sources/") for e in manifest.get("assets", [])):
                    observed.add("source")
        name = f"evidence/{index:03d}-{kind}" + (".zip" if archive else ".json" if kind != "attachment" else ".bin")
        members[name] = raw
        records.append({"kind": kind, "path": name, "original_name": Path(path).name,
                        "sha256": digest, "transport": number, "evidence_gaps": local_gaps,
                        "inner_manifest_verified": bool(manifest)})
        gaps.extend({**gap, "asset": name} for gap in local_gaps)
    for missing in sorted(set(required) - observed):
        gaps.append({"code": "REQUIRED_EVIDENCE_MISSING", "kind": missing})
    for missing in sorted(set(transports) - covered):
        gaps.append({"code": "TRANSPORT_EVIDENCE_MISSING", "transport": missing})
    data = {"schema_version": 1, "requirement": requirement.strip(), "transports": transports,
            "target_fingerprint": fingerprint, "assets": records, "evidence_gaps": gaps,
            "assembly": {"status": "incomplete" if gaps else "complete_within_declared_assets",
                         "required_kinds": required, "max_age_hours": max_age_hours,
                         "release_approval": False},
            "scope": "operator-declared requirement association and asset integrity/presence; "
                     "not business completeness, current-source revalidation, or release approval"}
    members["delivery.json"] = data
    data["bundle"] = artifacts.write_package(output_file, "delivery", members,
        context={"requirement": data["requirement"], "transports": transports,
                 "target_fingerprint": fingerprint}, gaps=gaps)
    return data
