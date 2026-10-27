#!/usr/bin/env python3
"""Build clean, self-contained standalone skill folders into dist/skills/.

Allowlist-driven (never exclusion-driven): only the entries below are copied.
The Python implementation, legacy execution shims, docs history, tests and
fixtures never enter a snapshot. Each snapshot is fully usable on its own:
SKILL.md + README + all references + the generated setup/compatibility
snapshots — no dependency on the repo root, other skills, or the plugin.

Usage: python tools/build_skills.py [--root PATH] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Per-skill allowlist. Directories are copied recursively.
ALLOWLIST: dict[str, list[str]] = {
    "sap-adt-cli": [
        "SKILL.md", "README.md", "README.zh-CN.md", "LICENSE",
        "references/",
    ],
    "sap-transport-gate": [
        "SKILL.md", "README.md", "README.zh-CN.md", "LICENSE",
        "references/",
    ],
    "abap-code-review": [
        "SKILL.md", "README.md", "README.zh-CN.md", "LICENSE", "references/",
    ],
    # The wiki's helper generators are content tools, not CLI execution code.
    "sap-integration-wiki": [
        "SKILL.md", "README.md", "README.zh-CN.md", "CONTRIBUTING.md", "LICENSE",
        "references/", "assets/", "scripts/",
    ],
}

# Defense in depth: never copy these even if an allowlisted dir contains them.
EXCLUDE_NAMES = {"__pycache__", ".git", ".pytest_cache", "reports", "review_package"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def _ignore(dir_path: str, names: list[str]) -> set[str]:
    ignored = set()
    for name in names:
        if name in EXCLUDE_NAMES:
            ignored.add(name)
        elif Path(name).suffix in EXCLUDE_SUFFIXES:
            ignored.add(name)
        elif name == ".env" or name.startswith(".env."):
            ignored.add(name)
    return ignored


def build_skill(root: Path, name: str, dest: Path) -> Path:
    src = root / "skills" / name
    if not src.is_dir():
        raise SystemExit(f"[build_skills] missing skill dir: {src}")

    # Generated snapshots must exist before packaging (run the sync tool).
    for required in ("references/setup.md", "references/runtime-compatibility.json"):
        if not (src / required).is_file():
            raise SystemExit(
                f"[build_skills] {name}: missing generated {required}; "
                "run tools/sync_skill_runtime_docs.py first"
            )

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for entry in ALLOWLIST[name]:
        source = src / entry
        if entry == "LICENSE" and not source.exists():
            source = root / "LICENSE"  # repo-wide MIT license fallback
        if not source.exists():
            # Bilingual README is optional per skill.
            if entry in ("README.zh-CN.md",):
                continue
            raise SystemExit(f"[build_skills] {name}: allowlisted entry missing: {entry}")
        target = dest / entry
        if source.is_dir():
            shutil.copytree(source, target, ignore=_ignore)
        else:
            shutil.copy2(source, target)
    return dest


def build_all(root: Path = ROOT, out_root: Path | None = None) -> list[Path]:
    out = (out_root or root / "dist" / "skills")
    compat = json.loads((root / "compatibility.json").read_text(encoding="utf-8"))
    names = [n for n in ALLOWLIST if n in compat["skills"]]
    if set(names) != set(compat["skills"]):
        raise SystemExit(
            "[build_skills] allowlist/compatibility mismatch: "
            f"{sorted(set(ALLOWLIST) ^ set(compat['skills']))}"
        )
    if out.exists():
        shutil.rmtree(out)
    return [build_skill(root, name, out / name) for name in names]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    built = build_all(args.root.resolve(), args.out)
    print("[build_skills] built:\n  " + "\n  ".join(str(p) for p in built))
    return 0


if __name__ == "__main__":
    sys.exit(main())
