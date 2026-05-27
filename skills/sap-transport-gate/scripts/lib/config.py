import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

# SKILL root = 3 levels up from this file (scripts/lib/config.py → scripts/lib → scripts → skill root)
# Resolved at import time so it works regardless of the caller's CWD.
_SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
_SKILL_DOTENV = _SKILL_ROOT / ".env"

CONFIG_DIR = Path.home() / ".sap-transport-gate"
CONFIG_FILE = CONFIG_DIR / "config.json"

SETUP_GUIDE = """\
SAP credentials not configured.

Credential lookup order (highest priority first):
  1. Process environment variables
  2. .env file in the SKILL directory  ({skill_dotenv})
  3. ~/.sap-transport-gate/config.json

Option A — SKILL-local .env file (recommended for per-skill isolation):
  Copy .env.example to .env inside the skill directory and fill in your values:
    SAP_URL=https://your-sap-system.example.com:8000
    SAP_USERNAME=YOUR_USERNAME
    SAP_PASSWORD=YOUR_PASSWORD
    SAP_CLIENT=100

Option B — Environment variables (CI / headless use):
  export SAP_URL="https://your-sap-system.example.com:8000"
  export SAP_USERNAME="YOUR_USERNAME"
  export SAP_PASSWORD="YOUR_PASSWORD"
  export SAP_CLIENT="100"

Option C — Persistent config file (interactive setup):
  python3 tr_collector.py configure
""".format(skill_dotenv=_SKILL_DOTENV)


@dataclass
class SapConfig:
    url: str
    username: str
    password: str
    client: str
    language: str = "EN"
    verify_ssl: bool = True

    def base_url(self) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(self.url.rstrip("/"))
        return f"{parsed.scheme}://{parsed.netloc}"


def _load_skill_dotenv() -> dict:
    if not _SKILL_DOTENV.exists():
        return {}
    result = {}
    with open(_SKILL_DOTENV) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            if key:
                result[key] = value
    return result


def load_config() -> Optional[SapConfig]:
    dotenv = _load_skill_dotenv()

    def _get(key: str, default: str = None) -> Optional[str]:
        return os.getenv(key) or dotenv.get(key) or default

    url = _get("SAP_URL")
    username = _get("SAP_USERNAME")
    password = _get("SAP_PASSWORD")
    client = _get("SAP_CLIENT")

    if url and username and password and client:
        return SapConfig(
            url=url,
            username=username,
            password=password,
            client=client,
            language=_get("SAP_LANGUAGE", "EN"),
            verify_ssl=_get("SAP_VERIFY_SSL", "1") != "0",
        )

    if not CONFIG_FILE.exists():
        return None

    try:
        with open(CONFIG_FILE) as f:
            data = json.load(f)
        return SapConfig(
            url=data["url"],
            username=data["username"],
            password=data["password"],
            client=data["client"],
            language=data.get("language", "EN"),
            verify_ssl=data.get("verify_ssl", True),
        )
    except (json.JSONDecodeError, KeyError):
        return None


def save_config(config: SapConfig) -> None:
    CONFIG_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)
    fd = os.open(CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(asdict(config), f, indent=2)


def get_config() -> SapConfig:
    config = load_config()
    if config is None:
        print(SETUP_GUIDE, file=sys.stderr)
        sys.exit(1)
    return config


def run_configure_wizard() -> SapConfig:
    existing = load_config()

    def _prompt(label: str, default: Optional[str] = None, secret: bool = False) -> str:
        hint = f" [{default}]" if default else ""
        prompt_text = f"{label}{hint}: "
        if secret:
            import getpass
            value = getpass.getpass(prompt_text)
        else:
            value = input(prompt_text)
        return value.strip() or (default or "")

    print("\nSAP Transport Gate — Connection Setup")
    print("=" * 40)

    url = _prompt("SAP System URL (e.g. https://my-sap.example.com:8000)", getattr(existing, "url", None))
    username = _prompt("SAP Username", getattr(existing, "username", None))
    password = _prompt("SAP Password", secret=True)
    client = _prompt("SAP Client (e.g. 100)", getattr(existing, "client", None))
    language = _prompt("Language code", getattr(existing, "language", "EN") or "EN")
    verify_ssl_raw = _prompt(
        "Verify SSL certificate? (y/n)",
        "y" if getattr(existing, "verify_ssl", True) else "n",
    )
    verify_ssl = verify_ssl_raw.lower() not in ("n", "no", "0", "false")

    config = SapConfig(
        url=url,
        username=username,
        password=password,
        client=client,
        language=language or "EN",
        verify_ssl=verify_ssl,
    )
    save_config(config)
    print(f"\nConfiguration saved to {CONFIG_FILE}")
    print("Warning: credentials are stored in plain text. Ensure this file remains private (permissions: 600).")
    return config
