"""Single-entity DDIC/data reads and key-based, bounded configuration differences."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from .. import policy
from . import client, comparison, handlers

IDENTIFIER = re.compile(r"(?:/[A-Z0-9_]+/)?[A-Z][A-Z0-9_]*\Z", re.ASCII)


def identifier(value):
    value = value.upper()
    if not IDENTIFIER.fullmatch(value) or len(value) > 40:
        raise ValueError("Invalid DDIC identifier")
    return value


def _records(sql, limit):
    result = handlers.run_sql(sql, limit)
    if result.is_error:
        raise ValueError(f"{result.error_code}: {result.text}")
    columns = [c["name"].upper() for c in result.data["columns"]]
    return [dict(zip(columns, row)) for row in result.data["rows"]]


def schema(name, kind):
    if kind not in ("table", "view"):
        raise ValueError("Configuration kind must be table or view")
    if kind == "view":
        rows = _records(f"SELECT VIEWNAME, VIEWCLASS FROM DD25L WHERE VIEWNAME = '{name}' AND AS4LOCAL = 'A'", 2)
        if len(rows) != 1 or rows[0].get("VIEWCLASS") not in ("D", "P"):
            raise ValueError("Only active database/projection views are queryable; maintenance/help views require explicit base-table evidence")
    else:
        rows = _records(f"SELECT TABNAME, TABCLASS FROM DD02L WHERE TABNAME = '{name}' AND AS4LOCAL = 'A'", 2)
        if len(rows) != 1 or rows[0].get("TABCLASS") not in ("TRANSP", "POOL", "CLUSTER"):
            raise ValueError("Expected an active database table")
    fields = _records(
        "SELECT FIELDNAME, KEYFLAG, DATATYPE, LENG, DECIMALS, POSITION FROM DD03L "
        f"WHERE TABNAME = '{name}' AND AS4LOCAL = 'A' ORDER BY POSITION", 1001)
    if not fields or len(fields) >= 1001:
        raise ValueError("DDIC field evidence is empty or exceeds 1000 fields")
    return [{"name": f["FIELDNAME"], "type": f["DATATYPE"], "length": f["LENG"],
             "decimals": f["DECIMALS"], "is_key": f["KEYFLAG"] == "X"}
            for f in fields if not f["FIELDNAME"].startswith(".")]


def read(config, name, *, kind="table", filters=(), columns=(), max_rows=100):
    name = identifier(name)
    if not 1 <= max_rows <= 1000:
        raise ValueError("Configuration row limit must be between 1 and 1000")
    fields = schema(name, kind)
    known = {f["name"] for f in fields}
    chosen = [identifier(c) for c in columns] if columns else [f["name"] for f in fields]
    if len(set(chosen)) != len(chosen) or not set(chosen) <= known:
        raise ValueError("Requested columns must be unique DDIC fields")
    clauses, selection = [], []
    for pair in filters:
        key, sep, value = pair.partition("=")
        key = identifier(key)
        if not sep or key not in known or len(value) > 1024:
            raise ValueError("Filters must be known FIELD=VALUE pairs (values at most 1024 chars)")
        clauses.append(key + " = '" + value.replace("'", "''") + "'")
        selection.append({"field": key, "equals": value})
    keys = [f["name"] for f in fields if f["is_key"]]
    sql = f"SELECT {', '.join(chosen)} FROM {name}"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    if keys:
        sql += " ORDER BY " + ", ".join(keys)
    result = handlers.run_sql(sql, max_rows + 1)
    if result.is_error:
        raise ValueError(f"{result.error_code}: {result.text}")
    rows = result.data["rows"]
    returned = [c["name"].upper() for c in result.data["columns"]]
    if returned != chosen or any(len(row) != len(chosen) for row in rows):
        raise ValueError("Data preview columns do not match the requested DDIC projection")
    truncated = len(rows) > max_rows
    return {
        "schema_version": 1, "target": policy.target(config), "entity": {"kind": kind, "name": name},
        "captured_at": datetime.now(timezone.utc).isoformat(), "fields": fields,
        "columns": result.data["columns"], "rows": rows[:max_rows], "filters": selection,
        "keys": keys, "client_field": next((f["name"] for f in fields if f["type"] == "CLNT"), None),
        "max_rows": max_rows, "complete_within_selection": not truncated,
        "evidence_gaps": ([{"code": "CONFIGURATION_ROW_LIMIT_REACHED", "limit": max_rows}] if truncated else []),
        "scope": "one DDIC entity under the current SAP client's Data Preview authorization; not SM30 authorization semantics",
    }


def difference(a, b, keys=(), include_client=False):
    gaps = list(a["evidence_gaps"]) + list(b["evidence_gaps"])
    ac, bc = ([c["name"].upper() for c in v["columns"]] for v in (a, b))
    if a["entity"] != b["entity"] or a["filters"] != b["filters"]:
        raise ValueError("Configuration comparison requires the same entity and filters")
    selected = list(keys) if keys else a["keys"]
    selected = [identifier(k) for k in selected]
    client_field = a["client_field"] if a["client_field"] == b["client_field"] else None
    ignored = [client_field] if client_field and not include_client else []
    selected = [k for k in selected if k not in ignored]
    af = {f["name"]: {k: v for k, v in f.items() if k != "is_key"} for f in a["fields"]}
    bf = {f["name"]: {k: v for k, v in f.items() if k != "is_key"} for f in b["fields"]}
    if ac != bc or af != bf or (not keys and a["keys"] != b["keys"]):
        return {"equal": None, "schema_changed": True, "from": a, "to": b,
                "evidence_gaps": gaps + [{"code": "CONFIGURATION_SCHEMA_CHANGED"}]}
    if not selected or len(set(selected)) != len(selected) or not set(selected) <= set(ac):
        raise ValueError("Comparison needs unique known --key fields or non-client DDIC keys")

    def index(snapshot):
        out = {}
        for row in snapshot["rows"]:
            value = dict(zip(ac, row))
            key = json.dumps([value[k] for k in selected], ensure_ascii=False)
            if key in out:
                gaps.append({"code": "CONFIGURATION_NON_UNIQUE_KEY", "key": selected})
            out[key] = {k: v for k, v in value.items() if k not in ignored}
        return out

    left, right = index(a), index(b)
    added = [right[k] for k in sorted(right.keys() - left.keys())]
    removed = [left[k] for k in sorted(left.keys() - right.keys())]
    changed = [{"key": json.loads(k), "from": left[k], "to": right[k]}
               for k in sorted(left.keys() & right.keys()) if left[k] != right[k]]
    return {"equal": not (added or removed or changed) if not gaps else None,
            "schema_changed": False, "keys": selected, "ignored_fields": ignored,
            "added_on_target": added if not gaps else None,
            "removed_on_target": removed if not gaps else None,
            "changed": changed if not any(g["code"] == "CONFIGURATION_NON_UNIQUE_KEY" for g in gaps) else None,
            "observed_only": bool(gaps),
            "from": a, "to": b, "evidence_gaps": gaps}


def compare(name, left, right, *, kind="table", filters=(), columns=(),
            max_rows=100, keys=(), include_client=False):
    configs = comparison.profiles(left, right)
    snapshots = []
    for config in configs:
        with client.connection_scope(config):
            snapshots.append(read(config, name, kind=kind, filters=filters,
                                  columns=columns, max_rows=max_rows))
    return difference(*snapshots, keys=keys, include_client=include_client)
