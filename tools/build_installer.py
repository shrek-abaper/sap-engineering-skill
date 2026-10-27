#!/usr/bin/env python3
"""Build the desktop installer / portable artifact for the current platform.

- Every platform: reuses the runtime tree from tools/build_runtime.py (builds
  it if missing) — one runtime per target, no second build pipeline.
- Windows: compiles packaging/windows/setup.iss with Inno Setup (iscc) when
  present; otherwise exits 2 with a clear blocked message.
- Linux/macOS: confirms the portable archive produced by build_runtime.py.

Usage: python tools/build_installer.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    # Import the sibling tool directly instead of shelling out a second
    # interpreter invocation for discovery.
    sys.path.insert(0, str(ROOT / "tools"))
    import build_runtime  # noqa: E402

    target = build_runtime.target_id()
    tree = ROOT / "dist" / "runtime" / target / "sap-adt"
    if not tree.is_dir():
        print(f"[installer] runtime tree missing for {target}; building ...")
        rc = subprocess.run([sys.executable, str(ROOT / "tools" / "build_runtime.py")]).returncode
        if rc != 0:
            return rc

    version = subprocess.run(
        [sys.executable, "-c",
         "from sap_adt.version import get_version; print(get_version())"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()

    if sys.platform.startswith("win"):
        iscc = shutil.which("iscc")
        if iscc is None:
            print(
                "[installer] BLOCKED: Inno Setup (iscc) not found. Install "
                "Inno Setup 6 on this Windows host, then re-run.",
                file=sys.stderr,
            )
            return 2
        spec = ROOT / "packaging" / "windows" / "setup.iss"
        out = ROOT / "dist" / "installers"
        out.mkdir(parents=True, exist_ok=True)
        cmd = [iscc, f"/DAppVersion={version}", str(spec)]
        print(f"[installer] {' '.join(cmd)}")
        return subprocess.run(cmd, cwd=ROOT).returncode

    archive = ROOT / "dist" / "runtime" / f"sap-adt-{version}-{target}.tar.gz"
    if not archive.is_file():
        print(f"[installer] portable archive missing: {archive}", file=sys.stderr)
        return 1
    print(f"[installer] portable artifact ready: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
