#!/usr/bin/env python3
"""Verify built core/Watt wheels in a disposable, offline Python environment.

Reuse build-interpreter dependencies, but force both project wheels into the
temporary environment. Never change its parent installation or contact SAP.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from build_manifest import version_from_pyproject

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    version = version_from_pyproject()
    wheels = [ROOT / "dist" / f"{name}-{version}-py3-none-any.whl"
              for name in ("sap_adt_cli", "sap_watt")]
    if not all(path.is_file() for path in wheels):
        raise SystemExit("Build both core and Watt Python wheels first.")
    with tempfile.TemporaryDirectory(prefix="watt-python-smoke-") as directory:
        work = Path(directory)
        prefix = work / "venv"
        subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", str(prefix)],
                       check=True)
        scripts = prefix / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        env = {key: value for key, value in os.environ.items()
               if not key.upper().startswith(("SAP_", "_SAP_ADT_"))
               and key not in ("PYTHONPATH", "PYTHONHOME")}
        env.update({"HOME": str(work), "USERPROFILE": str(work), "PYTHONUTF8": "1"})

        def run(*args):
            return subprocess.run(list(map(str, args)), env=env, cwd=work, check=True,
                                  capture_output=True, encoding="utf-8").stdout.strip()

        def install(*paths):
            run(python, "-m", "pip", "install", "--no-index", "--no-deps",
                "--ignore-installed", "--find-links", ROOT / "dist", *paths)

        install(f"sap-adt-cli=={version}", f"sap-watt=={version}")
        for command in ("sap-adt", "sap-watt"):
            executable = scripts / (command + (".exe" if os.name == "nt" else ""))
            if run(executable, "--version") != f"{command}, version {version}":
                raise RuntimeError(f"{command} version mismatch")
        metadata = json.loads(run(python, "-c", """
import importlib.metadata as m, json, sys
from pathlib import Path
from sap_adt.updater import detect_installation
distributions = [m.distribution(name) for name in ('sap-adt-cli', 'sap-watt')]
assert all(Path(d.locate_file('')).resolve().is_relative_to(Path(sys.prefix).resolve())
           for d in distributions)
print(json.dumps({'owner': detect_installation().package,
                  'commands': [[e.name for e in d.entry_points if e.group == 'console_scripts']
                               for d in distributions]}))
"""))
        if metadata != {"owner": "sap-watt", "commands": [["sap-adt"], ["sap-watt"]]}:
            raise RuntimeError(f"Unexpected installation ownership: {metadata}")
        run(python, "-m", "pip", "uninstall", "--yes", "sap-watt")
        if run(scripts / ("sap-adt.exe" if os.name == "nt" else "sap-adt"),
               "--version") != f"sap-adt, version {version}":
            raise RuntimeError("Removing Watt damaged the legacy entry")
        owner = run(python, "-c",
                    "from sap_adt.updater import detect_installation; print(detect_installation().package)")
        if owner != "sap-adt-cli":
            raise RuntimeError("Legacy update owner was not restored")
        install(f"sap-watt=={version}")
        run(scripts / ("sap-watt.exe" if os.name == "nt" else "sap-watt"), "--help")
        print(f"[smoke_python] OK: {version}: local wheel ownership, both entries, "
              "Watt removal/reinstall and update-owner fallback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
