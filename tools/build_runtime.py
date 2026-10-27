#!/usr/bin/env python3
"""Build the self-contained sap-adt runtime for the current platform.

Wraps PyInstaller (onedir layout, packaging/pyinstaller/sap-adt.spec) and
emits a portable archive of the result. Output layout:

    dist/runtime/<os>-<arch>/sap-adt/        # onedir tree
    dist/runtime/sap-adt-<ver>-<os>-<arch>.tar.gz | .zip

The build must run on the target OS/arch itself — a Linux build does not
imply Windows/macOS support (no cross-build claims, spec §7.1).

Usage: python tools/build_runtime.py [--spec PATH] [--no-archive]
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = ROOT / "packaging" / "pyinstaller" / "sap-adt.spec"


def target_id() -> str:
    system = platform.system().lower()  # linux | windows | darwin
    machine = platform.machine().lower()  # x86_64 | amd64 | arm64 | ...
    machine = {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)
    return f"{system}-{machine}"


def archive_dir(tree: Path, out_dir: Path, name: str) -> Path:
    """Create .zip on Windows, .tar.gz elsewhere. Layout inside: sap-adt/."""
    if sys.platform.startswith("win"):
        target = out_dir / f"{name}.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(tree.rglob("*")):
                zf.write(path, path.relative_to(tree.parent))
    else:
        target = out_dir / f"{name}.tar.gz"
        with tarfile.open(target, "w:gz") as tf:
            tf.add(tree, arcname=tree.name)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--no-archive", action="store_true",
                        help="Only build the onedir tree, skip the portable archive")
    args = parser.parse_args()

    target = target_id()
    out_dir = ROOT / "dist" / "runtime" / target
    work = Path(tempfile.mkdtemp(prefix="sap-adt-build-"))
    try:
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm", "--clean",
            "--distpath", str(out_dir),
            "--workpath", str(work),
            str(args.spec),
        ]
        print(f"[build] target={target} spec={args.spec}", flush=True)
        subprocess.run(cmd, cwd=ROOT, check=True)

        tree = out_dir / "sap-adt"
        if not tree.is_dir():
            print(f"[build] ERROR: expected onedir at {tree}", file=sys.stderr)
            return 1

        version = subprocess.run(
            [sys.executable, "-c",
             "from sap_adt.version import get_version; print(get_version())"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()

        result = {"target": target, "version": version, "tree": str(tree)}
        if not args.no_archive:
            archive = archive_dir(tree, out_dir.parent, f"sap-adt-{version}-{target}")
            result["archive"] = str(archive)
            print(f"[build] archive: {archive}")
        (out_dir / "build-info.json").write_text(json.dumps(result, indent=2))
        print(f"[build] OK {json.dumps(result)}")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
