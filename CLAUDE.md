# CLAUDE.md

Watt is an engineering CLI for SAP lifecycle work with companion agent Skills.
ADT/ABAP is the current foundation, not the product boundary. The CLI provides
controlled operations; Skills and agents provide workflows and reasoning.

## Source boundaries

- `src/sap_adt/` is the only CLI business implementation; do not fork it by brand
  or put CLI execution code back into Skill folders.
- All SAP HTTP access uses `adt/client.py`; transport collection shares that
  client through `set_config()`. Do not introduce a separate collector client.
- `skills/<name>/` owns Skill content, references and evals. Read its `SKILL.md`
  and required references before changing its workflow; do not duplicate them here.
- Root `pyproject.toml` is the single CLI version source.
  `.claude-plugin/plugin.json` is the plugin version authority.
- `compatibility.json` declares CLI requirements/ranges;
  `docs/installation/runtime-setup.md` supplies shared installation content.
- Generate committed Skill setup/compatibility snapshots and README setup blocks
  with `tools/sync_skill_runtime_docs.py`. Never hand-edit GENERATED files or `dist/`.
- Archived `pub-*` Skill remotes are read-only: no subtree pulls or pushes.
  Maintain all Skills here; historical details are in [migration notes](docs/development/migration.md).

## Watt and sap-adt compatibility

- For every CLI feature/fix release, build and verify both `sap-adt-cli` and
  `sap-watt` for PyPI and npm at the same root CLI version. Publish both when
  authorized; never deliver new capabilities only through Watt.
- Python Watt is an entry package pinned to the exact core version. npm packages
  own separate commands/runtime slots and support independent installed upgrades.
- At the same version, both entries must preserve subcommands/options, JSON
  schemas, error/exit contracts and authorization behavior. Command display names
  and owning-package update actions may differ.
- Preserve existing scripts, configuration paths, environment variables,
  credential IDs, native artifact names and Skill/plugin IDs. No bare `watt` entry.
- Every CLI-aware Skill supports either compatible entry: prefer available,
  compatible `sap-watt`, otherwise compatible `sap-adt`; keep one prefix per task.
  Never require both entries or a branding-only migration. Offline work needs no CLI.
- Declare feature minimum versions and check relevant commands/options before use.
  Missing optional features must not disable unrelated supported work. Never
  fabricate results or silently install/upgrade; regenerate compatibility snapshots.
- Before release, verify both package families/entries, command/doc contracts,
  snapshots and supported coexistence/uninstall behavior using existing tests,
  `tools/smoke_python.py` and `tools/smoke_npm.py`; check advertised platforms natively.
  An untested alias is not compatibility evidence.
- Stopping legacy updates or changing contracts incompatibly needs a separately
  approved deprecation/migration plan; repository rebranding is not that approval.

## SAP safety and evidence

- Read-only by default. Source writes/activation require `allow_write`;
  transport mutations require `allow_transport`. Keep per-operation previews and
  fresh confirmation, production restrictions and fail-closed noninteractive gates.
  Never cache consent or let `--yes` bypass authorization.
- `run-class`/`run-report`/`run-abap` require independent, profile-only
  `allow_execute`, non-PRD and fresh approval; `--yes` needs a reviewed plan hash.
  Invocation-owned `$TMP` Class preparation/cleanup uses execution authorization,
  not `allow_write`; generic source writes retain their own gate and SAP permissions
  remain necessary. No automatic COMMIT, rollback or execution replay; an unknown
  execution retains its temporary object.
- Debug setup/controls require independent profile-only `allow_debug`, non-PRD
  and fresh confirmation; never inherit source/transport/global permissions.
  Authorized session reads/cleanup do not require re-enabling flags. Execution
  and debugging can change business data even when source writes are disabled.
- Keep non-secret profiles in `~/.sap-adt-cli/config.json` (0600); passwords belong
  in the existing keystore backends, not plaintext config. Preserve backend priority
  and migration behavior documented in the credential guide below.
- Preserve process env > explicit `SAP_ADT_DOTENV` > profile precedence; never
  scan CWD/Skill folders for dotenv. Complete connection env bypasses profiles.
  Legacy collector plaintext config is read only via explicit `--legacy-config`.
- `run-sql` unconditionally rejects `INSERT`/`UPDATE`/`DELETE`/`MODIFY`/`TRUNCATE`.
- Transport review never accepts SAP passwords or logs in directly; online ADT
  collection uses the shared CLI. Cite real evidence; declare `EVIDENCE_GAP`.
  LOW evidence means `NO_GO`; insufficient evidence cannot yield `GO`.
  A single ABAP file is not a full TR review. Any CRITICAL SECURITY,
  AUTHORIZATION or TRANSACTION_CONSISTENCY finding blocks release.
- Code review: without a functional spec, mark `[FUNC]` as `N/A`, never infer it.
  `[SEC]`/`[AUTH]`/`[STD]` findings require rule IDs; every finding needs a real
  code snippet of at most 15 lines.

## Development and verification

- New commands: update `adt/handlers.py` and Click registration in `cli.py`,
  document output formats and ADT endpoints, update the CLI Skill command index
  and contract-count references (including archived `refactor-*.md`), and add tests.
- Preserve the output envelope, closed error-code set and exit tiers; consult
  [architecture](docs/development/architecture.md) before changing these contracts.
- Local verification baseline (use an installed development environment):

```bash
python -m unittest discover -s tests -v
python tests/check_contract.py
python tools/sync_skill_runtime_docs.py --check
node --test packaging/npm/test/install.test.js
```

- Skill evals live under each Skill's `evals/`. See [contributing](CONTRIBUTING.md)
  for setup, secret scanning and manual credential-backend checks.
- Build order, dual-package artifacts and native smoke checks belong in the build
  guide below. Hosted runners run offline checks only; never connect them to SAP.
  Do not present fixtures or prior-platform results as current live certification.
- Publishing is a separate authorized step. Never push, tag, publish or switch
  the live marketplace without explicit approval; follow the release guide.

## Read on demand

| Task | Authoritative reference |
|---|---|
| Brand, audience and current scope | [README](README.md), [engineering principles](docs/design-principles.md) |
| Architecture and removed legacy entry points | [Architecture](docs/development/architecture.md), [migration](docs/development/migration.md) |
| Installation and platform limits | [Runtime setup](docs/installation/runtime-setup.md), [Windows](docs/installation/windows.md) |
| Credentials, precedence and profiles | [Credentials](skills/sap-adt-cli/references/credentials.md), [profiles](skills/sap-adt-cli/references/profiles.md) |
| CLI workflows and command index | [sap-adt-cli](skills/sap-adt-cli/SKILL.md) |
| Code review references and report workflow | [abap-code-review](skills/abap-code-review/SKILL.md) |
| TR evidence, decisions and report workflow | [sap-transport-gate](skills/sap-transport-gate/SKILL.md) |
| Integration selection, SAP versions and generators | [sap-integration-wiki](skills/sap-integration-wiki/SKILL.md) |
| Build, native checks and release procedure | [Building](docs/development/building.md), [releasing](docs/development/releasing.md) |
