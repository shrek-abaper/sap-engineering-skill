# Credential configuration

Read this when `status` reports `CONFIG_MISSING`, when setting up a profile's
password, or when a user reports credential/keystore problems. See
`profiles.md` for multi-environment (profile) management.

## First-time setup

Run `status` first; on `CONFIG_MISSING`, collect all credentials in a SINGLE
question call (one array, not field-by-field — sequential calls open separate
UI tabs that can overwrite earlier answers). Fields:

1. SAP System URL — include port, e.g. `https://my-sap.example.com:8000`
2. SAP Username — dialog user, e.g. `DEVELOPER`
3. SAP Password — SAP logon password
4. SAP Client — 3 digits, e.g. `100`
5. Skip SSL check? — yes for self-signed/internal, no for production

Save non-secret fields with one command, then store the password:

```bash
python3 "$SAP_CLI" configure --profile dev \
  --url "https://my-sap-dev.example.com:8000" \
  --username "DEVELOPER" --client "100"
# add --no-verify-ssl when skipping the certificate check
python3 "$SAP_CLI" credentials set dev        # hidden prompt
```

Non-interactive alternative (avoids shell history; configure moves the value
into the keystore and removes it from config.json):

```bash
SAP_PASSWORD="mysecret" python3 "$SAP_CLI" configure --profile dev \
  --url "https://my-sap-dev.example.com:8000" \
  --username "DEVELOPER" --client "100"
```

Verify with `status`. Flagged configure failures are JSON error envelopes
(`CONFIG_MISSING` for missing fields, exit 2; `BAD_REQUEST` for an invalid
profile name, exit 1).

## Where secrets live

- Connection profile (non-secret): `~/.sap-adt-cli/config.json` (mode 0600).
- Password: the operating-system keystore only, never plain config text.
  Old single-connection / plaintext configs migrate automatically to a
  profile named `default` with the password moved into the keystore.
- Backend priority: `env` (`SAP_ADT_<PROFILE>_PASSWORD`) → `keyring`
  (Credential Manager / Keychain / Secret Service) → `dpapi` (WSL2) →
  `pass` (GPG) → `file` (scrypt + Fernet fallback with a master passphrase).
- Stored passwords are **not machine-portable** (DPAPI / Keychain binding);
  re-run `credentials set <profile>` after moving machines.
- There is no export command; `-v/--verbose` output and tracebacks stay
  redacted. Global `--keystore <name>` forces a backend fail-closed.

## Credential commands

| Command | Purpose |
|---|---|
| `credentials status` | Stored/not-stored per profile; never prints the secret |
| `credentials doctor` | Active backend, file modes, entries — run first on credential issues |
| `credentials set PROFILE [--user U] [--password P]` | Store a password (hidden prompt preferred) |
| `credentials forget PROFILE` | Purge the password from all writable keystores |

## Environment / `.env` overrides

- SKILL-local `.env` (copy `.env.example`): fill `SAP_URL`, `SAP_USERNAME`,
  `SAP_PASSWORD`, `SAP_CLIENT`; isolated per skill.
- One-off env vars (nothing written): `SAP_URL=… SAP_USERNAME=… SAP_PASSWORD=…
  SAP_CLIENT=100 python3 sap_adt_cli.py status`.
- Precedence: process env vars → SKILL-local `.env` → selected profile.
  When all four `SAP_*` are present they override profiles entirely;
  `SAP_PROFILE` only selects among profiles otherwise.
- Optional: `SAP_LANGUAGE`, `SAP_VERIFY_SSL=0`, `SAP_ALLOW_WRITE=1`,
  `SAP_ALLOW_TRANSPORT=1`. Keep both allow flags `0` unless the user
  explicitly authorizes write/transport.

## Capability flags

`--allow-write` controls `write-source`/`activate`; `--allow-transport`
controls `create-transport`/`release-transport`. Both default to disabled and
are **global** (apply to every profile — verify the active profile before any
write). Enabling a flag never bypasses the per-operation `[y/N]` confirmation.
