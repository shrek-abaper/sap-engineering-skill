"""Hash-bound, dependency-ordered changes; evidence is not an atomic transaction."""
from __future__ import annotations

import json
from pathlib import Path

from .. import errors
from . import development, handlers, lifecycle, source_write, unit_regression


def _file(directory, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError("manifest files must be relative to the manifest directory")
    path = (directory / relative).resolve()
    if not path.is_relative_to(directory):
        raise ValueError("manifest file escapes its directory")
    content = path.read_bytes()
    if len(content) > 2097152:
        raise ValueError("manifest source exceeds 2 MiB")
    return source_write.canonical_source(source_write.decode_local(content))


def prepare(path, target):
    manifest_path = Path(path).resolve()
    raw = manifest_path.read_bytes()
    if len(raw) > 2097152:
        raise ValueError("manifest exceeds 2 MiB")
    def unique(pairs):
        data = {}
        for key, value in pairs:
            if key in data:
                raise ValueError("duplicate manifest key: " + key)
            data[key] = value
        return data
    manifest = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    if (not isinstance(manifest, dict) or set(manifest) - {
            "schema_version", "operations", "activate", "unit", "atc"}
            or type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1):
        raise ValueError("unsupported change manifest schema/fields")
    operations = manifest.get("operations")
    if not isinstance(operations, list) or not 1 <= len(operations) <= 100:
        raise ValueError("manifest requires 1-100 explicit operations")
    by_id, identities = {}, set()
    for operation in operations:
        if not isinstance(operation, dict) or set(operation) - {
                "id", "depends_on", "action", "type", "name", "group", "file",
                "transport", "part", "check", "package", "description",
                "software_component", "transport_layer", "service_definition",
                "binding_protocol", "binding_category"}:
            raise ValueError("invalid operation fields")
        key = operation.get("id")
        if not isinstance(key, str) or not key or key in by_id:
            raise ValueError("operation IDs must be unique nonempty strings")
        if (operation.get("action") not in ("write-source", "write-definition", "create-object")
                or operation.get("type") not in development.SPECS
                or not isinstance(operation.get("name"), str)):
            raise ValueError("unsupported change operation or object")
        common = {"id", "depends_on", "action", "type", "name", "group", "transport"}
        specific = {
            "write-source": {"file", "part", "check"},
            "write-definition": {"file"},
            "create-object": {"package", "description", "software_component", "transport_layer",
                              "service_definition", "binding_protocol", "binding_category"},
        }
        if set(operation) - common - specific[operation["action"]]:
            raise ValueError("operation includes options for a different action")
        uri = development.object_uri(operation["type"], operation["name"], operation.get("group"))
        identity = (uri, operation.get("part", "main"))
        if identity in identities:
            raise ValueError("duplicate object/source-part identity")
        identities.add(identity)
        dependencies = operation.get("depends_on", [])
        if not isinstance(dependencies, list) or any(not isinstance(d, str) for d in dependencies):
            raise ValueError("depends_on must be an array of operation IDs")
        if "check" in operation and not isinstance(operation["check"], bool):
            raise ValueError("check must be boolean")
        if operation["action"] != "write-source" and "part" in operation:
            raise ValueError("part applies only to text source writes")
        by_id[key] = operation
    order, visiting = [], set()
    def visit(key):
        if key not in by_id:
            raise ValueError("unknown dependency: " + key)
        if key in visiting:
            raise ValueError("cyclic change dependencies")
        if key in order:
            return
        visiting.add(key)
        for parent in by_id[key].get("depends_on", []):
            visit(parent)
        visiting.remove(key)
        order.append(key)
    for key in by_id:
        visit(key)
    items = []
    for key in order:
        op = by_id[key]
        kind, name, group = op["type"], op["name"].upper(), op.get("group")
        uri = development.object_uri(kind, name, group)
        item = {"id": key, "action": op["action"], "operation": op}
        if op["action"] == "create-object":
            if manifest.get("activate") or manifest.get("unit") or manifest.get("atc"):
                raise ValueError("creation is a separate reviewed phase before source/activation/test")
            options = {k: op[k] for k in (
                "package", "description", "transport", "group", "software_component",
                "transport_layer", "service_definition", "binding_protocol", "binding_category") if k in op}
            item["plan"] = development.creation_plan(kind, name, target=target, **options)
        else:
            content = _file(manifest_path.parent, op.get("file"))
            item["file_sha256"] = source_write.sha256_text(content)
            if op["action"] == "write-definition":
                item["plan"] = lifecycle.plan(kind, name, target=target,
                    transport=op.get("transport"), group=group, content=content)
            else:
                baseline = handlers.read_source_main(uri, part=op.get("part", "main"))
                if baseline.is_error:
                    raise ValueError("unobserved baseline; create objects in a separately reviewed phase: " + baseline.text)
                plan = source_write.WritePlan(kind, name, group, uri, op.get("transport"),
                    False, target, source_write.canonical_source(baseline.text), content,
                    part=op.get("part", "main"), check_before_write=op.get("check", True))
                item["plan"] = {**plan.__dict__, "plan_sha256": plan.plan_sha256}
        items.append(item)
    unit = manifest.get("unit")
    if unit is not None:
        if not isinstance(unit, dict) or set(unit) - {"objects", "type", "group", "risk_levels", "durations"}:
            raise ValueError("invalid Unit gate")
        selected = unit.get("objects", [])
        if not isinstance(selected, list) or not selected or len(selected) > 100:
            raise ValueError("Unit gate requires 1-100 explicit object names")
        if unit.get("type", "class") not in ("class", "program", "interface", "include", "function", "function-group"):
            raise ValueError("unsupported Unit gate type")
        unit = unit_regression.plan(selected, unit.get("type", "class"), unit.get("group"),
            None, None, False, 100,
            unit_regression.selection(unit.get("risk_levels", ["harmless"]), unit_regression.RISKS),
            unit_regression.selection(unit.get("durations", ["short"]), unit_regression.DURATIONS), target)
    atc = manifest.get("atc", [])
    if not isinstance(atc, list) or len(atc) > 100:
        raise ValueError("ATC gate must contain at most 100 explicit objects")
    for obj in atc:
        if not isinstance(obj, dict) or set(obj) - {"type", "name", "group", "variant"}:
            raise ValueError("invalid ATC gate fields")
        if obj.get("type") not in ("class", "program", "interface", "include", "function"):
            raise ValueError("unsupported ATC object type")
        handlers.get_object_uri(obj["type"], obj["name"], group=obj.get("group"))
    activate = manifest.get("activate", False)
    if not isinstance(activate, bool):
        raise ValueError("activate must be boolean")
    if (unit or atc) and not activate:
        raise ValueError("final Unit/ATC evidence requires explicit activate=true")
    if activate and any(i["action"] == "write-definition" for i in items):
        raise ValueError("XML definitions require separate explicit activation before regression")
    data = {"action": "apply-change-set", "target": target, "manifest": str(manifest_path),
            "manifest_sha256": lifecycle.digest(manifest), "operations": items,
            "activate": activate, "unit": unit, "atc": atc,
            "semantics": "sequential verified writes; no atomicity or automatic rollback"}
    data["plan_sha256"] = lifecycle.digest(data)
    return data


def execute(plan):
    data = {"plan": plan, "operations": [], "activation": "not_attempted",
            "gates": [], "outcome": "not_changed", "unattempted": []}
    try:
        current = prepare(plan["manifest"], plan["target"])
        if current["plan_sha256"] != plan["plan_sha256"]:
            raise ValueError("manifest, source files or SAP baselines changed after confirmation")
        for item in plan["operations"]:
            op, prepared = item["operation"], item["plan"]
            data["outcome"] = "incomplete"
            data["operations"].append({"id": item["id"], "evidence": None,
                                       "error": "outcome unknown; inspect before retrying"})
            if item["action"] == "create-object":
                result = development.create(prepared)
            elif item["action"] == "write-definition":
                result = lifecycle.execute(prepared)
            else:
                write = source_write.WritePlan(**{k: v for k, v in prepared.items()
                                                   if k != "plan_sha256"})
                report = source_write.execute(write, current_content_sha256=lambda op=op:
                    source_write.sha256_text(_file(Path(plan["manifest"]).parent, op["file"])))
                failure = report.final_decision()
                result = handlers.AdtResult(kind="write", data=report.to_data(),
                    is_error=failure is not None, error_code=failure.code if failure else None,
                    text=failure.message if failure else "")
            data["operations"][-1] = {"id": item["id"], "evidence": result.data,
                                      "error": result.text if result.is_error else None}
            if result.is_error:
                raise ValueError("operation failed or outcome unknown: " + item["id"])
        if plan["activate"]:
            objects = {}
            for item in plan["operations"]:
                op = item["operation"]
                uri = handlers.get_object_uri(op["type"], op["name"], group=op.get("group"))
                objects[uri] = {"type": op["type"], "name": op["name"], "group": op.get("group")}
            data["activation"] = "unknown"
            result = handlers.activate_objects(list(objects.values()))
            if result.is_error:
                raise ValueError(result.text)
            for item in plan["operations"]:
                prepared = item["plan"]
                active = handlers.read_source_main(prepared["object_uri"], version="active",
                                                  part=prepared["part"])
                version = handlers.object_version(prepared["object_uri"])
                if (active.is_error or version.is_error or version.text.lower() != "active"
                        or source_write.canonical_source(active.text) != prepared["content"]):
                    raise ValueError("combined activation/readback not verified")
            data["activation"] = "verified"
        if plan["unit"]:
            result = unit_regression.run(plan["unit"])
            data["gates"].append({"kind": "unit", "evidence": result.data})
            if result.is_error or result.meta.get("partial") or result.meta.get("no_tests_found") or result.data["summary"]["status"] != "passed":
                raise ValueError("final Unit gate did not pass")
        for obj in plan["atc"]:
            result = handlers.run_atc(obj["type"], obj["name"], group=obj.get("group"),
                                      variant=obj.get("variant", "STANDARD"), max_results=1000)
            data["gates"].append({"kind": "atc", "object": obj, "evidence": result.data})
            meta = result.meta or {}
            if (result.is_error or meta.get("partial") or meta.get("result_incomplete")
                    or meta.get("unparsed_nodes") or len((result.data or {}).get("findings", [])) >= 1000 or any(
                    f.get("severity") == "error" and not f.get("exempted")
                    for f in (result.data or {}).get("findings", []))):
                raise ValueError("final ATC gate did not pass")
        data["outcome"] = "completed"
        return handlers.AdtResult(kind="scalar", data=data)
    except (Exception, KeyboardInterrupt) as exc:
        data["unattempted"] = [i["id"] for i in plan["operations"][len(data["operations"]):]]
        return handlers.AdtResult(kind="scalar", data=data, is_error=True,
            error_code=errors.WRITE_INCOMPLETE if data["outcome"] == "incomplete" else errors.BASELINE_CHANGED,
            text=(str(exc) or "Interrupted; remote state is unconfirmed") +
                 "; completed changes remain; do not replay automatically")
