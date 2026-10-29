#!/usr/bin/env python3
"""Smoke-test dist/npm with a local runtime, without publishing or SAP access.

Run build_runtime.py on each target OS, then build_npm.py before this tool.
Uses a temporary global npm prefix and cache; never modifies the user's npm
installation or the publishable manifest. Requires Python and Node on the
target OS (WSL can invoke Windows Python).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from build_runtime import target_id

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    target = target_id()
    staging = ROOT / "dist" / "npm"
    manifest = json.loads((staging / "runtime-manifest.json").read_text(encoding="utf-8"))
    entry = manifest["artifacts"].get(target)
    if not entry:
        raise SystemExit(f"No {target} artifact in dist/npm; build its runtime and rerun build_npm.py.")
    version = manifest["cli_version"]
    archive = ROOT / "dist" / "runtime" / f"sap-adt-{version}-{target}.{entry['format']}"
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest.lower() != entry["sha256"].lower():
        raise SystemExit("Runtime SHA-256 differs from dist/npm; rerun build_npm.py.")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise SystemExit("npm is required on the target OS.")

    with tempfile.TemporaryDirectory(prefix="sap-adt-npm-smoke-") as tmp:
        work = Path(tmp)
        pkg = work / "pkg"
        pkg.mkdir()
        for name in ("package.json", "README.md", "LICENSE"):
            shutil.copy2(staging / name, pkg / name)
        shutil.copytree(staging / "scripts", pkg / "scripts")
        # Local test URLs must never leak into the publishable staging tree.
        entry["url"] = archive.as_uri()
        manifest["release_state"] = "local-test"
        (pkg / "runtime-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        cache = str(work / "cache")
        packed = subprocess.run(
            [npm, "pack", str(pkg), "--json", "--ignore-scripts", "--offline", "--cache", cache],
            cwd=work, capture_output=True, text=True, check=True,
        )
        tarball = work / json.loads(packed.stdout)[0]["filename"]
        prefix = work / "global"
        subprocess.run(
            [npm, "install", "--global", "--prefix", str(prefix), "--cache", cache,
             "--offline", "--ignore-scripts", "--no-audit", "--no-fund", str(tarball)],
            cwd=work, check=True,
        )
        bin_path = prefix / "sap-adt.cmd" if os.name == "nt" else prefix / "bin" / "sap-adt"
        env = {**os.environ, "SAP_ADT_INSTALL_ALLOW_FILE": "1"}
        subprocess.run([str(bin_path), "install"], cwd=work, env=env, check=True)
        actual = subprocess.run(
            [str(bin_path), "--version"], cwd=work, capture_output=True, text=True, check=True,
        ).stdout.strip()
        if actual != f"sap-adt, version {version}":
            raise SystemExit(f"Unexpected runtime version: {actual}")
        help_text = subprocess.run(
            [str(bin_path), "--help"], cwd=work, capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=True,
        ).stdout
        for command in ("configure", "update", "list-feeds", "query-feed",
                        "get-versions", "get-version-source", "diff-versions",
                        "get-transport", "Setup and maintenance", "ADT commands"):
            if command not in help_text:
                raise SystemExit(f"Runtime --help does not list {command}.")
        subprocess.run(
            [str(bin_path), "transport", "diff", "--help"], cwd=work,
            capture_output=True, text=True, check=True,
        )
        print(f"[smoke_npm] OK: {target}: npm pack -> global install -> runtime install -> {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
