"""Explicit Unit gates, source-bound supplied line coverage and failing skeletons."""
from __future__ import annotations

import math
import hashlib
import re
from pathlib import Path

from .. import artifacts, policy
from . import handlers, source_write


def coverage(path, prepared, config):
    if path is None:
        return {"status": "unavailable", "provider": None, "percent": None,
                "evidence_gaps": [{"code": "COVERAGE_NOT_COLLECTED",
                    "message": "AUnit result counts are not code coverage. Supply a source/target-bound line-coverage report."}]}
    report = artifacts.read_json(path)
    if (not isinstance(report, dict) or report.get("schema_version") != 1
            or report.get("target_fingerprint") != policy.target(config)["fingerprint"]
            or not isinstance(report.get("files"), list) or not 1 <= len(report["files"]) <= 100):
        raise ValueError("Coverage requires schema_version=1, matching target_fingerprint and 1..100 files")
    selected = [o["uri"].lower().rstrip("/") + "/" for o in prepared["objects"]]
    covered_total = executable_total = 0
    files, seen = [], set()
    for item in report["files"]:
        uri = handlers.source_uri(item["uri"])
        if uri.lower() in seen or not any(uri.lower().startswith(p) for p in selected):
            raise ValueError("Coverage file is duplicated or outside the selected Unit objects")
        seen.add(uri.lower())
        result = handlers.get_source(uri)
        if result.is_error:
            raise ValueError("Coverage source could not be verified")
        source = result.data["source"]
        if source_write.sha256_text(source_write.canonical_source(source)) != item.get("source_sha256"):
            raise ValueError("Coverage source hash differs from current SAP source")
        lines, covered = item.get("executable_lines"), item.get("covered_lines")
        if not isinstance(lines, list) or not isinstance(covered, list):
            raise ValueError("Coverage requires executable_lines and covered_lines arrays")
        if any(type(n) is not int or not 1 <= n <= result.data["line_count"] for n in lines + covered):
            raise ValueError("Coverage line is outside the source document")
        if len(set(lines)) != len(lines) or len(set(covered)) != len(covered) or not set(covered) <= set(lines):
            raise ValueError("Coverage lines must be unique; covered must be executable")
        executable_total += len(lines)
        covered_total += len(covered)
        files.append({**item, "uri": uri})
    return {
        "status": "available" if executable_total else "not_run",
        "provider": "supplied-source-bound-line-coverage",
        "percent": 100 * covered_total / executable_total if executable_total else None,
        "covered_lines": covered_total, "executable_lines": executable_total,
        "files": files, "evidence_gaps": [],
        "report_sha256": hashlib.sha256(artifacts.json_bytes(report)).hexdigest(),
        "scope": "supplied files only; measurement authenticity and full-scope coverage are not attested",
    }


def bind_options(prepared, coverage_report, bundle, minimum):
    if bundle is None and minimum is None and coverage_report.get("report_sha256") is None:
        return
    prepared["evidence_options"] = {
        "bundle": str(Path(bundle).resolve()) if bundle else None,
        "min_coverage": minimum, "coverage_report_sha256": coverage_report.get("report_sha256")}
    prepared["plan_sha256"] = hashlib.sha256(artifacts.json_bytes({
        k: v for k, v in prepared.items() if k != "plan_sha256"})).hexdigest()


def gate(data, meta, coverage_report, minimum=None):
    if minimum is not None and (not math.isfinite(minimum) or not 0 <= minimum <= 100):
        raise ValueError("Minimum coverage must be between 0 and 100")
    state = data["summary"]["status"]
    reasons = []
    if state == "failed":
        status = "failed"
        reasons.append("UNIT_FAILURE")
    elif state != "passed" or meta.get("partial") or data.get("evidence_gaps"):
        status = "incomplete" if state != "not_run" else "not_run"
        reasons.append("UNIT_EVIDENCE_INCOMPLETE")
    else:
        status = "passed"
    if minimum is not None:
        if coverage_report["percent"] is None:
            reasons.append("COVERAGE_UNAVAILABLE")
            if status != "failed":
                status = "incomplete"
        elif coverage_report["percent"] < minimum:
            status = "failed"
            reasons.append("COVERAGE_BELOW_THRESHOLD")
    return {"status": status, "reasons": reasons, "min_coverage": minimum,
            "coverage_scope": "supplied verified-source files only",
            "policy": "unit-evidence-v1", "release_approval": False}


def skeleton(name, path):
    name = name.upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,25}", name):
        raise ValueError("Test class name must contain 1..26 ABAP identifier characters")
    source = (
        f"CLASS {name.lower()} DEFINITION FINAL FOR TESTING\n"
        "  DURATION SHORT RISK LEVEL HARMLESS.\n"
        "  PRIVATE SECTION.\n"
        "    METHODS requires_specification FOR TESTING.\n"
        "ENDCLASS.\n\n"
        f"CLASS {name.lower()} IMPLEMENTATION.\n"
        "  METHOD requires_specification.\n"
        "    cl_abap_unit_assert=>fail( msg = 'Replace with a specification-based test' ).\n"
        "  ENDMETHOD.\n"
        "ENDCLASS.\n"
    )
    with open(path, "x", encoding="utf-8") as stream:
        stream.write(source)
    return {"path": str(Path(path).resolve()), "source": source, "uploaded": False,
            "status": "template_requires_business_assertions"}
