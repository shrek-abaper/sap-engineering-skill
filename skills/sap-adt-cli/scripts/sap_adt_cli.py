#!/usr/bin/env python3
"""Compatibility shim: sap-adt-cli → sap-adt (the ``sap_adt`` package).

The CLI business logic moved to the `sap-adt` distribution (src/sap_adt/).
This shim only forwards — it contains no implementation code.

What it preserves:
  - The `sap-adt-cli` program name and all command semantics.
  - The legacy skill-local .env layer: if skills/sap-adt-cli/.env exists, it
    is declared to the package via SAP_ADT_DOTENV (same file, same rules,
    explicit path instead of the removed __file__-based lookup).

What changed (see docs/development/migration.md once published):
  - No automatic `pip install` of click/requests/urllib3 on first run.
    Install the package once: `pip install sap-adt` (or `pip install -e .`
    from this repository's root).
"""
import os
import sys
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
_skill_env = _SKILL_ROOT / ".env"

if "SAP_ADT_DOTENV" not in os.environ and _skill_env.exists():
    os.environ["SAP_ADT_DOTENV"] = str(_skill_env)

try:
    from sap_adt.cli import main
except ImportError:
    sys.stderr.write(
        "The sap-adt CLI package is not installed in this Python environment.\n"
        "The old first-run auto-install of dependencies was removed.\n"
        "Install the package first, e.g.:\n"
        "  pip install sap-adt            # released wheel\n"
        "  pip install -e <repo-root>     # from this repository's source\n"
    )
    sys.exit(2)

if __name__ == "__main__":
    main(prog_name="sap-adt-cli")
