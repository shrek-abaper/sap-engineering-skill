# Generic SKILL.md agents (opencode, Cursor, WorkBuddy-class tools)

The skills are plain `SKILL.md` folders. Two supported ways to use them:

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

## Verified environments

| Environment | Status |
|---|---|
| Claude Code (plugin) | static validation done; real install/update needs a manual check |
| opencode | documented flow only (no automated verification here) |
| WorkBuddy-class agents | **unverified** — discovery, shell access and install permissions were not confirmed in this workspace |
