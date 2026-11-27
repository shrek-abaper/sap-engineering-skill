#!/usr/bin/env python3
"""Build the Watt Python entry package from the single core version."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def stage(root: Path = ROOT) -> Path:
    # Read the source, not possibly stale installed distribution metadata.
    version = next(
        line.split("=", 1)[1].strip().strip('"')
        for line in (root / "pyproject.toml").read_text(encoding="utf-8").splitlines()
        if line.startswith("version =")
    )
    destination = root / "dist" / "watt-python"
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    source = root / "packaging" / "python"
    template = (source / "pyproject.toml").read_text(encoding="utf-8")
    (destination / "pyproject.toml").write_text(
        template.replace("0.0.0", version), encoding="utf-8")
    shutil.copy2(source / "sap_watt.py", destination / "sap_watt.py")
    shutil.copy2(root / "packaging" / "watt" / "README.md", destination / "README.md")
    shutil.copy2(root / "LICENSE", destination / "LICENSE")
    return destination


def main() -> int:
    destination = stage()
    subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(ROOT / "dist"), str(destination)],
        cwd=ROOT, check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
