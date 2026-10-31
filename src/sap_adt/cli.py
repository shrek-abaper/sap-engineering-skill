#!/usr/bin/env python3
import json
import os
import sys

import click

from sap_adt import config as config_module
from sap_adt import credentials, credentials_reports, errors, log_redaction, output, updater
from sap_adt.adt import client as adt_client
from sap_adt.adt import handlers
from sap_adt.adt import source_write
from sap_adt.config import (
    run_configure_wizard,
    save_config_from_flags,
    load_config,
    load_config_with_source,
    load_env_connection,
    list_profiles,
    set_active_profile,
    remove_profile,
    SapConfig,
)
from sap_adt.config import ConfigError, ProfileNotFoundError
from sap_adt.keystore.base import KeyStoreError
from sap_adt.transport import collector, legacy_config
from sap_adt.transport import handlers as collector_handlers
from sap_adt.version import get_version

_KEYSTORE_CHOICES = ("env", "keyring", "dpapi", "pass", "file")

_SETUP_HELP = (0, "Setup and maintenance")
_FIND_HELP = (1, "Find objects")
_SOURCE_HELP = (2, "Read and change source")
_DATA_HELP = (3, "Inspect data and types")
_DIAGNOSIS_HELP = (4, "Test and diagnose")
_HISTORY_HELP = (5, "Compare source versions")
_TRANSPORT_HELP = (6, "Transport requests")


class _HelpCommand(click.Command):
    def __init__(self, *args, help_group, help_order=0, **kwargs):
        self.help_group = help_group
        self.help_order = help_order
        super().__init__(*args, **kwargs)


class _HelpGroup(click.Group):
    def __init__(self, *args, help_group, help_order=0, **kwargs):
        self.help_group = help_group
        self.help_order = help_order
        super().__init__(*args, **kwargs)


class SapAdtGroup(click.Group):
    """Render task sections from metadata on registered commands."""

    command_class = _HelpCommand
    group_class = _HelpGroup

    def format_options(self, ctx, formatter):
        rows = [record for param in self.get_params(ctx)
                if (record := param.get_help_record(ctx)) is not None]
        if rows:
            with formatter.section("Options"):
                formatter.write_dl(
                    rows, col_max=min(30, max(10, formatter.width - 24)))
        self.format_commands(ctx, formatter)

    def format_commands(self, ctx, formatter):
        sections = {}
        for name in self.list_commands(ctx):
            command = self.get_command(ctx, name)
            if command is not None and not command.hidden:
                sections.setdefault(command.help_group, []).append(
                    (command.help_order, name, command))
        for (_, title), commands in sorted(sections.items()):
            with formatter.section(title):
                formatter.write_dl([
                    (name, command.get_short_help_str())
                    for _, name, command in sorted(commands)
                ])


def _profile_name():
    """Best-effort active profile name for the envelope; never blocks output."""
    try:
        return load_config().profile_name
    except Exception:  # noqa: BLE001 - unconfigured/error results still print
        return None


def _argv_command() -> str:
    return next((a for a in sys.argv[1:] if not a.startswith("-")), "sap-adt")


def _emit_error(decision, exit_code: int | None = None) -> None:
    """Print the JSON error envelope on stderr and apply the tiered exit code.

    ``exit_code`` overrides the tier map only for deliberate exceptions:
    the env-write safety refusal carries CONFIG_MISSING (SAP_ENVIRONMENT is
    genuinely not configured) but must act as a non-retryable refusal (3).
    """
    try:
        command = click.get_current_context().info_name
    except RuntimeError:
        command = _argv_command()
    envelope = decision.to_envelope(command, _profile_name())
    click.echo(json.dumps(envelope, indent=2, ensure_ascii=False), err=True)
    raise SystemExit(decision.exit_code if exit_code is None else exit_code)


def _gate(code: str, message: str, exit_code: int | None = None) -> None:
    _emit_error(errors.decision(code, message), exit_code)


def _require_config(config):
    """Emit the CONFIG_MISSING envelope for commands that pre-check config."""
    if config is None:
        _gate(errors.CONFIG_MISSING,
              "Not configured. Run: sap-adt configure")


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


def _production_refusal_hint(config) -> str:
    if config.environment_source == "inferred":
        return (
            f"environment 'prd' was inferred from the profile name; if this "
            f"is not a production system, set it explicitly with "
            f"`configure --profile {config.profile_name} --environment dev`."
        )
    return "the profile is explicitly marked environment=prd."


def _profile_or_env_hint(config, flag: str) -> str:
    return (
        f"Re-run `configure --profile {config.profile_name} {flag}` to enable "
        f"it on this profile, or set the legacy global switch."
    )


def _require_write(config: SapConfig) -> None:
    _require_env_write_context(config, "write")
    if config.is_production:
        _gate(
            errors.WRITE_DISABLED,
            f"Write operations are hard-refused on profile "
            f"'{config.profile_name}' (environment=prd); neither the global "
            f"nor the profile flag can override this. "
            f"{_production_refusal_hint(config)}",
        )
    if not config.allow_write:
        who = config.profile_name or "(environment variables)"
        _gate(
            errors.WRITE_DISABLED,
            f"Source code write is disabled for '{who}' (effective flag "
            f"source: {config.write_source}). {_profile_or_env_hint(config, '--allow-write')}",
        )


def _require_transport_write(config: SapConfig) -> None:
    _require_env_write_context(config, "transport")
    if config.is_production:
        _gate(
            errors.TRANSPORT_DISABLED,
            f"Transport write operations are hard-refused on profile "
            f"'{config.profile_name}' (environment=prd); neither the global "
            f"nor the profile flag can override this. "
            f"{_production_refusal_hint(config)}",
        )
    if not config.allow_transport:
        who = config.profile_name or "(environment variables)"
        _gate(
            errors.TRANSPORT_DISABLED,
            f"Transport write operations are disabled for '{who}' "
            f"(effective flag source: {config.transport_source}). "
            f"{_profile_or_env_hint(config, '--allow-transport')}",
        )


def _require_debug(config: SapConfig) -> None:
    if config.is_production:
        _gate(
            errors.DEBUG_DISABLED,
            "Debugging is hard-refused in environment=prd. "
            f"{_production_refusal_hint(config)}",
        )
    if config.allow_debug and config.from_environment and config.environment_source != "explicit":
        _gate(
            errors.CONFIG_MISSING,
            "SAP_ENVIRONMENT must be set explicitly when enabling debugging "
            "via SAP_ALLOW_DEBUG.",
            exit_code=3,
        )
    if not config.allow_debug:
        who = config.profile_name or "(environment variables)"
        _gate(
            errors.DEBUG_DISABLED,
            f"Debugging is disabled for '{who}' (source: {config.debug_source}). "
            "Enable allow_debug explicitly; allow_write does not grant debug access.",
        )


def _require_env_write_context(config, kind: str = "write") -> None:
    """Env-var/.env connections need SAP_ENVIRONMENT before any write.

    Reads are unaffected: there is no profile name to infer the environment
    from, so CI/container callers must declare the target explicitly.
    """
    if not getattr(config, "from_environment", False):
        return
    requested = (config.env_write_requested if kind == "write"
                 else config.env_transport_requested)
    if not requested:
        return
    if config.environment_source == "default":
        # Configuration is missing (SAP_ENVIRONMENT), but this is also a
        # non-retryable safety refusal: exit 3 with the CONFIG_MISSING code.
        _gate(
            errors.CONFIG_MISSING,
            "SAP_ENVIRONMENT must be set explicitly when enabling writes via "
            "environment variables (no profile context available to infer "
            "from).",
            exit_code=3,
        )
    if config.is_production:
        code = errors.WRITE_DISABLED if kind == "write" else errors.TRANSPORT_DISABLED
        _gate(code, "Writes are hard-refused when SAP_ENVIRONMENT=prd.")


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


@click.group(name="sap-adt", cls=SapAdtGroup)
@click.version_option(version=get_version(), prog_name="sap-adt")
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
    """Read, check and change ABAP objects in SAP.

    SAP source and transport writes require capabilities and confirmation.
    Debugger controls require separate allow_debug permission. Unit tests
    and debugger controls can execute application code.

    Start with 'configure', then 'status'. Use '--profile NAME' for one
    command or 'profile use NAME' to switch persistently.

    Run 'COMMAND --help' for parameters, output formats and safety details.
    See 'configure --help' for connection and credential resolution.
    """
    log_redaction.configure_logging(verbose)
    output.set_format(fmt)
    if profile:
        config_module.set_profile_override(profile)
    if keystore:
        credentials.set_preferred(keystore)


@cli.command("update", help_group=_SETUP_HELP, help_order=60,
             short_help="[LOCAL UPDATE] Check or upgrade this CLI.")
@click.option("--check", "check_only", is_flag=True, help="Check versions without modifying anything.")
@click.option("--major", is_flag=True, help="Explicitly allow a newer major stable release.")
@click.option("--yes", is_flag=True, help="Confirm this update for non-interactive use.")
def update_cmd(check_only, major, yes):
    """Check for or install a stable CLI update using the original install channel.

    Defaults to the current major version. No SAP connection or credentials
    are needed. Source, local npm, npx and standalone installs get guidance
    instead of an unsafe in-place replacement.
    """
    launcher = os.environ.get("_SAP_ADT_UPDATE_LAUNCHER") == "1"
    try:
        report = updater.check_update(major=major)
        summary = (
            f"Channel: {report['channel']}\n"
            f"Current: {report['current']}\nTarget: {report['target']}\n"
            + ("Update available." if report["update_available"] else "No newer stable release.")
        )
        if report["guidance"]:
            summary += f"\n{report['guidance']}"
        if check_only or not report["update_available"]:
            if launcher:
                click.echo(json.dumps({"update_plan": None, "message": summary}))
            else:
                click.echo(summary)
            return
        click.echo(summary, err=launcher)
        commands = updater.update_commands(report)
        if report["channel"] == "npm-global" and not launcher:
            raise updater.UpdateError(
                errors.CONFIRM_REQUIRED, "Run update through the npm sap-adt launcher, "
                "not the inner runtime; it must exit before files can be replaced.",
            )
        if commands:
            for command in commands:
                click.echo(f"Command: {json.dumps(command)}", err=launcher)
        else:
            click.echo("Stage and verify the npm runtime, then update this global package.",
                       err=True)
        if not yes:
            if not sys.stdin.isatty():
                raise updater.UpdateError(
                    errors.CONFIRM_REQUIRED,
                    "Run update in a terminal or pass --yes explicitly; nothing was changed.",
                )
            if not click.confirm("Update this CLI installation?", default=False, err=True):
                raise updater.UpdateError(errors.USER_ABORTED, "Update cancelled; nothing was changed.")
        if report["channel"] == "npm-global":
            click.echo(json.dumps({"update_plan": {
                "target": report["target"], "current": report["current"],
                "root": report["installation"].root,
            }}))
            return
        updater.apply_python_update(report, commands)
        click.echo(f"Updated and verified sap-adt {report['target']}.")
    except updater.UpdateError as exc:
        # In particular, do not call _profile_name(): maintenance must not read
        # or migrate SAP configuration just to render an error.
        click.echo(json.dumps(errors.decision(
            exc.code, str(exc), hint=exc.hint or
            "Use the original install channel; no SAP configuration is needed."
        ).to_envelope("update"), ensure_ascii=False), err=True)
        raise SystemExit(errors.exit_code_for(exc.code))


@cli.command(help_group=_SETUP_HELP, help_order=10,
             short_help="Configure a connection profile.")
@click.option("--url",                    default=None, help="SAP system URL (e.g. https://my-sap.example.com:8000)")
@click.option("--username",               default=None, help="SAP username")
@click.option("--password",               default=None, help="SAP password (see security warning below)")
@click.option("--client",                 default=None, help="SAP client number (e.g. 100)")
@click.option("--language",               default=None, help="Language code (default: EN)")
@click.option("--no-verify-ssl",          is_flag=True, default=False, help="Disable SSL certificate verification")
@click.option("--allow-write/--no-allow-write",         default=False, help="Enable source code write for THIS profile (preferred)")
@click.option("--allow-transport/--no-allow-transport", default=False, help="Enable transport writes for THIS profile (preferred)")
@click.option("--allow-debug/--no-allow-debug", default=None,
              help="Enable debugger for THIS profile only (default: disabled; "
                   "independent of writes). Can pause/run ABAP; PRD is refused.")
@click.option("--global-allow-write/--no-global-allow-write", default=None,
              help="Write the LEGACY global fallback switch (applies only when the profile declares neither)")
@click.option("--global-allow-transport/--no-global-allow-transport", default=None,
              help="Write the LEGACY global transport fallback switch")
@click.option("--environment", default=None,
              type=click.Choice(["dev", "qas", "prd"]),
              help="Logical environment (default: inferred from profile name; prd hard-refuses writes and debugging)")
@click.option("--profile", default=None, help="Profile name to create or update (default: active profile, or 'default' on first run)")
def configure(url, username, password, client, language, no_verify_ssl,
              allow_write, allow_transport, global_allow_write,
              global_allow_transport, environment, profile, allow_debug):
    """Save SAP connection credentials for one environment profile.

    The saved profile becomes the active profile. Add more environments
    with `configure --profile NAME` and switch with `profile use NAME`.

    Profiles are stored in ~/.sap-adt-cli/config.json; passwords are stored
    in the OS keystore. SAP_PROFILE also selects a profile per command.

    Credential resolution (highest priority first):
      1. Process environment variables (SAP_URL, SAP_USERNAME,
         SAP_PASSWORD, SAP_CLIENT)
      2. Dotenv file declared by SAP_ADT_DOTENV (explicit path)
      3. Profile in ~/.sap-adt-cli/config.json + OS keystore

    A complete env/dotenv set overrides profiles entirely (all four required
    keys or none). The CLI never scans the current directory or a skill
    folder for .env files.

    When called with flags the credentials are saved non-interactively —
    useful for agent workflows. When called with no flags an interactive
    wizard is launched instead (recommended for human use in a terminal,
    as it avoids exposing the password in shell history).

    Security note: passing --password on the command line may expose it in
    shell history and process listings. Prefer the interactive wizard or
    the SAP_PASSWORD environment variable.

    Debugging defaults to disabled and does not inherit allow_write,
    allow_transport or legacy global switches. For an existing profile,
    'configure --profile NAME --allow-debug' changes only that capability;
    '--no-allow-debug' disables it. Unspecified write/TLS settings are kept.
    Complete env/dotenv connections use SAP_ALLOW_DEBUG and an explicit
    SAP_ENVIRONMENT instead. Debugging may pause execution or let application
    code write business data even when source writes remain disabled.
    """
    if any([url, username, password, client]) or allow_debug is not None:
        if password:
            click.echo(
                "Warning: passing --password on the command line may expose it in shell history "
                "and process listings. Consider using the interactive wizard (no flags) or "
                "the SAP_PASSWORD environment variable instead.",
                err=True,
            )
        # Non-interactive path: callers are agents, so failures are JSON
        # envelopes with tiered exits (never plain text). Discrimination is
        # by explicit connection/debug flags, not TTY state.
        try:
            verify_ssl = not no_verify_ssl
            if allow_debug is not None:
                context = click.get_current_context()
                profile = profile or context.find_root().params.get("profile")
                if context.get_parameter_source("allow_write") == click.core.ParameterSource.DEFAULT:
                    allow_write = None
                if context.get_parameter_source("allow_transport") == click.core.ParameterSource.DEFAULT:
                    allow_transport = None
                if context.get_parameter_source("no_verify_ssl") == click.core.ParameterSource.DEFAULT:
                    verify_ssl = None
            # Profile-scoped is the default; --allow-write/--allow-transport
            # write the profile section, the --global-* legacy flags the
            # top-level fallback. Setting neither leaves existing values.
            save_config_from_flags(
                url=url,
                username=username,
                password=password,
                client=client,
                language=language,
                verify_ssl=verify_ssl,
                allow_write=allow_write,
                allow_transport=allow_transport,
                profile=profile,
                environment=environment,
                profile_scope=True,
                global_write=global_allow_write,
                global_transport=global_allow_transport,
                allow_debug=allow_debug,
            )
        except (ConfigError, ProfileNotFoundError, ValueError) as e:
            _emit_error(errors.classify(e))
    else:
        # Interactive wizard: human-in-the-loop flow keeps plain text.
        run_configure_wizard(profile=profile)


@cli.command(help_group=_SETUP_HELP, help_order=40,
             short_help="Show local connection settings.")
def status():
    """Show the active SAP environment profile and connection configuration."""
    config, source = _load_config_with_source()
    if config is None:
        _gate(errors.CONFIG_MISSING,
              "Not configured. Run: sap-adt configure "
              "(manage environments with 'profile list').")
    click.echo(f"Profile:         {config.profile_name or '(environment override)'}")
    click.echo(f"URL:             {config.url}")
    click.echo(f"Username:        {config.username}")
    click.echo(f"Client:          {config.client}")
    click.echo(f"Language:        {config.language}")
    click.echo(f"SSL:             {'verify' if config.verify_ssl else 'skip (self-signed allowed)'}")
    env_note = {
        "inferred": " (inferred from profile name)",
        "explicit": " (explicit)",
        "default": "",
    }.get(config.environment_source, "")
    click.echo(f"Environment:     {config.environment}{env_note}")
    legacy = " (legacy fallback)" if config.write_source == "global" else ""
    legacy_t = " (legacy fallback)" if config.transport_source == "global" else ""
    refused = config.write_source == "hard-refused"
    refused_t = config.transport_source == "hard-refused"
    click.echo(
        "Write mode:      "
        + ("HARD-REFUSED (environment=prd)" if refused
           else f"{'ENABLED' if config.allow_write else 'DISABLED'} (source: {config.write_source}{legacy})")
    )
    click.echo(
        "Transport write: "
        + ("HARD-REFUSED (environment=prd)" if refused_t
           else f"{'ENABLED' if config.allow_transport else 'DISABLED'} (source: {config.transport_source}{legacy_t})")
    )
    click.echo(
        "Debug mode:      "
        + ("HARD-REFUSED (environment=prd)" if config.debug_source == "hard-refused"
           else f"{'ENABLED' if config.allow_debug else 'DISABLED'} (source: {config.debug_source})")
    )
    click.echo(f"Config source:   {source}")


@cli.group("profile", help_group=_SETUP_HELP, help_order=20,
           short_help="List, switch or remove profiles.")
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
        click.echo("No profiles configured. Run: sap-adt configure")
        return
    allow_write, allow_transport = config_module.get_global_capabilities()
    click.echo(f"{'':1} {'NAME':<16} {'ENV':<5} {'CLIENT':<7} {'USERNAME':<16} URL")
    for p in profiles:
        marker = "*" if p["active"] else " "
        click.echo(
            f"{marker} {p['name']:<16} {p['environment']:<5} {p['client']:<7} {p['username']:<16} {p['url']}"
        )
    active = next((p["name"] for p in profiles if p["active"]), None)
    click.echo(f"\nActive profile: {active or '(none)'}")
    click.echo(
        f"Legacy global fallback switches — write: {'ENABLED' if allow_write else 'DISABLED'}, "
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


@cli.group("credentials", help_group=_SETUP_HELP, help_order=30,
           short_help="Store and diagnose profile passwords.")
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
@click.option("--coverage", is_flag=True, default=False,
              help="Instead of the keystore report, show command coverage for the "
                   "connected ADT system (from its discovery document).")
def credentials_doctor(coverage):
    """Diagnose backend availability; --coverage adds the ADT resource matrix."""
    if coverage:
        result = handlers.coverage()
        if result.is_error:
            _abort_on_error(result)
        if output.get_format() == "json":
            click.echo(json.dumps(result.data, indent=2, ensure_ascii=False))
        else:
            click.echo(result.text)
        return
    click.echo(credentials_reports.doctor_text())


@cli.command("run-unit-test", help_group=_DIAGNOSIS_HELP, help_order=30,
             short_help="[RUNS ABAP] Unit tests; harmless by default.")
@click.argument("object_name")
@click.option("--type", "object_type", default="class",
              type=click.Choice(["program", "class", "interface", "include", "function"]),
              help="Object type containing the tests (default: class)")
@click.option("--group", default=None, help="Function group (required for --type function)")
@click.option("--risk-level", default="harmless",
              type=click.Choice(["harmless", "dangerous", "critical"]),
              help="harmless is default and read-only; dangerous/critical may modify data and require allow_write")
@click.option("--duration", default="short",
              type=click.Choice(["short", "medium", "long"]))
@click.option("--yes", is_flag=True, default=False,
              help="Skip confirmation for dangerous/critical (trusted automation only)")
@click.option("--fail-on", default="error",
              type=click.Choice(["error", "warning", "info", "never"]))
@click.option("--require-tests", is_flag=True, default=False,
              help="Exit 1 if no test method executed; an empty run is not a pass.")
def run_unit_test_cmd(object_name, object_type, group, risk_level, duration, yes, fail_on, require_tests):
    """Run ABAP Unit tests for a class/program/include (read-only at harmless)."""
    config = _load_config()
    _require_config(config)
    if risk_level in ("dangerous", "critical"):
        # Executing code at these levels may modify business data: treat as
        # a write operation (profile-level prd refusal happens inside the
        # shared gate), then show the risk-specific confirmation preview.
        _require_write(config)
        preview = [
            f"Action   : Run ABAP Unit tests ({risk_level} risk, {duration} duration)",
            f"Object   : {object_type.upper()} {object_name.upper()}",
            f"WARNING  : {risk_level}-level tests may MODIFY BUSINESS DATA on this system.",
        ]
        _confirm_change(preview, yes=yes)

    result = handlers.run_unit_test(
        object_type, object_name, group=group,
        risk_level=risk_level, duration=duration,
    )
    if result.is_error:
        _abort_on_error(result)
    click.echo(output.render(result, output.get_format(),
                             command="run-unit-test", profile=_profile_name()))
    if result.meta.get("partial") or (require_tests and result.meta.get("no_tests_found")):
        sys.exit(1)
    _fail_on_findings(result, fail_on)


def _fail_on_findings(result, threshold: str) -> None:
    if threshold == "never":
        return
    levels = {"error": {"error"}, "warning": {"error", "warning"},
              "info": {"error", "warning", "info"}}
    # Human-approved exemptions are auditable in output but never fail CI.
    found = [
        f for f in (result.data or {}).get("findings", [])
        if f.get("severity") in levels[threshold] and not f.get("exempted")
    ]
    if found:
        sys.exit(1)


@cli.command("run-atc", help_group=_DIAGNOSIS_HELP, help_order=20,
             short_help="Run static quality checks.")
@click.argument("object_name")
@click.option("--type", "object_type", default="class",
              type=click.Choice(["program", "class", "interface", "include", "function"]))
@click.option("--group", default=None, help="Function group (required for --type function)")
@click.option("--variant", default="STANDARD", show_default=True, help="ATC check variant")
@click.option("--max-results", default=100, show_default=True)
@click.option("--fail-on", default="error",
              type=click.Choice(["error", "warning", "info", "never"]))
def run_atc_cmd(object_name, object_type, group, variant, max_results, fail_on):
    """Run static ATC checks for an object (no side effects, no gate)."""
    result = handlers.run_atc(object_type, object_name, group=group,
                              variant=variant, max_results=max_results)
    if result.is_error:
        _abort_on_error(result)
    click.echo(output.render(result, output.get_format(),
                             command="run-atc", profile=_profile_name()))
    _fail_on_findings(result, fail_on)


@cli.command("discovery", help_group=_SETUP_HELP, help_order=50,
             short_help="List advertised SAP capabilities.")
@click.option("--emit-markdown", "emit_markdown", default=None,
              type=click.Path(writable=True, dir_okay=False),
              help="Write a generated endpoint table to PATH (local file only).")
def discovery_cmd(emit_markdown):
    """List ADT resources exposed by this system (Atom discovery document).

    Returns a 'capabilities' envelope (collections with href/title/
    content_types); --format xml returns the raw Atom service document.
    """
    if emit_markdown:
        result = handlers.discovery()
        if result.is_error:
            _abort_on_error(result)
        md = handlers.coverage_lib.render_discovery_markdown(
            result.data["collections"]
        )
        with click.open_file(emit_markdown, "w", encoding="utf-8") as f:
            f.write(md)
        click.echo(f"Wrote generated endpoint table to {emit_markdown}")
        return
    _output(handlers.discovery())


@cli.command("get-program", help_group=_SOURCE_HELP,
             short_help="Read a program's ABAP source.")
@click.argument("program_name")
def get_program(program_name):
    """Retrieve ABAP program (report) source code.

    PROGRAM_NAME is the ABAP object name, e.g. SAPMV45A or ZMYREPORT.
    Names are case-insensitive; uppercase is recommended.
    """
    _output(handlers.get_program(program_name))


@cli.command("list-feeds", help_group=_DIAGNOSIS_HELP, help_order=40,
             short_help="Find diagnostic feeds and filters.")
def list_feeds_cmd():
    """List /sap/bc/adt/feeds with FQL attributes and query variants (JSON)."""
    _output(handlers.list_feeds())


@cli.command("get-dump", help_group=_DIAGNOSIS_HELP, help_order=60,
             short_help="Inspect one runtime dump.")
@click.argument("identifier")
@click.option("--max-chars", type=click.IntRange(1, 200000), default=20000,
              show_default=True, help="Shared character budget for diagnostic chapter text.")
def get_dump_cmd(identifier, max_chars):
    """Read one runtime dump's metadata and formatted evidence (GET /runtime/dump).

    JSON dumps envelope by default; partial/unavailable detail exits 1 with
    evidence gaps and ST22 fallback. XML returns the metadata document.
    """
    result = handlers.get_dump(identifier, max_chars=max_chars)
    _output(result)
    if result.meta.get("partial"):
        sys.exit(1)


@cli.command("get-source", help_group=_SOURCE_HELP,
             short_help="Read source by URI and line range.")
@click.argument("uri")
@click.option("--start-line", type=click.IntRange(1), default=1, show_default=True)
@click.option("--end-line", type=click.IntRange(1), default=None)
def get_source_cmd(uri, start_line, end_line):
    """Read a returned source URI, including test includes (plain ABAP default).

    GET repository /source/main or /includes/{part}; --format json includes
    one-based range metadata for the locally selected lines.
    """
    _output(handlers.get_source(uri, start_line=start_line, end_line=end_line))


def _debug_config(action=None, yes=False):
    config = _load_config()
    _require_config(config)
    if output.get_format() == "xml":
        _gate(errors.BAD_REQUEST, "Debugger commands support JSON or text, not XML")
    if action:
        _require_debug(config)
        _confirm_change([
            f"Action   : Debugger {action}",
            f"Profile  : {config.profile_name or '(environment variables)'}",
            "WARNING  : Debugging can pause execution; stepping/resuming may MODIFY BUSINESS DATA.",
            "Scope    : Current SAP user only; no system debugging or variable modification.",
        ], yes=yes)
    return config


def _debug_output(result):
    _output(result)
    if result.meta.get("partial"):
        sys.exit(1)


@cli.group("debug", help_group=_DIAGNOSIS_HELP, help_order=70,
           short_help="[MAY RUN ABAP] Experimental debugger.")
def debug_group():
    """Experimental debugger; requires separate allow_debug permission.

    Source writes can remain disabled. serve/breakpoint/listen/attach/step/
    continue require a non-PRD environment and fresh confirmation per action.
    Stepping/resuming can execute business writes; this is not a read-only
    sandbox. Stack/variable reads use an authorized attached session.
    status/detach/cleanup remain available after disabling debug permission;
    detaching may let existing execution continue.

    Start a bounded foreground owner with 'serve'.
    """


@debug_group.command("serve")
@click.option("--ttl", type=click.IntRange(10, 1800), default=900, show_default=True)
@click.option("--idle", type=click.IntRange(5, 1800), default=120, show_default=True)
@click.option("--yes", is_flag=True)
def debug_serve(ttl, idle, yes):
    """Own a debugger in this foreground process; prints a session handle.

    Start in another terminal. Ctrl-C/expiry attempts non-terminating cleanup.
    No SAP credentials or cookies are written into the local descriptor.
    Requires allow_debug, not allow_write. PRD is refused; complete
    env/dotenv connections also require an explicit SAP_ENVIRONMENT.
    """
    config = _debug_config("serve", yes)
    from sap_adt.debugger.owner import Owner
    owner = None
    try:
        owner = Owner(config, ttl=ttl, idle=idle)
        click.echo(output.render(handlers.debug_result(owner.open()), output.get_format(),
                                 command="debug serve", profile=_profile_name(), compact=True))
        sys.stdout.flush()
        result = owner.run()
        owner = None
        click.echo(output.render(handlers.debug_result(result), output.get_format(),
                                 command="debug serve", profile=_profile_name(), compact=True))
        if result.get("evidence_gaps"):
            sys.exit(1)
    except Exception as exc:
        if owner is not None:
            owner.finish()
        _abort_on_error(handlers._err(exc))


@debug_group.command("status")
@click.option("--session", required=True)
def debug_status(session):
    """Read owner state over private IPC; no SAP request."""
    config = _debug_config()
    _debug_output(handlers.debug_operation(config, session, "status", {}))


@debug_group.command("breakpoint")
@click.option("--session", required=True)
@click.option("--uri", required=True)
@click.option("--line", required=True, type=click.IntRange(1, 10000000))
@click.option("--yes", is_flag=True)
def debug_breakpoint(session, uri, line, yes):
    """Set one owned source-line breakpoint before listening (POST /breakpoints).

    Requires allow_debug, non-PRD and fresh confirmation; not source writes.
    A matching breakpoint can interrupt application execution.
    """
    config = _debug_config("breakpoint", yes)
    _debug_output(handlers.debug_operation(config, session, "breakpoint", {"uri": uri, "line": line}))


@debug_group.command("listen")
@click.option("--session", required=True)
@click.option("--timeout", type=click.IntRange(1, 30), default=15, show_default=True)
@click.option("--yes", is_flag=True)
def debug_listen(session, timeout, yes):
    """Wait for the current user's debuggee (POST /debugger/listeners).

    Requires allow_debug, non-PRD and fresh confirmation; not source writes.
    Timeout is not a hit or permission to trigger unrelated business code.
    """
    config = _debug_config("listen", yes)
    _debug_output(handlers.debug_operation(config, session, "listen", {"timeout": timeout}))


@debug_group.command("attach")
@click.option("--session", required=True)
@click.option("--debuggee", required=True)
@click.option("--yes", is_flag=True)
def debug_attach(session, debuggee, yes):
    """Attach this owner's returned debuggee (POST /debugger?method=attach).

    Requires allow_debug, non-PRD and fresh confirmation; not source writes.
    Attachment can pause the target's execution.
    """
    config = _debug_config("attach", yes)
    _debug_output(handlers.debug_operation(config, session, "attach", {"debuggee": debuggee}))


@debug_group.command("stack")
@click.option("--session", required=True)
def debug_stack(session):
    """Read the attached stack (GET /debugger/stack?method=getStack)."""
    config = _debug_config()
    _debug_output(handlers.debug_operation(config, session, "stack", {}))


@debug_group.command("vars")
@click.option("--session", required=True)
@click.option("--id", "ids", multiple=True)
@click.option("--parent", default=None, help="Expand exactly one parent, e.g. @LOCALS.")
@click.option("--limit", type=click.IntRange(1, 100), default=20, show_default=True)
@click.option("--max-chars", type=click.IntRange(1, 4000), default=500, show_default=True)
def debug_vars(session, ids, parent, limit, max_chars):
    """Read explicit variables/one parent (POST getVariables/getChildVariables)."""
    config = _debug_config()
    _debug_output(handlers.debug_operation(config, session, "vars", {
        "ids": list(ids), "parent": parent, "limit": limit, "max_chars": max_chars,
    }))


@debug_group.command("step")
@click.option("--session", required=True)
@click.option("--action", type=click.Choice(["into", "over", "return"]), default="over")
@click.option("--yes", is_flag=True)
def debug_step(session, action, yes):
    """Execute one approved step (POST /debugger?method=stepInto/Over/Return).

    Requires allow_debug, non-PRD and fresh confirmation. Application code
    may write business data even with allow_write=false. Never blindly retry.
    """
    config = _debug_config("step " + action, yes)
    _debug_output(handlers.debug_operation(config, session, "step", {
        "action": {"into": "stepInto", "over": "stepOver", "return": "stepReturn"}[action],
    }))


@debug_group.command("continue")
@click.option("--session", required=True)
@click.option("--yes", is_flag=True)
def debug_continue(session, yes):
    """Resume execution (POST /debugger?method=stepContinue); may write data.

    Requires allow_debug, non-PRD and fresh confirmation. Application code
    may write business data even with allow_write=false. Never blindly retry.
    """
    config = _debug_config("continue", yes)
    _debug_output(handlers.debug_operation(config, session, "continue", {}))


@debug_group.command("detach")
@click.option("--session", required=True)
def debug_detach(session):
    """Detach without terminating; remove owned listener/breakpoints and end owner.

    Does not require re-enabling debug or source-write permission.
    Detaching can allow existing application execution to proceed, not roll back.
    """
    config = _debug_config()
    _debug_output(handlers.debug_operation(config, session, "detach", {}))


@debug_group.command("cleanup")
@click.option("--session", required=True)
@click.option("--discard-local", is_flag=True, help="If owner unreachable, forget local state ONLY.")
@click.option("--yes", is_flag=True)
def debug_cleanup(session, discard_local, yes):
    """Clean owned resources; stale owners cannot prove remote release.

    Does not require re-enabling debug or source-write permission.
    Detaching can allow existing execution to proceed. Local discard is
    bookkeeping only and requires its own confirmation.
    """
    config = _debug_config()
    if discard_local:
        _confirm_change(["Discard local debugger state only; remote state remains unknown."], yes=yes)
    _debug_output(handlers.debug_operation(config, session, "cleanup", {}, discard=discard_local))


@cli.command("query-feed", help_group=_DIAGNOSIS_HELP, help_order=50,
             short_help="Read a filtered diagnostic feed page.")
@click.argument("uri")
@click.option("--query", default="", help="FQL expression advertised by list-feeds.")
@click.option("--max-results", default=20, show_default=True, type=click.IntRange(1, 500))
@click.option("--page-uri", default=None, help="next_uri returned by the previous page.")
def query_feed_cmd(uri, query, max_results, page_uri):
    """Read one page from an advertised diagnostic feed (Atom GET, no writes).

    URI is the feed content_uri from list-feeds. Summaries may contain
    untrusted HTML or sensitive diagnostic data; never execute their contents.
    """
    _output(handlers.query_feed(uri, query, max_results, page_uri))


@cli.command("get-versions", help_group=_HISTORY_HELP, help_order=10,
             short_help="List an object's stored versions.")
@click.argument("object_type", type=click.Choice([
    "program", "class", "interface", "include", "function", "function-group",
    "table", "structure", "cds-view", "domain", "data-element", "type-group",
]))
@click.argument("name")
@click.option("--group", default=None, help="Required for function modules.")
@click.option("--max-results", default=100, show_default=True, type=click.IntRange(1, 500),
              help="Version limit per source part/include.")
def get_versions_cmd(object_type, name, group, max_results):
    """Read versions via object metadata links, including separate class includes.

    JSON contains opaque content_uri values. Version 00000 is active source,
    not an immutable transport snapshot. Partial history exits 1 after output.
    """
    result = handlers.get_versions(object_type, name, group, max_results)
    _output(result)
    if result.meta.get("partial"):
        sys.exit(1)


@cli.command("get-version-source", help_group=_HISTORY_HELP, help_order=20,
             short_help="Read a selected version's source.")
@click.argument("uri")
def get_version_source_cmd(uri):
    """Read a content_uri from get-versions (plain source, --format json supported)."""
    _output(handlers.get_version_source(uri))


@cli.command("diff-versions", help_group=_HISTORY_HELP, help_order=30,
             short_help="Compare two stored source versions.")
@click.argument("from_uri")
@click.argument("to_uri")
@click.option("--context", default=3, show_default=True, type=click.IntRange(0, 100))
def diff_versions_cmd(from_uri, to_uri, context):
    """Compare two version content URIs locally (JSON or --format text unified diff)."""
    _output(handlers.diff_versions(from_uri, to_uri, context))


@cli.command("get-transport", help_group=_TRANSPORT_HELP, help_order=20,
             short_help="Inspect a request's tasks and objects.")
@click.argument("trkorr")
def get_transport_cmd(trkorr):
    """Read /cts/transportrequests/<TRKORR>: request/task metadata and objects."""
    _output(handlers.get_transport(trkorr))


@cli.command("get-class", help_group=_SOURCE_HELP,
             short_help="Read a class's ABAP source.")
@click.argument("class_name")
def get_class(class_name):
    """Retrieve ABAP class source code.

    CLASS_NAME is the class name, e.g. ZCL_MY_CLASS or CL_SALV_TABLE.
    """
    _output(handlers.get_class(class_name))


@cli.command("get-function-group", help_group=_SOURCE_HELP,
             short_help="Read a function group's top include.")
@click.argument("function_group")
def get_function_group(function_group):
    """Retrieve ABAP function group top-include source code.

    FUNCTION_GROUP is the function group name, e.g. BAPI_SD_SALESORDER.
    Use get-function to retrieve a specific function module within the group.
    """
    _output(handlers.get_function_group(function_group))


@cli.command("get-function", help_group=_SOURCE_HELP,
             short_help="Read a function module's source.")
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


@cli.command("get-structure", help_group=_DATA_HELP,
             short_help="Inspect a structure's fields.")
@click.argument("structure_name")
def get_structure(structure_name):
    """Retrieve ABAP DDIC structure definition.

    STRUCTURE_NAME is the dictionary structure name, e.g. VBAKKOM.
    Returns a 'fields' envelope (JSON by default; --format xml for raw ADT).
    """
    _output(handlers.get_structure(structure_name))


@cli.command("get-table", help_group=_DATA_HELP,
             short_help="Inspect table field definitions.")
@click.argument("table_name")
def get_table(table_name):
    """Retrieve ABAP DDIC transparent table field definitions.

    TABLE_NAME is the dictionary table name, e.g. VBAK or MARA.
    Returns a 'fields' envelope (JSON by default; --format xml for raw ADT).
    """
    _output(handlers.get_table(table_name))


@cli.command("get-package", help_group=_FIND_HELP,
             short_help="Browse a package's objects.")
@click.argument("package_name")
def get_package(package_name):
    """List all objects in an ABAP package.

    PACKAGE_NAME is the development package name, e.g. ZMYPACKAGE.
    Returns an 'objects' envelope (JSON by default; source commands default to
    plain text; --format xml returns the raw ADT payload).
    """
    _output(handlers.get_package(package_name))


@cli.command("get-type-info", help_group=_DATA_HELP,
             short_help="Inspect a domain or data element.")
@click.argument("type_name")
def get_type_info(type_name):
    """Retrieve domain or data element information from DDIC.

    TYPE_NAME is the domain or data element name, e.g. MATNR or BUKRS.
    Tries domain first; falls back to the data element only on HTTP 404.
    Returns a 'scalar' envelope; data.resolved_as is 'domain' or 'dataelement'.
    """
    _output(handlers.get_type_info(type_name))


@cli.command("get-include", help_group=_SOURCE_HELP,
             short_help="Read an include's source.")
@click.argument("include_name")
def get_include(include_name):
    """Retrieve ABAP include source code.

    INCLUDE_NAME is the include program name, e.g. MV45AFZZ or LZMY_TOPINC.
    """
    _output(handlers.get_include(include_name))


@cli.command("get-interface", help_group=_SOURCE_HELP,
             short_help="Read an interface's source.")
@click.argument("interface_name")
def get_interface(interface_name):
    """Retrieve ABAP interface source code.

    INTERFACE_NAME is the interface name, e.g. ZIF_MY_INTERFACE or IF_SALV_MODEL.
    """
    _output(handlers.get_interface(interface_name))


@cli.command("get-transaction", help_group=_FIND_HELP,
             short_help="Inspect transaction metadata.")
@click.argument("transaction_name")
def get_transaction(transaction_name):
    """Retrieve transaction properties (package, application component).

    TRANSACTION_NAME is the transaction code, e.g. VA01 or MM60.
    Returns a 'scalar' envelope (facets: package/application/...).
    """
    _output(handlers.get_transaction(transaction_name))


@cli.command("search-object", help_group=_FIND_HELP, help_order=-10,
             short_help="Find objects by name or wildcard.")
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


@cli.command("syntax-check", help_group=_DIAGNOSIS_HELP, help_order=10,
             short_help="Check syntax without changing source.")
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


@cli.command("get-cds-view", help_group=_SOURCE_HELP,
             short_help="Read a CDS data definition.")
@click.argument("name")
def get_cds_view(name):
    """Retrieve CDS View DDL source code.

    NAME is the CDS entity name, e.g. ZI_INVENTORY_POSITION.
    Use the CDS entity name — not the underlying database view name.
    """
    _output(handlers.get_cds_view(name))


@cli.command("get-type-group", help_group=_SOURCE_HELP,
             short_help="Read a type group's source.")
@click.argument("name")
def get_type_group(name):
    """Retrieve ABAP type group (TYPE POOL) source code.

    NAME is the type group name, e.g. ICON or SLIS.
    """
    _output(handlers.get_type_group(name))


def _sha256_option(value):
    if value is None:
        return None
    v = value.strip().lower()
    if len(v) != 64 or any(c not in "0123456789abcdef" for c in v):
        raise click.BadParameter("expected a 64-character hex sha256")
    return v


def _write_target(config) -> dict:
    return {
        "profile": getattr(config, "profile_name", None),
        "environment": getattr(config, "environment", None),
        "url": getattr(config, "url", None),
        "client": getattr(config, "client", None),
        "user": getattr(config, "username", None),
    }


_DIFF_PREVIEW_LINES = 200


@cli.command("write-source", help_group=_SOURCE_HELP, help_order=10,
             short_help="[WRITE] Upload source; needs approval.")
@click.argument("object_type")
@click.argument("object_name")
@click.option("--file", "source_file", required=True, help="Source file path (UTF-8); use - to read from stdin")
@click.option("--group",     default=None,  help="Function group (required when OBJECT_TYPE is 'function')")
@click.option("--transport", default=None,  help="Transport request number (e.g. DEVK900001); omit for auto-assign")
@click.option("--activate",  is_flag=True,  default=False, help="Activate the object after writing and verify the active version")
@click.option("--expect-baseline-sha256", "expect_baseline", default=None,
              callback=lambda _c, _p, v: _sha256_option(v),
              help="Abort unless the remote source hash equals this (required with --yes; get it from --dry-run)")
@click.option("--expect-content-sha256", "expect_content", default=None,
              callback=lambda _c, _p, v: _sha256_option(v),
              help="Abort unless the canonical upload hash equals this")
@click.option("--dry-run",   is_flag=True,  default=False, help="Read the baseline and print hashes and diff; no lock or write")
@click.option("--yes",       is_flag=True,  default=False, help="Skip the interactive prompt only (requires --expect-baseline-sha256). Use only in trusted automation.")
def write_source_cmd(object_type, object_name, source_file, group, transport, activate,
                     expect_baseline, expect_content, dry_run, yes):
    """Write ABAP source code to SAP — requires allow_write + confirmation each time.

    OBJECT_TYPE: program / class / interface / include / function
    OBJECT_NAME: SAP object name (UPPERCASE recommended)

    Flow: read baseline → diff + confirm → lock → re-check baseline under
    the lock → write (PUT) → read back → unlock (always, in finally) →
    activate + verify active version (optional).

    Hashes are sha256 over canonical UTF-8 text (LF newlines, trailing
    blanks and trailing empty lines removed, as SAP stores them). --yes
    skips only the prompt: baseline/content checks still run, and
    --expect-baseline-sha256 is mandatory. stdout is a JSON result with
    per-stage status (accepted/verified/failed/unknown); unknown or partial
    results exit non-zero (WRITE_INCOMPLETE, exit 3) — never retry blindly.

    Requires 'allow_write' enabled in config. Run `configure` to enable.
    """
    config = _load_config()
    _require_config(config)
    _require_write(config)
    if yes and not expect_baseline and not dry_run:
        _gate(errors.CONFIRM_REQUIRED,
              "--yes requires --expect-baseline-sha256 (obtain it with --dry-run "
              "and review the diff); the operation was not performed.")
    if not yes and not dry_run and not _stdin_is_tty():
        _gate(errors.CONFIRM_REQUIRED,
              "Confirmation required but stdin is not a terminal; re-run in a "
              "terminal or pass --yes with --expect-baseline-sha256 for trusted "
              "automation.")

    def _read_upload() -> str:
        with click.open_file(source_file, "rb") as f:
            raw = f.read()
        try:
            return source_write.canonical_source(source_write.decode_local(raw))
        except UnicodeDecodeError as e:
            _gate(errors.BAD_REQUEST, f"source file is not valid UTF-8: {e}")

    content = _read_upload()
    try:
        uri = handlers.get_object_uri(object_type, object_name, group=group)
    except ValueError as e:
        _gate(errors.BAD_REQUEST, str(e))

    # Bind every request of this command to the resolved (and confirmed)
    # connection instead of re-resolving the profile per request.
    adt_client.set_config(config)
    try:
        base = handlers.read_source_main(uri)
        if base.is_error:
            _abort_on_error(base, "baseline read")
        plan = source_write.WritePlan(
            object_type=object_type, object_name=object_name, group=group,
            object_uri=uri, transport=transport, activate=activate,
            target=_write_target(config),
            baseline=source_write.canonical_source(base.text), content=content,
            expected_baseline_sha256=expect_baseline,
            expected_content_sha256=expect_content,
        )
        diff = source_write.unified_diff(plan.baseline, plan.content,
                                         f"{object_type.upper()} {object_name.upper()}")
        if dry_run:
            data = {**plan.describe(), "diff": "\n".join(diff)}
            problem = source_write.precheck(plan)
            if problem is not None:
                problem.data = data
                _emit_error(problem)
            _output(handlers.AdtResult(kind="write", data=data,
                                       object=handlers._obj(object_type, object_name),
                                       meta={"dry_run": True}))
            return
        problem = source_write.precheck(plan)
        if problem is not None:
            problem.data = plan.describe()
            _emit_error(problem)

        t = plan.target
        preview = [
            "Action   : Write source code",
            f"Target   : {t['profile']} ({t['environment']}) {t['url']} client {t['client']} user {t['user']}",
            f"Object   : {object_type.upper()} {object_name.upper()} ({uri})",
            f"Transport: {transport or '(auto-assigned)'}",
            f"Baseline : sha256 {plan.baseline_sha256} ({len(plan.baseline.splitlines())} lines)",
            f"Upload   : sha256 {plan.content_sha256} ({len(plan.content.encode('utf-8'))} bytes)",
            f"Activate : {'yes' if activate else 'no'}",
            f"Plan     : sha256 {plan.plan_sha256}",
        ]
        if plan.unchanged:
            preview.append("Diff     : (none — upload equals baseline; write is skipped)")
        else:
            preview.append("Diff     :")
            preview += diff[:_DIFF_PREVIEW_LINES]
            if len(diff) > _DIFF_PREVIEW_LINES:
                preview.append(f"... {len(diff) - _DIFF_PREVIEW_LINES} more diff lines (see --dry-run)")
        if yes:
            # Unattended: keep the bound plan visible on stderr for audit logs.
            for line in preview[:8]:
                click.echo(line, err=True)
        _confirm_change(preview, yes=yes)

        def _current_hash() -> str:
            # Re-read the file after confirmation (stdin cannot change: it
            # was consumed once and only the confirmed buffer is uploaded).
            if source_file == "-":
                return source_write.sha256_text(content)
            try:
                with open(source_file, "rb") as f:
                    now = source_write.canonical_source(source_write.decode_local(f.read()))
            except (OSError, UnicodeDecodeError) as e:
                return f"unreadable ({type(e).__name__})"
            return source_write.sha256_text(now)

        report = source_write.execute(
            plan, current_content_sha256=_current_hash,
            progress=lambda m: click.echo(m, err=True))
    finally:
        adt_client.set_config(None)

    final = report.final_decision()
    if final is not None:
        _emit_error(final)
    _output(handlers.AdtResult(kind="write", data=report.to_data(),
                               object=handlers._obj(object_type, object_name)))


@cli.command("activate", help_group=_SOURCE_HELP, help_order=20,
             short_help="[WRITE] Activate an object; needs approval.")
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


@cli.command("where-used", help_group=_FIND_HELP,
             short_help="Find references to an object.")
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


@cli.command("run-sql", help_group=_DATA_HELP, help_order=10,
             short_help="[SELECT ONLY] Preview query results.")
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


@cli.command("list-transports", help_group=_TRANSPORT_HELP, help_order=10,
             short_help="Find transport requests.")
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


@cli.command("create-transport", help_group=_TRANSPORT_HELP, help_order=40,
             short_help="[WRITE] Create a request; needs approval.")
@click.option("--package", "package", required=True,
              help="Package (DEVCLASS) to create the request for; $TMP for a local request")
@click.option("--description", required=True, help="Transport request description")
@click.option("--ref", "ref", required=True,
              help="Relative ADT object URI the request refers to, e.g. "
                   "/sap/bc/adt/programs/programs/zfoo/source/main")
@click.option("--yes", is_flag=True, default=False, help="Skip confirmation prompt. Use only in trusted automation.")
def create_transport_cmd(package, description, ref, yes):
    """Create a transport request — requires allow_transport + confirmation each time.

    Uses the measured CreateCorrectionRequest protocol (real-verified on
    Basis 7.56, 2026-09-17): DEVCLASS + object REF are both required.
    Returns the new transport request number (e.g. DEVK900003).

    Requires 'allow_transport' enabled in config. Run `configure` to enable.
    """
    config = _load_config()
    _require_config(config)
    _require_transport_write(config)
    preview = [
        "Action      : Create transport request",
        f"Package     : {package}",
        f"Ref object  : {ref}",
        f"Description : {description}",
        f"Owner       : {config.username}",
    ]
    _confirm_change(preview, yes=yes)
    _output(handlers.create_transport(package, description, ref))


@cli.command("release-transport", help_group=_TRANSPORT_HELP, help_order=50,
             short_help="[IRREVERSIBLE] Release a transport request.")
@click.argument("trkorr")
@click.option("--yes", is_flag=True, default=False, help="Skip confirmation prompt. Use only in trusted automation.")
@click.option("--dry-run", is_flag=True, default=False,
              help="Preflight only: existence, owner, status and gates; no release request.")
def release_transport_cmd(trkorr, yes, dry_run):
    """Release a transport request — irreversible, requires allow_transport + confirmation.

    After the release jobs are submitted the transport status is read back
    (poll up to 120s). RELEASE_UNVERIFIED means the final state is unknown —
    never re-release, verify manually in SE09/SE10.
    """
    config = _load_config()
    _require_config(config)
    _require_transport_write(config)
    if dry_run:
        result = handlers.release_transport(trkorr, dry_run=True)
        _output(result)
        return
    preview = [
        "Action  : Release transport request",
        f"TRKORR  : {trkorr}",
        "WARNING : This operation CANNOT be undone.",
        "          Once released, the transport cannot be recalled or modified.",
    ]
    _confirm_change(preview, yes=yes)

    def _progress(msg: str):
        click.echo(msg, err=True)

    result = handlers.release_transport(trkorr, progress=_progress)
    if result.is_error:
        _abort_on_error(result)
    _output(result)


@cli.group("transport", help_group=_TRANSPORT_HELP, help_order=30,
           short_help="Collect or compare requests (read-only).")
def transport_group():
    """Transport request utilities (online collection is read-only)."""


@transport_group.command("diff")
@click.argument("trkorr")
@click.option("--max-objects", default=50, show_default=True, type=click.IntRange(1, 500))
@click.option("--context", default=3, show_default=True, type=click.IntRange(0, 100))
def transport_diff_cmd(trkorr, max_objects, context):
    """Read-only object diffs against previous stored versions; gaps exit 1.

    Released requests require a stored version attributable to the request.
    Modifiable requests compare current active source, NOT a transport snapshot.
    Missing baselines, unsupported objects and limits are EVIDENCE_GAP, never
    silently treated as unchanged or new. Does not cover customizing row data.
    """
    result = handlers.diff_transport(trkorr, max_objects, context)
    _output(result)
    if result.meta.get("partial"):
        sys.exit(1)


def _transport_config(legacy: bool):
    """Resolve the connection for transport collect/ping.

    Default: the normal ADT resolution (process env > explicit dotenv >
    profile + OS keystore). The legacy plaintext collector config
    (~/.sap-transport-gate/config.json) is ONLY consulted on the explicit
    --legacy-config path, and only after the env/dotenv layer — it is never
    a silent fallback for a missing profile or failed authentication.
    """
    if legacy:
        env_config, _ = load_env_connection()
        if env_config is not None:
            return env_config
        try:
            return legacy_config.load_legacy_config()
        except legacy_config.LegacyConfigError as e:
            _gate(errors.CONFIG_MISSING, str(e))
    config = _load_config()
    _require_config(config)
    return config


@transport_group.command("collect")
@click.argument("tr_id")
@click.option("--output-dir", "-o", default=None,
              help="Output directory (default: ./review_package/<TR_ID>/)")
@click.option("--verbose", "-v", is_flag=True, help="Show each object fetch result")
@click.option("--legacy-config", is_flag=True, default=False,
              help="Explicitly read the legacy plaintext collector config "
                   "(~/.sap-transport-gate/config.json) instead of ADT "
                   "profiles; prints a migration warning. Never used "
                   "implicitly.")
def transport_collect_cmd(tr_id, output_dir, verbose, legacy_config):
    """Collect a TR's object list and source code into a review package (read-only).

    TR_ID is the transport request number, e.g. DEVK900001. The output
    package layout (manifest.json + sources/) is unchanged from the
    standalone tr_collector. Writes only to the output directory under the
    current working directory.
    """
    config = _transport_config(legacy_config)
    collector.run_collect(config, tr_id, output_dir, verbose,
                          collector_version=get_version())


@transport_group.command("ping")
@click.option("--legacy-config", is_flag=True, default=False,
              help="Explicitly read the legacy plaintext collector config "
                   "(see 'transport collect --help').")
def transport_ping_cmd(legacy_config):
    """Check ADT connectivity for the transport connection (plain text)."""
    config = _transport_config(legacy_config)
    adt_client.set_config(config)
    result = collector_handlers.ping()
    if result.is_error:
        click.echo(result.text, err=True)
        sys.exit(1)
    click.echo(result.text)


def main(prog_name: str = "sap-adt", args=None) -> None:
    """Console-script entry (pyproject [project.scripts]).

    ``args`` optionally overrides argv for embedding/tests; None means Click
    reads sys.argv as usual.
    """
    # Frozen Windows Python can ignore PYTHONUTF8; pipes still need UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and not stream.isatty():
            stream.reconfigure(encoding="utf-8")
    cli(args=args, prog_name=prog_name)


if __name__ == "__main__":
    main()
