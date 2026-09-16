# Output-standardization refactor — handoff

End state after batches 0–9. Companion docs: `refactor-summary.md`
(batches/commits, six→seven protocol facts, follow-ups), `known-issues.md`
(unverified paths, trigger conditions), `../skills/sap-adt-cli/SKILL.md`
(operational contract, ≤140 lines).

## 1. Completed batches

| Batch | Scope |
|---|---|
| 0 | Sanitized real DEV fixtures, sanitizer, `raw/` gitignored (`021e3ed`) |
| 1 | `lib/output.py` envelope seam, `--format`/`SAP_ADT_FORMAT`, zero behavior change (`f2b947e`) |
| 2 | Seven pure parsers + golden tests (`0aee386`) |
| 3 | Commands emit kinds; endpoint migrations (syntax/transports/domain/package namespace) (`7f780a7`) |
| 3.5 | run-sql POST; DDL built-in lengths; `meta.unparsed_types`; no description key (`0f50149`) |
| 3.6 | POST usageReferences; optional usage_line/usage_uri (`1af2d63`) |
| 4a/4b | 16→18 error codes, single classifier, exit tiers 0/1/2/3/4 (`cf879fb`, `04980f5`) |
| 5.0 | Flag-driven non-interactive configure envelopes (`3932175`) |
| 5 | SKILL.md 522→≤140 lines; references split; adt_api verified facts (`15ad32a`) |
| 6 | DEV three-way verification 28/28; `check_contract.py` in CI (`f2707a3`) |
| 7.1 | run-sql rowNumber/UP TO meta (measured, not inferred) (`a6f4bce`) |
| 7.2–7.4 | `discovery` (kind `capabilities`), `doctor --coverage`, application/* non-narrowing (`f7f321e`) |
| 7.5 | `discovery --emit-markdown`, no auto-merge (`9394719`) |
| 7.6 | coverage boundary caveat (`5e5e69d`) |
| 8 | run-unit-test (risk gates) + run-atc (stable IDs, exemptions) (`5ddf576`, `9ba237a`) |
| 9.1 | Per-profile allow_write/transport + environment; prd hard refusal; SAP_ENVIRONMENT (`66eb7fc`) |
| 9.2 | release-transport newreleasejobs + readback poll, `--dry-run`, RELEASE_* codes (`f57128f`) |
| post-9.2 | server status_text + real preflight/released fixtures (`d24bc88`) |
| 10 (canceled) | Cross-process session layer **designed, approved, then rejected by real-machine evidence** — separate-process activate works without shared session; design archived at `design-session-layer-rejected.md` (2026-09-17) |
| 10 (protocol) | First real-machine write verification: lock/PUT/unlock/activate all four shapes were wrong; corrected to measured protocol, facts 7→12 (incl. create-transport CreateCorrectionRequest ASX shape — old shape 400, command changed to `--package`/`--ref`); 403 enqueue conflict → LOCKED_BY_OTHER; 34-command real-machine matrix in refactor-summary (23 real / 2 partial / 9 local) (2026-09-16/17) |

Real release verified: empty request ECDK944391 released on DEV400,
readback `R/Released` on poll attempt 1; capability flags restored to
disabled afterwards.

## 2. Contract as it stands today (verbatim from code)

`lib/errors.py` — closed code set and exit map:

```python
ALL_CODES = (
    CONFIG_MISSING, PROFILE_NOT_FOUND, AUTH_FAILED,
    CSRF_EXPIRED, OBJECT_NOT_FOUND, SERVICE_NOT_ACTIVE,
    BAD_REQUEST, SERVER_ERROR, LOCKED_BY_OTHER, NETWORK_ERROR, PARSE_FAILED,
    WRITE_DISABLED, TRANSPORT_DISABLED, CONFIRM_REQUIRED,
    USER_ABORTED, DML_REJECTED,
    RELEASE_UNVERIFIED, RELEASE_REJECTED,
)
# EXIT_CODE_MAP: 2=CONFIG_MISSING,PROFILE_NOT_FOUND,AUTH_FAILED;
#  3=WRITE_DISABLED,TRANSPORT_DISABLED,CONFIRM_REQUIRED,USER_ABORTED,DML_REJECTED;
#  4=OBJECT_NOT_FOUND; everything else (incl. CSRF_EXPIRED, BAD_REQUEST,
#  SERVER_ERROR, RELEASE_UNVERIFIED, RELEASE_REJECTED) = 1
```

`lib/output.py` — kinds and default formats:

```python
STRUCTURED_KINDS = ("source","fields","objects","rows","records",
                   "findings","scalar","capabilities")
# default: source->text, all others->json; --format xml = raw ADT payload
# list counts: fields/objects/rows/transports/findings/collections
_LIST_KEY = {"fields":"fields","objects":"objects","rows":"rows",
             "records":"transports","findings":"findings",
             "capabilities":"collections"}
```

`lib/config.py` — effective capability merge:

```python
# environment prd -> (False, False, "hard-refused", "hard-refused")
# elif key in profile section -> bool(profile[key]), "profile"
# else -> bool(global[key]), "global"
# environment inference (loose substring): prd/prod->prd, qas/qa->qas, else dev
```

34 Click commands, 8 parser modules, 18 error codes. `check_contract.py`
asserts all four tables stay aligned with SKILL.md and fails CI on drift.

## 3. Seven verified protocol facts (S/4HANA 2021 / Basis 7.56)

Canonical copy in `references/adt_api.md` (dated old→new table) and
`refactor-summary.md`. Short form:

1. Domain metadata: `/ddic/domains/{n}` v2, not `…/source/main`.
2. Syntax: POST `/checkruns` checkObjectList/reporter, checkmessages XML.
3. Transports: GET `/cts/transportrequests` transportorganizer.v1+xml.
4. Data preview: POST freestyle rowNumber body; vendor Accept (406 on application/xml); **rowNumber silently overrides SQL UP TO**.
5. Where-used: POST usageReferences, relative lowercase URI, CT+Accept both `application/*`, empty affectedObjects; discovery declares no accept version → do not narrow.
6. Package nodestructure has no namespace on payload elements (local-name matching); tables/structures source is CDS DDL; objectstructure is 404.
7. Release: POST `/cts/transportrequests/{TR}/newreleasejobs` + readback `tm:status`; missing request = HTTP 400 ADT_TM_COMMON_EXCEPTION. Measured empty-TR release: R within the first 2 s poll (attempt 1).

## 4. Remaining engineering backlog (three items)

1. **adt_api.md consolidation** — the file now carries the 11-row
   verified-facts table, modern endpoint sections, and legacy subsections;
   fold the legacy/duplicated blocks into one canonical old→new structure
   (one source of truth per endpoint) without dropping measured status
   codes/dates.
2. **Object-type registry** — replace the ad-hoc `get_object_uri` if/elif
   chain (and its per-type quirks: function needs `--group`, case, vendor
   types) with a declarative type registry (type → URI template, media
   types, group requirement, lock applicability) reused by handlers and
   docs.
3. **`configure` silently resets unspecified fields** — high/security
   (both flip directions of `verify_ssl` are dangerous); only explicitly
   passed flags must update stored values. Details in `known-issues.md`.

The session layer is **out of scope** (rejected, batch 10; see
`design-session-layer-rejected.md` for the re-trigger condition).

### Real-machine verification triggers (still open, tracked in known-issues.md)

These are not engineering tasks but unverified response paths waiting for
the first real capture:

1. Long release paths — RELEASE_UNVERIFIED timeout and a real
   `abortrelapifail` report (replace
   `synthetic/transport.release-report.synthetic.xml`).
2. ABAP Unit `testMethod` counts + ATC priority 1/2/exemptions (replace the
   two synthetic fixtures when QAS/dirty-object captures exist).
3. Non-empty transport tree (`tasks[]` nesting) + ECC legacy shapes.
4. (new) A real **failed activation** to verify the `chkl:messages/msg`
   parser shape (the current `error/message/checkResult` parser is
   unverified for failures; happy path live-verified).

Also queued (documented in summary): quickfix booleans, discovery-based
ATC/Unit reporter expansion, doctor --coverage UI consumption.

## 5. Red lines (do not weaken without explicit approval)

- Two capability gates (`allow_write`, `allow_transport`) + per-operation
  `[y/N]`; confirmations are one-shot, never cached/reused.
- `environment=prd` (inferred or explicit) hard-refuses every write; no
  flag/global/env override. Env-path writes require explicit SAP_ENVIRONMENT.
- run-sql: SELECT only, DML rejected before HTTP. dangerous/critical Unit
  = write semantics (gate + risk-specific prompt).
- write-source uses the measured stateful protocol (`_action=LOCK`,
  `?lockHandle=` PUT, `_action=UNLOCK`) and always unlocks in `finally`;
  lock handles never logged (progress line shows a short hash only).
- **Write-side 2xx is "accepted", never "completed"** — release, activate
  and unlock all require an independent readback; a foreign-context unlock
  200 is a measured silent no-op (adt_api.md top rule).
- Errors are JSON envelopes with the closed code set; Click usage errors
  stay plain text. `--yes` only by explicit user instruction.
- Passwords in keystore only; fixtures via sanitizer, synthetic/ separated
  and excluded from golden/byte regression; no host/user/business data.

## 6. Conditional follow-ups (triggered, not scheduled)

- First real **testMethod** AUnit response → verify
  `synthetic/unit.methods.synthetic.xml` paths; honor `unparsed_nodes`.
- First real **ATC priority 1/2 or exemption** → verify
  `synthetic/atc.priorities.synthetic.xml`.
- First **populated/slow release** → verify release report + polling;
  RELEASE_UNVERIFIED means manual SE09/SE10, never auto re-release.
- First real **failed activation** → verify `chkl:messages/msg` +
  `ioc:inactiveObjects` parser paths (known-issues); until then always
  confirm activations by readback, not 200.
- Requirement to **hold locks across processes** (long transaction,
  interactive multi-process edit) → reopen the archived session-layer
  design (`design-session-layer-rejected.md`) and re-verify protocol
  facts 8–11 on the target release first.
- Basis upgrade → re-probe usageReferences content type and Unit config
  versions (currently v4, fallback application/*).
- New command/kind/error code → update SKILL.md tables; check_contract
  fails until docs/code agree.
