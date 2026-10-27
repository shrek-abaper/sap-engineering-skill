# Claude Code

## Plugin install (unchanged identity)

```
/plugin marketplace add shrek-abaper/sap-engineering-skill
/plugin install sap-engineering-skills@sap-engineering
```

The plugin distributes **skill documentation only** — no CLI core. It does
not install the CLI, and it never downloads or upgrades anything at session
start.

## CLI is a separate, explicit install

Plugin installed ≠ CLI installed. The skills perform a conditional readiness
check (see `skills/<name>/references/setup.md`):

- offline tasks (reviewing provided ABAP source, knowledge questions) run
  without any CLI probe;
- online tasks check `sap-adt --version`, compare against
  `references/runtime-compatibility.json`, and ask before installing or
  upgrading.

## Compatibility

- Plugin/docs: 1.1.4.
- CLI range: `>=1.4.0,<2.0.0`.
- The live marketplace entry uses the `archive` source
  (`sap-engineering-skills-<ver>.zip` + SHA-256), which requires Claude Code
  ≥ 2.1.224 (verified against the official marketplace reference). Older
  clients cannot install this plugin until they upgrade.
