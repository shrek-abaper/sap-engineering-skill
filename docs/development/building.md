# Building

All builds are local. There is no cloud CI (hosted runners cannot reach real
SAP systems); see [releasing.md](releasing.md).

## One-time environment

```bash
python3 -m venv .venv
.venv/bin/pip install -e . click requests urllib3 keyring cryptography build pyinstaller
```

Node.js ≥ 18 and npm are only needed for the npm channel; Inno Setup 6 only
for the Windows installer (on Windows).

## Steps

```bash
# 1. Python artifacts
.venv/bin/python -m build                     # -> dist/*.whl, dist/*.tar.gz

# 2. Self-contained runtime (current platform only)
.venv/bin/python tools/build_runtime.py       # -> dist/runtime/<os>-<arch>/

# 3. Portable / installer
.venv/bin/python tools/build_installer.py     # Linux: portable archive;
                                              # Windows: Inno Setup if present

# 4. npm staging + tarball
.venv/bin/python tools/build_npm.py
cd dist/npm && npm pack && cd ../..

# 5. Skill snapshots + plugin payload
.venv/bin/python tools/sync_skill_runtime_docs.py
.venv/bin/python tools/build_skills.py
.venv/bin/python tools/build_plugin.py

# 6. Release candidate (copies artifacts, writes SHA256SUMS + manifest)
.venv/bin/python tools/build_manifest.py
.venv/bin/python tools/check_release.py
```

## Verification baseline

```bash
.venv/bin/python -m unittest discover -s tests -v   # unit/contract/distribution
.venv/bin/python tests/check_contract.py            # SKILL.md vs code
node --test packaging/npm/test/install.test.js      # installer error paths
gitleaks protect --staged --config .gitleaks.toml    # pre-commit secret scan
```

## Rules

- Never mark a platform verified from the existence of a script. A target is
  verified only after a real build + install smoke on that OS/arch
  (`packaging/targets.json`).
- Builds must not install dependencies at run time, auto-upgrade, read
  secrets, or write into the CLI install directory.
