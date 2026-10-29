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
 *  - the only network egress is the artifact download, through the selected
 *    environment, npm or Windows manual proxy (PAC scripts are never run)
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
const { fileURLToPath } = require("node:url");
const { findNpm, childEnv, installationHint, safeMessage } = require("./npm.js");

const PKG_DIR = path.resolve(__dirname, "..");
const MAX_REDIRECTS = 3;
// Node's core https client ignores HTTPS_PROXY before v24, so a blocked
// direct route hung this wizard forever. Connection setup has a hard deadline;
// after connecting, an idle timeout permits slow but progressing downloads.
const CONNECT_TIMEOUT_MS = intEnv("SAP_ADT_INSTALL_CONNECT_TIMEOUT_MS", 30_000);
const IDLE_TIMEOUT_MS = intEnv("SAP_ADT_INSTALL_IDLE_TIMEOUT_MS", 60_000);
const EXTRACT_TIMEOUT_MS = intEnv("SAP_ADT_INSTALL_EXTRACT_TIMEOUT_MS", 120_000);
const SELFTEST_TIMEOUT_MS = intEnv("SAP_ADT_INSTALL_SELFTEST_TIMEOUT_MS", 60_000);
const PROGRESS_INTERVAL_MS = 5_000;
const PROXY_NAMES = [
  "https_proxy", "HTTPS_PROXY", "npm_config_https_proxy", "npm_config_proxy",
  "http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY",
];
const NO_PROXY_NAMES = ["no_proxy", "NO_PROXY", "npm_config_noproxy"];
const WINDOWS_PROXY_SCRIPT = `
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$p = Get-ItemProperty -LiteralPath 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings' -ErrorAction SilentlyContinue
@{enabled=($p.ProxyEnable -eq 1);server=[string]$p.ProxyServer;bypass=[string]$p.ProxyOverride;automatic=([bool]$p.AutoConfigURL -or [bool]$p.AutoDetect)} | ConvertTo-Json -Compress
`;

function intEnv(name, fallback) {
  const raw = process.env[name];
  if (!raw) return fallback;
  const value = Number(raw);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function fail(message, code = 1) {
  process.stderr.write(`[sap-adt install] ERROR: ${safeMessage(message)}\n` +
    `Hint: ${message?.hint || installationHint(message)}\n`);
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

function resolveProxySettings(env = process.env, platform = process.platform, run = spawnSync) {
  if (firstEnv(env, PROXY_NAMES)) return { env, source: "environment" };
  const resolved = { ...env };
  const options = { env: childEnv(env), encoding: "utf8", timeout: 10_000, windowsHide: true };
  const npm = findNpm(env);
  if (npm) {
    // Read only proxy keys, never npm's full config (which can contain tokens).
    const result = run(process.execPath, [npm, "config", "get", "https-proxy", "proxy", "noproxy"], options);
    if (result.error || result.status !== 0) {
      throw new Error("Cannot read npm proxy settings within 10 seconds; set HTTPS_PROXY explicitly.");
    }
    const config = {};
    for (const line of result.stdout.split(/\r?\n/)) {
      const match = /^(https-proxy|proxy|noproxy)=(.*)$/.exec(line);
      if (match) config[match[1]] = ["null", "undefined"].includes(match[2].trim()) ? "" : match[2].trim();
    }
    if (!firstEnv(resolved, NO_PROXY_NAMES) && config.noproxy) resolved.no_proxy = config.noproxy;
    const proxy = config["https-proxy"] || config.proxy;
    if (proxy) {
      resolved.https_proxy = proxy;
      return { env: resolved, source: "npm configuration" };
    }
  }
  if (platform === "win32") {
    const powershell = path.join(env.SystemRoot || "C:\\Windows", "System32",
      "WindowsPowerShell", "v1.0", "powershell.exe");
    const result = run(powershell,
      ["-NoProfile", "-NonInteractive", "-Command", WINDOWS_PROXY_SCRIPT], options);
    if (result.error || result.status !== 0) {
      throw new Error("Cannot read Windows proxy settings within 10 seconds; set HTTPS_PROXY explicitly.");
    }
    let settings;
    try {
      settings = JSON.parse(result.stdout.replace(/^\uFEFF/, "").trim());
      if (!settings || typeof settings !== "object") throw new Error("missing settings");
    } catch {
      throw new Error("Cannot parse Windows proxy settings; set HTTPS_PROXY explicitly.");
    }
    if (settings.automatic) {
      throw new Error("Windows PAC/WPAD automatic proxy settings are not evaluated. " +
        "Set HTTPS_PROXY=http://host:port explicitly; no PAC script was downloaded or executed.");
    }
    if (settings.enabled && settings.server) {
      const server = String(settings.server).trim();
      const parts = server.split(";").map((part) => part.trim()).filter(Boolean);
      const proxy = parts.some((part) => part.includes("="))
        ? parts.find((part) => /^https\s*=/i.test(part))?.replace(/^https\s*=\s*/i, "")
        : server;
      if (!proxy) {
        throw new Error("Windows has no manual HTTPS proxy endpoint; set HTTPS_PROXY to an HTTP CONNECT proxy.");
      }
      resolved.https_proxy = proxy;
      if (!firstEnv(resolved, NO_PROXY_NAMES) && settings.bypass) {
        resolved.no_proxy = String(settings.bypass).replace(/;/g, ",");
      }
      return { env: resolved, source: "Windows user proxy settings" };
    }
  }
  return { env: resolved, source: "direct (no proxy configured)" };
}

function npmEnvironment(env = process.env, platform = process.platform, run = spawnSync) {
  const network = resolveProxySettings(env, platform, run);
  const resolved = childEnv(network.env);
  if (network.source === "Windows user proxy settings") {
    const raw = firstEnv(network.env, PROXY_NAMES);
    const proxy = raw.includes("://") ? raw : `http://${raw}`;
    resolved.npm_config_https_proxy = proxy;
    resolved.npm_config_proxy = proxy;
    resolved.npm_config_noproxy = firstEnv(network.env, NO_PROXY_NAMES);
  }
  return resolved;
}

/* Proxy for a target URL, or null when the request should go direct.
 * Honors the usual spellings plus npm's own config variables; `env` is
 * injectable so the tests never depend on the machine's network. */
function proxyForUrl(targetUrl, env = process.env) {
  const target = new URL(targetUrl);
  if (bypassesProxy(target.hostname, target.port || "443", firstEnv(env, NO_PROXY_NAMES))) return null;
  const raw = firstEnv(env, PROXY_NAMES);
  if (!raw) return null;

  let proxy;
  try {
    proxy = new URL(raw.includes("://") ? raw : `http://${raw}`);
  } catch {
    throw new Error("Proxy is not a valid URL; set HTTPS_PROXY=http://host:port and URL-encode credentials.");
  }
  // Only plain HTTP CONNECT proxies: TLS-to-the-proxy would need TLS-in-TLS,
  // and refusing loudly beats a half-working tunnel.
  if (proxy.protocol !== "http:") {
    throw new Error(`unsupported proxy scheme "${proxy.protocol}" in HTTPS_PROXY (only http:// proxies are supported)`);
  }

  return proxy;
}

function bypassesProxy(hostname, port, noProxy) {
  if (!noProxy) return false;
  const host = hostname.replace(/^\[|\]$/g, "").toLowerCase();
  for (let entry of noProxy.split(",")) {
    entry = entry.trim().toLowerCase();
    if (!entry) continue;
    if (entry === "*") return true;
    if (entry === "<local>" && !net.isIP(host) && !host.includes(".")) return true;
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
function openTunnel(proxy, host, port, signal) {
  return new Promise((resolve, reject) => {
    host = host.replace(/^\[|\]$/g, "");
    const target = net.isIP(host) === 6 ? `[${host}]` : host;
    const headers = { Host: `${target}:${port}` };
    if (proxy.username) {
      const user = decodeURIComponent(proxy.username);
      const pass = decodeURIComponent(proxy.password || "");
      headers["Proxy-Authorization"] =
        `Basic ${Buffer.from(`${user}:${pass}`).toString("base64")}`;
    }
    const req = http.request({
      host: proxy.hostname.replace(/^\[|\]$/g, ""),
      port: proxy.port || 80,
      method: "CONNECT",
      path: `${target}:${port}`,
      headers,
      agent: false,
      timeout: CONNECT_TIMEOUT_MS,
      signal,
    });
    const deadline = setTimeout(() => req.destroy(new Error(
      `proxy CONNECT to ${proxy.host} timed out after ${CONNECT_TIMEOUT_MS} ms — ` +
      "check HTTPS_PROXY/NO_PROXY and that the proxy allows CONNECT")), CONNECT_TIMEOUT_MS);
    req.on("connect", (res, socket, head) => {
      clearTimeout(deadline);
      req.setTimeout(0);
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
      if (head.length) socket.unshift(head);
      const secure = tls.connect({
        socket,
        host,
        servername: net.isIP(host) ? undefined : host,
      });
      const abort = () => secure.destroy(new Error("Proxy TLS connection cancelled."));
      signal.addEventListener("abort", abort, { once: true });
      if (signal.aborted) abort();
      const handshake = setTimeout(() => secure.destroy(new Error(
        `TLS handshake with ${target} through the proxy timed out after ${CONNECT_TIMEOUT_MS} ms`)),
      CONNECT_TIMEOUT_MS);
      const cleanup = () => {
        clearTimeout(handshake);
        signal.removeEventListener("abort", abort);
      };
      secure.once("secureConnect", () => {
        cleanup();
        resolve(secure);
      });
      secure.once("error", (e) => {
        cleanup();
        reject(new Error(`TLS handshake with ${target} through the proxy failed: ${e.message} ` +
          "(a TLS-intercepting proxy needs NODE_EXTRA_CA_CERTS pointing at its CA)"));
      });
    });
    req.on("timeout", () => req.destroy(new Error(
      `proxy CONNECT to ${proxy.host} timed out after ${CONNECT_TIMEOUT_MS} ms — ` +
      "check HTTPS_PROXY/NO_PROXY and that the proxy allows CONNECT")));
    req.on("error", (error) => {
      clearTimeout(deadline);
      reject(error);
    });
    req.end();
  });
}

class TunnelAgent extends https.Agent {
  constructor(proxy) {
    super({ keepAlive: false, maxSockets: 1 });
    this.proxy = proxy;
    this.controller = new AbortController();
  }

  // Node's Agent contract: a 2-argument createConnection is the async form.
  createConnection(options, cb) {
    const host = options.servername || options.host;
    openTunnel(this.proxy, host, options.port || 443, this.controller.signal).then(
      (socket) => cb(null, socket),
      cb,
    );
  }

  destroy() {
    this.controller.abort();
    super.destroy();
  }
}

function timeoutHint(target, proxy) {
  const via = proxy ? ` via proxy ${proxy.host}` : "";
  const advice = proxy
    ? "check HTTPS_PROXY or add this host to NO_PROXY"
    : "if this network requires a proxy, set HTTPS_PROXY=http://host:port";
  return `timed out after ${IDLE_TIMEOUT_MS} ms waiting for data from ${target}${via} — ${advice}`;
}

function download(url, allowedHosts, dest, redirectsLeft, network) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    if (parsed.protocol === "file:") {
      if (process.env.SAP_ADT_INSTALL_ALLOW_FILE !== "1") {
        return reject(new Error(
          "file:// artifacts are refused (test-only; set SAP_ADT_INSTALL_ALLOW_FILE=1 to allow)"));
      }
      return fs.promises.copyFile(fileURLToPath(parsed), dest)
        .then(resolve, reject);
    }
    if (parsed.protocol !== "https:") {
      return reject(new Error(`refusing non-HTTPS artifact URL: ${url}`));
    }
    if (!allowedHosts.includes(parsed.host)) {
      return reject(new Error(`artifact host not allow-listed: ${parsed.host}`));
    }
    const proxy = proxyForUrl(url, network.env);
    const agent = proxy ? new TunnelAgent(proxy) : new https.Agent({ keepAlive: false });
    const options = { timeout: IDLE_TIMEOUT_MS, agent };
    if (proxy) {
      info(`using proxy ${proxy.host} for ${parsed.host} (${network.source})`);
    } else {
      info(`direct connection to ${parsed.host}${firstEnv(network.env, NO_PROXY_NAMES) ? " (proxy bypass/no proxy)" : ""}`);
    }
    let deadline;
    const cleanup = () => {
      clearTimeout(deadline);
      agent.destroy();
    };
    const failDownload = (error) => {
      cleanup();
      reject(error);
    };
    const req = https.get(url, options, (res) => {
      clearTimeout(deadline);
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        res.resume();
        if (redirectsLeft <= 0) return failDownload(new Error("too many redirects"));
        let next;
        try {
          next = new URL(res.headers.location, url);
        } catch {
          return failDownload(new Error("invalid redirect location"));
        }
        if (next.protocol !== "https:") {
          return failDownload(new Error(`refusing redirect to non-HTTPS: ${next}`));
        }
        if (!allowedHosts.includes(next.host)) {
          return failDownload(new Error(`refusing redirect to non-allow-listed host: ${next.host}`));
        }
        cleanup();
        return resolve(download(next.toString(), allowedHosts, dest, redirectsLeft - 1, network));
      }
      if (res.statusCode !== 200) {
        res.resume();
        return failDownload(new Error(`download failed: HTTP ${res.statusCode}`));
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
      pipeline(res, counter, fs.createWriteStream(dest)).then(() => {
        cleanup();
        resolve();
      }, failDownload);
    });
    deadline = setTimeout(() => req.destroy(new Error(
      `connection to ${parsed.host} timed out after ${CONNECT_TIMEOUT_MS} ms` +
      `${proxy ? " through the selected proxy; check HTTPS_PROXY/NO_PROXY" : "; configure HTTPS_PROXY if a proxy is required"}`)),
    CONNECT_TIMEOUT_MS);
    req.on("socket", (socket) => {
      if (proxy) clearTimeout(deadline); // TunnelAgent hands back an established TLS socket.
      else socket.once("secureConnect", () => clearTimeout(deadline));
    });
    req.on("timeout", () => req.destroy(new Error(timeoutHint(parsed.host, proxy))));
    req.on("error", failDownload);
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
function extract(archive, format, destDir, run = spawnSync) {
  fs.mkdirSync(destDir, { recursive: true });
  const args = format === "zip"
    ? ["-xf", archive, "-C", destDir]
    : ["-xzf", archive, "-C", destDir];
  const result = run("tar", args, {
    encoding: "utf8", timeout: EXTRACT_TIMEOUT_MS, killSignal: "SIGKILL", windowsHide: true,
  });
  if (result.error?.code === "ETIMEDOUT") {
    throw new Error(`Archive extraction timed out after ${EXTRACT_TIMEOUT_MS} ms.`);
  }
  if (result.error) throw new Error(`tar unavailable: ${safeMessage(result.error)}`);
  if (result.status !== 0) {
    const error = new Error(`Archive extraction failed (exit ${result.status}).`);
    error.hint = installationHint(result.stderr || "extract");
    throw error;
  }

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

function renameRuntime(from, to) {
  for (let attempt = 0; ; attempt++) {
    try {
      return fs.renameSync(from, to);
    } catch (error) {
      // Windows scanners can retain short-lived handles after a child exits.
      if (process.platform !== "win32" || attempt >= 20 ||
          !["EACCES", "EPERM", "EBUSY"].includes(error.code)) throw error;
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 100);
    }
  }
}

/* Rename, or copy when staging and target sit on different filesystems
 * (os.tmpdir() is tmpfs on many Linux/WSL setups → EXDEV). */
function moveTree(staging, target) {
  try {
    renameRuntime(staging, target);
  } catch (e) {
    if (e.code !== "EXDEV") throw e;
    fs.cpSync(staging, target, { recursive: true });
    fs.rmSync(staging, { recursive: true, force: true });
  }
}

/* Swap runtime atomically-ish: stage -> rename old aside -> rename new in ->
 * on any failure, restore the old one and leave it working. */
function installTree(staging, runtimeDir, validate = () => {}) {
  const backup = `${runtimeDir}.old-${process.pid}-${crypto.randomBytes(6).toString("hex")}`;
  let movedOld = false;
  let replacing = false;
  try {
    if (fs.existsSync(runtimeDir)) {
      renameRuntime(runtimeDir, backup);
      movedOld = true;
    }
    replacing = true;
    moveTree(staging, runtimeDir);
    validate(runtimeDir);
  } catch (e) {
    try {
      if (replacing) fs.rmSync(runtimeDir, { recursive: true, force: true });
      if (movedOld) renameRuntime(backup, runtimeDir);
    } catch {
      e.message += movedOld
        ? ` Rollback incomplete; previous runtime backup is at ${backup}. Restore it before retrying.`
        : ` Cleanup incomplete at ${runtimeDir}; inspect it before retrying.`;
      e.hint = movedOld
        ? `Keep ${backup}. Close file handles and restore it to ${runtimeDir} before retrying.`
        : `Close file handles and inspect the incomplete runtime at ${runtimeDir} before retrying.`;
      e.needsInspection = true;
      throw e;
    }
    e.message += movedOld ? " Previous runtime restored."
      : replacing ? " Failed candidate removed; no runtime was installed."
        : " Existing installation was not replaced.";
    throw e;
  }
  if (movedOld) {
    try {
      fs.rmSync(backup, { recursive: true, force: true });
    } catch {
      process.stderr.write(`[sap-adt install] WARNING: verified runtime installed, but backup cleanup ` +
        `failed at ${backup}. Close file handles and remove that backup after verification.\n`);
    }
  }
}

function verifyRuntime(bin, run = spawnSync) {
  const result = run(bin, ["--version"], {
    encoding: "utf8", timeout: SELFTEST_TIMEOUT_MS, killSignal: "SIGKILL", windowsHide: true,
  });
  if (result.error || result.status !== 0) {
    const error = new Error(result.error?.code === "ETIMEDOUT"
      ? `Runtime self-test timed out after ${SELFTEST_TIMEOUT_MS} ms.`
      : `Runtime self-test failed (exit ${result.status ?? result.error?.code ?? "unknown"}).`);
    error.hint = installationHint({
      code: result.error?.code,
      message: `self-test ${result.stderr || ""}`,
    });
    throw error;
  }
  return result.stdout.trim();
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
    const network = new URL(entry.url).protocol === "https:"
      ? resolveProxySettings() : { env: process.env, source: "environment" };
    await download(entry.url, allowedHosts, archive, MAX_REDIRECTS, network);

    const actual = await sha256File(archive);
    if (actual.toLowerCase() !== entry.sha256.toLowerCase()) {
      throw new Error(`sha256 mismatch: expected ${entry.sha256}, got ${actual}. Nothing was installed.`);
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
      throw new Error(`archive has no ${exeName} at its root`);
    }

    const runtimeDir = path.join(PKG_DIR, "runtime", key, "sap-adt");
    fs.mkdirSync(path.dirname(runtimeDir), { recursive: true });
    let version;
    installTree(treeRoot, runtimeDir, (installed) => {
      version = verifyRuntime(path.join(installed, exeName));
    });
    info(`installed ${version || path.join(runtimeDir, exeName)}`);
    info("next: sap-adt configure   (interactive; password goes to the OS keystore)");
  } finally {
    try {
      fs.rmSync(tmp, { recursive: true, force: true });
    } catch {
      process.stderr.write(`[sap-adt install] WARNING: temporary files remain at ${tmp}; ` +
        "close file handles and clean up that directory.\n");
    }
  }
}

if (require.main === module) {
  main().catch((e) => fail(e, e.needsInspection ? 3 : 1));
}

// Helpers only; the wizard itself stays a script.
module.exports = { moveTree, installTree, extract, verifyRuntime, proxyForUrl, resolveProxySettings, npmEnvironment };
