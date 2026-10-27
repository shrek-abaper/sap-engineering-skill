#!/usr/bin/env node
/* sap-adt launcher (npm bin entry).
 *
 * Dispatches to the installed self-contained runtime. The runtime must have
 * been fetched once by `<bin> install` — a normal invocation NEVER downloads
 * or upgrades anything. Node.js is required only for this launcher path;
 * the runtime itself is a native, Python-free executable.
 *
 * `sap-adt install` is our custom install wizard, not an npx/npm feature.
 */
"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

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
    fail(
      `sap-adt runtime is not installed for ${platformKey()}.\n` +
      `Run the install wizard once:  npx @shrek-abaper/sap-adt-cli install\n` +
      `(or: <this-bin> install). Nothing was downloaded or modified.`,
      2,
    );
  }

  // Argument array, no shell: exit code and both streams pass through.
  const result = spawnSync(bin, argv, { stdio: "inherit" });
  if (result.error) {
    fail(`Failed to launch runtime at ${bin}: ${result.error.message}`, 2);
  }
  process.exit(result.status === null ? 1 : result.status);
}

main(process.argv.slice(2));
