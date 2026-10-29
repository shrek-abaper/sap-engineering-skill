"use strict";

const fs = require("node:fs");
const path = require("node:path");

function findNpm(env = process.env) {
  const candidates = [
    env.npm_execpath,
    path.join(path.dirname(process.execPath), "node_modules", "npm", "bin", "npm-cli.js"),
    path.resolve(path.dirname(process.execPath), "..", "lib", "node_modules", "npm", "bin", "npm-cli.js"),
    ...(env.PATH || env.Path || "").split(path.delimiter).flatMap((dir) => [
      path.join(dir, "npm"),
      path.join(dir, "node_modules", "npm", "bin", "npm-cli.js"),
    ]),
  ];
  for (const candidate of candidates) {
    if (!candidate) continue;
    try {
      const real = fs.realpathSync(candidate);
      if (path.basename(real) === "npm-cli.js" && fs.statSync(real).isFile()) return real;
    } catch { /* Continue with the next conventional npm location. */ }
  }
  return "";
}

function childEnv(env = process.env) {
  return Object.fromEntries(Object.entries(env).filter(([key]) =>
    !key.toUpperCase().startsWith("SAP_")));
}

function pythonFallback(platform = process.platform) {
  const python = platform === "win32" ? "py -3" : "python3";
  const venv = platform === "win32" ? ".venv-sap-adt\\Scripts\\python.exe" : ".venv-sap-adt/bin/python";
  return "Use Python >=3.10 in a separate virtual environment instead:\n" +
    `${python} -m venv .venv-sap-adt\n${venv} -m pip install "sap-adt-cli>=1.5.0,<2"`;
}

function safeMessage(value) {
  return String(value?.message || value).replace(
    /(\b[a-z][a-z0-9+.-]*:\/\/)[^\s/]*@/gi, "$1<redacted>@");
}

function installationHint(error, platform = process.platform) {
  const text = `${error?.code || ""} ${error?.message || error}`.toLowerCase();
  if (/407|proxy authentication/.test(text)) {
    return "The proxy requires authentication. Set HTTPS_PROXY with URL-encoded credentials " +
      "or configure npm's https-proxy; do not use SAP credentials.";
  }
  if (/certificate|self.signed|unable.to.verify|cert_has_expired/.test(text)) {
    return "Configure the trusted corporate CA with NODE_EXTRA_CA_CERTS, then restart this command. " +
      "Do not disable TLS verification.";
  }
  if (/enospc|edquot|no space|disk full/.test(text)) {
    return "Free space on both the temporary-file drive and the installation drive, then retry.";
  }
  if (/eacces|eperm|ebusy|access.denied|permission|being used|winerror (5|32)/.test(text)) {
    return "Close running sap-adt processes and check installation-folder permissions, " +
      "antivirus quarantine and file locks. Do not automatically elevate privileges. " +
      pythonFallback(platform);
  }
  if (/self-test|exec format|enoexec|glibc|vcruntime|dll|win32 application/.test(text)) {
    return (platform === "win32"
      ? "Check Windows architecture, missing DLLs and antivirus quarantine; close other sap-adt processes. "
      : platform === "linux"
        ? "Check CPU architecture and glibc compatibility; this runtime is not an Alpine/musl build. "
        : "Check that a native runtime was published for this macOS architecture. ") +
      pythonFallback(platform);
  }
  if (/extract|tar unavailable/.test(text)) {
    return "Check tar on PATH, free disk space and archive access. Windows requires tar.exe. " +
      "For a genuinely slow extraction, increase SAP_ADT_INSTALL_EXTRACT_TIMEOUT_MS after investigation.";
  }
  if (/unsupported platform|not published/.test(text)) return pythonFallback(platform);
  if (/sha256|unsafe|traversal|symlink/.test(text)) {
    return "Retry the matching official release; do not bypass checksums or archive safety checks.";
  }
  if (/enoent|not found/.test(text)) {
    return "Check that Node.js >=18, npm and tar are available on PATH. " + pythonFallback(platform);
  }
  if (/401|403/.test(text)) {
    return "Check npm registry authentication and corporate firewall rules; do not use SAP credentials.";
  }
  if (/404/.test(text)) {
    return "Check that this package version has a published release asset for your platform. " +
      pythonFallback(platform);
  }
  if (/timeout|timed out|etimedout|enotfound|eai_again|econn|proxy|network|429|50[234]/.test(text)) {
    return "Check DNS/firewall access to the npm registry and GitHub release CDN. " +
      "Set HTTPS_PROXY or npm's https-proxy if required, and check NO_PROXY bypass rules.";
  }
  return "Inspect this installation before retrying. Check network, free disk space and folder permissions; " +
    "SAP configuration is unchanged.";
}

module.exports = { findNpm, childEnv, pythonFallback, safeMessage, installationHint };
