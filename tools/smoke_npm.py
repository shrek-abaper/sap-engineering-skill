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
from smoke_diagnostics import check_cli
from smoke_debugger import check_cli as check_debugger
from smoke_execution import check_cli as check_execution

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
        # Local test URLs must never leak into the publishable staging tree.
        entry["url"] = archive.as_uri()
        manifest["release_state"] = "local-test"
        cache = str(work / "cache")
        prefix = work / "global"
        manager = [npm, "--prefix", str(prefix), "--cache", cache]
        bins = {}
        packages = {}
        for package, folder, command in (
            ("sap-adt-cli", "npm", "sap-adt"), ("sap-watt", "npm-watt", "sap-watt"),
        ):
            staging = ROOT / "dist" / folder
            pkg = work / package
            pkg.mkdir()
            for name in ("package.json", "README.md", "LICENSE"):
                shutil.copy2(staging / name, pkg / name)
            shutil.copytree(staging / "scripts", pkg / "scripts")
            source_manifest = json.loads(
                (staging / "runtime-manifest.json").read_text(encoding="utf-8"))
            if source_manifest["cli_version"] != version or source_manifest["artifacts"][target]["sha256"] != digest:
                raise SystemExit(f"{package} runtime manifest does not match the shared runtime.")
            (pkg / "runtime-manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            packed = subprocess.run(
                [npm, "pack", str(pkg), "--json", "--ignore-scripts", "--offline", "--cache", cache],
                cwd=work, capture_output=True, text=True, check=True,
            )
            tarball = work / json.loads(packed.stdout)[0]["filename"]
            packages[package] = tarball
            subprocess.run(
                [*manager, "install", "--global", "--offline", "--ignore-scripts",
                 "--no-audit", "--no-fund", str(tarball)], cwd=work, check=True,
            )
            bin_path = prefix / f"{command}.cmd" if os.name == "nt" else prefix / "bin" / command
            bins[package] = bin_path
            env = {**os.environ, "SAP_ADT_INSTALL_ALLOW_FILE": "1"}
            subprocess.run([str(bin_path), "install"], cwd=work, env=env, check=True)
            actual = subprocess.run(
                [str(bin_path), "--version"], cwd=work, capture_output=True, text=True, check=True,
            ).stdout.strip()
            if actual != f"{command}, version {version}":
                raise SystemExit(f"Unexpected runtime version: {actual}")
            help_text = subprocess.run(
                [str(bin_path), "--help"], cwd=work, capture_output=True,
                encoding="utf-8", errors="replace", check=True,
            ).stdout
            for expected in ("configure", "update", "list-feeds", "query-feed",
                             "get-versions", "get-version-source", "diff-versions",
                             "get-transport", "get-dump", "get-source",
                             "Setup and maintenance", "Test and diagnose",
                             "Read and change source", "Transport requests",
                             "run-class", "run-report", "run-abap", f"Usage: {command}"):
                if expected not in help_text:
                    raise SystemExit(f"Runtime --help does not list {expected}.")
            subprocess.run(
                [str(bin_path), "transport", "diff", "--help"], cwd=work,
                capture_output=True, text=True, check=True,
            )
            check_cli([str(bin_path)])
            check_debugger([str(bin_path)])
            check_execution([str(bin_path)])
            print(f"[smoke_npm] OK: {target}: pack -> install -> runtime -> {actual}")
        for removed, survivor in (("sap-watt", "sap-adt-cli"), ("sap-adt-cli", "sap-watt")):
            subprocess.run([*manager, "uninstall", "--global", "--offline",
                            "--ignore-scripts", removed], cwd=work, check=True)
            subprocess.run([str(bins[survivor]), "--version"], cwd=work, check=True)
            if removed == "sap-watt":
                subprocess.run([*manager, "install", "--global", "--offline", "--ignore-scripts",
                                "--no-audit", "--no-fund", str(packages[removed])],
                               cwd=work, check=True)
                subprocess.run([str(bins[removed]), "install"], cwd=work, env=env, check=True)
        print(f"[smoke_npm] OK: {target}: both package uninstall orders preserve the other entry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
