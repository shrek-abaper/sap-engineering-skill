"use strict";

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { installTree, npmEnvironment } = require("./install.js");
const { findNpm, childEnv, installationHint } = require("./npm.js");

function isUpdate(argv) {
  for (let i = 0; i < argv.length; i++) {
    if (["--help", "--version"].includes(argv[i])) return false;
    if (["--profile", "--keystore", "--format", "-f"].includes(argv[i])) {
      i++;
    } else if (argv[i] === "--") {
      return argv[i + 1] === "update";
    } else if (!argv[i].startsWith("-")) {
      return argv[i] === "update" && !argv.slice(i + 1).includes("--help");
    }
  }
  return false;
}

function checked(run, command, args, options) {
  const result = run(command, args, options);
  if (result.error || result.status !== 0) {
    throw new Error(`Update step failed (${result.status ?? result.error?.code ?? "could not start"}). ` +
      installationHint(result.error || result.stderr || "Inspect npm permissions/connectivity"));
  }
  return result;
}

function applyUpdate(root, npm, plan, run = spawnSync, environment = process.env) {
  const pkg = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
  if (!plan || plan.root !== root || pkg.version !== plan.current ||
      !/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(plan.target)) {
    throw new Error("Invalid update plan; nothing was changed.");
  }
  const env = childEnv(environment);
  // Stage outside the installed package: npm replaces that directory, and
  // Windows cannot replace a still-running frozen runtime.
  const staging = fs.mkdtempSync(path.join(os.tmpdir(), "sap-adt-update-"));
  let committing = false;
  try {
    const options = { env, stdio: ["inherit", 2, "pipe"], encoding: "utf8",
      maxBuffer: 1024 * 1024, timeout: 600_000, killSignal: "SIGKILL", windowsHide: true };
    checked(run, process.execPath, [npm, "install", "--prefix", staging,
      "--global=false",
      "--ignore-scripts", "--no-audit", "--no-fund", "--no-package-lock",
      "--save-exact", `sap-adt-cli@${plan.target}`], options);
    const stagedPackage = path.join(staging, "node_modules", "sap-adt-cli");
    const stagedMetadata = JSON.parse(fs.readFileSync(path.join(stagedPackage, "package.json"), "utf8"));
    if (stagedMetadata.name !== "sap-adt-cli" || stagedMetadata.version !== plan.target) {
      throw new Error("Staged npm package version mismatch; the installed package was not changed.");
    }
    checked(run, process.execPath, [path.join(stagedPackage, "scripts", "install.js")], options);
    const stagedVersion = checked(run, process.execPath,
      [path.join(stagedPackage, "scripts", "run.js"), "--version"],
      { env, encoding: "utf8", timeout: 60_000 }).stdout.trim();
    if (stagedVersion !== `sap-adt, version ${plan.target}`) {
      throw new Error("Staged runtime version mismatch; the installed package was not changed.");
    }
    // Check scope again immediately before the first change to the live install.
    const globalRoot = checked(run, process.execPath, [npm, "root", "--global"],
      { env, encoding: "utf8", timeout: 60_000 }).stdout.trim();
    if (path.resolve(globalRoot, "sap-adt-cli") !== root) {
      throw new Error("npm global root changed; the installed package was not changed.");
    }
    committing = true;
    checked(run, process.execPath, [npm, "install", "--global", "--ignore-scripts",
      "--no-audit", "--no-fund", `sap-adt-cli@${plan.target}`], options);
    const updated = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
    if (updated.name !== "sap-adt-cli" || updated.version !== plan.target) {
      throw new Error("npm did not update the expected package directory.");
    }
    installTree(path.join(stagedPackage, "runtime"), path.join(root, "runtime"));
    const actual = checked(run, process.execPath, [path.join(root, "scripts", "run.js"), "--version"],
      { env, encoding: "utf8", timeout: 60_000 }).stdout.trim();
    if (actual !== `sap-adt, version ${plan.target}`) throw new Error("Final runtime version mismatch.");
    process.stdout.write(`Updated and verified sap-adt ${plan.target}.\n`);
  } catch (error) {
    if (committing) {
      error.needsInspection = true;
      error.message += " The npm package may already have changed; repair with npm install -g " +
        `"sap-adt-cli@${plan.target}" followed by sap-adt install. No full npm rollback is guaranteed.`;
    }
    throw error;
  } finally {
    fs.rmSync(staging, { recursive: true, force: true });
  }
}

function runUpdate(root, bin, argv) {
  const npm = findNpm();
  if (!npm) throw new Error("npm-cli.js not found; repair the Node.js/npm installation.");
  const env = npmEnvironment();
  const result = spawnSync(bin, argv, {
    stdio: ["inherit", "pipe", "inherit"], encoding: "utf8", maxBuffer: 1024 * 1024,
    timeout: 120_000, killSignal: "SIGKILL", windowsHide: true,
    env: { ...env, _SAP_ADT_UPDATE_LAUNCHER: "1",
      _SAP_ADT_NPM_ROOT: root, _SAP_ADT_NPM_NODE: process.execPath, _SAP_ADT_NPM_CLI: npm },
  });
  if (result.error) throw new Error("Could not complete the runtime update check. " +
    installationHint(result.error));
  if (result.status !== 0) return result.status ?? 1;
  const response = JSON.parse(result.stdout);
  if (!Object.hasOwn(response, "update_plan")) throw new Error("Missing runtime update plan.");
  if (response.message) process.stdout.write(`${response.message}\n`);
  if (response.update_plan) applyUpdate(root, npm, response.update_plan, spawnSync, env);
  return 0;
}

module.exports = { findNpm, isUpdate, childEnv, applyUpdate, runUpdate };
