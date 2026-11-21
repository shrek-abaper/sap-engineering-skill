"""Bounded ABAP Unit selection, reviewed execution scope and local JUnit."""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET

from . import handlers
from .. import errors

RISKS = ("harmless", "dangerous", "critical")
DURATIONS = ("short", "medium", "long")
TYPES = {
    "CLAS": "class", "PROG": "program", "REPS": "include",
    "FUGR": "function-group", "INTF": "interface",
}
_NAME = re.compile(r"(?:/[A-Z0-9_]+/)?[A-Z$][A-Z0-9_$]*\Z", re.ASCII)


class SelectionError(ValueError):
    def __init__(self, result):
        super().__init__(result.text)
        self.result = result


def selection(values, allowed):
    chosen = set(values)
    if chosen - set(allowed) - {"all"}:
        raise ValueError("Invalid Unit selection")
    if "all" in chosen:
        chosen = set(allowed)
    if not chosen or not chosen <= set(allowed):
        raise ValueError("Invalid or empty Unit selection")
    return [v for v in allowed if v in chosen]


def plan(names, object_type, group, package, transport, recursive, limit,
         risks, durations, target, *, junit=None):
    if not 1 <= limit <= 500:
        raise ValueError("Unit selection limit must be between 1 and 500")
    if sum((bool(names), bool(package), bool(transport))) != 1:
        raise ValueError("Choose object names, --package or --transport, exclusively")
    if recursive and not package:
        raise ValueError("--recursive requires --package")
    objects, excluded, visited = {}, [], set()

    def add(typ, name, parent=None):
        name = (name or "").upper()
        if not _NAME.fullmatch(name) or len(name) > 40:
            raise ValueError("Invalid Unit object name")
        uri = handlers._unit_uri(typ, name, parent)
        objects[uri] = {"type": typ, "name": name, "group": parent, "uri": uri}
        if len(objects) > limit:
            raise ValueError("Unit selection exceeds --max-objects; nothing executed")

    def unwrap(result):
        if result.is_error:
            raise SelectionError(result)
        if (result.meta or {}).get("partial"):
            raise ValueError("Cannot execute a partial Unit object selection")
        return result.data

    def entries(items):
        for item in items:
            adt_type = (item.get("type") or "").upper()
            raw = adt_type.split("/")[0]
            name = item.get("name")
            if adt_type == "PROG/I":
                add("include", name)
            elif raw in TYPES and not (raw == "FUGR" and adt_type not in ("FUGR", "FUGR/F")):
                add(TYPES[raw], name)
            elif raw == "DEVC" and recursive:
                packages.append(name)
            else:
                excluded.append({"type": raw, "name": name,
                                 "reason": "not a supported Unit container"})

    packages = [package] if package else []
    while packages:
        name = packages.pop(0)
        if name.upper() in visited:
            continue
        visited.add(name.upper())
        if len(visited) > limit:
            raise ValueError("Package traversal exceeds --max-objects")
        entries(unwrap(handlers.get_package(name))["objects"])
    if transport:
        requests = [transport.upper()]
        seen = set()
        while requests:
            number = requests.pop(0)
            if number in seen:
                continue
            seen.add(number)
            if len(seen) > limit:
                raise ValueError("Transport/task traversal exceeds --max-objects")
            detail = unwrap(handlers.get_transport(number))
            entries(detail["objects"])
            requests.extend(t["trkorr"] for t in detail["transport"].get("tasks", [])
                            if t.get("trkorr"))
    for name in names:
        add(object_type, name, group)
    result = {
        "target": target, "objects": sorted(objects.values(), key=lambda o: o["uri"]),
        "excluded": sorted(excluded, key=lambda o: (o["type"], o["name"] or "")),
        "risks": list(risks), "durations": list(durations),
        "scope": {"package": package, "transport": transport, "recursive": recursive},
        "local_artifacts": {"junit": junit},
        "source_binding": "selected-object-identities-not-atomic-source-snapshot",
        "protocol": "aunit-config-v4/sameProgram=true/assignedTests=false",
    }
    result["plan_sha256"] = hashlib.sha256(
        json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result


def run(prepared):
    runs, classes, findings, gaps = [], [], [], []
    counts = dict.fromkeys(("total", "executed", "passed", "failed", "skipped",
                           "unknown", "class_failures", "not_run_classes"), 0)
    duration_ms = 0
    states = []
    for obj in prepared["objects"]:
        try:
            result = handlers.run_unit_test(
                obj["type"], obj["name"], group=obj["group"],
                risk_level=(prepared["risks"][0] if len(prepared["risks"]) == 1
                            else prepared["risks"]),
                duration=(prepared["durations"][0] if len(prepared["durations"]) == 1
                          else prepared["durations"]))
        except KeyboardInterrupt:
            result = handlers.AdtResult(is_error=True, error_code=errors.EXECUTION_INCOMPLETE,
                                        text="Interrupted; Unit execution may still be running")
        if result.is_error:
            runs.append({"object": obj, "error": {
                "code": result.error_code, "message": result.text}, "data": None})
            gaps.append({"code": "UNIT_REQUEST_FAILED_OR_UNKNOWN", "object": obj,
                         "message": "Stopped; no execution request is replayed."})
            break
        data = result.data
        runs.append({"object": obj, "data": data, "meta": result.meta})
        classes.extend({**c, "object": obj} for c in data["test_classes"])
        findings.extend(data["findings"])
        gaps.extend(data["evidence_gaps"])
        states.append(data["summary"]["status"])
        for key in counts:
            counts[key] += data["summary"].get(key, 0)
        duration_ms += (result.meta or {}).get("duration_ms") or 0
    if len(runs) < len(prepared["objects"]):
        gaps.append({"code": "OBJECTS_NOT_ATTEMPTED",
                     "objects": prepared["objects"][len(runs):]})
    if not counts["executed"] and not gaps:
        gaps.append({"code": "NO_TESTS_EXECUTED", "message": "No test method executed."})
    status = ("failed" if "failed" in states else
              "incomplete" if any(r.get("error") for r in runs) or "incomplete" in states
              or (counts["executed"] and "not_run" in states) else
              "not_run" if not counts["executed"] else "passed")
    data = {"plan": prepared, "runs": runs, "test_classes": classes,
            "findings": findings, "summary": {"status": status, **counts},
            "evidence_gaps": gaps}
    meta = {"partial": status == "incomplete" or any(
                (r.get("meta") or {}).get("partial") or r.get("error") for r in runs),
            "no_tests_found": not counts["executed"],
            "duration_ms": duration_ms,
            "total": counts["total"], "failed": counts["failed"], "skipped": counts["skipped"],
            "duration_category": (runs[0].get("meta") or {}).get("duration_category")
            if len(runs) == 1 else None,
            "risk_level": prepared["risks"][0] if len(prepared["risks"]) == 1
            else prepared["risks"], "config_version": "v4"}
    problem = next((r["error"] for r in runs if r.get("error")), None)
    return handlers.AdtResult(
        kind="findings", data=data, meta=meta,
        raw=result.raw if len(runs) == 1 and not result.is_error else None,
        is_error=problem is not None, error_code=problem["code"] if problem else None,
        text=problem["message"] if problem else "")


def junit(data):
    root = ET.Element("testsuites")
    for run_result in data["runs"]:
        obj = run_result["object"]
        suite = ET.SubElement(root, "testsuite", name=obj["type"] + "/" + obj["name"])
        failures = errors = skipped = 0
        result = run_result.get("data")
        if result is None:
            case = ET.SubElement(suite, "testcase", name="execution")
            ET.SubElement(case, "error").text = json.dumps(run_result.get("error", {}))
            errors += 1
        else:
            for cls in result["test_classes"]:
                for method in cls["methods"]:
                    case = ET.SubElement(
                        suite, "testcase", classname=cls["name"] or "",
                        name=method["name"] or "",
                        time=str((method["duration_ms"] or 0) / 1000))
                    state = method["status"]
                    if state in ("failed", "unknown"):
                        ET.SubElement(case, "failure" if state == "failed" else "error").text = (
                            json.dumps(method["alerts"], ensure_ascii=False))
                        failures += state == "failed"
                        errors += state == "unknown"
                    elif state == "skipped":
                        ET.SubElement(case, "skipped")
                        skipped += 1
                if cls["alerts"] and cls["status"] in ("failed", "incomplete", "not_run"):
                    case = ET.SubElement(suite, "testcase", classname=cls["name"] or "",
                                         name="class-fixture")
                    tag = "skipped" if cls["status"] == "not_run" else "error"
                    ET.SubElement(case, tag).text = json.dumps(cls["alerts"])
                    skipped += tag == "skipped"
                    errors += tag == "error"
            if result["evidence_gaps"]:
                case = ET.SubElement(suite, "testcase", name="evidence")
                tag = "skipped" if result["summary"]["status"] == "not_run" else "error"
                ET.SubElement(case, tag).text = json.dumps(result["evidence_gaps"])
                skipped += tag == "skipped"
                errors += tag == "error"
        suite.set("tests", str(len(suite)))
        suite.set("failures", str(failures))
        suite.set("errors", str(errors))
        suite.set("skipped", str(skipped))
    if not data["runs"] or any(g["code"] == "OBJECTS_NOT_ATTEMPTED" for g in data["evidence_gaps"]):
        suite = ET.SubElement(root, "testsuite", name="selection", tests="1", errors="1")
        case = ET.SubElement(suite, "testcase", name="unexecuted-scope")
        ET.SubElement(case, "error").text = json.dumps(data["evidence_gaps"])
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
