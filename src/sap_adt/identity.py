"""Presentation identity only; installation ownership comes from metadata."""
import os

import click


def command_name() -> str:
    context = click.get_current_context(silent=True)
    if context is not None:
        name = context.find_root().info_name
        if name in ("sap-adt", "sap-watt"):
            return name
    return "sap-watt" if os.environ.get("_SAP_ADT_COMMAND") == "sap-watt" else "sap-adt"
