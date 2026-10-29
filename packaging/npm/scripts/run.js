#!/usr/bin/env node
/* sap-adt launcher (npm bin entry).
 *
 * Dispatches to the installed self-contained runtime. The runtime must have
 * been fetched once by `<bin> install` — a normal invocation NEVER downloads
 * or upgrades anything (except the explicitly requested update command).
 * Node.js is required only for this launcher path;
 * the runtime itself is a native, Python-free executable.
 *
 * `sap-adt install` is our custom install wizard, not an npx/npm feature.
 */
"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { pythonFallback, safeMessage, installationHint } = require("./npm.js");

const PKG_DIR = path.resolve(__dirname, "..");

function platformKey() {
  const osMap = { linux: "linux", darwin: "darwin", win32: "windows" };
  const archMap = { x64: "x86_64", arm64: "aarch64" };
  const os = osMap[process.platform];
  const arch = archMap[process.arch];
  return os && arch ? `${os}-${arch}` : `${process.platform}-${process.arch}`;
}

function runtimeBin() {
  const exe = process.platform === "win32" ? "sap-adt.exe" : "sap-adt";
  return path.join(PKG_DIR, "runtime", platformKey(), "sap-adt", exe);
}

function fail(message, code = 1) {
  process.stderr.write(`${message}\n`);
  process.exit(code);
}

function main(argv) {
  if (argv[0] === "install") {
    // Custom install wizard (fetch + verify + atomic install of the runtime).
    const result = spawnSync(process.execPath,
      [path.join(__dirname, "install.js"), ...argv.slice(1)],
      { stdio: "inherit" });
    process.exit(result.status === null ? 1 : result.status);
  }

  const bin = runtimeBin();
  if (!fs.existsSync(bin)) {
    try {
      const manifest = JSON.parse(fs.readFileSync(path.join(PKG_DIR, "runtime-manifest.json"), "utf8"));
      if (manifest.artifacts && !manifest.artifacts[platformKey()]) {
        fail(`No native runtime is published for ${platformKey()} in this package.\n` +
          pythonFallback(), 2);
      }
    } catch { /* The install wizard diagnoses a missing or invalid manifest. */ }
    fail(
      `sap-adt runtime is not installed for ${platformKey()}.\n` +
      `Run the install wizard once:  npx sap-adt-cli install\n` +
      `(or: <this-bin> install). Nothing was downloaded or modified.`,
      2,
    );
  }

  const { isUpdate, runUpdate } = require("./update.js");
  if (isUpdate(argv)) {
    try {
      process.exit(runUpdate(PKG_DIR, bin, argv));
    } catch (error) {
      process.stderr.write(JSON.stringify({
        ok: false, format_version: 1, command: "update",
        error: { code: error.needsInspection ? "CONFIRM_REQUIRED" : "SERVER_ERROR",
          message: safeMessage(error), http_status: null,
          hint: installationHint(error) },
      }) + "\n");
      process.exit(error.needsInspection ? 3 : 1);
    }
  }

  // Argument array, no shell: exit code and both streams pass through.
  const result = spawnSync(bin, argv, { stdio: "inherit" });
  if (result.error) {
    fail(`Failed to launch runtime at ${bin}: ${safeMessage(result.error)}\n` +
      installationHint({ code: result.error.code, message: "runtime self-test startup" }), 2);
  }
  process.exit(result.status === null ? 1 : result.status);
}

main(process.argv.slice(2));
