"""Native SAP quality checks and explicitly bound abaplint JSON evidence."""
from __future__ import annotations

import hashlib

from .. import artifacts, policy
from . import comparison, handlers


def lint_report(path, manifest_path, config, kind, name, group):
    if not path or not manifest_path:
        return {"engine": "abaplint", "status": "unavailable", "findings": [],
                "evidence_gaps": [{"code": "ABAPLINT_BOUND_REPORT_REQUIRED"}]}
    report, manifest = artifacts.read_json(path), artifacts.read_json(manifest_path)
    if not isinstance(report, list) or len(report) > 10000:
        raise ValueError("abaplint --format json must be an array of at most 10000 issues")
    current = comparison.snapshot(kind, name, group=group)
    if (manifest.get("schema_version") != 1 or manifest.get("completed") is not True
            or type(manifest.get("files_checked")) is not int or manifest["files_checked"] < 1
            or not isinstance(manifest.get("engine_version"), str) or not manifest["engine_version"]
            or manifest.get("target_fingerprint") != policy.target(config)["fingerprint"]
            or manifest.get("source_sha256") != current["sha256"]
            or manifest.get("report_sha256") != hashlib.sha256(artifacts.json_bytes(report)).hexdigest()):
        raise ValueError("abaplint completion, report hash, target or active source binding is invalid")
    if manifest.get("object_uri") != current["uri"]:
        raise ValueError("abaplint manifest names a different source URI")
    source_file = manifest.get("source_file")
    if not isinstance(source_file, str) or not source_file:
        raise ValueError("abaplint manifest must identify its one source_file")
    findings = []
    for issue in report:
        if (not isinstance(issue, dict) or issue.get("file") != source_file
                or issue.get("severity") not in ("Error", "Warning", "Info", "error", "warning", "info")
                or not isinstance(issue.get("description"), str) or not issue.get("key")
                or not isinstance(issue.get("start"), dict)
                or type(issue["start"].get("row")) is not int or issue["start"]["row"] < 1):
            raise ValueError("Unsupported abaplint issue schema, severity or source-file scope")
        findings.append({"severity": issue["severity"].lower(), "text": issue["description"],
                         "line": issue["start"]["row"], "column": issue["start"].get("col"),
                         "rule_id": issue["key"], "uri": current["uri"], "file": issue["file"]})
    return {"engine": "abaplint", "status": "available", "findings": findings,
            "provenance": manifest, "evidence_gaps": [],
            "attestation": "caller-supplied measurement; hashes/source binding verified, execution not attested"}


def collect(config, kind, name, *, group=None, variant="STANDARD",
            engines=("syntax", "atc"), fail_on="error", abaplint_report=None,
            abaplint_manifest=None):
    requested = list(dict.fromkeys(engines))
    if not requested or set(requested) - {"syntax", "atc", "abaplint"}:
        raise ValueError("Select syntax, atc and/or abaplint")
    if abaplint_report or abaplint_manifest:
        if "abaplint" not in requested:
            requested.append("abaplint")
    results, findings, gaps = [], [], []
    severities = {"error": {"error"}, "warning": {"error", "warning"},
                  "info": {"error", "warning", "info"}}
    if fail_on not in severities:
        raise ValueError("Unknown quality threshold")
    for engine in requested:
        if engine == "abaplint":
            try:
                item = lint_report(abaplint_report, abaplint_manifest, config, kind, name, group)
            except Exception as exc:
                item = {"engine": engine, "status": "incomplete", "findings": [],
                        "evidence_gaps": [{"code": "ABAPLINT_EVIDENCE_INVALID", "message": str(exc)}]}
        else:
            result = (handlers.syntax_check(kind, name, group) if engine == "syntax" else
                      handlers.run_atc(kind, name, group, variant=variant))
            if result.is_error:
                item = {"engine": engine, "status": "unavailable", "findings": [],
                        "evidence_gaps": [{"code": result.error_code, "message": result.text}]}
            else:
                meta = result.meta or {}
                item = {"engine": engine, "status": "available", "findings": result.data["findings"],
                        "meta": meta, "evidence_gaps": []}
                if meta.get("result_incomplete") or meta.get("partial") or meta.get("unparsed_nodes"):
                    item["status"] = "incomplete"
                    item["evidence_gaps"].append({"code": "QUALITY_RESULT_INCOMPLETE"})
                if any(f.get("severity") not in ("error", "warning", "info") for f in item["findings"]):
                    item["status"] = "incomplete"
                    item["evidence_gaps"].append({"code": "QUALITY_SEVERITY_UNKNOWN"})
        blocking = any(f.get("severity") in severities[fail_on] and not f.get("exempted")
                       for f in item["findings"])
        if item["status"] == "available":
            item["status"] = "failed" if blocking else "passed"
        item["blocking_findings"] = blocking
        results.append(item)
        findings.extend({**f, "engine": engine} for f in item["findings"])
        gaps.extend({**g, "engine": engine} for g in item["evidence_gaps"])
    status = ("failed" if any(r["blocking_findings"] for r in results) else
              "incomplete" if gaps or any(r["status"] != "passed" for r in results) else "passed")
    return {"target": policy.target(config), "object": {"type": kind, "name": name.upper()},
            "engines": results, "findings": findings, "evidence_gaps": gaps,
            "gate": {"status": status, "fail_on": fail_on, "policy": "quality-evidence-v1",
                     "required_engines": requested, "release_approval": False}}
