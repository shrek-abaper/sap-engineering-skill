"""Human-readable diagnostics for credential backends (`credentials doctor`).

This module only READS state and formats text. It never prints secrets;
entries are profile names, and backend availability diagnostics are the
one-liner reasons the backends themselves provide.
"""
import os
import platform
import stat
from pathlib import Path
from typing import List, Optional

from . import config as config_module
from . import credentials
from .keystore import REGISTRY, select
from .keystore.base import BackendUnavailableError, KeyStore


def platform_line() -> str:
    system = platform.system()
    release = platform.release()
    label = f"{system} {release}"
    distro = os.environ.get("WSL_DISTRO_NAME")
    if _is_wsl():
        label += " (WSL2" + (f", {distro}" if distro else "") + ")"
    return label


def _is_wsl() -> bool:
    for store in REGISTRY:
        if store.name == "dpapi" and hasattr(store, "_is_wsl"):
            try:
                return bool(store._is_wsl())
            except OSError:
                return False
    return False


def mount_fs_for(path: Path, mounts_path: str = "/proc/mounts") -> Optional[str]:
    """Return the filesystem type of the mount owning ``path`` (Linux only).

    Parses /proc/mounts directly — no shell-out — with longest-prefix match.
    Returns None when the information is unavailable.
    """
    try:
        target = Path(path).resolve()
    except OSError:
        return None
    best_mount, best_fs = None, None
    try:
        with open(mounts_path, encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 3:
                    continue
                mount, fs = parts[1], parts[2]
                try:
                    mount_path = Path(mount).resolve()
                except OSError:
                    continue
                if target == mount_path or mount_path in target.parents:
                    if best_mount is None or len(str(mount_path)) > len(str(best_mount)):
                        best_mount, best_fs = mount_path, fs
    except OSError:
        return None
    return best_fs


def drvfs_warning(path: Path, mounts_path: str = "/proc/mounts") -> str:
    fs = mount_fs_for(Path(path), mounts_path=mounts_path)
    if fs not in ("drvfs", "9p"):
        return ""
    return (
        f"WARNING: {path} is on a {fs} Windows mount; chmod 0600 is ineffective "
        "there because permissions are governed by Windows ACLs. Move the "
        "~/.sap-adt-cli directory to the native WSL filesystem."
    )


def _selected() -> Optional[KeyStore]:
    try:
        return select()
    except BackendUnavailableError:
        return None


def _mode(path: Path) -> str:
    try:
        return oct(stat.S_IMODE(path.stat().st_mode))[2:].zfill(4)
    except OSError:
        return "----"


def _store_lines() -> List[str]:
    lines = []
    selected = _selected()
    for store in REGISTRY:
        try:
            ok, reason = store.available()
        except Exception as e:  # a probe itself must never break doctor
            ok, reason = False, f"probe raised: {e}"
        mark = "✓" if ok else "✗"
        tag = "  ← selected" if selected is not None and store.name == selected.name else ""
        lines.append(f"  {store.name:<8} {mark}  {reason}{tag}")
    return lines


def _entries_line() -> str:
    keys = set()
    notes = []
    for store in REGISTRY:
        list_keys = getattr(store, "list_keys", None)
        if list_keys is None:
            continue
        try:
            found = list_keys()
        except Exception:
            found = []
        if found is None:
            ok, _reason = store.available()
            if ok:
                notes.append(f"{store.name} entries cannot be enumerated")
            continue
        keys.update(found)
    # Environment overrides: list the variable names, never values.
    env_vars = sorted(
        name for name in os.environ
        if name.startswith("SAP_ADT_") and name.endswith("_PASSWORD")
    )
    if env_vars:
        notes.append("env: " + ", ".join(env_vars))
    text = ", ".join(sorted(keys)) if keys else "(none)"
    if notes:
        text += "  [" + "; ".join(notes) + "]"
    return text


def _file_line() -> str:
    candidates = []
    for attr, store_name in (("secrets_file", "dpapi"), ("store_file", "file")):
        for store in REGISTRY:
            if store.name == store_name and hasattr(store, attr):
                candidates.append(getattr(store, attr))
    existing = next((p for p in candidates if Path(p).exists()), None)
    target = existing or config_module.CONFIG_DIR
    fs = mount_fs_for(Path(target)) or "n/a"
    if existing:
        return f"store    : {existing}  (mode {_mode(existing)}, fs={fs})"
    return f"store    : {config_module.CONFIG_DIR}  (fs={fs}; no local secret file yet)"


def doctor_text() -> str:
    lines = [
        f"platform : {platform_line()}",
        f"selected : {_selected().name if _selected() else '(none available)'}",
        "",
        *_store_lines(),
        "",
        _file_line(),
        f"entries  : {_entries_line()}",
    ]
    warning = drvfs_warning(config_module.CONFIG_DIR)
    if warning:
        lines.extend(["", warning])
    return "\n".join(lines)


def status_text() -> str:
    """Per-profile configured/not table. Never includes passwords."""
    profiles = config_module.list_profiles() or []
    selected = _selected()
    lines = [
        f"Selected keystore (auto): {selected.name if selected else '(none available)'}",
        "",
        f"{'':1} {'PROFILE':<16} {'USERNAME':<16} STATUS",
    ]
    for p in profiles:
        name = p["name"]
        backends = []
        for store in REGISTRY:
            ok, _reason = store.available()
            if not ok:
                continue
            try:
                if store.get(name) is not None:
                    backends.append(store.name)
            except Exception:
                continue
        marker = "*" if p.get("active") else " "
        if backends:
            state = f"configured ({', '.join(backends)})"
        else:
            state = "not configured"
        lines.append(f"{marker} {name:<16} {p.get('username', ''):<16} {state}")
    if len(lines) == 3:
        lines.append("No profiles configured. Run: sap-adt-cli configure")
    return "\n".join(lines)
