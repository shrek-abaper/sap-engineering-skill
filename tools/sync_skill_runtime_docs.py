#!/usr/bin/env python3
"""Generate per-skill runtime snapshots and keep them in sync.

Sources of truth:
  - docs/installation/runtime-setup.md  (shared install/diagnostics body)
  - compatibility.json                  (per-skill CLI requirements + ranges)

Generated outputs per skill (committed, so a source checkout's skill folder
is self-contained without running any build):
  - skills/<name>/references/setup.md
  - skills/<name>/references/runtime-compatibility.json
  - README.md generated block between
    <!-- BEGIN GENERATED cli-setup --> and <!-- END GENERATED cli-setup -->
    (only in skills whose README contains the markers)

Usage:
  python tools/sync_skill_runtime_docs.py           # write mode
  python tools/sync_skill_runtime_docs.py --check   # verify only, exit 1 on drift
  python tools/sync_skill_runtime_docs.py --root PATH  # operate on another tree (tests)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKILLS = ["sap-adt-cli", "sap-transport-gate", "abap-code-review", "sap-integration-wiki"]

BEGIN = "<!-- BEGIN GENERATED cli-setup -->"
END = "<!-- END GENERATED cli-setup -->"
GEN_NOTE = ("<!-- GENERATED from docs/installation/runtime-setup.md + "
            "compatibility.json by tools/sync_skill_runtime_docs.py — "
            "do not edit; run the tool to refresh -->")


def load_sources(root: Path):
    body = (root / "docs" / "installation" / "runtime-setup.md").read_text(encoding="utf-8")
    compat = json.loads((root / "compatibility.json").read_text(encoding="utf-8"))
    return body, compat


def requirement_preamble(name: str, spec: dict) -> str:
    req = spec["cli_requirement"]
    lines = [f"# {name}: CLI runtime requirement", ""]
    if req == "required":
        lines.append("**This skill needs the `sap-adt` CLI for online "
                     "operations.** If it is missing or incompatible, guide "
                     "installation per below — never fake an online result.")
    elif req == "conditional":
        need = ", ".join(spec.get("cli_required_for", []))
        skip = ", ".join(spec.get("cli_not_required_for", []))
        lines.append("**This skill needs the `sap-adt` CLI only for: "
                     f"{need}.** It works without the CLI for: {skip}. "
                     "A missing CLI degrades the task to the offline mode "
                     "with an explicit declaration — it is never a blocker "
                     "for offline work.")
    else:
        lines.append("**This skill does NOT need the CLI.** The content "
                     "below exists only so you can help users install it for "
                     "*other* skills; never demand an install for this one.")
    return "\n".join(lines)


def render_setup_md(name: str, spec: dict, body: str) -> str:
    return (GEN_NOTE + "\n\n" + requirement_preamble(name, spec)
            + "\n\n---\n\n" + body)


def render_compat_json(name: str, spec: dict, compat: dict) -> str:
    snapshot = {
        "schema_version": compat["schema_version"],
        "generated_from": "compatibility.json",
        "plugin_name": compat["plugin_name"],
        "plugin_version": compat["plugin_version"],
        "cli": compat["cli"],
        "skill": {"name": name, **spec},
    }
    return json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n"


def render_readme_block(name: str, spec: dict, compat: dict) -> str:
    req = spec["cli_requirement"]
    rng = compat["cli"]["compatible_versions"]
    if req == "not-required":
        status = "This skill needs **no CLI** — it works fully offline."
    elif req == "conditional":
        status = ("Offline review works without it; online collection needs "
                  "the `sap-adt` CLI.")
    else:
        status = "Online operations need the `sap-adt` CLI."
    return (
        f"{BEGIN}\n{GEN_NOTE}\n\n"
        f"{status} Compatible CLI range: `{rng}`.\n"
        "Install/readiness guide: [`references/setup.md`](references/setup.md).\n"
        f"{END}"
    )


def apply_or_check(path: Path, content: str, check: bool, drift: list) -> None:
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if check:
        if current != content:
            drift.append(str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def apply_readme_block(path: Path, block: str, check: bool, drift: list) -> None:
    if not path.exists():
        return  # README.md optional per skill
    text = path.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        return  # markers opt-in; untouched READMEs stay manual
    pre, _, rest = text.partition(BEGIN)
    _, _, post = rest.partition(END)
    new = pre + block + post
    if check:
        if new != text:
            drift.append(f"{path} (cli-setup block)")
    else:
        path.write_text(new, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify only; report drift without modifying files")
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="repository root to operate on (tests use a copy)")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    body, compat = load_sources(root)
    drift: list[str] = []

    for name in SKILLS:
        spec = compat["skills"][name]
        skill_dir = root / "skills" / name
        refs = skill_dir / "references"
        apply_or_check(refs / "setup.md", render_setup_md(name, spec, body),
                       args.check, drift)
        apply_or_check(refs / "runtime-compatibility.json",
                       render_compat_json(name, spec, compat), args.check, drift)
        apply_readme_block(skill_dir / "README.md",
                           render_readme_block(name, spec, compat),
                           args.check, drift)

    if drift:
        print("drift detected (run without --check to regenerate):")
        for d in drift:
            print(f"  {d}")
        return 1
    print("all generated snapshots in sync" if args.check else "snapshots written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
