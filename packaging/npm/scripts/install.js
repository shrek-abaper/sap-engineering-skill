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
 *
 * Test seam: file:// artifact URLs are accepted ONLY when the environment
 * variable SAP_ADT_INSTALL_ALLOW_FILE=1 is set (local packaging tests).
 */
"use strict";

const { spawnSync } = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const https = require("node:https");
const os = require("node:os");
const path = require("node:path");
const { pipeline } = require("node:stream/promises");

const PKG_DIR = path.resolve(__dirname, "..");
const MAX_REDIRECTS = 3;

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
    https.get(url, (res) => {
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
      pipeline(res, fs.createWriteStream(dest)).then(resolve, reject);
    }).on("error", reject);
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
    fs.renameSync(staging, runtimeDir);
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

main().catch((e) => fail(e.message));
