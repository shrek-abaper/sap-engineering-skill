# npm / npx install

**Node.js ≥ 18 is required for this channel only.** The installed runtime is
a native executable — no Python. General guide:
[runtime-setup.md](runtime-setup.md).

## Two ways to run it

**A. Global command (recommended):** the npm package is `sap-adt-cli`, but its
bin is **`sap-adt`** — a global install puts that command on PATH.

```bash
npm install -g "sap-adt-cli@^1.4.0"
sap-adt install            # fetch + verify + install the runtime
sap-adt --version
```

**B. npx (no global install):** npx does **not** add `sap-adt` to PATH, so
keep the package prefix on every call.

```bash
npx "sap-adt-cli@^1.4.0" install
npx "sap-adt-cli@^1.4.0" --version
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

## Local packaging tests (no registry, no network)

```bash
python tools/build_runtime.py            # build the runtime for this platform
python tools/build_npm.py --local-file-urls
cd dist/npm && npm pack
# in a scratch project:
npm install <path>/sap-adt-cli-1.4.1.tgz
SAP_ADT_INSTALL_ALLOW_FILE=1 ./node_modules/.bin/sap-adt install
./node_modules/.bin/sap-adt --version
```

`file://` artifacts are refused unless `SAP_ADT_INSTALL_ALLOW_FILE=1` is set
(test seam only). Error paths are covered by
`node --test packaging/npm/test/install.test.js`.
