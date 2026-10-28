# Contributing

## Tests

The suite is plain `unittest` (no pytest required) and lives at the repository
root in `tests/`:

```bash
python3 -m unittest discover -s tests -v
```

Tests import the `sap_adt` package from `src/`: run `pip install -e .` once in
your venv (most suites also put `src/` on the path when run from the repo
root). Required packages: `click`, `requests`, `urllib3`, plus the optional
`keyring` and `cryptography` (backends are exercised through injected seams,
but the `file` backend uses the real `cryptography` package).

There is no cloud CI: hosted runners cannot reach real SAP systems, so
verification is local — `python -m unittest discover -s tests -v` and
`python tests/check_contract.py`. Run them before pushing.

## Secret scanning

`gitleaks` runs as a pre-commit hook (`.pre-commit-config.yaml`), using
`.gitleaks.toml` (built-in rules plus a hardcoded-secret rule; `tests/`,
`references/`, docs and placeholder templates such as `.env.example` are
allowlisted zones).

```bash
pre-commit install
# or run manually
gitleaks protect --staged --config .gitleaks.toml
gitleaks detect   --config .gitleaks.toml
```

Never commit real hostnames, SIDs, usernames or passwords — use the placeholders
`D01` / `Q01` / `DEVUSER` / `YOUR_PASSWORD` style strings.

## Manual WSL / DPAPI verification checklist

There is no WSL GitHub runner, so the DPAPI backend must be hand-tested after
changes to `dpapi_store.py` or the migration flow. Use a throwaway HOME and
placeholder credentials only:

```bash
TMPHOME=$(mktemp -d)
mkdir -p "$TMPHOME/.sap-adt-cli"
cat > "$TMPHOME/.sap-adt-cli/config.json" <<'JSON'
{"version":2,"active_profile":"dev","allow_write":false,"allow_transport":false,
"profiles":{"dev":{"url":"https://D01.example.com:8000","username":"DEVUSER",
"password":"PLACEHOLDER-SECRET","client":"100","language":"EN","verify_ssl":true}}}
JSON
CLI="sap-adt"

# 1. First command triggers migration: warning printed, password stripped
HOME="$TMPHOME" sap-adt profile list
! grep -q PLACEHOLDER "$TMPHOME/.sap-adt-cli/config.json"   # no plaintext left
test "$(stat -c %a "$TMPHOME/.sap-adt-cli/secrets.json")" = 600
test ! -e "$TMPHOME/.sap-adt-cli/config.json.bak"           # no backup copies

# 2. Backend selection and status/doctor output
HOME="$TMPHOME" sap-adt credentials status     # dev -> configured (dpapi)
HOME="$TMPHOME" sap-adt credentials doctor      # dpapi selected, mode 0600, fs=ext4

# 3. Idempotency: second run prints no migration warning
HOME="$TMPHOME" sap-adt status 2>&1 | grep -c "plain text" | grep -q '^0$'

# 4. Forget removes the DPAPI blob
HOME="$TMPHOME" sap-adt credentials forget dev
HOME="$TMPHOME" sap-adt credentials status | grep -q "not configured"

rm -rf "$TMPHOME"
```

Prerequisites on the WSL side: `WSL_DISTRO_NAME` set (or `/proc/version`
mentions `microsoft`), `powershell.exe` on `$PATH`. If interop is disabled,
check `[interop]` / `appendWindowsPath=true` in `/etc/wsl.conf` — `credentials
doctor` reports the same hint.

Verify the drvfs warning deliberately: point a throwaway config directory at
`/mnt/c/...` and confirm `credentials doctor` prints the chmod/ACL warning.
