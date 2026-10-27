"""Explicit legacy adapter for the old tr_collector config (compat window).

Reads the standalone collector's plaintext config at
~/.sap-transport-gate/config.json. This is ONLY invoked on the explicit
--legacy-config path; the default transport collect resolution never touches
this file, so a missing ADT profile or failed authentication can never
silently fall back to it.

The warning is printed on every use and names only the file path — never the
credentials it contains. Users are pointed at `sap-adt configure` to migrate.
"""
import json
import sys
from pathlib import Path

from sap_adt.config import SapConfig

LEGACY_CONFIG_DIR = Path.home() / ".sap-transport-gate"
LEGACY_CONFIG_FILE = LEGACY_CONFIG_DIR / "config.json"


class LegacyConfigError(Exception):
    """Legacy config missing or unreadable (mapped to CONFIG_MISSING)."""


def load_legacy_config() -> SapConfig:
    if not LEGACY_CONFIG_FILE.exists():
        raise LegacyConfigError(
            f"Legacy collector config not found at {LEGACY_CONFIG_FILE}. "
            "Run `sap-adt configure` to create an ADT profile instead."
        )
    try:
        with open(LEGACY_CONFIG_FILE) as f:
            data = json.load(f)
        config = SapConfig(
            url=data["url"],
            username=data["username"],
            password=data["password"],
            client=data["client"],
            language=data.get("language", "EN"),
            verify_ssl=data.get("verify_ssl", True),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise LegacyConfigError(
            f"Legacy collector config at {LEGACY_CONFIG_FILE} is invalid: "
            f"{e}. Run `sap-adt configure` to create an ADT profile instead."
        ) from e

    print(
        f"WARNING: reading legacy plaintext config {LEGACY_CONFIG_FILE}.\n"
        "The old standalone collector stored the SAP password unencrypted. "
        "Run `sap-adt configure` to migrate to a profile with the password in "
        "the OS keystore, then drop --legacy-config. After migrating, remove "
        "the old file or keep it private (permissions 600).",
        file=sys.stderr,
    )
    return config
