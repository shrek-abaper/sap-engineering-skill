"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const crypto = require("node:crypto");
const { spawnSync } = require("node:child_process");
const { pathToFileURL } = require("node:url");
const { isUpdate, childEnv, applyUpdate, findNpm, runUpdate } = require("../scripts/update.js");

function fixture(t) {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), "sap-adt-update-test-"));
  t.after(() => fs.rmSync(work, { recursive: true, force: true }));
  const root = path.join(work, "global", "sap-adt-cli");
  fs.mkdirSync(path.join(root, "runtime"), { recursive: true });
  fs.writeFileSync(path.join(root, "runtime", "old"), "old runtime");
  fs.writeFileSync(path.join(root, "package.json"),
    JSON.stringify({ name: "sap-adt-cli", version: "1.5.3" }));
  return { work, root, plan: { root, current: "1.5.3", target: "1.6.0" } };
}

function fakeManager(root, calls, failAt = "") {
  return (node, args, options) => {
    calls.push({ node, args, options });
    assert.equal(node, process.execPath, "never execute a .cmd shim through a shell");
    if (args.includes("--prefix")) {
      const stage = args[args.indexOf("--prefix") + 1];
      const pkg = path.join(stage, "node_modules", "sap-adt-cli");
      fs.mkdirSync(path.join(pkg, "runtime"), { recursive: true });
      fs.writeFileSync(path.join(pkg, "runtime", "new"), "verified runtime");
      fs.writeFileSync(path.join(pkg, "package.json"),
        JSON.stringify({ name: "sap-adt-cli", version: "1.6.0" }));
      assert.ok(fs.existsSync(path.join(root, "runtime", "old")));
    }
    if (args[0].endsWith("install.js")) {
      assert.ok(fs.existsSync(path.join(root, "runtime", "old")));
      if (failAt === "artifact") return { status: 1 };
    }
    if (args.includes("root")) {
      return { status: 0, stdout: failAt === "scope" ? path.dirname(root) + "-other" : path.dirname(root) };
    }
    if (args.includes("--global") && args.includes("install")) {
      if (failAt === "commit") return { status: 1 };
      fs.rmSync(path.join(root, "runtime"), { recursive: true });
      fs.writeFileSync(path.join(root, "package.json"),
        JSON.stringify({ name: "sap-adt-cli", version: "1.6.0" }));
    }
    return { status: 0, stdout: args.includes("--version")
      ? `sap-adt, version ${failAt === "version" ? "1.5.3" : "1.6.0"}\n` : "" };
  };
}

test("route only update commands, including global options and nested help", () => {
  assert.ok(isUpdate(["update", "--check"]));
  assert.ok(isUpdate(["--profile", "qas", "-f", "json", "update", "--yes"]));
  assert.ok(isUpdate(["--profile=qas", "update"]));
  assert.ok(isUpdate(["--", "update"]));
  assert.ok(!isUpdate(["get-program", "update"]));
  assert.ok(!isUpdate(["--profile", "update", "status"]));
  assert.ok(!isUpdate(["update", "--help"]));
  assert.ok(!isUpdate(["--help", "update"]));
  assert.ok(!isUpdate(["--version"]));
});

test("package-manager environment excludes SAP credentials and preserves proxy settings", () => {
  const env = childEnv({ SAP_PASSWORD: "secret", SAP_ADT_DEV_PASSWORD: "secret",
    SAP_ADT_DOTENV: "/fake", HTTPS_PROXY: "http://proxy:8080", PATH: "/bin" });
  assert.deepEqual(env, { HTTPS_PROXY: "http://proxy:8080", PATH: "/bin" });
});

test("stage, verify, then replace only the selected global installation", (t) => {
  const { root, plan } = fixture(t);
  const calls = [];
  applyUpdate(root, "/tools/npm-cli.js", plan, fakeManager(root, calls));
  assert.equal(fs.readFileSync(path.join(root, "runtime", "new"), "utf8"), "verified runtime");
  const commit = calls.findIndex((call) => call.args.includes("--global") && call.args.includes("install"));
  const stagedVerify = calls.findIndex((call) => call.args.includes("--version"));
  assert.ok(commit > stagedVerify);
  assert.ok(calls[commit].args.includes("sap-adt-cli@1.6.0"));
  for (const call of calls) {
    assert.ok(!call.options.shell);
    if (call.args.includes("install")) assert.ok(call.args.includes("--ignore-scripts"));
  }
  const staging = calls[0].args[calls[0].args.indexOf("--prefix") + 1];
  assert.ok(!fs.existsSync(staging), "temporary staging is cleaned up");
});

test("registry proxy environment is retained across every staged and commit step", (t) => {
  const { root, plan } = fixture(t);
  const calls = [];
  applyUpdate(root, "/tools/npm-cli.js", plan, fakeManager(root, calls), {
    npm_config_https_proxy: "http://proxy.example:8080",
    npm_config_noproxy: "internal.example", SAP_PASSWORD: "fake-secret",
  });
  for (const { options } of calls) {
    assert.equal(options.env.npm_config_https_proxy, "http://proxy.example:8080");
    assert.equal(options.env.npm_config_noproxy, "internal.example");
    assert.ok(!Object.hasOwn(options.env, "SAP_PASSWORD"));
  }
});

for (const failure of ["artifact", "version", "scope"]) {
  test(`preflight ${failure} failure leaves the existing package and runtime untouched`, (t) => {
    const { root, plan } = fixture(t);
    const calls = [];
    assert.throws(() => applyUpdate(root, "/tools/npm-cli.js", plan,
      fakeManager(root, calls, failure)));
    assert.equal(JSON.parse(fs.readFileSync(path.join(root, "package.json"))).version, "1.5.3");
    assert.equal(fs.readFileSync(path.join(root, "runtime", "old"), "utf8"), "old runtime");
    assert.ok(!calls.some((call) => call.args.includes("--global") && call.args.includes("install")));
    const staging = calls[0].args[calls[0].args.indexOf("--prefix") + 1];
    assert.ok(!fs.existsSync(staging));
  });
}

test("commit failure reports incomplete state and a repair command, never success", (t) => {
  const { root, plan } = fixture(t);
  assert.throws(() => applyUpdate(root, "/tools/npm-cli.js", plan,
    fakeManager(root, [], "commit")), /No full npm rollback is guaranteed/);
});

test("npm failures classify captured stderr without exposing proxy userinfo", (t) => {
  const { root, plan } = fixture(t);
  assert.throws(() => applyUpdate(root, "/tools/npm-cli.js", plan, () => ({
    status: 1, stderr: "certificate verify failed via https://user:fake-secret@proxy.example",
  })), error => /NODE_EXTRA_CA_CERTS/.test(error.message) && !/fake-secret/.test(error.message));
  assert.ok(fs.existsSync(path.join(root, "runtime", "old")));
});

test("invalid or stale plans do not invoke any update step", (t) => {
  const { root, plan } = fixture(t);
  for (const invalid of [{ ...plan, target: "--anything" }, { ...plan, root: "/other" },
    { ...plan, current: "1.4.0" }]) {
    const calls = [];
    assert.throws(() => applyUpdate(root, "/tools/npm-cli.js", invalid,
      fakeManager(root, calls)), /Invalid update plan/);
    assert.equal(calls.length, 0);
  }
});

test("locate npm-cli.js without running shell scripts", (t) => {
  const { work } = fixture(t);
  const npm = path.join(work, "npm-cli.js");
  fs.writeFileSync(npm, "// fixture");
  assert.equal(findNpm({ npm_execpath: npm, PATH: "" }), npm);
});

test("launcher consumes a read-only runtime response and propagates refusal", (t) => {
  const { root, work } = fixture(t);
  const script = path.join(work, "runtime.js");
  fs.writeFileSync(script, 'console.log(JSON.stringify({update_plan:null,message:"No update."}));');
  assert.equal(runUpdate(root, process.execPath, [script]), 0);
  fs.writeFileSync(script, "process.exit(3);");
  assert.equal(runUpdate(root, process.execPath, [script]), 3);
});

test("real npm upgrade with isolated prefix/cache and a local verified artifact", {
  skip: process.platform === "win32" ? "POSIX fake runtime; Windows orchestration is covered above" : false,
}, (t) => {
  const { work } = fixture(t);
  const npm = findNpm();
  assert.ok(npm, "npm-cli.js is required for this offline packaging test");
  const prefix = path.join(work, "prefix");
  const root = path.join(prefix, "lib", "node_modules", "sap-adt-cli");
  fs.mkdirSync(path.join(root, "runtime"), { recursive: true });
  fs.writeFileSync(path.join(root, "runtime", "old"), "old runtime");
  fs.writeFileSync(path.join(root, "package.json"),
    JSON.stringify({ name: "sap-adt-cli", version: "1.5.3" }));
  const tree = path.join(work, "tree", "sap-adt");
  fs.mkdirSync(tree, { recursive: true });
  fs.writeFileSync(path.join(tree, "sap-adt"),
    "#!/bin/sh\nprintf 'sap-adt, version 1.6.0\\n'\n", { mode: 0o755 });
  const archive = path.join(work, "runtime.tar.gz");
  const tar = spawnSync("tar", ["-czf", archive, "-C", path.dirname(tree), "sap-adt"],
    { encoding: "utf8" });
  assert.equal(tar.status, 0, tar.stderr);
  const source = path.join(work, "package");
  fs.mkdirSync(source);
  fs.cpSync(path.resolve(__dirname, "..", "scripts"), path.join(source, "scripts"), { recursive: true });
  fs.writeFileSync(path.join(source, "package.json"), JSON.stringify({
    name: "sap-adt-cli", version: "1.6.0", bin: { "sap-adt": "scripts/run.js" },
    files: ["scripts/", "runtime-manifest.json"],
  }));
  fs.writeFileSync(path.join(source, "runtime-manifest.json"), JSON.stringify({
    cli_version: "1.6.0", release_state: "local-test", artifacts: {
      [`${process.platform}-${process.arch === "x64" ? "x86_64" : "aarch64"}`]: {
        url: pathToFileURL(archive).href, format: "tar.gz",
        sha256: crypto.createHash("sha256").update(fs.readFileSync(archive)).digest("hex"),
      },
    },
  }));
  const env = { ...childEnv(), npm_config_prefix: prefix,
    npm_config_cache: path.join(work, "cache"), npm_config_registry: "http://127.0.0.1:9",
    npm_config_fetch_retries: "0", SAP_ADT_INSTALL_ALLOW_FILE: "1" };
  const packed = spawnSync(process.execPath, [npm, "pack", source, "--ignore-scripts",
    "--pack-destination", work, "--json"], { env, encoding: "utf8", timeout: 60_000 });
  assert.equal(packed.status, 0, packed.stderr);
  const tarball = path.join(work, JSON.parse(packed.stdout)[0].filename);
  const plan = { root, current: "1.5.3", target: "1.6.0" };
  applyUpdate(root, npm, plan, (node, args, options) => {
    // Replace only the registry target with our packed fixture. The real npm,
    // installer, atomic runtime handoff and version readbacks all still run.
    const localArgs = args.map((arg) => arg === "sap-adt-cli@1.6.0" ? tarball : arg);
    const result = spawnSync(node, localArgs,
      { ...options, env, stdio: "pipe", encoding: "utf8" });
    assert.equal(result.status, 0, result.stderr);
    return result;
  });
  assert.equal(JSON.parse(fs.readFileSync(path.join(root, "package.json"))).version, "1.6.0");
  assert.ok(!fs.existsSync(path.join(root, "runtime", "old")));
  const actual = spawnSync(path.join(prefix, "bin", "sap-adt"), ["--version"],
    { env, encoding: "utf8" });
  assert.equal(actual.status, 0, actual.stderr);
  assert.equal(actual.stdout.trim(), "sap-adt, version 1.6.0");
});
