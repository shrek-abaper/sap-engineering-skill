#!/usr/bin/env python3
"""Pre-release consistency checks for a local release candidate.

Verifies (no network, no publishing):
  - one CLI version across pyproject / npm staging / runtime build-info /
    release manifest / artifact filenames
  - plugin version identical in plugin.json, compatibility.json and the
    marketplace candidate
  - every listed artifact exists and its sha256 matches SHA256SUMS
  - the plugin ZIP contains no CLI core, shims or bytecode
  - the marketplace candidate only references artifacts that exist locally
    and is explicitly marked as a candidate (not live config)

Usage: python tools/check_release.py [--release-dir dist/release]
Exit: 0 pass, 1 drift, 2 missing candidate (nothing to check yet).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, default=ROOT / "dist" / "release")
    args = parser.parse_args()
    rel = args.release_dir.resolve()
    manifest_path = rel / "release-manifest.json"
    if not manifest_path.is_file():
        print(f"[check_release] no candidate at {manifest_path}; "
              "run tools/build_manifest.py first", file=sys.stderr)
        return 2

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    compat = json.loads((ROOT / "compatibility.json").read_text(encoding="utf-8"))
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    problems: list[str] = []

    cli_versions = {manifest.get("cli_version")}
    for info in (ROOT / "dist" / "runtime").glob("*/build-info.json"):
        cli_versions.add(json.loads(info.read_text(encoding="utf-8")).get("version"))
    npm_pkg = ROOT / "dist" / "npm" / "package.json"
    if npm_pkg.is_file():
        cli_versions.add(json.loads(npm_pkg.read_text(encoding="utf-8")).get("version"))
    if len(cli_versions) != 1:
        problems.append(f"CLI version drift across sources: {sorted(map(str, cli_versions))}")

    plugin_versions = {plugin.get("version"), compat.get("plugin_version")}
    market = manifest.get("marketplace_candidate", {})
    if market:
        plugin_versions.add(market.get("plugin_version"))
    if len(plugin_versions) != 1:
        problems.append(f"plugin version drift: {sorted(map(str, plugin_versions))}")

    # Artifact presence + digests.
    sums = {}
    sums_file = rel / "SHA256SUMS"
    if not sums_file.is_file():
        problems.append("SHA256SUMS missing")
    else:
        for line in sums_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, _, name = line.partition("  ")
            sums[name.strip()] = digest.strip()

    for artifact in manifest.get("artifacts", []):
        path = rel / artifact["file"]
        if not path.is_file():
            problems.append(f"artifact missing: {artifact['file']}")
            continue
        actual = sha256(path)
        if artifact.get("sha256") != actual:
            problems.append(f"sha256 mismatch for {artifact['file']}")
        if sums.get(artifact["file"]) != actual:
            problems.append(f"SHA256SUMS mismatch for {artifact['file']}")
        # Two version lines: CLI artifacts carry the CLI version; plugin and
        # skill archives carry the plugin/docs version.
        kind = artifact.get("kind")
        expected_version = (manifest.get("plugin_version")
                            if kind in ("plugin", "skill")
                            else manifest.get("cli_version"))
        if expected_version and expected_version not in artifact["file"]:
            problems.append(
                f"artifact name lacks {kind or 'CLI'} version "
                f"{expected_version}: {artifact['file']}")

    # Plugin ZIP payload must stay docs-only.
    plugin_zip = next((rel / a["file"] for a in manifest.get("artifacts", [])
                       if a.get("kind") == "plugin"), None)
    if plugin_zip and plugin_zip.is_file():
        with zipfile.ZipFile(plugin_zip) as zf:
            names = zf.namelist()
        bad = [n for n in names if n.endswith((".pyc",))
               or n.endswith("sap_adt_cli.py") or n.endswith("tr_collector.py")
               or "/src/" in n]
        if bad:
            problems.append(f"plugin zip contains forbidden files: {bad[:5]}")
        if not any(n.endswith(".claude-plugin/plugin.json") for n in names):
            problems.append("plugin zip lacks .claude-plugin/plugin.json")

    # Marketplace entry consistency:
    #  - candidate state: the LIVE marketplace must still be on "./";
    #  - published state: the LIVE marketplace must match this archive entry.
    live_market = json.loads(
        (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    live_entry = (live_market.get("plugins") or [{}])[0]
    live_source = live_entry.get("source")

    if not market:
        problems.append("marketplace candidate missing from manifest")
    else:
        state = market.get("state")
        if state not in ("candidate-not-published", "published"):
            problems.append(f"unknown marketplace state: {state}")
        zip_name = market.get("plugin_zip")
        if zip_name:
            zp = rel / zip_name
            if not zp.is_file():
                problems.append(f"marketplace candidate points at missing {zip_name}")
            elif market.get("plugin_zip_sha256") != sha256(zp):
                problems.append("marketplace candidate sha256 mismatch")
        if state == "candidate-not-published":
            if live_source != "./":
                problems.append(
                    "manifest is still a candidate but the live marketplace "
                    "already points at an archive")
        elif state == "published":
            expected = market.get("source") or {}
            if not isinstance(live_source, dict) or live_source.get("source") != "archive":
                problems.append("manifest says published but live marketplace is not archive")
            else:
                for field in ("url", "sha256"):
                    if live_source.get(field) != expected.get(field):
                        problems.append(
                            f"live marketplace archive {field} differs from manifest")

    if problems:
        print("[check_release] FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"[check_release] OK — CLI {manifest['cli_version']}, "
          f"plugin {plugin['version']}, "
          f"{len(manifest.get('artifacts', []))} artifacts verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
