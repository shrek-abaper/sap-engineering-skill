# Test fixtures — sap-adt-cli

Real ADT response fixtures for the offline parser/golden tests. Nothing here
may contain real hosts, usernames, transport numbers, or business data — the
parser layer must be fully testable offline (no HTTP).

## Directory layout

```
tests/fixtures/
├── raw/                      # GITIGNORED — real captures, never committed
│   ├── _exit_codes.txt       # exit codes captured through the unmodified CLI
│   ├── _system.md            # capture system/profile notes (local only)
│   ├── sanitize.map.json     # GITIGNORED real→placeholder value map
│   └── <raw captures...>
├── sanitize.py               # raw/ → sanitized fixtures (stdlib only)
├── sanitize.map.example.json # template for raw/sanitize.map.json
├── golden/                   # normalized parser output, compared in
│                             # tests/test_sap_adt_cli_parsers.py
└── *.xml / *.json / *.abap   # sanitized fixtures listed below
```

## Capturing a new baseline (read-only commands only)

Prerequisites: a connected profile that is **DEV only** (a profile whose name
contains `prd`/`prod`/`qas` must never be captured). Check first:

```bash
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py status
# Verify: profile name, Write mode DISABLED, Transport write DISABLED
```

Only read-only commands are allowed during capture: `get-*`, `search-object`,
`where-used`, `list-transports`, `syntax-check`, `run-sql` (SELECT only).
Never run `write-source`, `activate`, `create-transport`, `release-transport`,
`configure`, `credentials set|forget`, and never pass `--yes`.

```bash
FX=skills/sap-adt-cli/tests/fixtures/raw
mkdir -p "$FX"
CLI="python3 skills/sap-adt-cli/scripts/sap_adt_cli.py"
$CLI get-table VBAK > "$FX/get-table.VBAK.xml" ; echo "get-table.VBAK.xml $?" >> "$FX/_exit_codes.txt"
# ... repeat per command; record BOTH stdout payload and stderr (errors)
```

For endpoints the current CLI cannot call correctly yet (newer ADT protocol),
raw payloads may be captured with equivalent **read-only** requests (GET or
read-only POST such as `checkruns`/`nodestructure`) using the CLI's own
`lib.client.make_adt_request` for auth/CSRF. Mark those files `*.raw.xml` and
explain how they were captured in `raw/_system.md`.

## Sanitizing

1. Copy `sanitize.map.example.json` to `raw/sanitize.map.json` and fill in the
   real values observed on the capture system (the map stays git-ignored).
2. Run:

   ```bash
   python3 skills/sap-adt-cli/tests/fixtures/sanitize.py
   python3 skills/sap-adt-cli/tests/fixtures/sanitize.py --check
   ```

The sanitizer copies only the files in its explicit `FILE_MAP` allow-list;
anything else remains in `raw/`. Transforms:

| Real value | Placeholder |
|---|---|
| internal host / URL / IP | `sap-dev.example.com` / `https://sap-dev.example.com:8000` |
| ADT username | `DEVELOPER` |
| profile name | `dev` |
| transport numbers (`xxxK9nnnnnnn`) | `DEVK9XXXXX` |
| `run-sql` business rows | synthetic `BUKRS`/`BUTXT`, same columns/row count |

Brand/business names specific to the landscape go into the local map's
`extra_leaks` list; the committed sanitizer itself never contains them.

After sanitizing, additionally grep the committable tree (excluding `raw/`):

```bash
grep -rnE "<internal-ip>|<real-user>|Nextev|DEVK9[0-9]{6}" \
  skills/sap-adt-cli/tests/fixtures/ --exclude-dir=raw
```

## Fixture inventory (captured 2026-09-15, S/4HANA 2021 / SAP_BASIS 7.56)

| File | Kind | Notes |
|---|---|---|
| `get-table.VBAK.s4hana.xml` | fields | DDL source (`define table`), 7.56 shape; element references only |
| `get-table.T001.s4hana.xml` | fields | DDL source, customizing table |
| `get-table.REPOSRC.s4hana.xml` | fields | DDL with a real built-in type (`abap.rawstring(0)`) |
| `get-structure.VBAKKOM.s4hana.xml` | fields | DDL source (`define structure`) |
| `get-class.CL_GUI_FRONTEND_SERVICES.abap` | source | plain ABAP source, byte-level text-mode baseline |
| `get-type-info.MATNR.dtel.xml` | scalar | `DTEL/DE`, data element branch |
| `get-type-info.MATNR18.dtel.xml` | scalar | Current CLI falls back to data element even for domain-like names (domain endpoint 404s on 7.56) |
| `get-type-info.CHAR10.domain.xml` | scalar | True `DOMA/DD` payload via `/ddic/domains/{name}` (new protocol) |
| `get-transaction.VA01.xml` | scalar | `ris/objectProperties` facet XML |
| `search-object.CL_GUI_WILDCARD.xml` | objects | non-empty Atom-style references |
| `search-object.empty.xml` | objects | empty `objectReferences` — must normalize to `ok:true`, `row_count:0`, exit 0 |
| `get-package.SABP_UNIT.cli-current.json` | objects | Current CLI output: `[]` (inline parser misses prefix-only abapxml namespace) |
| `get-package.SABP_UNIT.asxml.xml` | objects | Real nodestructure payload the new parser must handle |
| `list-transports.empty.xml` | records | New transportorganizer tree, empty root (`DEVELOPER`) |
| `list-transports.searchconfig.xml` | records | search-configuration metadata |
| `syntax-check.CL_GUI.clean.xml` | findings | New checkrun API, zero messages |
| `syntax-check.SAPMV45A.warnings.xml` | findings | real W-messages with line URIs |
| `run-sql.t001.json` | rows | synthetic company rows; real columns/row count |
| `run-sql.t100.raw.xml` | rows | raw dataPreview column-oriented XML via legacy GET→POST fallback (SAP-standard T100 messages) |
| `run-sql.t100.post.raw.xml` | rows | same shape via direct POST `freestyle` (current wire form) |
| `golden/*.json` | all | expected parser output; keep in sync when parsers change |
| `error.404.txt` / `error.404.xml` | error | CLI-wrapped text and raw `ExceptionResourceNotFound` body |
| `error.403-csrf.txt` | error | expired-token 403 body |
| `error.405-whereused-legacy.txt` / `error.405-usageReferences.raw.xml` | error | legacy GET retired / new endpoint requires POST |
| `error.406-list-transports.txt` | error | legacy worklist Accept rejected |
| `error.404-syntaxcheck.txt` | error | legacy syntaxcheck endpoint retired |
| `error.dml-rejected.txt` | error | DML policy gate rejection |
| `baseline-exit-codes.tsv` | meta | exit codes of the unmodified CLI per raw file |

## Known gaps

- **where-used success payloads** (hits and empty): the new
  `usageReferences` POST needs a request body whose inner structure was not
  fully reverse-engineered yet; to be completed during the protocol migration.
- **list-transports mixed-status**: the capture service user has an empty
  transport tree.
- **ECC 6 / older-release shapes** (field-metadata XML, legacy where-used /
  transport worklist / syntaxcheck payloads): to be provided from an older
  system; parsers must accept both shapes.
