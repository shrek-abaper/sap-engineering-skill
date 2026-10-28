#!/usr/bin/env python3
"""Build the metadata-only deprecation stub for the old PyPI name `sap-adt`.

PyPI cannot rename a project. Publishing this stub (same version as the CLI)
to the old name makes `pip install -U sap-adt` pull `sap-adt-cli` instead.
The version is read from the single source (pyproject via sap_adt.version).

Usage: python tools/build_deprecation_stub.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "packaging" / "pypi-deprecation-stub"


def main() -> int:
    version = subprocess.run(
        [sys.executable, "-c",
         "from sap_adt.version import get_version; print(get_version())"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()
    out = ROOT / "dist" / "release"
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sap-adt-stub-") as td:
        d = Path(td)
        (d / "pyproject.toml").write_text(
            (TEMPLATE_DIR / "pyproject.toml.in").read_text(encoding="utf-8")
            .replace("{{version}}", version), encoding="utf-8")
        shutil.copy2(TEMPLATE_DIR / "README.md", d / "README.md")
        shutil.copy2(ROOT / "LICENSE", d / "LICENSE")
        subprocess.run(
            [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(out), str(d)],
            cwd=ROOT, check=True,
        )
    print(f"[stub] built sap-adt {version} deprecation stub in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
