# Building

Linux/Windows builds and live SAP verification run locally. The manually
dispatched `build-macos-runtime.yml` workflow builds on native Intel and
Apple Silicon macOS runners, runs offline tests and verifies an isolated
npm installation. It never connects to SAP or publishes packages.
See [releasing.md](releasing.md).

## One-time environment

```bash
python3 -m venv .venv
.venv/bin/pip install -e . click requests urllib3 keyring cryptography build pyinstaller
```

Node.js ≥ 18 and npm are only needed for the npm channel; Inno Setup 6 only
for the Windows installer (on Windows).

## Steps

```bash
# 1. Python artifacts
.venv/bin/python -m build                     # -> dist/*.whl, dist/*.tar.gz
.venv/bin/python tools/build_watt.py          # -> same-version sap_watt wheel/sdist
.venv/bin/python tools/smoke_python.py        # -> offline, isolated entry/core ownership checks

# 2. Self-contained runtime (current platform only)
.venv/bin/python tools/build_runtime.py       # -> dist/runtime/<os>-<arch>/

# 3. Portable / installer
.venv/bin/python tools/build_installer.py     # Linux: portable archive;
                                              # Windows: Inno Setup if present

# 4. npm staging + tarball
.venv/bin/python tools/build_npm.py
# Stages dist/npm (sap-adt-cli) and dist/npm-watt (sap-watt).
# build_manifest.py packs both; do not hand-edit staged package identities.

# 5. Skill snapshots + plugin payload
.venv/bin/python tools/sync_skill_runtime_docs.py
.venv/bin/python tools/build_skills.py
.venv/bin/python tools/build_plugin.py

# 6. Release candidate (copies artifacts, writes SHA256SUMS + manifest)
.venv/bin/python tools/build_manifest.py
.venv/bin/python tools/check_release.py --skip-marketplace
```

## Executor 1.6.6 verification

The local source passed 613 Python tests, 47 Node installer/update
tests, the command/documentation contract, generated-snapshot checks, wheel/sdist
builds, self-contained Skill builds and a clean-venv wheel installation.
Real SAP reads verified enhancement/message/lock metadata, bounded references,
two-profile source/configuration comparisons and single-object syntax/ATC.
The harmless standard-class Unit run executed **zero tests** and correctly
remained `not_run`; it is not passing Unit evidence. The current user's TR list
and selected dump feed were empty, so nonempty TR/dump success paths remain
fixture-verified. abaplint uses supplied bound native JSON, and coverage uses
supplied source-bound measurements; neither is attested native instrumentation.
This executor acceptance performed no SAP source/configuration writes or
transport release. Distribution verification is separate from live SAP
certification.

On 2026-11-27 UTC, the 1.6.6 Linux/Windows native runtimes passed isolated npm
installation and diagnostic/debugger/execution cross-process smokes. Windows
passed 40 targeted executor Python tests with temporary official MinGit, and
42 npm regressions with 5 platform-specific skips. Its desktop installer,
built with verified official portable Inno Setup 6.7.4, passed native PATH
cleanup tests, silent per-user installation in a Unicode/space path,
same-version upgrade and uninstall, preserving synthetic configuration and
user/machine PATH.

Both macOS targets ran 613 Python tests (3 skips), 47 npm tests (46 passed,
1 skip), native builds and isolated npm runtime smokes in
[Actions run 46073493281](https://github.com/shrek-abaper/sap-engineering-skill/actions/runs/46073493281),
source `cb7b743b5f497af398773618ddcdb2b014a68d3a`.
No personal Mac, signing/notarization, live Windows/macOS SAP access,
graphical/elevated Windows installation or actual PATH mutation is certified.
See `packaging/targets.json` for the precise current platform claims; the
older release notes below remain historical.

## Windows runtime from WSL

WSL can drive a native Windows build when Windows Python, Node.js/npm and
`tar.exe` are installed on the host. This is not cross-compilation:
PyInstaller and the npm smoke test must run as Windows processes.
Inno Setup is only needed for the separate desktop installer, not the npm ZIP.

From the checkout, use `py.exe -0p` to locate a Windows Python supported by
PyInstaller (Python 3.12 was verified). In Windows PowerShell, with the
checkout as the current directory:

```powershell
$python = 'C:\Path\To\Python312\python.exe' # use the path from py.exe -0p
$venv = Join-Path $env:TEMP 'sap-adt-windows-build\venv'
& $python -m venv $venv
$python = Join-Path $venv 'Scripts\python.exe'
& $python -m pip install -e . keyring cryptography pyinstaller
& $python tools/build_runtime.py
```

Alternatively, invoke that Windows venv from WSL (replace its path):

```bash
powershell.exe -NoProfile -NonInteractive -Command \
  '& "C:\Path\To\venv\Scripts\python.exe" tools/build_runtime.py; exit $LASTEXITCODE'
```

The build produces `dist/runtime/sap-adt-<ver>-windows-x86_64.zip`.
Keep the Linux archive of the same version alongside it, then stage both:

```bash
.venv/bin/python tools/build_npm.py
powershell.exe -NoProfile -NonInteractive -Command \
  '& "C:\Path\To\venv\Scripts\python.exe" tools/smoke_npm.py; exit $LASTEXITCODE'
```

The smoke tool uses a temporary Windows-local npm prefix/cache, so npm does
not run from a UNC current directory. It verifies the real runtime through
the npm `.cmd` shim without changing the user's global installation or
contacting SAP. It also checks local artifact SHA-256 before testing.
The GNU-tar-specific traversal fixture is skipped on Windows; it still runs
in the Linux suite.

For Windows npm regressions, copy `packaging/npm` to a Windows-local temporary
directory, change to that copy, then run:

```powershell
node --test test/install.test.js test/update.test.js
```

Do not run these Node tests from a WSL UNC checkout: Node 24 can fail while
probing ancestor `package.json` files on the UNC share. The installed-runtime
smoke already avoids this by using a Windows-local working directory.

Build and local verification do not publish anything. A new npm version
and its Windows release ZIP must be published together before registry
users can install it.

## macOS runtime on hosted runners

After pushing a reviewed source commit, explicitly dispatch:

```bash
gh workflow run build-macos-runtime.yml --ref main
```

The workflow uses macOS 15 Intel and Apple Silicon runners with Python
3.14 and Node.js 22. Each job checks its native target, runs offline tests,
builds the runtime and tests `npm pack` through runtime installation in a
temporary global prefix/cache. Only successful jobs upload versioned
archives and build metadata; download them before assembling the release.
No SAP credentials, signing certificates or publishing tokens are used.

This does not verify a personal Mac, older macOS, Keychain interaction,
Gatekeeper/quarantine behavior, signing/notarization or live SAP access.
Do not mark a target verified until its native job actually succeeds.

### Desktop installer verification

With Inno Setup 6 installed, add the directory containing `ISCC.exe` to the
Windows process PATH, then run with the Windows build venv:

```powershell
$env:PATH = 'C:\Path\To\Inno Setup 6;' + $env:PATH
& $python tools/build_installer.py
& $python tools/smoke_windows_installer.py
```

Inno Setup 6.7.4 also supports `/PORTABLE=1 /CURRENTUSER /VERYSILENT /NOICONS`
with `/DIR=<temporary-directory>`. Verify the official download's SHA-256
and Authenticode signature before running it. Provision the portable compiler
in a Windows-local temporary directory, not a WSL UNC share: its setup can
fail while writing `.url` INI entries on that share. Only the child process
PATH needs the compiler directory; no persistent PATH or execution-policy
change is required.

The smoke test compiles native PATH cleanup tests, then performs silent
per-user installation, same-version upgrade, CLI launch and uninstall of
the actual desktop installer. It refuses to run over an existing install,
uses a synthetic home and a temporary Unicode/space install path, and
disables the PATH task and shortcuts. Logs stay in `dist/installer-smoke/`.
No real credentials or SAP connection are used.

This verifies the silent installer lifecycle, not graphical wizard clicks,
real PATH registry mutation, elevated installs or SmartScreen behavior.
Publishing and signing remain separate authorized steps.

## Verification baseline

```bash
.venv/bin/python -m unittest discover -s tests -v   # unit/contract/distribution
.venv/bin/python tests/check_contract.py            # SKILL.md vs code
.venv/bin/python tools/smoke_diagnostics.py "$PWD/.venv/bin/python" -m sap_adt
.venv/bin/python tools/smoke_debugger.py "$PWD/.venv/bin/python" -m sap_adt
.venv/bin/python tools/smoke_execution.py "$PWD/.venv/bin/python" -m sap_adt
node --test packaging/npm/test/*.test.js             # installer/update error paths
gitleaks protect --staged --config .gitleaks.toml    # pre-commit secret scan
```

`smoke_diagnostics.py` starts a loopback-only synthetic HTTP server and checks
Unit failure evidence, the empty-run gate, a source line window, dump details
and partial-evidence exits through the actual CLI process. It removes SAP
connection variables and uses a temporary home. Pass an absolute installed
CLI path to check a wheel or native runtime instead of the source checkout.
`smoke_debugger.py` proves one foreground owner can service distinct CLI
processes with the same synthetic SAP context: breakpoint/listen/attach,
stack/UTF-8 variables, gated controls and scoped non-terminating cleanup.
It checks that descriptors never contain SAP session material or variables.
The debugger unit suite additionally covers unknown control outcomes,
unconfirmed cleanup, private IPC, expiry, process death and POSIX SIGTERM.
Native Windows runs verify the actual protected DACL, not `chmod` emulation;
Windows TerminateProcess is abrupt death, not a catchable POSIX SIGTERM.
Interactive Windows console Ctrl-C remains outside automated verification.

`smoke_execution.py` checks Class/Report output, the complete temporary-Class
lifecycle with `allow_write=false`, continued refusal of generic source writes,
independent consent and output truncation against a loopback-only fixture.
It never uses SAP credentials or a live target.

`smoke_npm.py` runs all three smokes after packing and isolated installation;
the existing native macOS workflow therefore checks these primitives too.
Redirected stdout/stderr must remain UTF-8 even when Windows Python starts
with a legacy code page.

The 1.6.5 release gate on 2026-11-22 passed 560 Python tests and 47 npm
regressions on Linux, a clean wheel installation and all three installed
runtime smokes. Windows-native ZIP/npm and the Inno Setup 6.7.4 desktop
installer passed; Windows-local npm regressions passed 42 tests with 5
platform-specific skips. Silent per-user install in a Unicode/space path,
same-version upgrade, uninstall and native PATH cleanup tests preserved the
synthetic configuration and both user/machine PATH. Both native macOS targets
passed 560 Python tests (3 skips), 46 npm tests (1 skip), builds and isolated
installation smokes in
[Actions run 44951555059](https://github.com/shrek-abaper/sap-engineering-skill/actions/runs/44951555059),
source `b417e220d700c1c97ce8f561e336cd824b3811e4`.
These native builds do not certify live SAP access on Windows/macOS. Isolated
DEV acceptance and remaining server-risk/DDIC/service/transport limits are
documented in the Skill's `references/core-workflows.md`.

The 1.6.4 release gate on 2026-11-21 passed 518 Python tests and 47 npm
regressions on Linux, plus a clean wheel installation and all three installed
runtime smokes. Windows-native ZIP/npm installation passed all three smokes;
Windows-local npm regressions passed 42 tests with 5 platform-specific skips.
Both native macOS targets passed 518 Python tests (3 skips), 46 npm tests
(1 skip), builds and isolated npm runtime smokes in
[Actions run 44904521434](https://github.com/shrek-abaper/sap-engineering-skill/actions/runs/44904521434),
source `f2a61e3e99f8f8de2ddaa1e7b4a7af27fba49004`.
Execution smokes on every target kept generic source writes disabled.
The Windows 1.6.4 desktop installer was subsequently built using official
portable Inno Setup 6.7.4 on the Windows host through WSL interop. Native
PATH cleanup tests, silent per-user install in a Unicode/space path,
same-version upgrade and uninstall passed; synthetic configuration and
user/machine PATH remained unchanged. GUI clicks, actual PATH mutation,
elevation, signing and live SAP access remain unverified. DEV development
verification and remaining RAP/TR live-verification gaps are documented
in the Skill development reference.

The 1.6.2 release gate repeated the same matrix from the 1.6.2 source on
2026-10-31: Linux passed the 467-test Python suite and 47 npm regressions;
Windows-local npm regressions passed 42 with 5 platform-specific skips;
Linux/Windows installed npm runtimes and a clean Python wheel passed the
diagnostic/debugger smokes; the Windows desktop installer (Inno Setup 6.7.4)
passed silent install, same-version upgrade and uninstall; both macOS
targets passed 467 tests (3 skips) and installed-runtime smokes in
[Actions run 41207366848](https://github.com/shrek-abaper/sap-engineering-skill/actions/runs/41207366848)
at source `d5e21255fd3793226a6ec797ca4818f98bdc96e1`. The verified
`write-source` workflow was accepted on a live non-production S/4HANA client
(see CHANGELOG); the distribution smokes themselves stay offline.

The 1.6.1 release gate includes Linux/Windows native npm runtimes, clean Python
wheel installations, the Windows silent desktop-installer lifecycle and both
native macOS workflow targets. Each installed runtime must pass the diagnostic
and cross-process debugger smokes. These use synthetic offline responses,
not live debugger attachment; previous-version builds do not validate a new
candidate. Tagging/publication require separate approval.

Verified on 2026-10-30: Linux and both native macOS targets passed the
441-test Python suite (platform-specific skips apply); Linux passed all 47
npm regressions. Windows-local npm regressions passed 42 tests with 5
platform-specific skips. Linux/Windows installed npm runtimes and a clean
Python wheel passed the diagnostic/debugger smokes; the Windows 1.6.1
desktop installer passed silent install, same-version upgrade and uninstall.
Both macOS builds and installed-runtime smokes passed
[Actions run 40994475197](https://github.com/shrek-abaper/sap-engineering-skill/actions/runs/40994475197)
at source `26bf0580df4613803225f997abadda249601936e`.

Live QAS checked dump metadata/formatted
details and test-include reads. That system returned empty Unit runs for
the inspected standard classes, so executed-method pass/failure parsing is
covered by synthetic fixtures, not claimed as live-verified.
There is no approved non-business live debug target in this verification
scope; the CLI does not enable writes, install fixtures or interrupt
business sessions to obtain one.
Subsequent read-only live checks verified debugger-resource discovery and
the adapter's CSRF preflight. Generic XML discovery was rejected with HTTP
406; requesting the Atom service media type fixed it and is enforced by
the synthetic fixture. The selected non-production profile now has explicitly approved independent
debug permission, with source/transport writes still disabled. Current-source
local owner startup, separate-process status and cleanup passed; the owner
exited and its descriptor was removed. No live breakpoint/listener/attachment
was created because no approved non-business target and trigger were supplied.
Discovery, CSRF and local owner lifecycle do not prove SAP debug authorization
or persistent affinity.

Before publishing an upgrade, `--skip-marketplace` leaves the previous
published plugin archive live. After publication and the marketplace
update, run `tools/check_release.py` again without that flag.

## Rules

- Never mark a platform verified from the existence of a script. A target is
  verified only after a real build + install smoke on that OS/arch
  (`packaging/targets.json`).
- Builds must not install dependencies at run time, auto-upgrade, read
  secrets, or write into the CLI install directory.
