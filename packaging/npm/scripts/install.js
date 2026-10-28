#!/usr/bin/env node
/* sap-adt runtime install wizard (invoked via `sap-adt install`).
 *
 * Flow: platform match -> download over HTTPS -> sha256 verify -> safe
 * extract -> atomic swap -> self-test from the absolute path. The expected
 * digest comes from the version-bound runtime-manifest.json bundled with
 * this package — never from the same endpoint as the payload.
 *
 * Hard rules:
 *  - digest mismatch, unsupported platform, download failure, or unsafe
 *    archive entries abort WITHOUT touching any existing runtime
 *  - redirects stay on HTTPS and must stay on the artifact host or an
 *    explicitly allow-listed redirect host in the manifest
 *  - extraction rejects absolute paths, ".." traversal, and symlinks
 *  - no curl|sh, no shell:true, no string-concatenated commands
 *  - the only network egress is the artifact download, through the proxy
 *    named by HTTPS_PROXY/HTTP_PROXY when the environment sets one
 *
 * Test seam: file:// artifact URLs are accepted ONLY when the environment
 * variable SAP_ADT_INSTALL_ALLOW_FILE=1 is set (local packaging tests).
 */
"use strict";

const { spawnSync } = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const http = require("node:http");
const https = require("node:https");
const net = require("node:net");
const os = require("node:os");
const path = require("node:path");
const tls = require("node:tls");
const { Transform } = require("node:stream");
const { pipeline } = require("node:stream/promises");

const PKG_DIR = path.resolve(__dirname, "..");
const MAX_REDIRECTS = 3;
// Node's core https client ignores HTTPS_PROXY before v24, so a blocked
// direct route hung this wizard forever. Both timers are inactivity-based:
// a slow but progressing download is never aborted.
const CONNECT_TIMEOUT_MS = intEnv("SAP_ADT_INSTALL_CONNECT_TIMEOUT_MS", 30_000);
const IDLE_TIMEOUT_MS = 60_000;
const PROGRESS_INTERVAL_MS = 5_000;

function intEnv(name, fallback) {
  const raw = process.env[name];
  if (!raw) return fallback;
  const value = Number(raw);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function fail(message, code = 1) {
  process.stderr.write(`[sap-adt install] ERROR: ${message}\n`);
  process.exit(code);
}

function info(message) {
  process.stdout.write(`[sap-adt install] ${message}\n`);
}

function platformKey() {
  const osMap = { linux: "linux", darwin: "darwin", win32: "windows" };
  const archMap = { x64: "x86_64", arm64: "aarch64" };
  const o = osMap[process.platform];
  const a = archMap[process.arch];
  return o && a ? `${o}-${a}` : `${process.platform}-${process.arch}`;
}

function loadManifest() {
  const file = path.join(PKG_DIR, "runtime-manifest.json");
  if (!fs.existsSync(file)) fail(`runtime-manifest.json missing in ${PKG_DIR}`, 2);
  let manifest;
  try {
    manifest = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (e) {
    fail(`runtime-manifest.json is not valid JSON: ${e.message}`, 2);
  }
  if (!manifest || typeof manifest !== "object" || !manifest.artifacts) {
    fail("runtime-manifest.json has no artifacts section", 2);
  }
  return manifest;
}

function pickArtifact(manifest, key) {
  const entry = manifest.artifacts[key];
  if (!entry) {
    const supported = Object.keys(manifest.artifacts).join(", ") || "(none)";
    fail(`unsupported platform "${key}". Supported: ${supported}`, 1);
  }
  for (const field of ["url", "sha256", "format"]) {
    if (!entry[field]) fail(`manifest entry for ${key} lacks "${field}"`, 2);
  }
  if (!/^[0-9a-f]{64}$/i.test(entry.sha256)) {
    fail(`manifest sha256 for ${key} is malformed`, 2);
  }
  return entry;
}

function firstEnv(env, names) {
  for (const name of names) {
    const value = env[name];
    if (value && value.trim()) return value.trim();
  }
  return "";
}

/* Proxy for a target URL, or null when the request should go direct.
 * Honors the usual spellings plus npm's own config variables; `env` is
 * injectable so the tests never depend on the machine's network. */
function proxyForUrl(targetUrl, env = process.env) {
  const raw = firstEnv(env, [
    "https_proxy", "HTTPS_PROXY", "npm_config_https_proxy", "npm_config_proxy",
    "http_proxy", "HTTP_PROXY",
  ]);
  if (!raw) return null;

  let proxy;
  try {
    proxy = new URL(raw.includes("://") ? raw : `http://${raw}`);
  } catch {
    throw new Error(`HTTPS_PROXY is not a valid URL (got "${raw.replace(/:[^:@/]*@/, ":***@")}")`);
  }
  // Only plain HTTP CONNECT proxies: TLS-to-the-proxy would need TLS-in-TLS,
  // and refusing loudly beats a half-working tunnel.
  if (proxy.protocol !== "http:") {
    throw new Error(`unsupported proxy scheme "${proxy.protocol}" in HTTPS_PROXY (only http:// proxies are supported)`);
  }

  const target = new URL(targetUrl);
  const noProxy = firstEnv(env, ["no_proxy", "NO_PROXY", "npm_config_noproxy"]);
  return bypassesProxy(target.hostname, target.port || "443", noProxy) ? null : proxy;
}

function bypassesProxy(hostname, port, noProxy) {
  if (!noProxy) return false;
  const host = hostname.replace(/^\[|\]$/g, "").toLowerCase();
  for (let entry of noProxy.split(",")) {
    entry = entry.trim().toLowerCase();
    if (!entry) continue;
    if (entry === "*") return true;
    // "host:port" (never "::1" — the host part must be colon-free)
    const withPort = /^([^:]+):(\d+)$/.exec(entry);
    if (withPort) {
      if (withPort[2] !== String(port)) continue;
      entry = withPort[1];
    }
    entry = entry.replace(/^\[|\]$/g, "");
    if (entry.startsWith("*.")) entry = entry.slice(1); // *.corp.com -> .corp.com
    if (entry.startsWith(".")) {
      if (host === entry.slice(1) || host.endsWith(entry)) return true;
    } else if (entry.endsWith(".*")) {
      if (host.startsWith(entry.slice(0, -1))) return true; // 10.* -> 10.
    } else if (host === entry) {
      return true;
    }
  }
  return false;
}

function fmtBytes(n) {
  const units = ["B", "KiB", "MiB", "GiB"];
  let value = n;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${unit === 0 ? value : value.toFixed(1)} ${units[unit]}`;
}

/* HTTPS through an HTTP(S) proxy: CONNECT tunnel, then TLS to the target so
 * the certificate is still verified against the real host name. */
function openTunnel(proxy, host, port) {
  return new Promise((resolve, reject) => {
    const target = net.isIP(host) === 6 ? `[${host}]` : host;
    const headers = { Host: `${target}:${port}` };
    if (proxy.username) {
      const user = decodeURIComponent(proxy.username);
      const pass = decodeURIComponent(proxy.password || "");
      headers["Proxy-Authorization"] =
        `Basic ${Buffer.from(`${user}:${pass}`).toString("base64")}`;
    }
    const req = http.request({
      host: proxy.hostname,
      port: proxy.port || 80,
      method: "CONNECT",
      path: `${target}:${port}`,
      headers,
      agent: false,
      timeout: CONNECT_TIMEOUT_MS,
    });
    req.on("connect", (res, socket) => {
      if (res.statusCode === 407) {
        socket.destroy();
        return reject(new Error(
          `proxy ${proxy.host} requires authentication (HTTP 407) — put credentials in ` +
          "HTTPS_PROXY as http://user:pass@host:port"));
      }
      if (res.statusCode < 200 || res.statusCode >= 300) {
        socket.destroy();
        return reject(new Error(
          `proxy CONNECT ${proxy.host} -> ${target}:${port} failed: HTTP ${res.statusCode}`));
      }
      const secure = tls.connect({
        socket,
        servername: net.isIP(host) ? undefined : host,
      });
      secure.setTimeout(CONNECT_TIMEOUT_MS, () => secure.destroy(new Error(
        `TLS handshake with ${target} through the proxy timed out after ${CONNECT_TIMEOUT_MS} ms`)));
      secure.once("secureConnect", () => {
        secure.setTimeout(0);
        resolve(secure);
      });
      secure.once("error", (e) => reject(new Error(
        `TLS handshake with ${target} through the proxy failed: ${e.message} ` +
        "(a TLS-intercepting proxy needs NODE_EXTRA_CA_CERTS pointing at its CA)")));
    });
    req.on("timeout", () => req.destroy(new Error(
      `proxy CONNECT to ${proxy.host} timed out after ${CONNECT_TIMEOUT_MS} ms — ` +
      "check HTTPS_PROXY/NO_PROXY and that the proxy allows CONNECT")));
    req.on("error", reject);
    req.end();
  });
}

class TunnelAgent extends https.Agent {
  constructor(proxy) {
    super({ keepAlive: false, maxSockets: 1 });
    this.proxy = proxy;
  }

  // Node's Agent contract: a 2-argument createConnection is the async form.
  createConnection(options, cb) {
    const host = options.servername || options.host;
    openTunnel(this.proxy, host, options.port || 443).then(
      (socket) => cb(null, socket),
      cb,
    );
  }
}

function timeoutHint(target, proxy) {
  const via = proxy ? ` via proxy ${proxy.host}` : "";
  const advice = proxy
    ? "check HTTPS_PROXY or add this host to NO_PROXY"
    : "if this network requires a proxy, set HTTPS_PROXY=http://host:port";
  return `timed out after ${IDLE_TIMEOUT_MS} ms connecting to ${target}${via} — ${advice}`;
}

function download(url, allowedHosts, dest, redirectsLeft) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    if (parsed.protocol === "file:") {
      if (process.env.SAP_ADT_INSTALL_ALLOW_FILE !== "1") {
        return reject(new Error(
          "file:// artifacts are refused (test-only; set SAP_ADT_INSTALL_ALLOW_FILE=1 to allow)"));
      }
      return fs.promises.copyFile(decodeURIComponent(parsed.pathname), dest)
        .then(resolve, reject);
    }
    if (parsed.protocol !== "https:") {
      return reject(new Error(`refusing non-HTTPS artifact URL: ${url}`));
    }
    if (!allowedHosts.includes(parsed.host)) {
      return reject(new Error(`artifact host not allow-listed: ${parsed.host}`));
    }
    const proxy = proxyForUrl(url);
    const options = { timeout: IDLE_TIMEOUT_MS };
    if (proxy) {
      info(`using proxy ${proxy.host} for ${parsed.host}`);
      options.agent = new TunnelAgent(proxy);
    }

    const req = https.get(url, options, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        res.resume();
        if (redirectsLeft <= 0) return reject(new Error("too many redirects"));
        let next;
        try {
          next = new URL(res.headers.location, url);
        } catch {
          return reject(new Error("invalid redirect location"));
        }
        if (next.protocol !== "https:") {
          return reject(new Error(`refusing redirect to non-HTTPS: ${next}`));
        }
        if (!allowedHosts.includes(next.host)) {
          return reject(new Error(`refusing redirect to non-allow-listed host: ${next.host}`));
        }
        return resolve(download(next.toString(), allowedHosts, dest, redirectsLeft - 1));
      }
      if (res.statusCode !== 200) {
        res.resume();
        return reject(new Error(`download failed: HTTP ${res.statusCode}`));
      }
      const total = Number(res.headers["content-length"]) || 0;
      info(`downloading ${total ? fmtBytes(total) : "artifact"}${proxy ? ` via ${proxy.host}` : ""}`);
      const started = Date.now();
      let received = 0;
      let lastReport = started;
      const counter = new Transform({
        transform(chunk, _encoding, callback) {
          received += chunk.length;
          const now = Date.now();
          if (now - lastReport >= PROGRESS_INTERVAL_MS) {
            lastReport = now;
            const pct = total ? ` (${Math.floor((received / total) * 100)}%)` : "";
            info(`downloading ${fmtBytes(received)}${total ? ` of ${fmtBytes(total)}` : ""}${pct}`);
          }
          callback(null, chunk);
        },
        flush(callback) {
          info(`downloaded ${fmtBytes(received)} in ${((Date.now() - started) / 1000).toFixed(1)} s`);
          callback();
        },
      });
      pipeline(res, counter, fs.createWriteStream(dest)).then(resolve, reject);
    });
    req.on("timeout", () => req.destroy(new Error(timeoutHint(parsed.host, proxy))));
    req.on("error", reject);
  });
}

function sha256File(file) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash("sha256");
    fs.createReadStream(file)
      .on("data", (d) => hash.update(d))
      .on("end", () => resolve(hash.digest("hex")))
      .on("error", reject);
  });
}

/* Extract with tar (bsdtar on Windows handles .zip too) via an argument
 * array — never a shell. Then walk entries rejecting traversal/symlinks. */
function extract(archive, format, destDir) {
  fs.mkdirSync(destDir, { recursive: true });
  const args = format === "zip"
    ? ["-xf", archive, "-C", destDir]
    : ["-xzf", archive, "-C", destDir];
  const result = spawnSync("tar", args, { encoding: "utf8" });
  if (result.error) throw new Error(`tar unavailable: ${result.error.message}`);
  if (result.status !== 0) throw new Error(`tar failed: ${result.stderr.trim()}`);

  for (const entry of fs.readdirSync(destDir, { recursive: true })) {
    const full = path.join(destDir, entry);
    const stat = fs.lstatSync(full);
    if (stat.isSymbolicLink()) {
      throw new Error(`archive contains a symlink (refused): ${entry}`);
    }
    const rel = path.relative(destDir, full);
    if (rel.startsWith("..") || path.isAbsolute(rel)) {
      throw new Error(`archive entry escapes target dir (refused): ${entry}`);
    }
  }
}

/* Rename, or copy when staging and target sit on different filesystems
 * (os.tmpdir() is tmpfs on many Linux/WSL setups → EXDEV). */
function moveTree(staging, target) {
  try {
    fs.renameSync(staging, target);
  } catch (e) {
    if (e.code !== "EXDEV") throw e;
    fs.cpSync(staging, target, { recursive: true });
    fs.rmSync(staging, { recursive: true, force: true });
  }
}

/* Swap runtime atomically-ish: stage -> rename old aside -> rename new in ->
 * on any failure, restore the old one and leave it working. */
function installTree(staging, runtimeDir) {
  const backup = `${runtimeDir}.old-${process.pid}`;
  let movedOld = false;
  try {
    if (fs.existsSync(runtimeDir)) {
      fs.renameSync(runtimeDir, backup);
      movedOld = true;
    }
    moveTree(staging, runtimeDir);
    if (movedOld) fs.rmSync(backup, { recursive: true, force: true });
  } catch (e) {
    fs.rmSync(runtimeDir, { recursive: true, force: true });
    if (movedOld) fs.renameSync(backup, runtimeDir);
    throw e;
  }
}

async function main() {
  const manifest = loadManifest();
  if (manifest.release_state && manifest.release_state !== "published") {
    info(`NOTE: manifest is marked "${manifest.release_state}" — this package is a pre-release candidate.`);
  }
  const key = platformKey();
  const entry = pickArtifact(manifest, key);
  const exeName = process.platform === "win32" ? "sap-adt.exe" : "sap-adt";

  info(`platform ${key}; fetching ${entry.url}`);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "sap-adt-install-"));
  try {
    const archive = path.join(tmp, `artifact.${entry.format === "zip" ? "zip" : "tar.gz"}`);
    const allowedHosts = [new URL(entry.url).host, ...(entry.allowed_redirect_hosts || [])];
    await download(entry.url, allowedHosts, archive, MAX_REDIRECTS);

    const actual = await sha256File(archive);
    if (actual.toLowerCase() !== entry.sha256.toLowerCase()) {
      fail(`sha256 mismatch: expected ${entry.sha256}, got ${actual}. Nothing was installed.`, 1);
    }
    info("sha256 verified");

    const staging = path.join(tmp, "staging");
    extract(archive, entry.format, staging);
    // The archive root is the onedir tree (sap-adt/); normalize to the
    // runtime slot: runtime/<platform>/sap-adt/... containing the exe.
    const treeRoot = fs.existsSync(path.join(staging, "sap-adt", exeName))
      ? path.join(staging, "sap-adt")
      : staging;
    if (!fs.existsSync(path.join(treeRoot, exeName))) {
      fail(`archive has no ${exeName} at its root`, 1);
    }

    const runtimeDir = path.join(PKG_DIR, "runtime", key, "sap-adt");
    fs.mkdirSync(path.dirname(runtimeDir), { recursive: true });
    installTree(treeRoot, runtimeDir);

    const bin = path.join(runtimeDir, exeName);
    const selftest = spawnSync(bin, ["--version"], { encoding: "utf8" });
    if (selftest.status !== 0) {
      fail(`self-test failed (${bin} --version exited ${selftest.status}). Restored previous runtime if any.`, 1);
    }
    info(`installed ${selftest.stdout.trim() || bin}`);
    info("next: sap-adt configure   (interactive; password goes to the OS keystore)");
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
}

if (require.main === module) {
  main().catch((e) => fail(e.message));
}

// Pure helpers only; the wizard itself stays a script.
module.exports = { moveTree, proxyForUrl };
