#!/usr/bin/env python3
import importlib.util
import json
import os
import subprocess
import sys

_SKILL_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def _ensure_deps():
    deps = [
        ("click",    "click>=8.1.0"),
        ("requests", "requests>=2.31.0"),
        ("urllib3",  "urllib3>=2.0.0"),
    ]
    missing = [pip_spec for mod_name, pip_spec in deps if not importlib.util.find_spec(mod_name)]
    if not missing:
        return
    print(f"[setup] Installing missing packages: {', '.join(missing)}", file=sys.stderr)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet"] + missing,
        check=True,
    )
    print("[setup] Done.", file=sys.stderr)


_ensure_deps()

sys.path.insert(0, _SKILL_SCRIPTS_DIR)

import click
from lib import config as config_module
from lib.config import (
    run_configure_wizard,
    save_config_from_flags,
    load_config,
    load_config_with_source,
    list_profiles,
    set_active_profile,
    remove_profile,
    SapConfig,
)
from lib import credentials, credentials_reports, errors, handlers, log_redaction, output
from lib.config import ConfigError, ProfileNotFoundError
from lib.keystore.base import KeyStoreError

__version__ = "1.3.0"

_KEYSTORE_CHOICES = ("env", "keyring", "dpapi", "pass", "file")


def _profile_name():
    """Best-effort active profile name for the envelope; never blocks output."""
    try:
        return load_config().profile_name
    except Exception:  # noqa: BLE001 - unconfigured/error results still print
        return None


def _argv_command() -> str:
    return next((a for a in sys.argv[1:] if not a.startswith("-")), "sap-adt-cli")


def _emit_error(decision) -> None:
    """Print the JSON error envelope on stderr and apply the tiered exit code."""
    try:
        command = click.get_current_context().info_name
    except RuntimeError:
        command = _argv_command()
    envelope = decision.to_envelope(command, _profile_name())
    click.echo(json.dumps(envelope, indent=2, ensure_ascii=False), err=True)
    raise SystemExit(decision.exit_code)


def _gate(code: str, message: str) -> None:
    _emit_error(errors.decision(code, message))


def _require_config(config):
    """Emit the CONFIG_MISSING envelope for commands that pre-check config."""
    if config is None:
        _gate(errors.CONFIG_MISSING,
              "Not configured. Run: sap-adt-cli configure")


def _load_config():
    """load_config() that turns ConfigError into the error envelope."""
    try:
        return load_config()
    except (ConfigError, ProfileNotFoundError) as e:
        _emit_error(errors.classify(e))


def _load_config_with_source():
    try:
        return load_config_with_source()
    except (ConfigError, ProfileNotFoundError) as e:
        _emit_error(errors.classify(e))


def _abort_on_error(result, stage: str = "") -> None:
    """Fail a multi-stage command (write/activate) from a classified result."""
    if result.is_error:
        code = result.error_code or errors.SERVER_ERROR
        message = f"{stage}: {result.text}" if stage else result.text
        _emit_error(errors.decision(
            code, message,
            http_status=result.http_status,
            hint=result.hint,
        ))


def _output(result) -> None:
    if result.is_error:
        code = result.error_code or errors.SERVER_ERROR
        _emit_error(errors.decision(
            code, result.text,
            http_status=result.http_status, hint=result.hint,
        ))
    command = click.get_current_context().info_name
    try:
        rendered = output.render(
            result, output.get_format(),
            command=command, profile=_profile_name(),
        )
    except output.FormatUnsupported as exc:
        _gate(errors.BAD_REQUEST, str(exc))
    click.echo(rendered)


def _require_write(config: SapConfig) -> None:
    if not config.allow_write:
        _gate(
            errors.WRITE_DISABLED,
            "Source code write is disabled. Re-run `configure` and enable "
            "write mode (answer 'y' to 'Enable source code write?'), or use "
            "the --allow-write flag during configure.",
        )


def _require_transport_write(config: SapConfig) -> None:
    if not config.allow_transport:
        _gate(
            errors.TRANSPORT_DISABLED,
            "Transport write operations are disabled. Re-run `configure` and "
            "enable transport mode (answer 'y' to 'Enable transport write "
            "operations?'), or use the --allow-transport flag during configure.",
        )


def _require_sql_write(config: dict) -> None:
    """
    Abort if SQL write operations (DML) are not permitted.

    Current policy: DML statements are ALWAYS rejected regardless of config.
    The allow_sql_write config field is reserved for future use — when the
    policy changes, replace the hardcoded False below with:
        config.get("allow_sql_write", False)
    """
    # POLICY: hardcoded False — SQL write is unconditionally disabled in this version.
    # To enable in future: replace `False` with `config.get("allow_sql_write", False)`
    allowed = False  # noqa: hardcoded policy

    if not allowed:
        _gate(
            errors.DML_REJECTED,
            "SQL write operations (INSERT/UPDATE/DELETE/MERGE/MODIFY/TRUNCATE) "
            "are not permitted. Direct DML execution via run-sql is disabled "
            "in this version.",
        )


def _stdin_is_tty() -> bool:
    return sys.stdin is not None and sys.stdin.isatty()


def _confirm_change(preview_lines: list, yes: bool = False) -> None:
    if yes:
        return
    if not _stdin_is_tty():
        _gate(
            errors.CONFIRM_REQUIRED,
            "Confirmation required but stdin is not a terminal; re-run in a "
            "terminal or pass --yes explicitly for trusted automation.",
        )
    click.echo("\u2500" * 50, err=True)
    click.echo("PREVIEW \u2014 changes to be made:", err=True)
    for line in preview_lines:
        click.echo(f"  {line}", err=True)
    click.echo("\u2500" * 50, err=True)
    answer = click.prompt(
        "Proceed with the above changes? [y/N]",
        default="N",
        err=True,
    )
    if answer.strip().lower() != "y":
        _gate(errors.USER_ABORTED, "Aborted \u2014 no changes made.")


@click.group(name="sap-adt-cli")
@click.version_option(version=__version__, prog_name="sap-adt-cli")
@click.option(
    "--profile",
    default=None,
    help="SAP environment profile to use for this single command "
         "(overrides active profile and SAP_PROFILE; see 'profile list')",
)
@click.option(
    "--keystore",
    default=None,
    type=click.Choice(_KEYSTORE_CHOICES),
    help="Force the credential backend for this command (fail-closed if it "
         "is unavailable); see 'credentials doctor'",
)
@click.option(
    "-f", "--format", "fmt",
    default=None,
    type=click.Choice(output.VALID_FORMATS),
    envvar=output.FORMAT_ENVVAR,
    help="Output format json|text|xml. Source commands default to plain "
         "text, others to a JSON envelope; xml returns the raw ADT payload. "
         "Env: SAP_ADT_FORMAT (flag wins over env).",
)
@click.option("-v", "--verbose", is_flag=True, default=False,
              help="Verbose logging (secrets stay redacted)")
def cli(profile, keystore, fmt, verbose):
    """Read and write ABAP source code and metadata from SAP systems via the ADT REST API.

    Multiple SAP environments are stored as profiles in
    ~/.sap-adt-cli/config.json. Switch persistently with 'profile use NAME'
    or per command with '--profile NAME' (SAP_PROFILE env var also supported).

    Credentials for the selected profile can additionally be overridden by
    environment variables (SAP_URL, SAP_USERNAME, SAP_PASSWORD, SAP_CLIENT)
    or the SKILL-local .env file.

    Run 'configure' on first use to save your connection settings.
    """
    log_redaction.configure_logging(verbose)
    output.set_format(fmt)
    if profile:
        config_module.set_profile_override(profile)
    if keystore:
        credentials.set_preferred(keystore)


@cli.command()
@click.option("--url",                    default=None, help="SAP system URL (e.g. https://my-sap.example.com:8000)")
@click.option("--username",               default=None, help="SAP username")
@click.option("--password",               default=None, help="SAP password (see security warning below)")
@click.option("--client",                 default=None, help="SAP client number (e.g. 100)")
@click.option("--language",               default=None, help="Language code (default: EN)")
@click.option("--no-verify-ssl",          is_flag=True, default=False, help="Disable SSL certificate verification")
@click.option("--allow-write/--no-allow-write",         default=False, help="Enable source code write (write-source, activate); GLOBAL, applies to every profile")
@click.option("--allow-transport/--no-allow-transport", default=False, help="Enable transport write operations (create-transport, release-transport); GLOBAL, applies to every profile")
@click.option("--profile", default=None, help="Profile name to create or update (default: active profile, or 'default' on first run)")
def configure(url, username, password, client, language, no_verify_ssl, allow_write, allow_transport, profile):
    """Save SAP connection credentials for one environment profile.

    The saved profile becomes the active profile. Add more environments
    with `configure --profile NAME` and switch with `profile use NAME`.

    When called with flags the credentials are saved non-interactively —
    useful for agent workflows. When called with no flags an interactive
    wizard is launched instead (recommended for human use in a terminal,
    as it avoids exposing the password in shell history).

    Security note: passing --password on the command line may expose it in
    shell history and process listings. Prefer the interactive wizard or
    the SAP_PASSWORD environment variable.
    """
    if any([url, username, password, client]):
        if password:
            click.echo(
                "Warning: passing --password on the command line may expose it in shell history "
                "and process listings. Consider using the interactive wizard (no flags) or "
                "the SAP_PASSWORD environment variable instead.",
                err=True,
            )
        # Non-interactive path: callers are agents, so failures are JSON
        # envelopes with tiered exits (never plain text). Discrimination is
        # by "any connection flag present", not TTY state.
        try:
            save_config_from_flags(
                url=url,
                username=username,
                password=password,
                client=client,
                language=language,
                verify_ssl=not no_verify_ssl,
                allow_write=allow_write,
                allow_transport=allow_transport,
                profile=profile,
            )
        except (ConfigError, ProfileNotFoundError, ValueError) as e:
            _emit_error(errors.classify(e))
    else:
        # Interactive wizard: human-in-the-loop flow keeps plain text.
        run_configure_wizard(profile=profile)


@cli.command()
def status():
    """Show the active SAP environment profile and connection configuration."""
    config, source = _load_config_with_source()
    if config is None:
        _gate(errors.CONFIG_MISSING,
              "Not configured. Run: sap-adt-cli configure "
              "(manage environments with 'profile list').")
    click.echo(f"Profile:         {config.profile_name or '(environment override)'}")
    click.echo(f"URL:             {config.url}")
    click.echo(f"Username:        {config.username}")
    click.echo(f"Client:          {config.client}")
    click.echo(f"Language:        {config.language}")
    click.echo(f"SSL:             {'verify' if config.verify_ssl else 'skip (self-signed allowed)'}")
    click.echo(f"Write mode:      {'ENABLED' if config.allow_write else 'DISABLED'} (global)")
    click.echo(f"Transport write: {'ENABLED' if config.allow_transport else 'DISABLED'} (global)")
    click.echo(f"Config source:   {source}")


@cli.group("profile")
def profile_group():
    """Manage SAP environment profiles (dev, qas, prd, ...)."""


@profile_group.command("list")
def profile_list():
    """List all configured SAP environments and show which one is active."""
    profiles = list_profiles()
    if profiles is None:
        _gate(errors.CONFIG_MISSING,
              f"Could not parse {config_module.CONFIG_FILE}. Fix or remove the file.")
    if not profiles:
        click.echo("No profiles configured. Run: sap-adt-cli configure")
        return
    allow_write, allow_transport = config_module.get_global_capabilities()
    click.echo(f"{'':1} {'NAME':<16} {'CLIENT':<7} {'USERNAME':<16} URL")
    for p in profiles:
        marker = "*" if p["active"] else " "
        click.echo(
            f"{marker} {p['name']:<16} {p['client']:<7} {p['username']:<16} {p['url']}"
        )
    active = next((p["name"] for p in profiles if p["active"]), None)
    click.echo(f"\nActive profile: {active or '(none)'}")
    click.echo(
        f"Global switches — write: {'ENABLED' if allow_write else 'DISABLED'}, "
        f"transport write: {'ENABLED' if allow_transport else 'DISABLED'}"
    )


@profile_group.command("use")
@click.argument("name")
def profile_use(name):
    """Switch the active SAP environment profile persistently."""
    try:
        set_active_profile(name)
    except ValueError as e:
        _gate(errors.PROFILE_NOT_FOUND, str(e))
    click.echo(f"Active profile is now '{name}'.")


@profile_group.command("remove")
@click.argument("name")
def profile_remove(name):
    """Delete a SAP environment profile (the active profile cannot be removed)."""
    try:
        remove_profile(name)
    except ValueError as e:
        _gate(errors.PROFILE_NOT_FOUND, str(e))
    click.echo(f"Profile '{name}' removed.")


@cli.group("credentials")
def credentials_group():
    """Manage profile passwords stored in the system keystore.

    Backends (in priority order): env, keyring, dpapi, pass, file.
    Run 'credentials doctor' to see which one is active on this machine.
    There is deliberately no 'export' command.
    """


def _find_profile_or_exit(profile_name):
    profiles = {p["name"]: p for p in (config_module.list_profiles() or [])}
    if profile_name not in profiles:
        _gate(
            errors.PROFILE_NOT_FOUND,
            f"Profile '{profile_name}' not found in {config_module.CONFIG_FILE}. "
            f"Create it first with `configure --profile {profile_name}`.",
        )
    return profiles[profile_name]


def _read_secret(profile_name, password_opt):
    if password_opt:
        click.echo(
            "Warning: --password may expose the secret in shell history and "
            "process listings. Prefer the interactive prompt or the "
            f"SAP_ADT_{profile_name.upper()}_PASSWORD environment variable.",
            err=True,
        )
        return password_opt
    env_name = f"SAP_ADT_{profile_name.upper()}_PASSWORD"
    env_value = os.getenv(env_name)
    if env_value:
        return env_value
    if sys.stdin.isatty():
        import getpass

        first = getpass.getpass("Password (input hidden): ")
        second = getpass.getpass("Confirm password: ")
        if first != second:
            _gate(errors.BAD_REQUEST, "Passwords do not match.")
        return first
    _gate(
        errors.CONFIG_MISSING,
        f"No password supplied and stdin is not a terminal. "
        f"Set {env_name} or pass --password.",
    )


@credentials_group.command("set")
@click.argument("profile_name", metavar="PROFILE")
@click.option("--user", default=None, help="SAP user (default: username stored in the profile)")
@click.option("--password", default=None, help="Password (prefer prompt or env var; see warning)")
def credentials_set(profile_name, user, password):
    """Store PROFILE's password in the selected keystore (prompted, hidden)."""
    profile = _find_profile_or_exit(profile_name)
    username = user or profile.get("username")
    if not username:
        _gate(errors.BAD_REQUEST,
              f"Profile '{profile_name}' has no username; pass --user.")
    secret = _read_secret(profile_name, password)
    try:
        backend = credentials.save(profile_name, username, secret)
    except KeyStoreError as e:
        _gate(errors.CONFIG_MISSING, str(e))
    click.echo(f"Password for profile '{profile_name}' stored in keystore '{backend}'.")


@credentials_group.command("forget")
@click.argument("profile_name", metavar="PROFILE")
def credentials_forget(profile_name):
    """Delete PROFILE's password from all writable keystores (or --keystore one)."""
    _find_profile_or_exit(profile_name)
    try:
        removed = credentials.forget(profile_name)
    except KeyStoreError as e:
        _gate(errors.CONFIG_MISSING, str(e))
    if removed:
        # delete() is idempotent: this is a purge across writable backends,
        # not a claim that every one of them held an entry.
        click.echo(f"Purged password for '{profile_name}' from: {', '.join(removed)}")
    else:
        click.echo(f"No writable keystore available to purge '{profile_name}' from.")


@credentials_group.command("status")
def credentials_status():
    """Show which profiles have a stored password — never prints the password."""
    click.echo(credentials_reports.status_text())


@credentials_group.command("doctor")
def credentials_doctor():
    """Diagnose backend availability, selected backend, files and entries."""
    click.echo(credentials_reports.doctor_text())


@cli.command("get-program")
@click.argument("program_name")
def get_program(program_name):
    """Retrieve ABAP program (report) source code.

    PROGRAM_NAME is the ABAP object name, e.g. SAPMV45A or ZMYREPORT.
    Names are case-insensitive; uppercase is recommended.
    """
    _output(handlers.get_program(program_name))


@cli.command("get-class")
@click.argument("class_name")
def get_class(class_name):
    """Retrieve ABAP class source code.

    CLASS_NAME is the class name, e.g. ZCL_MY_CLASS or CL_SALV_TABLE.
    """
    _output(handlers.get_class(class_name))


@cli.command("get-function-group")
@click.argument("function_group")
def get_function_group(function_group):
    """Retrieve ABAP function group top-include source code.

    FUNCTION_GROUP is the function group name, e.g. BAPI_SD_SALESORDER.
    Use get-function to retrieve a specific function module within the group.
    """
    _output(handlers.get_function_group(function_group))


@cli.command("get-function")
@click.argument("function_name")
@click.option("--group", required=True, help="Function group that contains the function module")
def get_function(function_name, group):
    """Retrieve ABAP function module source code.

    FUNCTION_NAME is the function module name,
    e.g. BAPI_SALESORDER_CREATEFROMDAT2.

    --group is required and must be the parent function group name,
    e.g. BAPI_SD_SALESORDER.
    """
    _output(handlers.get_function(function_name, group))


@cli.command("get-structure")
@click.argument("structure_name")
def get_structure(structure_name):
    """Retrieve ABAP DDIC structure definition.

    STRUCTURE_NAME is the dictionary structure name, e.g. VBAKKOM.
    Returns a 'fields' envelope (JSON by default; --format xml for raw ADT).
    """
    _output(handlers.get_structure(structure_name))


@cli.command("get-table")
@click.argument("table_name")
def get_table(table_name):
    """Retrieve ABAP DDIC transparent table field definitions.

    TABLE_NAME is the dictionary table name, e.g. VBAK or MARA.
    Returns a 'fields' envelope (JSON by default; --format xml for raw ADT).
    """
    _output(handlers.get_table(table_name))


@cli.command("get-package")
@click.argument("package_name")
def get_package(package_name):
    """List all objects in an ABAP package.

    PACKAGE_NAME is the development package name, e.g. ZMYPACKAGE.
    Returns an 'objects' envelope (JSON by default; source commands default to
    plain text; --format xml returns the raw ADT payload).
    """
    _output(handlers.get_package(package_name))


@cli.command("get-type-info")
@click.argument("type_name")
def get_type_info(type_name):
    """Retrieve domain or data element information from DDIC.

    TYPE_NAME is the domain or data element name, e.g. MATNR or BUKRS.
    Tries domain first; falls back to the data element only on HTTP 404.
    Returns a 'scalar' envelope; data.resolved_as is 'domain' or 'dataelement'.
    """
    _output(handlers.get_type_info(type_name))


@cli.command("get-include")
@click.argument("include_name")
def get_include(include_name):
    """Retrieve ABAP include source code.

    INCLUDE_NAME is the include program name, e.g. MV45AFZZ or LZMY_TOPINC.
    """
    _output(handlers.get_include(include_name))


@cli.command("get-interface")
@click.argument("interface_name")
def get_interface(interface_name):
    """Retrieve ABAP interface source code.

    INTERFACE_NAME is the interface name, e.g. ZIF_MY_INTERFACE or IF_SALV_MODEL.
    """
    _output(handlers.get_interface(interface_name))


@cli.command("get-transaction")
@click.argument("transaction_name")
def get_transaction(transaction_name):
    """Retrieve transaction properties (package, application component).

    TRANSACTION_NAME is the transaction code, e.g. VA01 or MM60.
    Returns a 'scalar' envelope (facets: package/application/...).
    """
    _output(handlers.get_transaction(transaction_name))


@cli.command("search-object")
@click.argument("query")
@click.option("--max-results", default=100, show_default=True, help="Maximum number of results to return")
def search_object(query, max_results):
    """Search for ABAP objects by name (supports * wildcard).

    QUERY is a name pattern, e.g. ZCL_ORDER* or BAPI_SALES*.
    Returns an 'objects' envelope (name/type/uri/package/description).

    Examples:
      search-object "ZCL_*"
      search-object "BAPI_SALESORDER*" --max-results 20
    """
    _output(handlers.search_object(query, max_results))


@cli.command("syntax-check")
@click.argument("object_type")
@click.argument("object_name")
@click.option("--group", default=None, help="Function group (required when OBJECT_TYPE is 'function')")
def syntax_check_cmd(object_type, object_name, group):
    """Check ABAP syntax — read-only, no system change.

    OBJECT_TYPE: program / class / interface / include / function
    OBJECT_NAME: SAP object name (UPPERCASE recommended)

    --group is required when OBJECT_TYPE is 'function'.

    Exits with code 0 if no errors; code 1 if errors are found or
    the request fails.
    """
    result = handlers.syntax_check(object_type, object_name, group=group)
    if result.is_error:
        _abort_on_error(result)
    command = click.get_current_context().info_name
    click.echo(output.render(
        result, output.get_format(), command=command, profile=_profile_name()
    ))
    # Exit 1 when the check found hard errors (warnings/info stay 0).
    if any((f.get("severity") == "error")
           for f in (result.data or {}).get("findings", [])):
        sys.exit(1)


@cli.command("get-cds-view")
@click.argument("name")
def get_cds_view(name):
    """Retrieve CDS View DDL source code.

    NAME is the CDS entity name, e.g. ZI_INVENTORY_POSITION.
    Use the CDS entity name — not the underlying database view name.
    """
    _output(handlers.get_cds_view(name))


@cli.command("get-type-group")
@click.argument("name")
def get_type_group(name):
    """Retrieve ABAP type group (TYPE POOL) source code.

    NAME is the type group name, e.g. ICON or SLIS.
    """
    _output(handlers.get_type_group(name))


@cli.command("write-source")
@click.argument("object_type")
@click.argument("object_name")
@click.option("--file", "source_file", required=True, help="Source file path; use - to read from stdin")
@click.option("--group",     default=None,  help="Function group (required when OBJECT_TYPE is 'function')")
@click.option("--transport", default=None,  help="Transport request number (e.g. DEVK900001); omit for auto-assign")
@click.option("--activate",  is_flag=True,  default=False, help="Activate the object after writing")
@click.option("--yes",       is_flag=True,  default=False, help="Skip confirmation prompt. Use only in trusted automation.")
def write_source_cmd(object_type, object_name, source_file, group, transport, activate, yes):
    """Write ABAP source code to SAP — requires allow_write + confirmation each time.

    OBJECT_TYPE: program / class / interface / include / function
    OBJECT_NAME: SAP object name (UPPERCASE recommended)

    Flow: lock → write (PUT) → unlock (always) → activate (optional).
    The unlock step always runs, even if the write fails.

    Requires 'allow_write' enabled in config. Run `configure` to enable.
    """
    config = _load_config()
    _require_config(config)
    _require_write(config)

    with click.open_file(source_file, "r", encoding="utf-8") as f:
        content = f.read()

    n = 4 if activate else 3
    byte_count = len(content.encode("utf-8"))
    preview = [
        "Action   : Write source code",
        f"Object   : {object_type.upper()} {object_name.upper()}",
        f"Size     : {byte_count} bytes",
        f"Transport: {transport or '(auto-assigned)'}",
        f"Activate : {'yes' if activate else 'no'}",
    ]
    _confirm_change(preview, yes=yes)

    try:
        uri = handlers.get_object_uri(object_type, object_name, group=group)
    except ValueError as e:
        _gate(errors.BAD_REQUEST, str(e))

    click.echo(f"[1/{n}] Locking {object_type.upper()} {object_name.upper()} ...", err=True, nl=False)
    lock_result = handlers.lock_object(uri)
    if lock_result.is_error:
        click.echo("  FAILED", err=True)
        _abort_on_error(lock_result, "lock")
    lock_handle = lock_result.text
    click.echo(f"  OK  (handle: {lock_handle})", err=True)

    try:
        click.echo(f"[2/{n}] Writing source ({byte_count} bytes) ...", err=True, nl=False)
        put_result = handlers.put_source(uri, content, lock_handle, transport=transport)
        if put_result.is_error:
            click.echo("  FAILED", err=True)
            _abort_on_error(put_result, "write")
        click.echo("  OK", err=True)
    finally:
        click.echo(f"[3/{n}] Unlocking ...", err=True, nl=False)
        handlers.unlock_object(uri, lock_handle)
        click.echo("  OK", err=True)

    if activate:
        click.echo(f"[4/{n}] Activating ...", err=True, nl=False)
        act_result = handlers.activate_object(object_type, object_name, group=group)
        if act_result.is_error:
            click.echo("  FAILED", err=True)
            _abort_on_error(act_result, "activate")
        click.echo("  OK", err=True)

    click.echo("Write complete.")


@cli.command("activate")
@click.argument("object_type")
@click.argument("object_name")
@click.option("--group", default=None, help="Function group (required when OBJECT_TYPE is 'function')")
@click.option("--yes",   is_flag=True, default=False, help="Skip confirmation prompt. Use only in trusted automation.")
def activate_cmd(object_type, object_name, group, yes):
    """Activate an ABAP object — requires allow_write + confirmation each time.

    OBJECT_TYPE: program / class / interface / include / function
    OBJECT_NAME: SAP object name (UPPERCASE recommended)

    Requires 'allow_write' enabled in config. Run `configure` to enable.
    """
    config = _load_config()
    _require_config(config)
    _require_write(config)
    preview = [
        "Action  : Activate object",
        f"Object  : {object_type.upper()} {object_name.upper()}",
    ]
    _confirm_change(preview, yes=yes)
    _output(handlers.activate_object(object_type, object_name, group=group))


@cli.command("where-used")
@click.argument("object_type")
@click.argument("object_name")
@click.option("--max-results", default=50, show_default=True, help="Maximum number of results to return")
@click.option("--group",       default=None, help="Function group (required when OBJECT_TYPE is 'function')")
def where_used_cmd(object_type, object_name, max_results, group):
    """List all objects that use the given ABAP object — read-only.

    OBJECT_TYPE: program / class / interface / include / function
    OBJECT_NAME: SAP object name (UPPERCASE recommended)

    Returns an 'objects' envelope; objects may carry usage_line/usage_uri.
    An empty result is ok:true with row_count:0 (exit 0).
    """
    _output(handlers.where_used(object_type, object_name, max_results=max_results, group=group))


@cli.command("run-sql")
@click.argument("sql")
@click.option("--max-rows", default=100, show_default=True, help="Maximum rows to return (max 10000)")
def run_sql_cmd(sql, max_rows):
    """Execute an Open SQL SELECT via ADT Data Preview — SELECT only.

    SQL is the Open SQL statement (must be quoted), e.g.:
      "SELECT * FROM t001 UP TO 10 ROWS"

    Supports SAP Open SQL syntax only — not Native SQL or JDBC-style syntax.
    Returns a 'rows' envelope (columns + row matrix).

    DML statements (INSERT, UPDATE, DELETE, MODIFY, TRUNCATE) are blocked.
    Detection is by first keyword, case-insensitive.
    """
    config = _load_config()
    _require_config(config)
    _SQL_WRITE_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "MERGE", "MODIFY", "TRUNCATE"}
    first_keyword = sql.strip().upper().split()[0] if sql.strip() else ""
    is_write_sql = first_keyword in _SQL_WRITE_KEYWORDS
    if is_write_sql:
        _require_sql_write(config)
    if max_rows > 10000:
        _gate(errors.BAD_REQUEST, "--max-rows cannot exceed 10000.")
    _output(handlers.run_sql(sql, max_rows))


@cli.command("list-transports")
@click.option("--user",   default=None,  help="SAP username to filter by (default: configured username)")
@click.option("--status", default="D",   show_default=True, help="Transport status: D=in development, R=released")
def list_transports_cmd(user, status):
    """List transport requests — read-only, no capability flag required.

    Returns a 'records' envelope with status/status_text per transport.
    """
    config = _load_config()
    _require_config(config)
    effective_user = user or config.username
    _output(handlers.list_transports(effective_user, status=status))


@cli.command("create-transport")
@click.option("--description", required=True, help="Transport request description")
@click.option("--category",    default="Workbench", show_default=True, help="Transport category: Workbench or Customizing")
@click.option("--yes",         is_flag=True, default=False, help="Skip confirmation prompt. Use only in trusted automation.")
def create_transport_cmd(description, category, yes):
    """Create a transport request — requires allow_transport + confirmation each time.

    Returns the new transport request number (e.g. DEVK900003).

    Requires 'allow_transport' enabled in config. Run `configure` to enable.
    """
    config = _load_config()
    _require_config(config)
    _require_transport_write(config)
    preview = [
        "Action      : Create transport request",
        f"Category    : {category}",
        f"Description : {description}",
        f"Owner       : {config.username}",
    ]
    _confirm_change(preview, yes=yes)
    _output(handlers.create_transport(description, category=category, username=config.username))


@cli.command("release-transport")
@click.argument("trkorr")
@click.option("--yes", is_flag=True, default=False, help="Skip confirmation prompt. Use only in trusted automation.")
def release_transport_cmd(trkorr, yes):
    """Release a transport request — irreversible, requires allow_transport + confirmation each time.

    TRKORR is the transport request number, e.g. DEVK900001.

    WARNING: This operation CANNOT be undone. Once released, the transport
    cannot be recalled or modified.

    Requires 'allow_transport' enabled in config. Run `configure` to enable.
    """
    config = _load_config()
    _require_config(config)
    _require_transport_write(config)
    preview = [
        "Action  : Release transport request",
        f"TRKORR  : {trkorr}",
        "WARNING : This operation CANNOT be undone.",
        "          Once released, the transport cannot be recalled or modified.",
    ]
    _confirm_change(preview, yes=yes)
    _output(handlers.release_transport(trkorr))


if __name__ == "__main__":
    cli(prog_name="sap-adt-cli")
