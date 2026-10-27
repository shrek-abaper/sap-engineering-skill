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
| npm (global) | Node.js ≥ 18 is available; you want the `sap-adt` command on PATH | Node.js only (no Python) | `npm install -g "sap-adt-cli@^1.4.0"`, then `sap-adt install` |
| npx (no global install) | Try it without changing PATH | Node.js ≥ 18 | `npx "sap-adt-cli@^1.4.0" install`, then prefix every call: `npx "sap-adt-cli@^1.4.0" <command>` |
| PyPI (wheel/sdist) | Python ≥ 3.10 available | Python | `pip install "sap-adt>=1.4.0,<2.0.0"` |
| Portable archive (Linux) | No dev environment | Linux x86_64, glibc ≥ 2.39 build | download the newest 1.x `sap-adt-<ver>-linux-x86_64.tar.gz` from the release page and unpack it, run inside it `./sap-adt/sap-adt` |
| Windows installer | No dev environment | Windows 10+ x64 | newest 1.x `sap-adt-<ver>-windows-x86_64-setup.exe` — **not built yet** (needs a Windows build host and a real install test) |
| Python source | Developers, contributors | Python ≥ 3.10 | `pip install -e .` from the repo |

The version ranges above are the skill's **compatible range** (declared in
`references/runtime-compatibility.json`). Resolving inside the range always
yields a compatible release, so these instructions do not need updating on
every CLI release. Never use an unbounded `@latest` — a future major could
break the skill.

All channels install the same runtime built from the same commit. `install`
in the npm channel is this package's own wizard (fetch → SHA-256 verify →
atomic install → self-test), not an npm built-in.

> Channel status (2026-10-28): npm and PyPI are live and the GitHub Release
> carries the Linux x86_64 portable runtime, the plugin/skill zips and the
> checksums. The Windows installer and the macOS runtime are **not built
> yet** — do not promise them until a real build and install smoke pass on
> those systems.

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
`npx "sap-adt-cli@^1.4.0" <command>`, or switch to
`npm install -g "sap-adt-cli@^1.4.0"` for the bare `sap-adt` command. npx caches the
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
| `no usable keystore backend` | No OS keystore available | See `credentials doctor` output; the encrypted-file fallback needs `cryptography` (bundled in the frozen runtime) |
| Sandbox/container without the user's desktop tools | The CLI may exist on the desktop but not in your sandbox | Ask the user; never assume the desktop install is reachable |
| No shell / no install permission / no network | Agent cannot install or run | Give the user the manual steps; continue offline work if the task allows |

## Version compatibility

Each skill declares the compatible CLI range in its generated
`references/runtime-compatibility.json` (derived from the repository's root
`compatibility.json`). Do not guess ranges and do not resolve `@latest` per
task — install the version the skill's snapshot names.
