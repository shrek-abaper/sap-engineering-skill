#!/usr/bin/env python3
"""Assemble the npm staging tree (dist/npm/) from the single CLI version.

Copies packaging/npm/{package.json,scripts/,README.md} + LICENSE, fills the
package version from pyproject.toml (never a second hand-maintained copy),
and generates runtime-manifest.json binding each built runtime archive's
sha256 to this exact package version.

The release URL template points at a GitHub Release that only exists once a
human runs the authorized release step; until then the manifest is marked
"release_state": "candidate-not-published" so nobody mistakes it for a
live channel.

--local-file-urls rewrites artifact URLs to file:// for LOCAL end-to-end
testing only (install.js refuses file:// unless SAP_ADT_INSTALL_ALLOW_FILE=1).

Usage: python tools/build_npm.py [--local-file-urls]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_PKG = ROOT / "packaging" / "npm"
STAGING = ROOT / "dist" / "npm"
RELEASE_REPO = "https://github.com/shrek-abaper/sap-engineering-skill"


def cli_version() -> str:
    return subprocess.run(
        [sys.executable, "-c",
         "from sap_adt.version import get_version; print(get_version())"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_artifacts(version: str, local_file_urls: bool) -> dict:
    runtime_dir = ROOT / "dist" / "runtime"
    artifacts = {}
    for archive in sorted(runtime_dir.glob(f"sap-adt-{version}-*")):
        if archive.suffix not in (".gz", ".zip"):
            continue
        # sap-adt-<ver>-linux-x86_64.tar.gz -> linux-x86_64
        stem = archive.name[len(f"sap-adt-{version}-"):]
        target = stem[:-7] if stem.endswith(".tar.gz") else stem[:-4]
        fmt = "zip" if stem.endswith(".zip") else "tar.gz"
        if local_file_urls:
            url = archive.resolve().as_uri()
            allowed = []
        else:
            url = (f"{RELEASE_REPO}/releases/download/sap-adt-v{version}/"
                   f"{archive.name}")
            # GitHub release assets redirect to release-assets.githubusercontent.com;
            # keep the legacy objects host too (older GitHub behavior).
            allowed = ["github.com", "release-assets.githubusercontent.com",
                       "objects.githubusercontent.com"]
        artifacts[target] = {
            "url": url,
            "sha256": sha256_file(archive),
            "format": fmt,
            "size_bytes": archive.stat().st_size,
            "allowed_redirect_hosts": allowed,
        }
    return artifacts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-file-urls", action="store_true",
                        help="TEST ONLY: point artifact URLs at local files")
    parser.add_argument("--release-state", default="candidate-not-published",
                        choices=["candidate-not-published", "published"],
                        help="Manifest state: keep candidate-not-published until "
                             "the GitHub Release exists, then regenerate with "
                             "'published' so installs stop printing the "
                             "pre-release note.")
    args = parser.parse_args(argv)

    version = cli_version()
    if STAGING.exists():
        shutil.rmtree(STAGING)
    (STAGING / "scripts").mkdir(parents=True)
    shutil.copy2(SRC_PKG / "README.md", STAGING / "README.md")
    shutil.copy2(ROOT / "LICENSE", STAGING / "LICENSE")
    for js in (SRC_PKG / "scripts").glob("*.js"):
        shutil.copy2(js, STAGING / "scripts" / js.name)

    pkg = json.loads((SRC_PKG / "package.json").read_text(encoding="utf-8"))
    pkg["version"] = version
    (STAGING / "package.json").write_text(
        json.dumps(pkg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    artifacts = collect_artifacts(version, args.local_file_urls)
    if not artifacts:
        print("[build_npm] WARNING: no runtime archives found under "
              "dist/runtime/ — run tools/build_runtime.py first. The staging "
              "manifest will be empty and the installer will report every "
              "platform as unsupported.", file=sys.stderr)
    manifest = {
        "cli_version": version,
        "release_state": "local-test" if args.local_file_urls
        else args.release_state,
        "artifacts": artifacts,
    }
    (STAGING / "runtime-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"[build_npm] staged dist/npm/ for CLI {version}; "
          f"artifacts: {sorted(artifacts) or '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
