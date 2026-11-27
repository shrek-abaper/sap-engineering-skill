"""Private, explicitly requested evidence archives with verifiable manifests."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def read_json(path, limit=10 * 1024 * 1024):
    with open(path, "rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("JSON artifact exceeds the byte budget")
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate JSON key")
            value[key] = item
        return value
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def write_package(path, kind, assets, *, context=None, gaps=None):
    if len(assets) > 500:
        raise ValueError("Package exceeds 500 assets")
    normalized, entries = {}, []
    total = 0
    for name, value in assets.items():
        member = PurePosixPath(name)
        if (member.is_absolute() or any(p in (".", "..") for p in name.split("/"))
                or "\\" in name or name == "manifest.json" or not name):
            raise ValueError("Invalid package member name")
        raw = value if isinstance(value, bytes) else json_bytes(value)
        total += len(raw)
        if len(raw) > 20 * 1024 * 1024 or total > 100 * 1024 * 1024:
            raise ValueError("Package exceeds the byte budget")
        normalized[name] = raw
        entries.append({"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    manifest = {
        "schema_version": 1, "kind": kind, "created_at": datetime.now(timezone.utc).isoformat(),
        "context": context or {}, "assets": sorted(entries, key=lambda a: a["path"]),
        "evidence_gaps": gaps or [], "partial": bool(gaps),
        "snapshot_semantics": "individually captured evidence; not an atomic SAP snapshot",
    }
    destination = Path(path)
    created = False
    try:
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        created = True
        with os.fdopen(fd, "wb") as stream, ZipFile(stream, "w", ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json_bytes(manifest))
            for name in sorted(normalized):
                archive.writestr(name, normalized[name])
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise
    return {"path": str(destination.resolve()), "manifest": manifest,
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}
