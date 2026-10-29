# Updating the CLI

The `update` command requires CLI 1.6.0 or newer.
Check `sap-adt update --help` first. Older versions require one manual
package-manager upgrade to obtain it; repeatedly running their `install`
command does not upgrade the npm package.

```bash
sap-adt update --check       # read-only registry check
sap-adt update              # preview, then fresh default-no confirmation
sap-adt update --yes         # explicitly approve this update in automation
sap-adt update --check --major  # explicitly look beyond the current major
sap-adt update --major       # allow a major upgrade, still asks for confirmation
```

Default selection is the newest stable release **within the current major**,
not an unbounded `latest`. Prereleases are excluded; fully yanked/empty PyPI
releases are excluded. It never downgrades or reinstalls an up-to-date CLI.
`--major` deliberately leaves the skill's compatibility guarantee: review
the skill's compatible range before using it. Successful check/update is
plain text, like other local maintenance commands; errors use the existing
JSON envelope and exit tiers.

## Installation channels

| Detected installation | Behavior |
|---|---|
| npm global, invoked through its launcher | Query npm versions using npm's registry settings; stage the exact target package with lifecycle scripts disabled, install and verify its platform runtime, then update the same global package and verify its final version |
| pip registry install | Use this CLI's Python interpreter, not an arbitrary `pip` on PATH; pin the selected version and verify with the same interpreter afterwards |
| pip user install | Keep `--user`; do not move the package into a system location |
| pipx main package | Use the owning pipx environment and pin the selected candidate through `--pip-args`; verify with the existing environment's interpreter |
| Project-local/workspace/linked npm or npx | Check only; provide guidance to use the owning project/lockfile or an explicit npx version range; do not overwrite project dependencies or npx caches |
| Editable/direct-URL Python, unknown manager, externally managed Python | Check only; retain the original installation workflow; never use sudo or `--break-system-packages` |
| Portable runtime / Windows installer | Check only; use the matching release archive/installer, not pip inside the frozen executable |

For registry Python and standalone version checks, metadata comes from
PyPI's `sap-adt-cli` project. An available Python version does **not** prove
a matching standalone artifact exists for your OS/architecture. npm runtime
availability is verified while staging, before the live install changes.
The package manager can also refuse an update for an unsupported Python or
Node.js version.

Examples for installations that are intentionally not self-modified:

```bash
# npx: retain a compatible selector on every call
npx "sap-adt-cli@^1" install
npx "sap-adt-cli@^1" --version

# Project-local npm: run from the owning project and review lockfile changes
npm install "sap-adt-cli@^1"
./node_modules/.bin/sap-adt install
```

Use the equivalent project-local shim on Windows. Do not copy this example
into an unrelated working directory or automatically change a workspace's
package manager.

## Safety and failure handling

- No SAP login, config migration, dotenv loading, keystore access, server
  write, activation or transport operation is involved. Package-manager
  child processes do not receive `SAP_*` environment variables.
- `--check` performs only registry reads and local inspection; npm may
  maintain its normal metadata cache/logs. Normal SAP commands never check
  for or download updates in the background.
- Without `--yes`, non-interactive update exits 3 (`CONFIRM_REQUIRED`);
  declining the prompt exits 3 (`USER_ABORTED`). Unsupported installation
  channels also exit 3 when asked to apply an available update.
- npm's frozen runtime exits before its Node launcher replaces files,
  avoiding self-overwrite of a running Windows runtime. Staging failures
  leave the installed package/runtime unchanged.
- npm commit and Python package-manager operations are **not full
  transactions**. Failure after modification reports an incomplete state,
  not success, with `CONFIRM_REQUIRED` (exit 3); inspect the installation
  before retrying. For npm, reinstall
  the reported exact target package and run `sap-adt install` to repair.
- Only a successful post-install version readback reports completion.
  CLI updates do not update separately installed skill folders.
