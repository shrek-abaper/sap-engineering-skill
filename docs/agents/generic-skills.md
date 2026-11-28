# Generic SKILL.md agents (Codex and other agents)

The skills are plain `SKILL.md` folders. Two supported ways to use them:

For WorkBuddy, prefer the [SkillHub marketplace installation guide](workbuddy.md).
The manual methods below remain a fallback when marketplace installation is unavailable.

## A. Copy one complete skill folder (recommended)

Take a built snapshot from `dist/skills/<name>/` (or, without building,
copy `skills/<name>/` from a source checkout — it already contains the
generated `references/setup.md` and `references/runtime-compatibility.json`).

**Copy the whole folder**, not just `SKILL.md`: references, setup snapshot
and compatibility file are required for self-contained guidance. Never mix
files from different skills into one directory.

## B. From a release

Each release publishes `<skill>-<plugin_version>.zip` (docs-only snapshot)
and `sap-engineering-skills-<plugin_version>.zip` (all four).

## Runtime expectations

- `sap-adt-cli` and `sap-transport-gate` (online collection) need the CLI;
  offline review and knowledge tasks do not.
- `abap-code-review` and `sap-integration-wiki` never need a CLI.
- The agent's shell may be a sandbox that cannot see the user's desktop
  install — check, ask, and never reinstall blindly.

## Supported agents

| Agent | How to use it |
|---|---|
| Claude Code | Install the plugin from this repository's marketplace |
| Codex | Copy the complete skill folders into the directory it scans |
| WorkBuddy | Prefer the [SkillHub marketplace](workbuddy.md); use manual import as a fallback |
| Other SKILL.md-compatible agents | Use the agent's own skill directory or import UI |

Discovery paths differ between agents: some read `~/.agents/skills/`, others
use a product-specific directory or an import UI. The copy steps above apply
either way — confirm the directory your agent scans before copying.
