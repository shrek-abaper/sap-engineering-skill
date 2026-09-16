import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

from . import credentials
from .keystore.base import KeyStoreError

# SKILL root = 3 levels up from this file (scripts/lib/config.py -> scripts/lib -> scripts -> skill root)
# Resolved at import time so it works regardless of the caller's CWD.
_SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
_SKILL_DOTENV = _SKILL_ROOT / ".env"

CONFIG_DIR = Path.home() / ".sap-adt-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"
CONFIG_VERSION = 2
DEFAULT_PROFILE_NAME = "default"
PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

_OLD_CONFIG_DIR = Path.home() / ".sap-abap-cli"
_OLD_CONFIG_FILE = _OLD_CONFIG_DIR / "config.json"

# Per-profile connection fields. Global capability flags (allow_write,
# allow_transport) live OUTSIDE profiles and apply to every environment.
_CONNECTION_FIELDS = ("url", "username", "password", "client", "language", "verify_ssl")

SETUP_GUIDE = """\
SAP credentials not configured.

Credential lookup order (highest priority first):
  1. Process environment variables
  2. .env file in the SKILL directory ({skill_dotenv})
  3. Selected profile in ~/.sap-adt-cli/config.json, with its password
     in the OS keystore (run `credentials doctor` to see the backend)

To set up your SAP connection, run:
  python3 sap_adt_cli.py configure

This saves a profile named '{default_profile}' and activates it. Additional SAP
environments can be added with `configure --profile NAME`; switch with
`profile use NAME` or override per command with `--profile NAME` / SAP_PROFILE.

Or create a SKILL-local .env file / set environment variables for a one-off
single-environment override:
  SAP_URL        - SAP system URL (e.g. https://my-sap.example.com:8000)
  SAP_USERNAME   - SAP username
  SAP_PASSWORD   - SAP password
  SAP_CLIENT     - SAP client number (e.g. 100)

Optional:
  SAP_PROFILE    - Profile name from config.json to use (ignored when SAP_URL etc. are set)
  SAP_LANGUAGE   - Language code (default: EN)
  SAP_VERIFY_SSL - Set to 0 to disable SSL verification (default: 1)
  SAP_ALLOW_WRITE - Set to 1 to enable source write commands (default: 0)
  SAP_ALLOW_TRANSPORT - Set to 1 to enable transport write commands (default: 0)

Per-profile keystore password (env backend): SAP_ADT_<PROFILE>_PASSWORD
Encrypted-file backend master passphrase (non-interactive): SAP_ADT_MASTER_PASSPHRASE
""".format(skill_dotenv=_SKILL_DOTENV, default_profile=DEFAULT_PROFILE_NAME)


@dataclass
class SapConfig:
    url: str
    username: str
    password: str
    client: str
    language: str = "EN"
    verify_ssl: bool = True
    allow_write: bool = False
    allow_transport: bool = False
    # Name of the profile this connection was loaded from. None when the
    # connection comes from environment variables / .env rather than a profile.
    profile_name: Optional[str] = None
    # Logical environment: dev | qas | prd.
    environment: str = "dev"
    # Where the environment value came from: "explicit" (profile/env),
    # "inferred" (profile name substring) or "default".
    environment_source: str = "default"
    # True when the connection comes from SAP_* env vars / .env (no profile).
    from_environment: bool = False
    # Raw write intent on the env path, before prd hard-refusal forces the
    # effective flag to False. None on the profile path.
    env_write_requested: Optional[bool] = None
    env_transport_requested: Optional[bool] = None
    # Effective capability provenance for status reporting.
    write_source: str = "global"        # profile | global | env | hard-refused
    transport_source: str = "global"

    def base_url(self) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(self.url.rstrip("/"))
        return f"{parsed.scheme}://{parsed.netloc}"

    @property
    def is_production(self) -> bool:
        return self.environment == "prd"

    def __repr__(self) -> str:
        # The highest-frequency real leak path is an exception traceback
        # printing this object; never include the password.
        return (
            f"SapConfig(url={self.url!r}, username={self.username!r}, "
            f"password='***', client={self.client!r}, profile_name={self.profile_name!r})"
        )


# ---------------------------------------------------------------------------
# Per-invocation profile selection (--profile / SAP_PROFILE)
# ---------------------------------------------------------------------------

# Set by the CLI group callback from the global --profile option. Kept as a
# module global so existing load_config() call sites need no arguments.
_profile_override: Optional[str] = None


def set_profile_override(name: Optional[str]) -> None:
    global _profile_override
    _profile_override = name or None


VALID_ENVIRONMENTS = ("dev", "qas", "prd")


def infer_environment(profile_name: Optional[str], explicit: Optional[str] = None,
                      ) -> Tuple[str, str]:
    """Return (environment, source). Explicit always beats inference.

    Substring matching is deliberately loose: a false prd only blocks writes
    (one explicit --environment fixes it), while a missed prd could open
    production. 'reproduce' matching 'prod' is accepted on purpose. Only the
    profile name is inspected, never the hostname.
    """
    if explicit:
        env = explicit.lower()
        if env not in VALID_ENVIRONMENTS:
            raise ValueError(
                f"Invalid environment '{explicit}'. Use dev, qas or prd."
            )
        return env, "explicit"
    if profile_name:
        low = profile_name.lower()
        if "prd" in low or "prod" in low:
            return "prd", "inferred"
        if "qas" in low or "qa" in low:
            return "qas", "inferred"
    return "dev", "default"


def effective_capabilities(section: dict, raw_global: dict, environment: str
                           ) -> Tuple[bool, bool, str, str]:
    """Merge profile-level flags with legacy global flags.

    prd profiles are hard-refused regardless of any flag. A profile-level
    declaration wins over the global fallback (which only applies when the
    profile section does not declare the flag).
    """
    if environment == "prd":
        return False, False, "hard-refused", "hard-refused"

    def one(key: str) -> Tuple[bool, str]:
        if key in section:
            return bool(section[key]), "profile"
        return bool(raw_global.get(key, False)), "global"

    w, ws = one("allow_write")
    t, ts = one("allow_transport")
    return w, t, ws, ts


def validate_profile_name(name: str) -> str:
    if not name or not PROFILE_NAME_RE.match(name):
        raise ValueError(
            f"Invalid profile name '{name}'. "
            "Use letters, digits, '_' or '-' only (e.g. dev, qas-1, prd_hq)."
        )
    return name


class ConfigError(Exception):
    """Configuration/credential problem (mapped to exit tier 2)."""


class ProfileNotFoundError(ConfigError):
    """Requested profile does not exist (exit tier 2)."""


def _fail(message: str):
    raise ConfigError(message)


def _fail_profile(message: str):
    raise ProfileNotFoundError(message)


# ---------------------------------------------------------------------------
# .env / environment-variable support (single-environment override layer)
# ---------------------------------------------------------------------------

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


def _env_value(key: str, dotenv: dict, default: str = None) -> Optional[str]:
    return os.getenv(key) or dotenv.get(key) or default


def _env_bool(key: str, dotenv: dict, default: bool = False) -> bool:
    value = _env_value(key, dotenv)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def _env_source(required_keys: list, dotenv: dict) -> str:
    env_keys = [key for key in required_keys if os.getenv(key)]
    dotenv_keys = [key for key in required_keys if not os.getenv(key) and dotenv.get(key)]
    if env_keys and dotenv_keys:
        return f"process environment + {_SKILL_DOTENV} (overrides config profiles)"
    if env_keys:
        return "process environment (overrides config profiles)"
    return f"{_SKILL_DOTENV} (overrides config profiles)"


# ---------------------------------------------------------------------------
# config.json v2 read/write and migration
# ---------------------------------------------------------------------------

def _write_raw(raw: Dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)
    raw = dict(raw)
    raw["version"] = CONFIG_VERSION
    fd = os.open(CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(raw, f, indent=2)
    # O_CREAT only sets permissions on creation; tighten an existing file too.
    os.chmod(CONFIG_FILE, 0o600)


def _migrate_flat(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a v1 flat config (one connection at top level) to v2 profiles."""
    section = {field: data.get(field) for field in _CONNECTION_FIELDS}
    if section["language"] is None:
        section["language"] = "EN"
    if section["verify_ssl"] is None:
        section["verify_ssl"] = True
    return {
        "version": CONFIG_VERSION,
        "active_profile": DEFAULT_PROFILE_NAME,
        "allow_write": bool(data.get("allow_write", False)),
        "allow_transport": bool(data.get("allow_transport", False)),
        "profiles": {DEFAULT_PROFILE_NAME: section},
    }


def _migrate_old_dir_if_needed() -> None:
    if CONFIG_FILE.exists() or not _OLD_CONFIG_FILE.exists():
        return
    try:
        import shutil
        CONFIG_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)
        shutil.copy2(_OLD_CONFIG_FILE, CONFIG_FILE)
        CONFIG_FILE.chmod(0o600)
        print(
            f"Config migrated: {_OLD_CONFIG_FILE} → {CONFIG_FILE}\n"
            f"Old directory {_OLD_CONFIG_DIR}/ can be removed manually.",
            file=sys.stderr,
        )
    except Exception as e:
        print(
            f"WARNING: Could not migrate config from {_OLD_CONFIG_FILE}: {e}\n"
            f"Run `sap-adt-cli configure` to set up credentials.",
            file=sys.stderr,
        )


def _migrate_plaintext_passwords(data: Dict[str, Any]) -> Dict[str, Any]:
    """Move legacy plaintext profile passwords into the selected keystore.

    Idempotent: profiles without a password field are untouched, so
    repeat runs have no side effects. No .bak file is created (backup
    copies are a common leak source). When no writable backend exists the
    plaintext field is retained as a read-only legacy path and warned
    about, rather than locking the user out.
    """
    profiles = data.get("profiles") or {}
    migrated = []  # (profile, backend)
    failed = []
    for name, section in profiles.items():
        password = section.get("password") if isinstance(section, dict) else None
        if not password:
            continue
        try:
            backend = credentials.save(name, section.get("username") or "", password)
        except KeyStoreError as e:
            failed.append((name, str(e)))
            continue
        del section["password"]
        migrated.append((name, backend))

    if migrated:
        _write_raw(data)
        names = ", ".join(name for name, _b in migrated)
        backends = ", ".join(sorted({backend for _n, backend in migrated}))
        print(
            f"WARNING: migrated {len(migrated)} password(s) stored in plain text "
            f"({names}) from {CONFIG_FILE} into the keystore ({backends}).\n"
            "These passwords previously sat on disk unencrypted — change them "
            "on the SAP side (SU01 / password reset), then run `configure` to "
            "store the new ones. No backup copy was created.",
            file=sys.stderr,
        )
    for name, reason in failed:
        print(
            f"WARNING: profile '{name}' keeps its password in plain text in "
            f"{CONFIG_FILE} because no writable keystore is available ({reason}).\n"
            "Run `credentials doctor`, then re-run any command to migrate.",
            file=sys.stderr,
        )
    return data


def _read_raw() -> Optional[Dict[str, Any]]:
    """Load normalized v2 config dict. Returns {} when absent, None when corrupt."""
    _migrate_old_dir_if_needed()
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE) as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if "profiles" not in data:
        data = _migrate_flat(data)
        _write_raw(data)
    data.setdefault("version", CONFIG_VERSION)
    data.setdefault("active_profile", None)
    data.setdefault("allow_write", False)
    data.setdefault("allow_transport", False)
    data.setdefault("profiles", {})
    _migrate_plaintext_passwords(data)
    return data


# ---------------------------------------------------------------------------
# Profile resolution
# ---------------------------------------------------------------------------

def _select_profile_name(raw: Dict[str, Any], explicit: Optional[str] = None) -> Optional[str]:
    profiles = raw.get("profiles") or {}
    name = explicit or _profile_override or os.getenv("SAP_PROFILE") or raw.get("active_profile")
    if name:
        if name not in profiles:
            available = ", ".join(sorted(profiles)) or "(none configured)"
            _fail_profile(
                f"Profile '{name}' not found in {CONFIG_FILE}.\n"
                f"Available profiles: {available}\n"
                f"Configure it with `configure --profile {name}` or list with `profile list`."
            )
        return name
    # No explicit/active profile: be lenient when exactly one environment exists.
    if len(profiles) == 1:
        return next(iter(profiles))
    return None


def _stored_password(name: str, username: str) -> Optional[str]:
    """Return the keystore password for a profile, or None when not stored."""
    try:
        return credentials.load(name, username, interactive=False).password
    except KeyStoreError:
        return None


def _config_from_section(
    name: str, section: Dict[str, Any], raw: Dict[str, Any]
) -> SapConfig:
    # Plaintext 'password' only exists for profiles that could not be migrated
    # because no writable backend was available (read-only legacy path).
    password = section.get("password") or _stored_password(name, section.get("username") or "")
    if not password:
        _fail(
            f"Profile '{name}' has no password in the keystore. Run "
            f"`credentials set {name}` or re-run `configure --profile {name}`."
        )
    try:
        environment, env_source = infer_environment(
            name, section.get("environment")
        )
        allow_write, allow_transport, wsrc, tsrc = effective_capabilities(
            section, raw, environment
        )
        return SapConfig(
            url=section["url"],
            username=section["username"],
            password=password,
            client=section["client"],
            language=section.get("language", "EN"),
            verify_ssl=section.get("verify_ssl", True),
            allow_write=allow_write,
            allow_transport=allow_transport,
            profile_name=name,
            environment=environment,
            environment_source=env_source,
            write_source=wsrc,
            transport_source=tsrc,
        )
    except KeyError as e:
        _fail(f"Profile '{name}' in {CONFIG_FILE} is missing required field {e}. Re-run `configure --profile {name}`.")


def load_config_with_source(profile: Optional[str] = None) -> Tuple[Optional[SapConfig], Optional[str]]:
    dotenv = _load_skill_dotenv()
    required_keys = ["SAP_URL", "SAP_USERNAME", "SAP_PASSWORD", "SAP_CLIENT"]

    url = _env_value("SAP_URL", dotenv)
    username = _env_value("SAP_USERNAME", dotenv)
    password = _env_value("SAP_PASSWORD", dotenv)
    client = _env_value("SAP_CLIENT", dotenv)

    if url and username and password and client:
        # Env/.env provide a complete connection: they override every profile.
        source_keys = required_keys + [
            "SAP_LANGUAGE",
            "SAP_VERIFY_SSL",
            "SAP_ALLOW_WRITE",
            "SAP_ALLOW_TRANSPORT",
            "SAP_ENVIRONMENT",
        ]
        selected = profile or _profile_override or os.getenv("SAP_PROFILE")
        env_explicit = _env_value("SAP_ENVIRONMENT", dotenv)
        environment, env_source = infer_environment(selected, env_explicit)
        if env_explicit:
            # SAP_ENVIRONMENT is explicit; inference used the provided value.
            env_source = "explicit"
        raw_write = _env_bool("SAP_ALLOW_WRITE", dotenv)
        raw_transport = _env_bool("SAP_ALLOW_TRANSPORT", dotenv)
        allow_write, allow_transport = raw_write, raw_transport
        wsrc = tsrc = "env"
        if environment == "prd":
            # Same hard refusal as a prd profile; env cannot override it.
            allow_write = allow_transport = False
            wsrc = tsrc = "hard-refused"
        return SapConfig(
            url=url,
            username=username,
            password=password,
            client=client,
            language=_env_value("SAP_LANGUAGE", dotenv, "EN"),
            verify_ssl=_env_value("SAP_VERIFY_SSL", dotenv, "1") != "0",
            allow_write=allow_write,
            allow_transport=allow_transport,
            profile_name=selected,
            environment=environment,
            environment_source=env_source,
            from_environment=True,
            env_write_requested=raw_write,
            env_transport_requested=raw_transport,
            write_source=wsrc,
            transport_source=tsrc,
        ), _env_source(source_keys, dotenv)

    raw = _read_raw()
    if raw is None:
        return None, None
    profiles = raw.get("profiles") or {}
    if not profiles:
        return None, None

    name = _select_profile_name(raw, explicit=profile)
    if name is None:
        return None, None

    config = _config_from_section(name, profiles[name], raw)
    return config, f"{CONFIG_FILE} (profile '{name}')"


def load_config(profile: Optional[str] = None) -> Optional[SapConfig]:
    config, _ = load_config_with_source(profile)
    return config


def get_config(profile: Optional[str] = None) -> SapConfig:
    config = load_config(profile)
    if config is None:
        raise ConfigError("Not configured. Run: sap-adt-cli configure")
    return config


# ---------------------------------------------------------------------------
# Profile management (configure / profile list|use|remove)
# ---------------------------------------------------------------------------

def list_profiles() -> Optional[List[Dict[str, Any]]]:
    raw = _read_raw()
    if raw is None:
        return None
    active = raw.get("active_profile")
    result = []
    for name, section in sorted((raw.get("profiles") or {}).items()):
        env, env_src = infer_environment(name, section.get("environment"))
        result.append({
            "name": name,
            "active": name == active,
            "url": section.get("url", ""),
            "username": section.get("username", ""),
            "client": section.get("client", ""),
            "language": section.get("language", "EN"),
            "verify_ssl": section.get("verify_ssl", True),
            "environment": env,
            "environment_source": env_src,
        })
    return result


def get_global_capabilities() -> Tuple[bool, bool]:
    raw = _read_raw() or {}
    return bool(raw.get("allow_write", False)), bool(raw.get("allow_transport", False))


def save_profile(
    *,
    name: str,
    url: str,
    username: str,
    password: str,
    client: str,
    language: str = "EN",
    verify_ssl: bool = True,
    allow_write: Optional[bool] = None,
    allow_transport: Optional[bool] = None,
    environment: Optional[str] = None,
) -> SapConfig:
    """Create/update one profile and make it the active profile.

    Non-secret fields (including per-profile capability flags and
    environment) go into the profile section; the password goes to the
    keystore. ``None`` capability flags leave the existing section value
    untouched (never written to the legacy global keys here).
    """
    validate_profile_name(name)
    raw = _read_raw() or {}
    profiles = raw.setdefault("profiles", {})
    existing = profiles.get(name) or {}

    env, _ = infer_environment(name, environment or existing.get("environment"))
    section = {
        "url": url.rstrip("/"),
        "username": username,
        "client": client,
        "language": language or existing.get("language") or "EN",
        "verify_ssl": verify_ssl,
        "environment": env,
    }
    # Carry over unspecified profile-level flags rather than resetting them.
    for key, val in (("allow_write", allow_write),
                     ("allow_transport", allow_transport)):
        if val is None:
            if key in existing:
                section[key] = existing[key]
        else:
            section[key] = bool(val)
    profiles[name] = section
    raw["active_profile"] = name

    effective_password = ""
    if password:
        credentials.save(name, username, password)
        effective_password = password
    else:
        effective_password = _stored_password(name, username) or ""

    _write_raw(raw)

    w, t, wsrc, tsrc = effective_capabilities(section, raw, env)
    return SapConfig(
        url=section["url"],
        username=username,
        password=effective_password,
        client=client,
        language=section["language"],
        verify_ssl=verify_ssl,
        allow_write=w,
        allow_transport=t,
        profile_name=name,
        environment=env,
        write_source=wsrc,
        transport_source=tsrc,
    )


def set_global_capabilities(allow_write: bool, allow_transport: bool) -> None:
    """Write the LEGACY global fallback switches (top-level config keys)."""
    raw = _read_raw() or {}
    raw["allow_write"] = bool(allow_write)
    raw["allow_transport"] = bool(allow_transport)
    _write_raw(raw)


def set_active_profile(name: str) -> None:
    validate_profile_name(name)
    raw = _read_raw() or {}
    if name not in (raw.get("profiles") or {}):
        available = ", ".join(sorted(raw.get("profiles") or {})) or "(none configured)"
        raise ValueError(f"Profile '{name}' not found. Available profiles: {available}")
    raw["active_profile"] = name
    _write_raw(raw)


def remove_profile(name: str) -> None:
    raw = _read_raw() or {}
    profiles = raw.setdefault("profiles", {})
    if name not in profiles:
        raise ValueError(f"Profile '{name}' not found.")
    if raw.get("active_profile") == name:
        raise ValueError(
            f"Profile '{name}' is currently active. "
            f"Run `profile use <other>` first, then remove it."
        )
    del profiles[name]
    _write_raw(raw)
    # Purge the password from every writable backend; failure must not
    # leave an orphaned secret silently.
    removed = credentials.forget(name)
    if removed:
        print(f"Removed password from keystore(s): {', '.join(removed)}", file=sys.stderr)


def save_config_from_flags(
    url: Optional[str],
    username: Optional[str],
    password: Optional[str],
    client: Optional[str],
    language: Optional[str] = None,
    verify_ssl: bool = True,
    allow_write: bool = False,
    allow_transport: bool = False,
    profile: Optional[str] = None,
    environment: Optional[str] = None,
    profile_scope: bool = False,
    global_write: Optional[bool] = None,
    global_transport: Optional[bool] = None,
) -> SapConfig:
    raw = _read_raw() or {}
    name = profile or os.getenv("SAP_PROFILE") or raw.get("active_profile") or DEFAULT_PROFILE_NAME
    validate_profile_name(name)
    existing = (raw.get("profiles") or {}).get(name, {})

    resolved_url = url or existing.get("url")
    resolved_username = username or existing.get("username")
    # SAP_PASSWORD is accepted as a documented alternative to --password
    # (avoids exposing the password in shell history / process listings).
    # An existing keystore entry satisfies the required-field check.
    resolved_password = (
        password
        or os.getenv("SAP_PASSWORD")
        or _stored_password(name, resolved_username or "")
    )
    resolved_client = client or existing.get("client")
    resolved_language = language or existing.get("language") or "EN"

    missing = [label for label, val in [
        ("--url", resolved_url),
        ("--username", resolved_username),
        ("--password", resolved_password),
        ("--client", resolved_client),
    ] if not val]

    if missing:
        raise ConfigError(
            f"Missing required fields for profile '{name}': {', '.join(missing)}"
        )

    if profile_scope:
        # Capability flags are written to the profile section (default).
        # --allow-write=False is meaningful (explicit disable), but the
        # Click default False on an unused flag must not wipe an existing
        # value: callers wanting "leave as-is" pass None. save_config_from_flags
        # is only called with connection flags present, so explicit False is
        # treated as a declared disable here.
        w, t = allow_write, allow_transport
    else:
        # Legacy: top-level fallback switches; profile section inherits.
        w, t = None, None

    config = save_profile(
        name=name,
        url=resolved_url,
        username=resolved_username,
        password=resolved_password,
        client=resolved_client,
        language=resolved_language,
        verify_ssl=verify_ssl,
        allow_write=w,
        allow_transport=t,
        environment=environment,
    )
    if not profile_scope:
        # Non-scoped call (legacy wizard/flag path): write top-level keys.
        set_global_capabilities(allow_write, allow_transport)
    elif global_write is not None or global_transport is not None:
        cur_raw = _read_raw() or {}
        set_global_capabilities(
            global_write if global_write is not None
            else bool(cur_raw.get("allow_write", False)),
            global_transport if global_transport is not None
            else bool(cur_raw.get("allow_transport", False)),
        )
    print(f"Profile '{name}' saved to {CONFIG_FILE} (active profile: {name})")
    print("Password stored in the keystore; run `credentials doctor` to see which backend is in use.")
    return config


def run_configure_wizard(profile: Optional[str] = None) -> SapConfig:
    raw = _read_raw() or {}
    existing_name = raw.get("active_profile")
    default_name = profile or os.getenv("SAP_PROFILE") or existing_name or DEFAULT_PROFILE_NAME

    def _prompt(label: str, default: Optional[str] = None, secret: bool = False) -> str:
        hint = f" [{default}]" if default else ""
        prompt_text = f"{label}{hint}: "
        if secret:
            import getpass
            value = getpass.getpass(prompt_text)
        else:
            value = input(prompt_text)
        return value.strip() or (default or "")

    print("\nSAP ADT CLI — Connection Setup")
    print("=" * 40)

    name = _prompt("Profile name (e.g. dev, qas, prd)", default_name)
    try:
        validate_profile_name(name)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    existing = (raw.get("profiles") or {}).get(name, {})

    url = _prompt("SAP System URL (e.g. https://my-sap.example.com:8000)", existing.get("url"))
    username = _prompt("SAP Username", existing.get("username"))
    has_stored = bool(_stored_password(name, existing.get("username") or username))
    password_hint = "(blank = keep existing)" if has_stored else None
    password = _prompt(f"SAP Password{(' ' + password_hint) if password_hint else ''}", secret=True)
    client = _prompt("SAP Client (e.g. 100)", existing.get("client"))
    language = _prompt("Language code", existing.get("language") or "EN")
    verify_ssl_raw = _prompt(
        "Verify SSL certificate? (y/n)",
        "y" if existing.get("verify_ssl", True) else "n",
    )
    verify_ssl = verify_ssl_raw.lower() not in ("n", "no", "0", "false")

    # Global capability flags — apply to ALL profiles.
    current_allow_write = bool(raw.get("allow_write", False))
    current_allow_transport = bool(raw.get("allow_transport", False))
    print("\nThe following switches are GLOBAL and apply to every profile.")
    allow_write_raw = _prompt(
        "Enable source code write (write-source, activate)? [y/N]",
        "y" if current_allow_write else "N",
    )
    allow_write = allow_write_raw.lower() in ("y", "yes")

    allow_transport_raw = _prompt(
        "Enable transport write operations (create-transport, release-transport)? [y/N]",
        "y" if current_allow_transport else "N",
    )
    allow_transport = allow_transport_raw.lower() in ("y", "yes")

    if not url or not username or not (password or has_stored) or not client:
        print("Error: URL, username, password and client are all required.", file=sys.stderr)
        sys.exit(1)

    config = save_profile(
        name=name,
        url=url,
        username=username,
        password=password,
        client=client,
        language=language or "EN",
        verify_ssl=verify_ssl,
        allow_write=allow_write,
        allow_transport=allow_transport,
    )
    print(f"\nProfile '{name}' saved to {CONFIG_FILE} (active profile: {name})")
    return config
