/* Error-path and happy-path tests for scripts/install.js.
 *
 * Fully offline: a fake runtime tar.gz (shell script printing a version) is
 * built with tar via argument arrays, manifests use file:// URLs, and every
 * invocation sets SAP_ADT_INSTALL_ALLOW_FILE=1 except the refusal test.
 *
 * Run: node --test packaging/npm/test/install.test.js
 */
"use strict";

const { test, beforeEach, afterEach } = require("node:test");
const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const SCRIPTS = path.resolve(__dirname, "..", "scripts"); // source templates
// Tests always run the COPIED scripts inside the staged package: PKG_DIR is
// derived from __dirname, so invoking the originals would bind the wrong dir.
const installScript = () => path.join(pkgDir, "scripts", "install.js");
const runScript = () => path.join(pkgDir, "scripts", "run.js");

let work;       // temp dir per test
let pkgDir;     // staged package copy with a test manifest
let artifact;   // fake runtime archive

function sha256(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

function platformKey() {
  const osMap = { linux: "linux", darwin: "darwin", win32: "windows" };
  const archMap = { x64: "x86_64", arm64: "aarch64" };
  return `${osMap[process.platform]}-${archMap[process.arch]}`;
}

function buildFakeRuntime(dir, payload) {
  // payload: { "sap-adt": <exe text>, ... } or { "evil": "../x" } variants
  const tree = path.join(dir, "tree", "sap-adt");
  fs.mkdirSync(tree, { recursive: true });
  const exe = path.join(tree, "sap-adt");
  fs.writeFileSync(exe, payload ?? "#!/bin/sh\necho 'sap-adt, version 0.0.0-test'\n");
  fs.chmodSync(exe, 0o755);
  const archive = path.join(dir, "runtime.tar.gz");
  const r = spawnSync("tar", ["-czf", archive, "-C", path.join(dir, "tree"), "sap-adt"],
    { encoding: "utf8" });
  assert.equal(r.status, 0, `tar failed: ${r.stderr}`);
  return archive;
}

function stagePackage(manifest) {
  fs.mkdirSync(path.join(pkgDir, "scripts"), { recursive: true });
  for (const f of fs.readdirSync(SCRIPTS)) {
    fs.copyFileSync(path.join(SCRIPTS, f), path.join(pkgDir, "scripts", f));
  }
  fs.writeFileSync(path.join(pkgDir, "runtime-manifest.json"), JSON.stringify(manifest));
}

function manifestFor(artifactPathOrUrl, overrides = {}) {
  const url = artifactPathOrUrl.includes("://")
    ? artifactPathOrUrl
    : pathToFileURL(artifactPathOrUrl).toString();
  return {
    cli_version: "0.0.0-test",
    release_state: "local-test",
    artifacts: {
      [platformKey()]: {
        url,
        sha256: sha256(artifactPathOrUrl.includes("://") ? artifact : artifactPathOrUrl),
        format: "tar.gz",
        ...overrides,
      },
    },
  };
}

function runInstall(extraEnv = {}) {
  return spawnSync(process.execPath, [installScript()], {
    cwd: pkgDir,
    encoding: "utf8",
    env: { ...process.env, SAP_ADT_INSTALL_ALLOW_FILE: "1", ...extraEnv },
  });
}

function runBin(args, extraEnv = {}) {
  return spawnSync(process.execPath, [runScript(), ...args], {
    cwd: pkgDir,
    encoding: "utf8",
    env: { ...process.env, ...extraEnv },
  });
}

beforeEach(() => {
  work = fs.mkdtempSync(path.join(os.tmpdir(), "sap-adt-install-test-"));
  pkgDir = path.join(work, "pkg");
  artifact = buildFakeRuntime(work);
});

afterEach(() => {
  fs.rmSync(work, { recursive: true, force: true });
});

test("happy path: install, then the bin runs the runtime", () => {
  stagePackage(manifestFor(artifact));
  const install = runInstall();
  assert.equal(install.status, 0, install.stderr);
  assert.match(install.stdout, /installed/);

  const bin = runBin(["--version"]);
  assert.equal(bin.status, 0, bin.stderr);
  assert.match(bin.stdout, /0\.0\.0-test/);
});

test("sha256 mismatch: install refused, nothing installed", () => {
  stagePackage(manifestFor(artifact, { sha256: "0".repeat(64) }));
  const result = runInstall();
  assert.equal(result.status, 1);
  assert.match(result.stderr, /sha256 mismatch/);
  const runtimeDir = path.join(pkgDir, "runtime");
  assert.ok(!fs.existsSync(runtimeDir), "runtime dir must not exist after refusal");
});

test("sha256 mismatch with existing runtime: old version preserved", () => {
  stagePackage(manifestFor(artifact));
  assert.equal(runInstall().status, 0);

  const other = buildFakeRuntime(path.join(work, "v2"),
    "#!/bin/sh\necho 'sap-adt, version 9.9.9-bad'\n");
  stagePackage(manifestFor(other, { sha256: "f".repeat(64) }));
  const result = runInstall();
  assert.equal(result.status, 1);
  assert.match(result.stderr, /sha256 mismatch/);

  const bin = runBin(["--version"]);
  assert.equal(bin.status, 0);
  assert.match(bin.stdout, /0\.0\.0-test/); // still the original
});

test("unsupported platform: clear refusal", () => {
  stagePackage({ cli_version: "0.0.0-test", release_state: "local-test", artifacts: {} });
  const result = runInstall();
  assert.equal(result.status, 1);
  assert.match(result.stderr, /unsupported platform/);
});

test("file:// artifact refused without the explicit test gate", () => {
  stagePackage(manifestFor(artifact));
  const result = spawnSync(process.execPath, [installScript()], {
    cwd: pkgDir, encoding: "utf8",
    env: { ...process.env, SAP_ADT_INSTALL_ALLOW_FILE: "0" },
  });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /file:\/\/ artifacts are refused/);
});

test("http:// artifact refused", () => {
  stagePackage(manifestFor("http://example.com/runtime.tar.gz"));
  const result = runInstall();
  assert.equal(result.status, 1);
  assert.match(result.stderr, /non-HTTPS/);
});

test("archive with traversal entry: rejected, runtime untouched", () => {
  // Craft an archive whose member escapes the target dir.
  const evilDir = path.join(work, "evil");
  fs.mkdirSync(evilDir, { recursive: true });
  fs.writeFileSync(path.join(evilDir, "payload"), "x");
  const evilArchive = path.join(work, "evil.tar.gz");
  const r = spawnSync("tar",
    ["-czf", evilArchive, "-C", evilDir, "--transform", "s|payload|../pwned|", "payload"],
    { encoding: "utf8" });
  assert.equal(r.status, 0, r.stderr);

  stagePackage(manifestFor(evilArchive));
  const result = runInstall();
  assert.notEqual(result.status, 0);
  assert.ok(!fs.existsSync(path.join(pkgDir, "pwned")),
    "traversal entry must not land outside the staging dir");
});

test("normal invocation without runtime: clear error, no download", () => {
  stagePackage(manifestFor(artifact)); // manifest present, runtime absent
  const bin = runBin(["--version"]);
  assert.equal(bin.status, 2);
  assert.match(bin.stderr, /runtime is not installed/);
  assert.match(bin.stderr, /install/);
});
