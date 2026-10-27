#!/usr/bin/env python3
"""Assemble the docs-only Claude Code plugin from the same clean skill snapshots.

Reuses tools/build_skills.py (one allowlist, one copy implementation) and adds
only plugin metadata. The payload deliberately excludes the Python core, the
legacy execution shims, tests and development caches.

Output:
    dist/plugin/
    ├── .claude-plugin/plugin.json
    ├── compatibility.json
    ├── LICENSE
    └── skills/<name>/...

Usage: python tools/build_plugin.py [--root PATH] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_skills  # noqa: E402


def build_plugin(root: Path = ROOT, out_root: Path | None = None) -> Path:
    out = (out_root or root / "dist" / "plugin")
    compat = json.loads((root / "compatibility.json").read_text(encoding="utf-8"))
    plugin_manifest = json.loads(
        (root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))

    if plugin_manifest.get("version") != compat.get("plugin_version"):
        raise SystemExit(
            "[build_plugin] version mismatch: .claude-plugin/plugin.json "
            f"({plugin_manifest.get('version')}) != compatibility.json "
            f"({compat.get('plugin_version')})"
        )

    if out.exists():
        shutil.rmtree(out)
    (out / ".claude-plugin").mkdir(parents=True)
    (out / "skills").mkdir(parents=True)

    shutil.copy2(root / "LICENSE", out / "LICENSE")
    shutil.copy2(root / "compatibility.json", out / "compatibility.json")
    shutil.copy2(root / ".claude-plugin" / "plugin.json",
                 out / ".claude-plugin" / "plugin.json")

    for name in build_skills.ALLOWLIST:
        build_skills.build_skill(root, name, out / "skills" / name)

    # Post-condition: nothing executable slipped into the payload.
    forbidden = [
        p for p in out.rglob("*")
        if p.name in ("sap_adt_cli.py", "tr_collector.py")
        or p.name == "__pycache__"
        or p.suffix in (".pyc", ".whl")
    ]
    if forbidden:
        raise SystemExit(
            "[build_plugin] forbidden files in payload: "
            + ", ".join(str(p.relative_to(out)) for p in forbidden))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    out = build_plugin(args.root.resolve(), args.out)
    print(f"[build_plugin] built {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
