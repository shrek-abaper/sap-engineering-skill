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
const { spawn, spawnSync } = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const net = require("node:net");
const os = require("node:os");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const SCRIPTS = path.resolve(__dirname, "..", "scripts"); // source templates
// Pure helpers; requiring the script does not run the wizard.
const { moveTree, proxyForUrl } = require(path.join(SCRIPTS, "install.js"));
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

test("proxyForUrl: https_proxy wins over the other spellings", () => {
  const env = {
    https_proxy: "http://lower:1",
    HTTPS_PROXY: "http://upper:2",
    HTTP_PROXY: "http://plain:3",
    npm_config_proxy: "http://npm:4",
  };
  assert.equal(proxyForUrl("https://github.com/x", env).host, "lower:1");
  assert.equal(
    proxyForUrl("https://github.com/x", { npm_config_https_proxy: "http://npm:5" }).host,
    "npm:5");
  assert.equal(proxyForUrl("https://github.com/x", {}), null);
  // scheme-less values are accepted as http
  assert.equal(
    proxyForUrl("https://github.com/x", { https_proxy: "proxy.corp:8080" }).host,
    "proxy.corp:8080");
});

test("proxyForUrl: NO_PROXY forms bypass the proxy", () => {
  const proxy = "http://proxy:8080";
  const cases = [
    ["*", "https://github.com/x", null],
    ["github.com", "https://github.com/x", null],
    [".github.com", "https://github.com/x", null],
    ["*.github.com", "https://github.com/x", null],
    ["other.com, github.com", "https://github.com/x", null],
    ["github.com:443", "https://github.com/x", null],
    ["github.com:8443", "https://github.com/x", proxy],
    ["GITHUB.COM", "https://github.com/x", null],
    ["10.*", "https://10.1.2.3/x", null],
    ["192.168.*", "https://10.1.2.3/x", proxy],
    ["release-assets.githubusercontent.com", "https://github.com/x", proxy],
  ];
  for (const [noProxy, target, expected] of cases) {
    const env = { https_proxy: proxy, no_proxy: noProxy };
    const got = proxyForUrl(target, env);
    assert.equal(got ? got.host : null, expected ? new URL(expected).host : null,
      `NO_PROXY=${noProxy} for ${target}`);
  }
});

test("proxyForUrl: unsupported scheme refused; credentials never echoed", () => {
  assert.throws(
    () => proxyForUrl("https://github.com/x", { https_proxy: "socks5://proxy:1080" }),
    /unsupported proxy scheme/);
  assert.equal(
    proxyForUrl("https://github.com/x", { https_proxy: "http://user:s3cret@proxy:8080" }).password,
    "s3cret");
  assert.throws(
    () => proxyForUrl("https://github.com/x", { https_proxy: "http://user:s3cret@[bad" }),
    (e) => /not a valid URL/.test(e.message) && !/s3cret/.test(e.message));
});

test("https artifact with an unreachable proxy fails fast, nothing installed", () => {
  // Regression for the hang: a blocked direct route used to wait forever.
  stagePackage({
    cli_version: "0.0.0-test",
    release_state: "local-test",
    artifacts: {
      [platformKey()]: {
        url: "https://github.com/example/runtime.tar.gz",
        sha256: "f".repeat(64),
        format: "tar.gz",
        allowed_redirect_hosts: ["release-assets.githubusercontent.com"],
      },
    },
  });
  const started = Date.now();
  const result = runInstall({
    https_proxy: "http://127.0.0.1:1",
    HTTPS_PROXY: "http://127.0.0.1:1",
    http_proxy: "", HTTP_PROXY: "",
    npm_config_proxy: "", npm_config_https_proxy: "",
    no_proxy: "", NO_PROXY: "", npm_config_noproxy: "",
  });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /ECONNREFUSED|proxy/i);
  assert.ok(Date.now() - started < 30_000, "must fail fast instead of hanging");
  assert.ok(!fs.existsSync(path.join(pkgDir, "runtime")),
    "runtime dir must not exist after a failed download");
});

test("proxy that accepts but never answers: times out, does not hang", async () => {
  const blackhole = net.createServer(() => {}); // accepts TCP, never replies
  await new Promise((resolve) => blackhole.listen(0, "127.0.0.1", resolve));
  const proxy = `http://127.0.0.1:${blackhole.address().port}`;

  stagePackage({
    cli_version: "0.0.0-test",
    release_state: "local-test",
    artifacts: {
      [platformKey()]: {
        url: "https://artifact.invalid/runtime.tar.gz",
        sha256: "f".repeat(64),
        format: "tar.gz",
      },
    },
  });

  const child = spawn(process.execPath, [installScript()], {
    cwd: pkgDir,
    env: {
      ...process.env,
      SAP_ADT_INSTALL_ALLOW_FILE: "1",
      SAP_ADT_INSTALL_CONNECT_TIMEOUT_MS: "800",
      https_proxy: proxy, HTTPS_PROXY: proxy,
      http_proxy: "", HTTP_PROXY: "",
      npm_config_proxy: "", npm_config_https_proxy: "",
      no_proxy: "", NO_PROXY: "", npm_config_noproxy: "",
    },
  });
  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (d) => { stdout += d; });
  child.stderr.on("data", (d) => { stderr += d; });
  const code = await new Promise((resolve, reject) => {
    const guard = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new Error(`installer hung (no exit in 5 s)\nstdout: ${stdout}\nstderr: ${stderr}`));
    }, 5_000);
    child.on("exit", (exitCode) => {
      clearTimeout(guard);
      resolve(exitCode);
    });
  });
  blackhole.close();

  assert.notEqual(code, 0);
  assert.match(stdout, /using proxy 127\.0\.0\.1:\d+/);
  assert.match(stderr, /timed out after 800 ms/);
  assert.match(stderr, /HTTPS_PROXY|NO_PROXY/);
  assert.ok(!fs.existsSync(path.join(pkgDir, "runtime")));
});

test("moveTree: falls back to a copy when rename crosses filesystems (EXDEV)", () => {
  const src = path.join(work, "src");
  const dst = path.join(work, "dst");
  fs.mkdirSync(src, { recursive: true });
  fs.writeFileSync(path.join(src, "payload"), "x");

  const realRename = fs.renameSync;
  fs.renameSync = () => {
    const e = new Error("EXDEV: cross-device link not permitted");
    e.code = "EXDEV";
    throw e;
  };
  try {
    moveTree(src, dst);
  } finally {
    fs.renameSync = realRename;
  }

  assert.equal(fs.readFileSync(path.join(dst, "payload"), "utf8"), "x");
  assert.ok(!fs.existsSync(src), "staging must be removed after the copy");
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
