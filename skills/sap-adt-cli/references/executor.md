# Atomic executor and evidence packages

These additive commands keep SAP interaction deterministic. They do not embed
LLM reasoning, build a persistent repository index, orchestrate a squad, attest
a human approver, or authorize a release. Existing credentials, ADT sessions and
independent write/execution/debug gates still apply.

## Target and output contract

Use explicit JSON for automation; default human-readable output remains.
Every envelope includes `meta`, `warnings` and `next_steps`, with `data` on
success or `error` on failure. `ok` means the operation/evidence acquisition
succeeded, **not** that tests or a quality/release gate passed.

```bash
sap-adt --profile dev -f json status
sap-adt --profile dev --expect-environment dev --expect-client 100 \
  --expect-target TARGET_SHA256 -f json get-class ZCL_ORDER
```

The configured-target fingerprint binds normalized origin (including port),
SAP client and logical environment, not user/password/profile aliases. It is
not server-attested identity. Expectations are checked before the command.
Operation metadata describes type, technical risk and approval mechanism;
it never grants a permission. Errors retain the closed error-code contract
and add a category. Explicit JSON is supported for local maintenance and
usage failures too; help remains help and `debug serve` remains JSONL.

## Metadata, impact and comparisons

`get-object` supports message classes, lock objects, enhancement spot/BAdI
containers and implementations. Enhancement-point lookup reads declarations
in the explicitly named owner program, not all its includes. Existing RAP
definition readers remain the RAP path. Backend resource availability applies.

```bash
sap-adt -f json get-object message-class 00
sap-adt -f json where-used class ZCL_ORDER --depth 2 --max-nodes 30
sap-adt -f json compare-object class ZCL_ORDER \
  --from-profile dev --to-profile qas
sap-adt -f json transport analyze DEVK900001 --max-objects 20
sap-adt -f json transport compare DEVK900001 \
  --from-profile dev --to-profile qas
```

Check `--help` for each object's selector. Deep references are bounded static
reverse references, not proof of all dynamic callers/prerequisites. Risk scores
are versioned observed technical indicators, not business release decisions.
Cross-profile comparisons resolve the two stored profiles explicitly, bypass
complete `SAP_*` connection overrides, isolate sessions and refuse aliases of
the same origin/client. Missing sides stay unknown, never empty/unchanged.
They compare active-at-read-time representations, not exact released snapshots.

## Unit, diagnosis and configuration

`run-unit-test --bundle NEW.zip` preserves results, JUnit, coverage evidence
and gate status. Zero executed tests are `not_run`, not a pass.
`--coverage-file` accepts only the documented target/source-bound supplied
line-coverage format; `--min-coverage` is checked over those supplied files.
Native SAP coverage instrumentation and measurement authenticity are not
claimed. Threshold/report/output options bind the reviewed Unit plan.
`unit skeleton NAME --output-file NEW.abap` creates an intentionally failing
local template; supply real business assertions before uploading it.

```bash
sap-adt -f json diagnose --message 'literal error text' --output-file diagnosis.zip
sap-adt -f json config-data read T002 --filter SPRAS=E \
  --max-rows 10 --output-file configuration.json
sap-adt -f json config-data compare T002 --filter SPRAS=E \
  --from-profile dev --to-profile qas
```

Diagnosis accepts one dump ID or literal message, reads a bounded advertised
feed page and attributable dumps/source context, and preserves gaps. Message
correlation is not root-cause inference. No test or execution is replayed.
Configuration reads address one table or database/projection view using
validated DDIC fields and equality filters. They do not emulate SM30 or scan
the whole system. Comparisons align declared keys and normalize matching
client fields unless `--include-client`; partial/nonunique selections cannot
prove equality or complete additions/removals.

## Quality and Git bridges

```bash
sap-adt -f json quality-check ZCL_ORDER --output-file quality.zip
sap-adt -f json git status --repo /path/to/abapgit-repository
sap-adt -f json git export DEVK900001 --repo /path/to/abapgit-repository \
  --mapping-file mapping.json --verify-transport --output-file git.zip
```

Quality defaults to SAP syntax and ATC. Repeated `--engine` selects required
engines; supplying `--abaplint-report` opts that engine in. The native abaplint
JSON array and `--abaplint-manifest` are both required. See the Skill's quality
manifest fields. Unknown severities, incomplete engines, invalid binding or
missing required reports never pass. No automatic tool installation occurs.
Supplied lint/coverage provenance is not independently attested.

Git reads are bounded local subprocesses, with no shell, optional index locks,
hooks, filesystem monitor, fetch, commit or push. Explicit object/file mappings
are caller assertions until `--verify-transport` confirms current SAP membership.
`--commit REF` exports that one commit's blobs/config, otherwise working-tree
bytes are used (not staged index blobs). Missing/deleted content is a gap.
Existing `.abapgit.xml` can be included; no SAP abapGit serializer is invoked,
and the delta archive is not certified as an importable abapGit repository.

## Requirement delivery package

First collect the already authorized evidence; packaging never runs SAP calls,
tests, checks, Git mutations or releases. Add `--bundle` to the existing
`transport collect` command to retain its legacy directory/schema and also
produce a hashed, target-bound ZIP.

```bash
sap-adt --profile dev -f json transport collect DEVK900001 \
  --output-dir reports/tr --bundle reports/transport.zip
sap-adt -f json delivery pack REQ-123 --transport DEVK900001 \
  --target-fingerprint TARGET_SHA256 \
  --asset transport=reports/transport.zip --asset unit=reports/unit.zip \
  --asset quality=reports/quality.zip --asset git=reports/git.zip \
  --asset configuration=reports/configuration.json \
  --asset diagnosis=reports/diagnosis.zip --output-file reports/delivery.zip
```

`--transport` and `--asset KIND=PATH` are repeatable. Kinds: `transport`,
`source`, `diff`, `unit`, `quality`, `configuration`, `diagnosis`, `git`,
`attachment`. Standard executor ZIPs are verified against every inner asset's
declared size/hash, including the exact member set, without extracting files.
JSON inputs need structured data, a target and capture timestamp; unbound or
unknown-age reports remain explicit gaps. Local attachments are preserved but
never satisfy a required evidence category. Duplicate input hashes cannot
count twice. Archive/path/size violations, hash corruption, known wrong targets
or unrelated TRs refuse the output entirely.

Default required kinds are transport, source, Unit, quality and Git. A transport
ZIP with collected `sources/` also satisfies source presence. Repeated
`--require-kind` declares a different applicable set; transport is always
required, and every declared TR needs its own transport evidence. Optional
configuration/dump evidence is not fabricated to fill an inapplicable category.
The default maximum age is 168 hours (`--max-age-hours`); known inner capture
timestamps remain checked even after repackaging.

Missing assets, unavailable/failed gates, zero tests, unverified membership,
stale evidence and inherited gaps produce a usable **partial package and exit
1**. Successful assembly means `complete_within_declared_assets`, not complete
business coverage, a fresh SAP-source revalidation, or release approval.
Requirement association is explicitly operator-supplied. Formal review and
squad orchestration remain outside the CLI.

All new package/JSON output paths are exclusive and private; never overwrite
existing evidence. ZIPs contain a manifest with per-asset SHA-256, gaps and
non-atomic snapshot semantics. Evidence can contain proprietary source or
business data: keep it in approved local storage, not in Git or public reports.
