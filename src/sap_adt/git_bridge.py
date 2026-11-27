"""Read-only local Git evidence and explicit TR-to-repository-file exports."""
from __future__ import annotations

import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

from . import artifacts


def _git(repo, *args, allow_failure=False):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1",
               GIT_CONFIG_GLOBAL=os.devnull)
    argv = (
        ["git", "--no-pager", "--no-optional-locks", "-c", "core.fsmonitor=false",
         "-c", f"core.hooksPath={os.devnull}", "-C", str(repo), *args])
    with subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) as process:
        def drain(stream, limit):
            output = bytearray()
            while chunk := stream.read(65536):
                if len(output) + len(chunk) > limit:
                    process.kill()
                    return bytes(output), True
                output.extend(chunk)
            return bytes(output), False
        with ThreadPoolExecutor(max_workers=2) as pool:
            stdout = pool.submit(drain, process.stdout, 8 * 1024 * 1024)
            stderr = pool.submit(drain, process.stderr, 1024 * 1024)
            try:
                code = process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise
            out, out_limit = stdout.result()
            err, err_limit = stderr.result()
    if out_limit or err_limit:
        raise ValueError("Git output exceeds its byte budget")
    result = subprocess.CompletedProcess(argv, code, out, err)
    if result.returncode and not allow_failure:
        raise ValueError("Local Git operation failed; check the explicit repository and revision")
    return result


def repository(path):
    root = Path(path).resolve(strict=True)
    actual = Path(_git(root, "rev-parse", "--show-toplevel").stdout.decode().strip()).resolve()
    if actual != root:
        raise ValueError("--repo must name the repository root")
    return root


def status(path):
    root = repository(path)
    raw = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
    tokens = raw.decode("utf-8").split("\0")
    changes, i = [], 0
    while i < len(tokens) and tokens[i]:
        token = tokens[i]
        if len(token) < 4:
            raise ValueError("Unrecognized Git status record")
        entry = {"status": token[:2], "path": token[3:]}
        if "R" in token[:2] or "C" in token[:2]:
            i += 1
            if i >= len(tokens) or not tokens[i]:
                raise ValueError("Git rename/copy record has no original path")
            entry["original_path"] = tokens[i]
        changes.append(entry)
        i += 1
    branch = _git(root, "symbolic-ref", "--short", "-q", "HEAD", allow_failure=True)
    head = _git(root, "rev-parse", "--verify", "HEAD", allow_failure=True)
    return {"repository": str(root), "branch": branch.stdout.decode().strip() or None,
            "head": head.stdout.decode().strip() if head.returncode == 0 else None,
            "changes": changes, "clean": not changes,
            "evidence_gaps": [],
            "scope": "local working tree/index; no fetch, remote contact, commit or push"}


def _path(root, name):
    if not isinstance(name, str) or not name:
        raise ValueError("Mapping files must be relative paths")
    relative = PurePosixPath(name)
    if (relative.is_absolute() or "\\" in name or any(
            p in ("", ".", "..", ".git") or p.startswith(".env") for p in name.split("/"))):
        raise ValueError("Mapping path escapes its declared source scope")
    target = (root / name).resolve()
    if not target.is_relative_to(root) or target.suffix.lower() not in (".abap", ".xml", ".json"):
        raise ValueError("Only in-repository ABAP/XML/JSON object files may be mapped")
    return target


def mapping(path, trkorr, mapping_file, *, commit=None, verify_transport=False, config=None):
    from .adt import handlers
    from . import policy
    if not handlers._valid_trkorr(trkorr):
        raise ValueError("Invalid transport number")
    root = repository(path)
    manifest = artifacts.read_json(mapping_file)
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != 1
            or manifest.get("transport", "").upper() != trkorr.upper()
            or not isinstance(manifest.get("objects"), list) or not 1 <= len(manifest["objects"]) <= 500):
        raise ValueError("Mapping needs schema_version=1, matching transport and 1..500 objects")
    state = status(root)
    revision = None
    changed = {p for item in state["changes"] for p in (
        item["path"], item.get("original_path")) if p}
    if commit:
        if not re.fullmatch(r"[A-Za-z0-9_./~^{}@-]{1,200}", commit):
            raise ValueError("Unsupported Git revision expression")
        revision = _git(root, "rev-parse", "--verify", "--end-of-options",
                        commit + "^{commit}").stdout.decode().strip()
        if not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", revision):
            raise ValueError("Git revision did not resolve to a commit")
        changed = set(filter(None, _git(root, "diff-tree", "--root", "--no-commit-id",
            "--name-only", "-r", "-z", revision, "--").stdout.decode("utf-8").split("\0")))
    rows, seen, gaps = [], set(), []
    identities = set()
    for obj in manifest["objects"]:
        identity = tuple(obj.get(k) for k in ("pgmid", "type", "name"))
        if not all(isinstance(v, str) and v for v in identity) or identity in identities:
            raise ValueError("Mapping object identities must be unique pgmid/type/name triples")
        identities.add(identity)
        if not isinstance(obj.get("files"), list) or not obj["files"]:
            raise ValueError("Each mapping object needs explicit repository files")
        for name in obj["files"]:
            _path(root, name)
            if name in seen:
                raise ValueError("A repository file cannot belong to multiple mapping entries")
            seen.add(name)
        rows.append({"object": {k: obj[k] for k in ("pgmid", "type", "name")},
                     "files": obj["files"], "changed_files": sorted(set(obj["files"]) & changed)})
    if verify_transport:
        if config is None:
            raise ValueError("Online transport verification requires an explicit connection")
        from .transport import analysis
        from .adt import client
        with client.connection_scope(config):
            objects, _, missing = analysis.objects(trkorr, 100)
        gaps.extend(missing)
        actual = {(o["pgmid"], o["type"], o["name"]) for o in objects}
        for row in rows:
            identity = tuple(row["object"][k] for k in ("pgmid", "type", "name"))
            if identity not in actual:
                gaps.append({"code": "MAPPING_OBJECT_NOT_VERIFIED_IN_TRANSPORT", "object": row["object"]})
    else:
        gaps.append({"code": "TRANSPORT_MEMBERSHIP_NOT_VERIFIED",
                     "message": "Mapping is caller-supplied; use --verify-transport for current SAP membership."})
    return {"repository": str(root), "transport": trkorr.upper(), "commit": revision,
            "target": policy.target(config) if verify_transport else None,
            "mapping": rows, "unmapped_changed_files": sorted(changed - seen),
            "transport_verified": verify_transport and not gaps, "evidence_gaps": gaps,
            "content_scope": "selected commit blobs" if revision else "current working-tree bytes, not index blobs",
            "scope": "explicit object/file mapping; commit provenance is not inferred"}


def export(path, trkorr, mapping_file, output_file, **options):
    data = mapping(path, trkorr, mapping_file, **options)
    root, assets = Path(data["repository"]), {}
    for row in data["mapping"]:
        for name in row["changed_files"]:
            try:
                if data["commit"]:
                    raw = _git(root, "cat-file", "blob", data["commit"] + ":" + name).stdout
                else:
                    with _path(root, name).open("rb") as stream:
                        raw = stream.read(8 * 1024 * 1024 + 1)
                    if len(raw) > 8 * 1024 * 1024:
                        raise ValueError("Mapped file exceeds 8 MiB")
                assets["files/" + name] = raw
            except (OSError, ValueError):
                data["evidence_gaps"].append({"code": "MAPPED_FILE_CONTENT_UNAVAILABLE", "path": name,
                    "message": "Deleted/missing files remain in mapping; absence is not an empty source."})
    config = root / ".abapgit.xml"
    raw = None
    if data["commit"]:
        spec = data["commit"] + ":.abapgit.xml"
        if _git(root, "cat-file", "-e", spec, allow_failure=True).returncode == 0:
            raw = _git(root, "cat-file", "blob", spec).stdout
    elif config.is_file() and config.resolve().is_relative_to(root):
        with config.open("rb") as stream:
            raw = stream.read(1024 * 1024 + 1)
    if raw is not None:
        if len(raw) > 1024 * 1024:
            raise ValueError("abapGit configuration exceeds 1 MiB")
        assets["files/.abapgit.xml"] = raw
    data["serialization"] = {
        "format": "existing-repository-files", "server_abapgit_serialization": False,
        "abapgit_config_included": "files/.abapgit.xml" in assets,
        "message": "No SAP abapGit serializer is invoked; repository file compatibility is not certified."}
    assets["mapping.json"] = data
    data["bundle"] = artifacts.write_package(output_file, "git-change-set", assets,
        context={"transport": trkorr.upper(), "commit": data["commit"],
                 "target": data["target"]}, gaps=data["evidence_gaps"])
    return data
