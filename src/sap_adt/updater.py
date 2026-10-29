"""Explicit, channel-aware updates. Never loads SAP configuration."""
from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import site
import subprocess
import sys
import sysconfig
from dataclasses import dataclass

import requests

from sap_adt import errors
from sap_adt.version import get_version

PACKAGE = "sap-adt-cli"
_STABLE = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", re.ASCII)
_RELEASES = "https://github.com/shrek-abaper/sap-engineering-skill/releases"


class UpdateError(Exception):
    def __init__(self, code: str, message: str, hint: str = ""):
        super().__init__(message)
        self.code = code
        self.hint = hint


@dataclass
class Installation:
    channel: str
    guidance: str = ""
    manager: tuple[str, ...] = ()
    root: str = ""


def child_environment() -> dict[str, str]:
    # Package managers and their children have no reason to receive SAP secrets.
    return {key: value for key, value in os.environ.items()
            if not key.upper().startswith("SAP_")}


def _failure_details(detail: str, *, npm: bool = False) -> tuple[str, str, str]:
    text = detail.lower()
    if "407" in text or "proxy authentication" in text:
        return ("PROXY_AUTH", errors.NETWORK_ERROR,
                "The proxy requires authentication. Configure HTTPS_PROXY or "
                + ("npm's https-proxy" if npm else "PIP_PROXY")
                + " with URL-encoded credentials; do not use SAP credentials.")
    if any(value in text for value in ("certificate", "sslerror", "self signed", "tls")):
        return ("TLS_CERTIFICATE", errors.NETWORK_ERROR,
                ("Configure NODE_EXTRA_CA_CERTS with the trusted corporate CA."
                 if npm else "Configure REQUESTS_CA_BUNDLE for version checks and "
                 "PIP_CERT for pip with the trusted corporate CA.")
                + " Do not disable TLS verification.")
    if any(value in text for value in ("enospc", "edquot", "no space", "disk full")):
        return ("DISK_FULL", errors.SERVER_ERROR,
                "Free space on the temporary-file and installation drives before retrying.")
    if any(value in text for value in (
            "eacces", "eperm", "ebusy", "permission denied", "access is denied",
            "winerror 5", "winerror 32", "errno 13", "being used")):
        return ("PERMISSION", errors.CONFIG_MISSING,
                "Close running sap-adt processes and check folder permissions, file locks "
                "and antivirus quarantine. Do not automatically elevate privileges; "
                "use a separate writable virtual environment if necessary.")
    if "externally-managed" in text or "externally managed" in text:
        return ("EXTERNALLY_MANAGED", errors.CONFIG_MISSING,
                "Use pipx or a virtual environment; do not use sudo or --break-system-packages.")
    if any(value in text for value in ("no module named", "enoent", "winerror 2")):
        return ("MISSING_TOOL", errors.CONFIG_MISSING,
                "Check the original Python/pip/pipx or Node.js/npm installation and PATH; "
                "do not switch to a different interpreter to repair this installation.")
    if any(value in text for value in ("requires-python", "requires a different python",
                                       "no matching distribution", "ebadengine")):
        return ("UNSUPPORTED_VERSION", errors.CONFIG_MISSING,
                "Check Python >=3.10 or Node.js >=18 and whether the selected version "
                "is available from your configured package index. Do not change registries silently.")
    if any(value in text for value in ("timeout", "timed out", "etimedout")):
        return ("TIMEOUT", errors.NETWORK_ERROR,
                "Check proxy/DNS/firewall access; if startup is blocked, close other processes. "
                "Inspect the installed version before retrying a timed-out upgrade.")
    if any(value in text for value in ("proxy", "connection", "dns", "enotfound",
                                       "econn", "eai_again", "network", "httperror",
                                       "401", "403", "429", "502", "503", "504")):
        return ("NETWORK", errors.NETWORK_ERROR,
                ("Check npm registry authentication, HTTPS_PROXY/npm proxy and NO_PROXY."
                 if npm else "Check PyPI/index connectivity, PIP_PROXY/HTTPS_PROXY and NO_PROXY.")
                + " Check corporate firewall rules; never supply SAP credentials.")
    return ("PACKAGE_MANAGER", errors.SERVER_ERROR,
            "Inspect package-manager connectivity, permissions and installation state. "
            "No automatic retry or privilege escalation was attempted.")


def _capture(args: list[str], *, timeout: int = 60,
             env: dict[str, str] | None = None) -> str:
    environment = child_environment()
    if env:
        environment.update(env)
    npm = any(Path(arg).name in ("npm", "npm-cli.js") for arg in args)
    try:
        result = subprocess.run(
            args, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout,
            env=environment, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        reason, code, hint = _failure_details("timeout", npm=npm)
        raise UpdateError(code, f"Update operation timed out after {timeout} seconds ({reason}).",
                          hint) from exc
    except OSError as exc:
        reason, code, hint = _failure_details(f"{type(exc).__name__} {exc}", npm=npm)
        raise UpdateError(errors.CONFIG_MISSING if code == errors.SERVER_ERROR else code,
                          f"The update package manager could not be started ({reason}).",
                          hint) from exc
    if result.returncode:
        reason, code, hint = _failure_details(
            f"{result.stderr}\n{result.stdout}", npm=npm)
        raise UpdateError(
            code, f"Update command failed (exit {result.returncode}; {reason}).", hint,
        )
    return result.stdout.strip()


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _npm_installation() -> Installation | None:
    root_value = os.environ.get("_SAP_ADT_NPM_ROOT")
    if not root_value:
        return None
    root = Path(root_value).resolve()
    package = _read_json(root / "package.json")
    executable = Path(sys.executable).resolve()
    if (package.get("name") != PACKAGE or package.get("version") != get_version()
            or not executable.is_relative_to(root / "runtime")
            or not (root / "scripts" / "run.js").is_file()):
        return Installation("unknown", "Launcher/runtime mismatch; run sap-adt install first.")
    node = os.environ.get("_SAP_ADT_NPM_NODE", "")
    npm = os.environ.get("_SAP_ADT_NPM_CLI", "")
    if not (Path(node).is_file() and Path(npm).is_file()
            and Path(npm).name == "npm-cli.js"):
        raise UpdateError(errors.CONFIG_MISSING,
                          "Cannot locate npm-cli.js; repair the Node.js/npm installation.")
    manager = (node, npm)
    global_root = Path(_capture([*manager, "root", "--global"])).resolve()
    if root == global_root / PACKAGE and root.parent == global_root:
        return Installation("npm-global", manager=manager, root=str(root))
    cache = Path(_capture([*manager, "config", "get", "cache"])).resolve()
    if root.is_relative_to(cache / "_npx"):
        return Installation(
            "npx", 'Use npx "sap-adt-cli@^MAJOR" install, then keep the same '
            'package selector on subsequent npx calls; the npx cache is not self-updated.',
            manager, str(root),
        )
    return Installation(
        "npm-local", "Update sap-adt-cli through the owning project's package manager "
        "and lockfile, then run that project's sap-adt install. "
        "Local, workspace and linked packages are not replaced automatically.",
        manager, str(root),
    )


def detect_installation() -> Installation:
    npm = _npm_installation()
    if npm is not None:
        return npm
    if getattr(sys, "frozen", False):
        return Installation(
            "standalone", f"Use the matching installer/portable release from {_RELEASES}. "
            "If installed by npm, invoke its launcher, not the inner runtime executable.",
        )
    try:
        dist = importlib.metadata.distribution(PACKAGE)
    except importlib.metadata.PackageNotFoundError:
        return Installation("source", "Update the source checkout using its development workflow.")
    if dist.read_text("direct_url.json"):
        return Installation(
            "source", "This is an editable or direct-URL install; update it from its "
            "original source, not a package registry.",
        )
    prefix = Path(sys.prefix).resolve()
    location = Path(dist.locate_file("")).resolve()
    pipx_meta = _read_json(prefix / "pipx_metadata.json")
    if pipx_meta:
        main_package = pipx_meta.get("main_package", {})
        if (isinstance(main_package, dict)
                and main_package.get("package") == PACKAGE
                and location.is_relative_to(prefix) and prefix.parent.name == "venvs"):
            pipx = shutil.which("pipx")
            if pipx:
                return Installation("pipx", manager=(pipx,), root=str(prefix))
        return Installation("unknown", "Use the owning pipx environment to update this package.")
    if (dist.read_text("INSTALLER") or "").strip() != "pip":
        return Installation("unknown", "Use the package manager that installed this CLI.")
    if (sys.prefix == sys.base_prefix
            and (Path(sysconfig.get_path("stdlib")) / "EXTERNALLY-MANAGED").exists()):
        return Installation(
            "externally-managed", "This Python is externally managed. Use its OS package "
            "manager or install in pipx/a virtual environment; no --break-system-packages.",
        )
    if location.is_relative_to(prefix):
        return Installation("pip", manager=(sys.executable, "-m", "pip"))
    user_site = Path(site.getusersitepackages()).resolve()
    if site.ENABLE_USER_SITE and location.is_relative_to(user_site):
        return Installation("pip-user", manager=(sys.executable, "-m", "pip"))
    return Installation("unknown", "Package metadata is outside this interpreter's install "
                        "locations. Use the original installation environment.")


def stable_version(value: str) -> tuple[int, int, int] | None:
    if not isinstance(value, str) or not _STABLE.fullmatch(value):
        return None
    return tuple(map(int, value.split(".")))


def _pip_proxy() -> str | None:
    proxy = os.environ.get("PIP_PROXY", "").strip()
    if proxy:
        return proxy
    if getattr(sys, "frozen", False) or importlib.util.find_spec("pip") is None:
        return None
    # `pip config get` reads one scope, not the effective merged settings.
    # Isolate pip's loader and return only the selected proxy, never a config dump.
    script = """
import json
from pip._internal.configuration import Configuration
from pip._internal.exceptions import ConfigurationError
config = Configuration(isolated=False)
config.load()
proxy = ""
for key in ("install.proxy", "global.proxy"):
    try:
        proxy = config.get_value(key).strip()
    except ConfigurationError:
        continue
    if proxy:
        break
print(json.dumps(proxy))
"""
    try:
        proxy = json.loads(_capture([sys.executable, "-c", script], timeout=10))
        if not isinstance(proxy, str):
            raise ValueError("Invalid proxy configuration")
    except (UpdateError, ValueError) as exc:
        code = (errors.NETWORK_ERROR if isinstance(exc, UpdateError)
                and exc.code == errors.NETWORK_ERROR else errors.CONFIG_MISSING)
        raise UpdateError(
            code, "Cannot read pip proxy configuration within 10 seconds; "
            "check this Python's pip setup or set PIP_PROXY explicitly.",
        ) from exc
    return proxy.strip() or None


def available_versions(installation: Installation) -> list[str]:
    if installation.manager and installation.channel.startswith(("npm-", "npx")):
        raw = _capture([*installation.manager, "view", PACKAGE, "versions", "--json"])
        try:
            versions = json.loads(raw)
        except ValueError as exc:
            raise UpdateError(errors.PARSE_FAILED, "npm returned invalid version metadata.") from exc
        if isinstance(versions, str):
            versions = [versions]
        if not isinstance(versions, list):
            raise UpdateError(errors.PARSE_FAILED, "npm returned no version list.")
        return versions
    proxy = _pip_proxy()
    try:
        response = requests.get(
            f"https://pypi.org/pypi/{PACKAGE}/json",
            timeout=(5, 20), allow_redirects=False,
            **({"proxies": {"http": proxy, "https": proxy}} if proxy else {}),
        )
        response.raise_for_status()
        if response.status_code != 200:
            raise UpdateError(errors.NETWORK_ERROR, "PyPI did not return package metadata.")
        releases = response.json()["releases"]
        if not isinstance(releases, dict):
            raise ValueError("Invalid releases")
        # Empty and fully yanked releases are not update candidates.
        return [version for version, files in releases.items()
                if isinstance(files, list) and any(
                    isinstance(file, dict) and not file.get("yanked", False)
                    for file in files)]
    except requests.RequestException as exc:
        reason, _, hint = _failure_details(f"{type(exc).__name__} {exc}")
        raise UpdateError(errors.NETWORK_ERROR,
                          f"Cannot check PyPI ({reason}).", hint) from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise UpdateError(errors.PARSE_FAILED, "PyPI returned invalid release metadata.") from exc


def check_update(*, major: bool = False) -> dict:
    current = get_version()
    current_parts = stable_version(current)
    if current_parts is None:
        raise UpdateError(errors.CONFIG_MISSING,
                          "The installed CLI has no stable version metadata; update it "
                          "through its original installation workflow.")
    installation = detect_installation()
    versions = [value for value in available_versions(installation)
                if stable_version(value) is not None]
    compatible = [value for value in versions
                  if major or stable_version(value)[0] == current_parts[0]]
    if not compatible:
        raise UpdateError(errors.OBJECT_NOT_FOUND,
                          "No stable release was found in the selected major-version range.")
    latest = max(compatible, key=stable_version)
    target = latest if stable_version(latest) > current_parts else current
    return {
        "channel": installation.channel, "current": current, "target": target,
        "update_available": target != current,
        "major": major, "guidance": installation.guidance.replace("MAJOR", str(current_parts[0])),
        "installation": installation,
    }


def update_commands(report: dict) -> list[list[str]]:
    installation = report["installation"]
    target = report["target"]
    if installation.channel in ("pip", "pip-user"):
        return [[*installation.manager, "install", "--upgrade",
                 *(["--user"] if installation.channel == "pip-user" else []),
                 f"{PACKAGE}=={target}"]]
    if installation.channel == "pipx":
        # Pin the candidate while letting pipx maintain its environment metadata.
        return [[*installation.manager, "upgrade", Path(installation.root).name,
                 "--pip-args", f"{PACKAGE}=={target}"]]
    if installation.channel == "npm-global":
        return []
    raise UpdateError(errors.CONFIRM_REQUIRED, installation.guidance)


def _repair_hint(report: dict) -> str:
    installation = report["installation"]
    command = update_commands(report)[0]
    if installation.channel == "pipx":
        command = [*command[:-1], f"--force-reinstall {command[-1]}"]
    else:
        command.insert(len(installation.manager) + 1, "--force-reinstall")

    def display(args: list[str]) -> str:
        if os.name == "nt":
            return "& " + " ".join("'" + value.replace("'", "''") + "'" for value in args)
        return shlex.join(args)

    repair = display(command)
    if installation.channel == "pipx":
        home = str(Path(installation.root).parent.parent)
        if os.name == "nt":
            home = home.replace("'", "''")
            repair = ("$oldPipxHome = $env:PIPX_HOME; try { $env:PIPX_HOME = '" +
                      home + "'; " + repair +
                      " } finally { $env:PIPX_HOME = $oldPipxHome }")
        else:
            repair = f"PIPX_HOME={shlex.quote(home)} {repair}"
    shell = " in PowerShell" if os.name == "nt" else ""
    return ("Inspect the installation before running a repair. "
            f"If repair is needed, run{shell}:\n{repair}\nThen verify:\n"
            + display([sys.executable, "-m", "sap_adt.cli", "--version"]))


def apply_python_update(report: dict, commands: list[list[str]]) -> None:
    installation = report["installation"]
    environment = ({"PIPX_HOME": str(Path(installation.root).parent.parent)}
                   if installation.channel == "pipx" else {})
    try:
        for command in commands:
            _capture(command, timeout=600, env=environment)
        actual = _capture([sys.executable, "-m", "sap_adt.cli", "--version"])
    except UpdateError as exc:
        raise UpdateError(
            errors.CONFIRM_REQUIRED,
            "Update did not complete and may have changed this installation. "
            f"Inspect it before retrying. {exc}",
            f"{exc.hint} {_repair_hint(report)}".strip(),
        ) from exc
    if actual != f"sap-adt, version {report['target']}":
        raise UpdateError(errors.CONFIRM_REQUIRED, "Package manager finished, but version "
                          "verification failed. Inspect this installation before retrying.",
                          _repair_hint(report))
