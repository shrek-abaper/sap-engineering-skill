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

## Channels

| Channel | When to use | Prerequisites | Command |
|---|---|---|---|
| npm / npx | Node.js ≥ 18 is available | Node.js only (no Python) | `npx sap-adt-cli@1.4.0 install` |
| Windows installer / portable | No dev environment at all | Windows 10+ x64 | run `sap-adt-1.4.0-windows-x86_64-setup.exe`, or unzip the portable archive and run `sap-adt.exe` inside |
| Portable archive (Linux/macOS) | No dev environment | supported OS/glibc | unpack `sap-adt-1.4.0-<os>-<arch>.tar.gz`, run inside it `./sap-adt/sap-adt` |
| Python source / wheel | Developers, contributors | Python ≥ 3.10 | `pip install sap-adt==1.4.0` (once released) or `pip install -e .` from the repo |

Pin the version that this skill's `references/runtime-compatibility.json`
declares — do not use `@latest`.

All channels install the same runtime built from the same commit. `install`
in the npm channel is this package's own wizard (fetch → SHA-256 verify →
atomic install → self-test), not an npm built-in.

> Release-channel note: until the first release is published, only the
> Python-source channel and locally built artifacts exist. Pre-release
> candidate manifests are marked `candidate-not-published` and their URLs
> are not yet live.

## Post-install self-test (from the install location)

```bash
sap-adt --version            # prints the exact CLI version
sap-adt credentials doctor   # which keystore backend is active (no secrets)
sap-adt configure            # interactive setup; the password never passes
                             # through chat, argv, or logs
sap-adt status               # local configuration state — this does NOT
                             # contact SAP; a live read command does
```

If PATH was just modified (installer), restart the terminal/agent before
assuming `sap-adt` is missing — or call the absolute path once to verify.

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
