#!/usr/bin/env python3
"""Compatibility shim: tr_collector → sap-adt transport (legacy resolution).

The collector logic moved to the `sap-adt` distribution
(src/sap_adt/transport/). This shim only forwards — it contains no
implementation code.

Command mapping:
  collect <args> → sap-adt transport collect <args> --legacy-config
  ping           → sap-adt transport ping --legacy-config
  (no command)   → sap-adt help

The --legacy-config flag reproduces the old resolution order: process env >
skill-local .env (declared via SAP_ADT_DOTENV below) >
~/.sap-transport-gate/config.json. It is never used without this flag, so
the default `sap-adt transport collect` never reads the old plaintext file.

What changed (see docs/development/migration.md once published):
  - `configure` is no longer forwarded: the old wizard wrote the SAP
    password in plain text. Use `sap-adt configure` instead (password goes
    to the OS keystore).
  - No automatic `pip install` of dependencies on first run; install the
    `sap-adt` package once.
"""
import os
import sys
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent.parent
_skill_env = _SKILL_ROOT / ".env"

if "SAP_ADT_DOTENV" not in os.environ and _skill_env.exists():
    os.environ["SAP_ADT_DOTENV"] = str(_skill_env)


def _forward(argv):
    if not argv or argv[0] not in ("collect", "ping"):
        return None
    rest = argv[1:]
    if "--legacy-config" not in rest:
        rest = [*rest, "--legacy-config"]
    return ["transport", argv[0], *rest]


def _install_hint():
    sys.stderr.write(
        "The sap-adt CLI package is not installed in this Python environment.\n"
        "The old first-run auto-install of dependencies was removed.\n"
        "Install the package first, e.g.:\n"
        "  pip install sap-adt            # released wheel\n"
        "  pip install -e <repo-root>     # from this repository's source\n"
    )
    sys.exit(2)


try:
    from sap_adt.cli import main
except ImportError:
    _install_hint()

if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "configure":
        sys.stderr.write(
            "`tr_collector.py configure` was removed: it stored the SAP "
            "password in plain text.\nRun `sap-adt configure` instead — it "
            "saves a profile with the password in the OS keystore, then "
            "re-run collect without --legacy-config.\n"
        )
        sys.exit(2)
    forwarded = _forward(argv)
    if forwarded is None:
        main(prog_name="tr_collector")
    else:
        main(prog_name="tr_collector", args=forwarded)
