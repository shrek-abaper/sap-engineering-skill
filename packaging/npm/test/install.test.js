/* Error-path and happy-path tests for scripts/install.js.
 *
 * Fully offline: a fake runtime (shell script on POSIX, Node executable on
 * Windows) is archived with tar via argument arrays, manifests use file://
 * URLs, and every invocation sets SAP_ADT_INSTALL_ALLOW_FILE=1 except the
 * refusal test.
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
const http = require("node:http");
const https = require("node:https");
const os = require("node:os");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const SCRIPTS = path.resolve(__dirname, "..", "scripts"); // source templates
const WINDOWS = process.platform === "win32";
const TEST_VERSION = WINDOWS ? process.version : "0.0.0-test";
// Pure helpers; requiring the script does not run the wizard.
const { moveTree, installTree, proxyForUrl, resolveProxySettings, npmEnvironment } =
  require(path.join(SCRIPTS, "install.js"));
const { installationHint, safeMessage } = require(path.join(SCRIPTS, "npm.js"));
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
  const exe = path.join(tree, WINDOWS ? "sap-adt.exe" : "sap-adt");
  if (WINDOWS && !Buffer.isBuffer(payload)) {
    fs.copyFileSync(process.execPath, exe);
  } else {
    fs.writeFileSync(exe, payload ?? "#!/bin/sh\necho 'sap-adt, version 0.0.0-test'\n");
    fs.chmodSync(exe, 0o755);
  }
  const archive = path.join(dir, WINDOWS ? "runtime.zip" : "runtime.tar.gz");
  const r = spawnSync("tar", [WINDOWS ? "-acf" : "-czf", archive, "-C", path.join(dir, "tree"), "sap-adt"],
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
        format: WINDOWS ? "zip" : "tar.gz",
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
  assert.ok(bin.stdout.includes(TEST_VERSION), bin.stdout);
});

test("file:// artifact with spaces and Unicode in its path: installs", () => {
  const dir = path.join(work, "runtime space \u6d4b\u8bd5");
  fs.mkdirSync(dir);
  const encodedArtifact = path.join(dir, path.basename(artifact));
  fs.copyFileSync(artifact, encodedArtifact);
  stagePackage(manifestFor(encodedArtifact));

  const result = runInstall();
  assert.equal(result.status, 0, result.stderr);
  const bin = runBin(["--version"]);
  assert.equal(bin.status, 0, bin.stderr);
  assert.ok(bin.stdout.includes(TEST_VERSION), bin.stdout);
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
  assert.ok(bin.stdout.includes(TEST_VERSION), bin.stdout); // still the original
});

test("unsupported platform: clear refusal", () => {
  stagePackage({ cli_version: "0.0.0-test", release_state: "local-test", artifacts: {} });
  const result = runInstall();
  assert.equal(result.status, 1);
  assert.match(result.stderr, /unsupported platform/);
  assert.match(result.stderr, /Python >=3\.10/);
  const bin = runBin(["--version"]);
  assert.equal(bin.status, 2);
  assert.match(bin.stderr, /No native runtime is published/);
  assert.match(bin.stderr, /-m venv/);
});

test("failed runtime self-test restores the previous executable", () => {
  stagePackage(manifestFor(artifact));
  assert.equal(runInstall().status, 0);
  const bin = path.join(pkgDir, "runtime", platformKey(), "sap-adt", WINDOWS ? "sap-adt.exe" : "sap-adt");
  const original = sha256(bin);
  const broken = buildFakeRuntime(path.join(work, "broken"),
    Buffer.from([0x7f, 0x45, 0x4c, 0x46, 1, 0, 0, 0]));
  stagePackage(manifestFor(broken));
  const result = runInstall();
  assert.equal(result.status, 1);
  assert.match(result.stderr, /self-test failed/);
  assert.match(result.stderr, /Previous runtime restored/);
  assert.equal(sha256(bin), original);
  assert.equal(runBin(["--version"]).status, 0);
  assert.ok(!fs.readdirSync(path.dirname(path.dirname(bin))).some(name => name.includes(".old-")));
});

test("failure to move the old runtime never deletes it", () => {
  const runtime = path.join(work, "existing");
  const candidate = path.join(work, "candidate");
  fs.mkdirSync(runtime);
  fs.mkdirSync(candidate);
  fs.writeFileSync(path.join(runtime, "old"), "old");
  const rename = fs.renameSync;
  fs.renameSync = (from, to) => {
    if (from === runtime) throw Object.assign(new Error("destination busy"), { code: "EBUSY" });
    return rename(from, to);
  };
  try {
    assert.throws(() => installTree(candidate, runtime), /destination busy/);
    assert.equal(fs.readFileSync(path.join(runtime, "old"), "utf8"), "old");
    assert.ok(fs.existsSync(candidate));
  } finally {
    fs.renameSync = rename;
  }
});

test("extraction and self-test deadlines kill stalled child processes", () => {
  stagePackage(manifestFor(artifact));
  for (const helper of ["extract", "verifyRuntime"]) {
    const script = `
const {spawnSync} = require("node:child_process");
const helper = require(${JSON.stringify(installScript())})[${JSON.stringify(helper)}];
const run = (_command, _args, options) => spawnSync(process.execPath,
  ["-e", "setTimeout(() => {}, 1500)"], options);
try {
  if (${JSON.stringify(helper)} === "extract") helper("unused", "tar.gz", ${JSON.stringify(path.join(work, "extract"))}, run);
  else helper("unused", run);
} catch (error) { console.error(error.message); process.exit(1); }
`;
    const result = spawnSync(process.execPath, ["-e", script], {
      encoding: "utf8", timeout: 15_000, killSignal: "SIGKILL",
      env: { ...process.env, SAP_ADT_INSTALL_EXTRACT_TIMEOUT_MS: "120",
        SAP_ADT_INSTALL_SELFTEST_TIMEOUT_MS: "120" },
    });
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stderr, /timed out after 120 ms/);
  }
});

test("incomplete rollback retains the backup and requests manual inspection", () => {
  const runtime = path.join(work, "existing");
  const candidate = path.join(work, "candidate");
  fs.mkdirSync(runtime);
  fs.mkdirSync(candidate);
  fs.writeFileSync(path.join(runtime, "old"), "old");
  const rename = fs.renameSync;
  fs.renameSync = (from, to) => {
    if (from.includes(".old-")) throw Object.assign(new Error("locked"), { code: "EBUSY" });
    return rename(from, to);
  };
  try {
    assert.throws(() => installTree(candidate, runtime, () => { throw new Error("self-test failed"); }),
      error => error.needsInspection && /Rollback incomplete/.test(error.message));
    const backup = fs.readdirSync(work).find(name => name.startsWith("existing.old-"));
    assert.ok(backup);
    assert.equal(fs.readFileSync(path.join(work, backup, "old"), "utf8"), "old");
  } finally {
    fs.renameSync = rename;
  }
});

test("failure hints identify recovery actions without echoing proxy credentials", () => {
  for (const [detail, expected] of [
    ["HTTP 407", /URL-encoded credentials/],
    ["SELF_SIGNED_CERT_IN_CHAIN certificate", /NODE_EXTRA_CA_CERTS/],
    ["ENOSPC", /Free space/],
    ["EBUSY", /Close running/],
    ["Runtime self-test GLIBC_2.39 not found", /glibc compatibility/],
    ["getaddrinfo ENOTFOUND", /DNS/],
  ]) assert.match(installationHint(detail, "linux"), expected);
  assert.match(installationHint("runtime self-test failed", "win32"), /missing DLLs/);
  assert.match(installationHint("unsupported platform", "darwin"), /python3 -m venv/);
  assert.ok(!safeMessage("failed https://user:fake-secret@proxy.example/x").includes("fake-secret"));
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
    ["<local>", "https://intranet/x", null],
    ["<local>", "https://github.com/x", proxy],
  ];
  for (const [noProxy, target, expected] of cases) {
    const env = { https_proxy: proxy, no_proxy: noProxy };
    const got = proxyForUrl(target, env);
    assert.equal(got ? got.host : null, expected ? new URL(expected).host : null,
      `NO_PROXY=${noProxy} for ${target}`);
  }
});

test("proxy discovery: environment overrides npm and Windows without running subprocesses", () => {
  const settings = resolveProxySettings({ HTTPS_PROXY: "http://explicit:8080" }, "win32",
    () => { throw new Error("must not inspect other proxy settings"); });
  assert.equal(settings.source, "environment");
  assert.equal(proxyForUrl("https://artifact.invalid/x", settings.env).host, "explicit:8080");
  assert.equal(proxyForUrl("https://artifact.invalid/x", { ALL_PROXY: "http://mixed:7890" }).host, "mixed:7890");
});

function proxyDiscovery(npmProxy, windows, extraEnv = {}, resolver = resolveProxySettings) {
  const npm = path.join(work, "npm-cli.js");
  fs.writeFileSync(npm, "// fixture; never executed");
  return resolver({ npm_execpath: npm, ...extraEnv }, "win32",
    (_command, args, options) => {
      assert.equal(options.shell, undefined);
      assert.equal(options.timeout, 10_000);
      return { status: 0, stdout: args.includes("config")
        ? `https-proxy=${npmProxy || "null"}\nproxy=null\nnoproxy=\n`
        : JSON.stringify(windows) };
    });
}

test("Windows manual proxy is passed to npm itself without changing configuration", () => {
  const env = proxyDiscovery("", { enabled: true, server: "127.0.0.1:7890",
    bypass: "localhost;*.corp" }, { SAP_PASSWORD: "fake-secret" }, npmEnvironment);
  assert.equal(env.npm_config_https_proxy, "http://127.0.0.1:7890");
  assert.equal(env.npm_config_proxy, "http://127.0.0.1:7890");
  assert.equal(env.npm_config_noproxy, "localhost,*.corp");
  assert.ok(!Object.hasOwn(env, "SAP_PASSWORD"));
});

test("proxy discovery: persistent npm config takes priority over Windows settings", () => {
  const settings = proxyDiscovery("http://npm:8080", { enabled: true, server: "windows:7890" });
  assert.equal(settings.source, "npm configuration");
  assert.equal(proxyForUrl("https://artifact.invalid/x", settings.env).host, "npm:8080");
});

test("proxy discovery: Windows manual and per-protocol proxies with bypass rules", () => {
  for (const server of ["127.0.0.1:7890", "http=127.0.0.1:7891;https=127.0.0.1:7890"]) {
    const settings = proxyDiscovery("", { enabled: true, server, bypass: "<local>;*.corp" });
    assert.equal(settings.source, "Windows user proxy settings");
    assert.equal(proxyForUrl("https://artifact.invalid/x", settings.env).host, "127.0.0.1:7890");
    assert.equal(proxyForUrl("https://intranet/x", settings.env), null);
    assert.equal(proxyForUrl("https://api.corp/x", settings.env), null);
  }
});

test("proxy discovery: explicit NO_PROXY overrides Windows bypass settings", () => {
  const settings = proxyDiscovery("", { enabled: true, server: "127.0.0.1:7890", bypass: "*" },
    { NO_PROXY: "internal.example" });
  assert.equal(proxyForUrl("https://artifact.invalid/x", settings.env).host, "127.0.0.1:7890");
  assert.equal(proxyForUrl("https://internal.example/x", settings.env), null);
});

test("proxy discovery: PAC and unsupported Windows proxy maps fail clearly, never execute a PAC", () => {
  assert.throws(() => proxyDiscovery("", { automatic: true }), /PAC\/WPAD.*not evaluated/);
  assert.throws(() => proxyDiscovery("", { enabled: true, server: "socks=127.0.0.1:1080" }),
    /no manual HTTPS proxy endpoint/);
  const settings = proxyDiscovery("", { enabled: false, server: "stale:7890" });
  assert.equal(proxyForUrl("https://artifact.invalid/x", settings.env), null);
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

test("proxy that accepts but never answers: times out, does not hang", async (t) => {
  const blackhole = net.createServer(() => {}); // accepts TCP, never replies
  await serve(t, blackhole);
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

  const result = await installChild(networkEnv(proxy, {
    SAP_ADT_INSTALL_CONNECT_TIMEOUT_MS: "800",
  }), 5_000);
  assert.notEqual(result.status, 0);
  assert.match(result.stdout, /using proxy 127\.0\.0\.1:\d+/);
  assert.match(result.stderr, /timed out after 800 ms/);
  assert.match(result.stderr, /HTTPS_PROXY|NO_PROXY/);
  assert.ok(!fs.existsSync(path.join(pkgDir, "runtime")));
});

async function installChild(env, timeout = 45_000) {
  const child = spawn(process.execPath, [installScript()], {
    cwd: pkgDir, env: { ...process.env, ...env },
  });
  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (chunk) => { stdout += chunk; });
  child.stderr.on("data", (chunk) => { stderr += chunk; });
  return new Promise((resolve, reject) => {
    const guard = setTimeout(() => {
      child.kill();
      reject(new Error(`installer did not exit within ${timeout} ms\n${stdout}\n${stderr}`));
    }, timeout);
    child.once("error", (error) => { clearTimeout(guard); reject(error); });
    child.once("close", (status) => { clearTimeout(guard); resolve({ status, stdout, stderr }); });
  });
}

function networkEnv(proxy, extras = {}) {
  return {
    https_proxy: proxy, HTTPS_PROXY: proxy, http_proxy: "", HTTP_PROXY: "",
    all_proxy: "", ALL_PROXY: "", npm_config_proxy: "", npm_config_https_proxy: "",
    no_proxy: "", NO_PROXY: "", npm_config_noproxy: "", ...extras,
  };
}

function serve(t, server) {
  const sockets = new Set();
  server.on("connection", (socket) => {
    sockets.add(socket);
    socket.once("close", () => sockets.delete(socket));
  });
  t.after(() => {
    for (const socket of sockets) socket.destroy();
    server.close();
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
}

test("dripping CONNECT response cannot extend the connection deadline indefinitely", async (t) => {
  const proxy = net.createServer((socket) => {
    socket.write("HTTP/1.1 200 Connection established\r\nX-Slow: ");
    const drip = setInterval(() => socket.write("x"), 100);
    socket.once("close", () => clearInterval(drip));
    socket.on("error", () => {});
  });
  await serve(t, proxy);
  stagePackage(manifestFor("https://artifact.invalid/runtime.tar.gz"));
  const result = await installChild(networkEnv(`http://127.0.0.1:${proxy.address().port}`, {
    SAP_ADT_INSTALL_CONNECT_TIMEOUT_MS: "800",
  }), 5_000);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /timed out after 800 ms/);
  assert.ok(!fs.existsSync(path.join(pkgDir, "runtime")));
});

test("proxy authentication failure is explicit and preserves an existing runtime", async (t) => {
  stagePackage(manifestFor(artifact));
  assert.equal(runInstall().status, 0);
  const proxy = http.createServer();
  proxy.on("connect", (_req, socket) => socket.end("HTTP/1.1 407 Proxy Authentication Required\r\n\r\n"));
  await serve(t, proxy);
  stagePackage(manifestFor("https://artifact.invalid/runtime.tar.gz"));
  const result = await installChild(networkEnv(`http://127.0.0.1:${proxy.address().port}`));
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /HTTP 407/);
  assert.ok(runBin(["--version"]).stdout.includes(TEST_VERSION));
});

function tlsFixture(t) {
  if (process.env.SAP_ADT_TEST_TLS_DIR) return process.env.SAP_ADT_TEST_TLS_DIR;
  const dir = path.join(work, "tls");
  fs.mkdirSync(dir);
  const result = spawnSync("openssl", ["req", "-x509", "-newkey", "rsa:2048", "-nodes",
    "-keyout", path.join(dir, "key.pem"), "-out", path.join(dir, "cert.pem"),
    "-days", "1", "-subj", "/CN=localhost",
    "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"], { encoding: "utf8" });
  if (result.error?.code === "ENOENT") {
    t.skip("requires openssl or SAP_ADT_TEST_TLS_DIR containing a temporary test certificate");
    return null;
  }
  assert.equal(result.status, 0, result.stderr);
  return dir;
}

test("real verified HTTPS download through CONNECT and redirect, including proxy credentials", async (t) => {
  const dir = tlsFixture(t);
  if (!dir) return;
  const body = fs.readFileSync(artifact);
  let port;
  const target = https.createServer({
    key: fs.readFileSync(path.join(dir, "key.pem")),
    cert: fs.readFileSync(path.join(dir, "cert.pem")),
  }, (req, res) => {
    if (req.url === "/redirect") {
      res.writeHead(302, { location: `https://localhost:${port}/runtime` });
      res.end();
    } else {
      res.writeHead(200, { "content-length": body.length });
      res.end(body);
    }
  });
  await serve(t, target);
  port = target.address().port;
  const authorities = [];
  const proxy = http.createServer();
  proxy.on("connect", (req, socket, head) => {
    authorities.push(req.url);
    assert.equal(req.headers["proxy-authorization"],
      `Basic ${Buffer.from("test-user:test-proxy-password").toString("base64")}`);
    const upstream = net.connect(port, "127.0.0.1", () => {
      socket.write("HTTP/1.1 200 Connection established\r\n\r\n");
      if (head.length) upstream.write(head);
      socket.pipe(upstream).pipe(socket);
    });
    upstream.on("error", () => socket.destroy());
    socket.on("error", () => upstream.destroy());
    socket.once("close", () => upstream.destroy());
  });
  await serve(t, proxy);
  stagePackage(manifestFor(`https://127.0.0.1:${port}/redirect`, {
    allowed_redirect_hosts: [`localhost:${port}`],
  }));
  const result = await installChild(networkEnv(
    `http://test-user:test-proxy-password@127.0.0.1:${proxy.address().port}`,
    { NODE_EXTRA_CA_CERTS: path.join(dir, "cert.pem") }));
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /sha256 verified/);
  assert.match(result.stdout, /installed/);
  assert.deepEqual(authorities, [`127.0.0.1:${port}`, `localhost:${port}`]);
  assert.ok(!result.stdout.includes("test-proxy-password"));
  assert.ok(!result.stderr.includes("test-proxy-password"));
});

test("proxy accepts CONNECT but stalls TLS: connection still has a hard deadline", async (t) => {
  const proxy = http.createServer();
  proxy.on("connect", (_req, socket) => {
    socket.write("HTTP/1.1 200 Connection established\r\n\r\n");
    socket.on("data", () => {});
    socket.on("error", () => {});
  });
  await serve(t, proxy);
  stagePackage(manifestFor("https://artifact.invalid/runtime.tar.gz"));
  const result = await installChild(networkEnv(`http://127.0.0.1:${proxy.address().port}`, {
    SAP_ADT_INSTALL_CONNECT_TIMEOUT_MS: "800",
  }), 5_000);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /timed out after 800 ms/);
  assert.ok(!fs.existsSync(path.join(pkgDir, "runtime")));
});

test("proxy support does not bypass TLS certificate verification", async (t) => {
  const dir = tlsFixture(t);
  if (!dir) return;
  const target = https.createServer({
    key: fs.readFileSync(path.join(dir, "key.pem")),
    cert: fs.readFileSync(path.join(dir, "cert.pem")),
  }, (_req, res) => res.end("must not be accepted"));
  await serve(t, target);
  stagePackage(manifestFor(`https://127.0.0.1:${target.address().port}/runtime`));
  const result = await installChild(networkEnv("http://127.0.0.1:1", {
    NO_PROXY: "*", NODE_EXTRA_CA_CERTS: "", NODE_TLS_REJECT_UNAUTHORIZED: "1",
  }));
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /certificate|self.signed/i);
  assert.ok(!fs.existsSync(path.join(pkgDir, "runtime")));
});

test("HTTPS body stall triggers idle timeout without installing a partial runtime", async (t) => {
  const dir = tlsFixture(t);
  if (!dir) return;
  const target = https.createServer({
    key: fs.readFileSync(path.join(dir, "key.pem")),
    cert: fs.readFileSync(path.join(dir, "cert.pem")),
  }, (_req, res) => {
    res.writeHead(200, { "content-length": 2 });
    res.write("x");
  });
  await serve(t, target);
  stagePackage(manifestFor(`https://127.0.0.1:${target.address().port}/runtime`));
  const result = await installChild(networkEnv("http://127.0.0.1:1", {
    NO_PROXY: "*", NODE_EXTRA_CA_CERTS: path.join(dir, "cert.pem"),
    SAP_ADT_INSTALL_IDLE_TIMEOUT_MS: "800",
  }), 5_000);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /timed out after 800 ms/);
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

test("archive with traversal entry: rejected, runtime untouched",
  { skip: process.platform !== "linux" && "fixture creation requires GNU tar --transform" }, () => {
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
