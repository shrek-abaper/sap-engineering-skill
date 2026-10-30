# Multiple SAP environments (profiles)

Read this when working with more than one system (DEV/QAS/PRD) or when the
user names an environment. Credential storage details are in `credentials.md`.

Profiles store one connection (URL/username/client/language/SSL) per system
in `~/.sap-adt-cli/config.json`; the per-profile password lives in the
keystore. Capabilities are profile-scoped; only write/transport support
legacy global fallbacks. Debug permission never inherits a global switch.

```bash
# Configure environments (each save activates that profile)
sap-adt configure --profile dev --url "https://sap-dev…" --username … --client 100
SAP_PASSWORD="…" sap-adt configure --profile prd --url "https://sap-prd…" --username … --client 200

profile list                 # all environments, * = active
profile use prd              # persistent switch
--profile dev <command>      # one-off override (global option, BEFORE the command)
SAP_PROFILE=qas <command>    # one-off override via env
profile remove qas           # delete (active profile is protected)
```

Profile selection order (highest first): `--profile` > `SAP_PROFILE` >
`active_profile` (`profile use`). With exactly one profile it is used even
when `active_profile` is unset.

## Per-profile environment and capability flags

Each profile section carries `environment` (`dev|qas|prd`) and its own
`allow_write`/`allow_transport`/`allow_debug` flags. `configure --environment N` and
`configure --allow-write/--allow-transport` write the **profile section**
(the preferred scope). `configure --global-allow-write/--global-allow-transport`
writes the legacy top-level fallback, used only when the profile declares
that individual flag. Effective write/transport resolution: `environment=prd` → always refused;
else profile value if declared; else legacy global.

- Environment defaults to an inference from the profile name (`prd`/`prod`
  anywhere → `prd`, loose substring match by design; `qas`/`qa` → `qas`).
  Override with `--environment`. `status` shows the resolved value and source.
- A prd profile hard-refuses all write/transport operations and debugger
  setup/controls regardless of
  any flag; the env-var path requires explicit `SAP_ENVIRONMENT` to write.
- Debug permission (CLI 1.6.1+) defaults to false, independently of writes.
  `configure --profile qas --allow-debug` updates an existing profile while
  preserving unspecified write/TLS settings; `--no-allow-debug` disables it.
  It has no global fallback. Complete env/dotenv connections instead use
  `SAP_ALLOW_DEBUG=true` and explicit `SAP_ENVIRONMENT=dev|qas`. Debugging can
  pause execution or let application code write business data even when
  source writes are disabled. Keep per-action approval and scoped cleanup.

## Agent rules

- When the user names an environment ("在 QAS 看一下 / check in PRD"), run
  `profile list` if unsure, then `profile use NAME` for a whole session in one
  system or prefix individual commands with `--profile NAME`.
- State the target profile before/after writes or debugger controls; do not
  infer authorization from a flag set on another profile or for another capability.
  When unsure, run `status` and read the `Profile:` line.
- Editing a profile with the wizard and leaving the password blank keeps the
  previously stored password.
- `.env` / the four `SAP_*` environment variables override profiles
  completely; if `status` shows `Config source: … environment …`, profile
  switching has no effect until the override is removed.
