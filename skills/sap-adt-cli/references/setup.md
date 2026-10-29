<!-- GENERATED from docs/installation/runtime-setup.md + compatibility.json by tools/sync_skill_runtime_docs.py — do not edit; run the tool to refresh -->

# sap-adt-cli: CLI runtime requirement

**This skill needs the `sap-adt` CLI for online operations.** If it is missing or incompatible, guide installation per below — never fake an online result.

---

# sap-adt CLI — installation & readiness guide

This document is the single source of truth for installing the CLI. Each
skill that can use the CLI carries a generated copy of this guide in its
`references/` directory (regenerate/check with
`tools/sync_skill_runtime_docs.py`).

The CLI command is `sap-adt`. Configuration lives in `~/.sap-adt-cli/config.json`
(non-secret fields) and the OS keystore (passwords) — identical across all
channels and shared by all skills.

## Credentials & precedence

The CLI resolves the connection in this order (highest first):

1. **Process environment variables** — `SAP_URL`, `SAP_USERNAME`,
   `SAP_PASSWORD`, `SAP_CLIENT` (optionally `SAP_LANGUAGE`,
   `SAP_VERIFY_SSL`, `SAP_ALLOW_WRITE`, `SAP_ALLOW_TRANSPORT`,
   `SAP_ENVIRONMENT`).
2. **Dotenv file declared by `SAP_ADT_DOTENV`** — merged per key with the
   process environment (the shell value wins); this layer only applies when
   all four required keys resolve.
3. **Profile** in `~/.sap-adt-cli/config.json` + the OS keystore.

A complete env/dotenv set overrides profiles entirely, and `--profile` is then
ignored for connection data. The CLI never scans the current directory, a
skill folder or a guessed install path for `.env` files. `sap-adt status`
prints which source is active.

## Channels

| Channel | When to use | Prerequisites | Command |
|---|---|---|---|
| npm (global) | Node.js ≥ 18 is available; you want the `sap-adt` command on PATH | Node.js only (no Python) | `npm install -g "sap-adt-cli@^1.5.0"`, then `sap-adt install` |
| npx (no global install) | Try it without changing PATH | Node.js ≥ 18 | `npx "sap-adt-cli@^1.5.0" install`, then prefix every call: `npx "sap-adt-cli@^1.5.0" <command>` |
| PyPI (wheel/sdist) | Python ≥ 3.10 available | Python | `pip install "sap-adt-cli>=1.5.0,<2.0.0"` |
| Portable archive (Linux) | No dev environment | Linux x86_64, glibc ≥ 2.39 build | download the newest 1.x `sap-adt-<ver>-linux-x86_64.tar.gz` from the release page and unpack it, run inside it `./sap-adt/sap-adt` |
| Portable archive (macOS, experimental) | No dev environment | macOS 15+ Intel / Apple Silicon | from CLI 1.6.0, unpack `sap-adt-<ver>-darwin-x86_64.tar.gz` / `sap-adt-<ver>-darwin-aarch64.tar.gz`, then run `./sap-adt/sap-adt` |
| Windows installer | No dev environment | Windows 10+ x64 | newest compatible `sap-adt-<ver>-windows-x86_64-setup.exe` from CLI 1.5.3; unsigned, silent per-user lifecycle verified |
| Python source | Developers, contributors | Python ≥ 3.10 | `pip install -e .` from the repo |

The version ranges above are the skill's **compatible range** (declared in
`references/runtime-compatibility.json`). Resolving inside the range always
yields a compatible release, so these instructions do not need updating on
every CLI release. Never use an unbounded `@latest` — a future major could
break the skill.

All channels install the same runtime built from the same commit. `install`
in the npm channel is this package's own wizard (fetch → SHA-256 verify →
atomic install → self-test), not an npm built-in.

> Channel status (CLI 1.6.0, 2026-10-29): npm `sap-adt-cli` and PyPI `sap-adt-cli`
> (renamed from `sap-adt`; the old project was removed from PyPI after the
> rename) are live and the GitHub
> Release carries Linux x86_64, Windows x86_64 and experimental macOS 15+
> Intel / Apple Silicon runtimes, the Windows desktop
> installer, the plugin/skill zips
> and the checksums. To migrate from the old name run
> `pip uninstall -y sap-adt` first, then install `sap-adt-cli` — do not use
> `pip install -U sap-adt`. On 2026-10-29 the Windows x64 runtime/npm channel
> and the desktop installer's silent per-user lifecycle passed local
> verification through WSL interop. Windows npm support requires 1.5.3 or
> newer; older launchers may support only Linux. Graphical wizard clicks,
> actual PATH mutation and elevated installs remain unverified. macOS artifacts
> require native CI build, offline test and isolated npm install gates.
> Personal Macs, older macOS, Keychain, Gatekeeper/quarantine,
> signing/notarization and live SAP on macOS remain unverified.

## Proxied / restricted networks

The npm/npx `install` wizard downloads the runtime itself, so it needs egress
to the GitHub release CDN.

**From CLI 1.6.0:** proxy selection is explicit
environment variables → persistent npm proxy configuration → Windows current-user
manual Internet Settings → direct connection. Thus enabling a Windows manual
system proxy no longer also requires setting terminal environment variables.
The installer prints the selected route without credentials and never changes
the system's proxy settings. Windows per-protocol `https=host:port` and manual
bypass rules are supported; explicit `NO_PROXY` takes precedence.

Older installers, and Linux/macOS users with desktop-only proxy settings,
need explicit npm configuration or proxy variables before `sap-adt install`:

| Variable | Example | Meaning |
|---|---|---|
| `HTTPS_PROXY` / `https_proxy` | `http://proxy.example.com:8080` | Proxy for the artifact download (CONNECT tunnel) |
| `NO_PROXY` / `no_proxy` | `localhost,10.*,.example.com` | Hosts that go direct |

- Only `http://` proxy URLs are supported; `https://` and `socks5://` are
  refused with an error rather than half-working.
- Windows PAC/WPAD auto-configuration is not evaluated or downloaded; set
  `HTTPS_PROXY` explicitly instead. WinHTTP machine settings and integrated
  NTLM/Kerberos proxy authentication are not auto-imported.
- Proxy credentials go in the URL: `http://user:password@proxy:8080`.
- The artifact certificate is still verified against the real host name. If
  the proxy terminates TLS, point `NODE_EXTRA_CA_CERTS` at its CA bundle:
  `NODE_EXTRA_CA_CERTS=/path/to/corporate-ca.pem sap-adt install`.
- The installer bounds DNS/TCP/proxy/TLS connection setup to 30 seconds; receiving
  data has a 60-second inactivity timeout, not a total download deadline.
  Stalled or dripping CONNECT responses cannot extend setup indefinitely.
  `SAP_ADT_INSTALL_CONNECT_TIMEOUT_MS` and `SAP_ADT_INSTALL_IDLE_TIMEOUT_MS`
  can override these limits for diagnostics. A timeout can indicate an
  unreachable proxy, a blocked `CONNECT`, TLS interception or a stalled CDN.
- It also bounds extraction to 120 seconds and the runtime self-test to
  60 seconds (`SAP_ADT_INSTALL_EXTRACT_TIMEOUT_MS` /
  `SAP_ADT_INSTALL_SELFTEST_TIMEOUT_MS`). These are per-stage limits, not a
  single deadline for the whole installation.
- The npm `update` launcher passes discovered Windows manual proxy
  settings to its registry checks and package downloads as child-process
  environment variables. User npm/system settings are not changed. The
  initial external `npm install` command still needs npm proxy configuration
  or standard proxy environment variables.

If the download still cannot work, install the runtime by hand: download
the matching Linux/macOS `.tar.gz` or Windows x86_64 `.zip` from the release
page and compare its SHA-256 with the installed package's
`runtime-manifest.json`. For a **global** npm install, unpack the inner
`sap-adt/` directory into
`<npm root -g>/sap-adt-cli/runtime/<platform>/sap-adt/`; `npm root -g` prints
the package root on Linux, macOS and Windows. Close running CLI processes
first. Do not copy global instructions into an npx cache or project-local
installation. On macOS, `<platform>` is `darwin-aarch64` for Apple Silicon
or `darwin-x86_64` for Intel. Python >=3.10 in a virtual environment is an
alternative when a matching native runtime is unavailable.

## Installation/update failure recovery

The safeguards below require CLI/npm package 1.6.0 or newer.

The runtime installer retains the previous runtime until its replacement
passes `--version`. Validation failure restores the old runtime; if restoration
is blocked, exit 3 reports the retained backup path for manual recovery.
Do not delete that backup or blindly retry. Initial installs with no previous
runtime remove the failed candidate instead.

Updates require explicit confirmation and a final version readback. npm
package commits and pip/pipx upgrades are not full transactions: after a
possibly modifying failure, inspect the installation first and follow the
same-channel repair command printed by the updater. SAP configuration and
credentials are not changed. Never bypass TLS, checksums or PEP668 to repair
an installation. Initial `npm install` and `python -m pip install` are external
tools; their own errors are supplemented by the diagnostics below, not
intercepted by this CLI.

## Post-install self-test (from the install location)

```bash
sap-adt --version            # prints the exact CLI version
sap-adt credentials doctor   # which keystore backend is active (no secrets)
sap-adt configure            # interactive setup; the password never passes
                             # through chat, argv, or logs
sap-adt status               # local configuration state — this does NOT
                             # contact SAP; a live read command does
```

If you installed through **npx** instead of a global/local install, there is
no `sap-adt` entry on PATH — prefix the commands:
`npx "sap-adt-cli@^1.5.0" <command>`, or switch to
`npm install -g "sap-adt-cli@^1.5.0"` for the bare `sap-adt` command. npx caches the
package and the runtime you installed under `~/.npm/_npx/`; clearing that
cache requires running `install` again.

If PATH was just modified (installer), restart the terminal/agent before
assuming `sap-adt` is missing — or call the absolute path once to verify.

## Dotenv template (optional layer)

Save this to a private path (never inside a skill folder or the repository),
fill it in, and declare the path — the CLI only reads the file you name:

```ini
SAP_URL=https://your-sap-system.example.com:8000
SAP_USERNAME=YOUR_USERNAME
SAP_PASSWORD=YOUR_PASSWORD
SAP_CLIENT=100
SAP_LANGUAGE=EN
SAP_VERIFY_SSL=1   # set to 0 only for self-signed / internal-CA systems
```

```bash
chmod 600 ~/.config/sap-adt.env
export SAP_ADT_DOTENV="$HOME/.config/sap-adt.env"
```

Write/activate/transport operations still require the capability flags and
per-operation confirmation; the env layer only supplies the connection.

## Diagnostics matrix

| Symptom | Meaning | Action |
|---|---|---|
| `command not found` | Not installed, or PATH not refreshed in this session | Restart terminal; if still missing, install per above (ask the user first) |
| Works at absolute path, not by name | PATH stale in the running agent/terminal | Restart the agent; do NOT reinstall |
| Version below the compatible range | Runtime too old for the skill | Upgrade via the same channel; confirm with the user |
| `install` cannot reach the release CDN | The network requires a proxy and none is configured (or the proxy blocks `CONNECT`) | Set `HTTPS_PROXY`/`NO_PROXY` — see *Proxied / restricted networks* |
| Proxy HTTP 407 / `PROXY_AUTH` | The proxy requires authentication | Configure URL-encoded proxy credentials through `HTTPS_PROXY`, npm proxy or `PIP_PROXY`; never use SAP credentials |
| Certificate verification / `TLS_CERTIFICATE` | A trusted corporate CA is missing or expired | npm: `NODE_EXTRA_CA_CERTS`; Python version checks: `REQUESTS_CA_BUNDLE`; pip: `PIP_CERT`. Do not disable verification |
| `EACCES`, `EPERM`, `EBUSY` / `PERMISSION` | Unwritable installation or locked files | Close CLI processes, inspect folder permissions/quarantine; use a writable venv if needed, not automatic elevation |
| `ENOSPC` / `DISK_FULL` | Temporary or installation drive is full | Free space on both drives, then inspect installation state before retrying |
| Runtime self-test failure | Unsupported CPU/glibc, missing DLLs or blocked startup | Check the platform-specific hint; use Python in a venv if the native runtime is incompatible |
| Unsupported native platform | No matching asset is published, including current macOS | Use the printed Python >=3.10 virtual-environment commands; repeating `install` will not create an asset |
| Rollback incomplete / exit 3 | Installation state needs human inspection | Retain and restore the reported backup, or follow the scoped package-manager repair command; do not auto-retry |
| pip externally managed / PEP668 | Python belongs to an OS package manager | Use pipx or a venv; do not use `sudo pip` or `--break-system-packages` |
| `no usable keystore backend` | No OS keystore available | See `credentials doctor` output; the encrypted-file fallback needs `cryptography` (bundled in the frozen runtime) |
| Sandbox/container without the user's desktop tools | The CLI may exist on the desktop but not in your sandbox | Ask the user; never assume the desktop install is reachable |
| No shell / no install permission / no network | Agent cannot install or run | Give the user the manual steps; continue offline work if the task allows |

## Version compatibility

Each skill declares the compatible CLI range in its generated
`references/runtime-compatibility.json` (derived from the repository's root
`compatibility.json`). Do not guess ranges and do not resolve `@latest` per
task — install the version the skill's snapshot names.
