# npm / npx install

**Node.js ≥ 18 is required for this channel only.** The installed runtime is
a native executable — no Python. General guide:
[runtime-setup.md](runtime-setup.md).

## Two ways to run it

**A. Global command (recommended):** the npm package is `sap-adt-cli`, but its
bin is **`sap-adt`** — a global install puts that command on PATH.

```bash
npm install -g "sap-adt-cli@^1.5.0"
sap-adt install            # fetch + verify + install the runtime
sap-adt --version
```

**B. npx (no global install):** npx does **not** add `sap-adt` to PATH, so
keep the package prefix on every call.

```bash
npx "sap-adt-cli@^1.5.0" install
npx "sap-adt-cli@^1.5.0" --version
```

npx caches the package, and the runtime you installed, under
`~/.npm/_npx/`; clearing that cache means running `install` again.

`install` is the package's own wizard, not an npm built-in:

1. matches OS/arch against the version-bound `runtime-manifest.json`;
2. downloads the artifact over HTTPS (redirect hosts allow-listed);
3. verifies SHA-256 from the manifest (never from the download endpoint);
4. extracts with traversal/symlink checks and swaps atomically, keeping the
   previous runtime on failure;
5. self-tests `sap-adt --version` via the absolute install path.

A normal `sap-adt` invocation never downloads or upgrades anything. The
runtime lives inside the npm package directory; upgrading the package
requires re-running `install`.

## Explicit updates (CLI 1.6.0+)

```bash
sap-adt update --check     # query versions; do not change the installation
sap-adt update             # preview and confirm a same-major stable update
sap-adt update --yes       # explicit approval for automation
```

The global npm launcher stages the exact new package and its verified
runtime before changing the live installation, then verifies the installed
version. The frozen process exits before replacement, including on Windows.
Staging failures leave the existing install untouched; the subsequent npm
commit is not a full transaction, so later failures include repair guidance.
Local/workspace/linked packages and npx caches are not self-modified: update
through their owning project/lockfile or an explicit npx selector instead.
SAP configuration and credentials are not read or changed.

Versions before 1.6.0 have no `update` command. Bootstrap once with
`npm install -g "sap-adt-cli@^1.6.0"` followed by `sap-adt install`.
`--major` explicitly allows
crossing major versions and can exceed a skill's compatible range.

From 1.6.0, the installer discovers proxies in this order:
environment variables, npm's persistent `https-proxy`/`proxy` configuration,
then Windows current-user manual proxy settings. Windows bypass rules are
honored unless explicit `NO_PROXY` overrides them. It reports the selected
route, bounds connection setup to 30 seconds, and aborts a stalled transfer
after 60 seconds of inactivity. PAC/WPAD, SOCKS and automatic integrated proxy
authentication are not supported; explicit HTTP CONNECT proxy configuration
is required for those environments. No system proxy setting is changed.

The `update` launcher also passes discovered Windows manual proxy
settings to npm's registry checks and both package-install steps. This
does not make the initial external `npm install -g` command import system
proxies: configure npm or `HTTPS_PROXY` for that bootstrap step.

Runtime replacement now keeps the old runtime until its self-test succeeds.
Failed self-tests restore it; blocked restoration exits 3 with the retained
backup location. Extraction and self-test have 120/60-second limits, tunable
with `SAP_ADT_INSTALL_EXTRACT_TIMEOUT_MS` and
`SAP_ADT_INSTALL_SELFTEST_TIMEOUT_MS`. Errors include proxy/TLS, disk,
permissions, platform and startup recovery hints. Unsupported platforms
receive Python virtual-environment commands instead of an install loop.
See [failure recovery](runtime-setup.md#installationupdate-failure-recovery).

For older installers or Linux/macOS desktop-only proxies, set `HTTPS_PROXY`
(and `NO_PROXY` for internal hosts) before `install` — see
[Proxied / restricted networks](runtime-setup.md#proxied--restricted-networks).

## Windows availability

Windows x64 is supported starting with npm package **1.5.3**.
Availability depends on the installed package's
`runtime-manifest.json`: it must include `windows-x86_64`, with the matching
ZIP uploaded to the release. A package that lists only `linux-x86_64` cannot
install on Windows, even if `npm install -g` succeeds.

To replace a Linux-only launcher on Windows:

```powershell
npm install -g "sap-adt-cli@^1.5.3"
sap-adt install
sap-adt --version
```

The Windows npm channel requires Node.js and the Windows `tar.exe` (included
with current Windows 10/11), but no Python on the end user's machine.
The separate Inno Setup desktop installer has a verified silent per-user
lifecycle; see [Windows scope and limitations](windows.md).

## macOS availability (experimental, 1.6.0+)

macOS 15+ Intel (`darwin-x86_64`) and Apple Silicon (`darwin-aarch64`) use
the same npm/npx commands above. Both targets must pass native GitHub
Actions builds, offline tests and isolated npm installation before release.
No Python is needed for the installed runtime.

This is not verification on a personal Mac. Older macOS, Keychain,
Gatekeeper/quarantine, signing/notarization and live SAP on macOS remain
unverified. If a desktop proxy is enabled only in macOS settings, explicitly
configure npm or `HTTPS_PROXY`; only Windows manual system proxies are
auto-imported. Python >=3.10 in a venv remains an alternative.

## Local packaging tests (no registry, no network)

```bash
python tools/build_runtime.py            # build the runtime for this platform
python tools/build_npm.py
python tools/smoke_npm.py
```

Run these with Windows Python to verify Windows, not with WSL's Linux Python.
The smoke tool packs a temporary copy with a local artifact URL, uses an
isolated global npm prefix and cache, runs `install`, `--version`, and
`--help`, then removes its temporary files. It does not modify the
publishable staging manifest, user npm installation, or SAP configuration.

`file://` artifacts are refused unless `SAP_ADT_INSTALL_ALLOW_FILE=1` is set
(test seam only). Error paths are covered by
`node --test packaging/npm/test/install.test.js`.
