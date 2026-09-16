# Batch 10 design — cross-process session layer (REJECTED before implementation)

**Status: REJECTED 2026-09-17, before any product code for the session layer
was written.** The rejection is based on **measured evidence**, not priority.
The full approved design is archived below in case a future requirement
reopens it; the protocol fixes uncovered during verification shipped instead
(see `../references/adt_api.md` facts 8–12).

## Why it was proposed

Hypothesis: `write-source` ends with `finally` unlock, so a later
**separate-process** `activate` had no lock/session and "must fail" — the
first persistent state file in the project (cookie jar, CSRF token, lock
handles) was proposed to share stateful sessions across processes.

## Measured verdict (S/4HANA 2021 / SAP_BASIS 7.56, DEV400 client 400)

Real four-phase experiment on a throw-away `$TMP` program
`Z_ADT_SESSION_PROBE` (baseline Active → write-source → separate-process
activate → readback):

- **The gap does not exist.** After write-source unlocks, a brand-new
  process activates successfully: `POST /activation?method=activate` 200,
  readback confirms the object leaves `/activation/inactiveobjects` and
  `adtcore:version` returns to `active`. ADT activation requires **no lock
  and no shared stateful session**.
- What actually failed was the write protocol itself (never live-verified
  before): lock/PUT/unlock/activate all used shapes the server rejects —
  fixed in the protocol commit; the session layer was solving nothing.
- Orphaned stateful-session locks **self-heal**: a crash-simulated enqueue
  was absent from SM12 the next morning (server-side stateful context
  timeout). Building lock *visibility* would therefore address a problem
  that resolves itself.

Two measured facts that govern any future design:

1. **Unlock 2xx ≠ unlocked.** `POST {object}?_action=UNLOCK` returns 200
   with an empty body even from a foreign stateful context while releasing
   nothing (the next `_action=LOCK` still gets 403 "currently editing").
   `lockedByEditor="false"` is per-session state, not SM12 truth. Release is
   real only (a) inside the owning stateful session, or (b) from another
   process that replays the **original cookie jar** plus the handle — the
   crash-lock → cookie-restore → unlock → fresh LOCK 200 cycle proved both
   directions.
2. **Cookies observed under Basic auth**: `SAP_SESSIONID_ECD_400`,
   `sap-contextid`, `sap-usercontext` — **no `MYSAPSSO2`**. The original
   design's persistence whitelist missed `sap-contextid`/`sap-usercontext`;
   without them cross-process reattachment cannot work.

Decision: do not add the project's first persistent credential-bearing file
(cookies are equivalent to credentials) to gain visibility into a
self-healing problem. All batch-10 machinery below — `session-*.json`,
`locks[]`, triple validation, orphan recovery, `stale_contexts`,
`--discard-local` — is shelved with it.

## Re-trigger condition

Take this document off the shelf ONLY when a real requirement appears to
**hold an enqueue across processes**, e.g.:

- a long transaction whose lifetime exceeds one CLI invocation;
- an interactive editing session where one process locks and a different
  process writes/activates under the same lock;
- explicit operator demand for crash-recovery of locks instead of waiting
  for server-context timeout.

When that happens, re-run the step-0 experiment on the target release
first: protocol shapes (facts 8–11) and the timeout behavior are
release-specific.

---

## Archived design as approved (2026-09-16, seven points + two mandated changes)

### Governing principle

A lock handle on disk **never authorizes a write**. Each write command
re-enqueues in its own process (`_action=LOCK` → fresh handle → PUT →
`finally` unlock). Persisted handles exist only for `status` visibility and
best-effort recovery in `session end`; the time/pid/cookie-fingerprint
triple classifies recovery candidates, never grants PUT rights.

### 1. Persistence

`~/.sap-adt-cli/session-<profile>.json`, 0600, directory 0700, atomic
tmp+`os.replace`, `flock` sidecar for inter-process exclusion
(non-interactive local contention → LOCKED_BY_OTHER with a message that
distinguishes *local process* from *SAP-side foreign lock*; agents handle
those differently: wait/end vs. find the owner). Top level:
`schema_version`, `identity{base_url,client,username,cred_epoch}`,
`cookies` (whitelist; on 7.56 Basic auth that is SAP_SESSIONID_*,
sap-contextid, sap-usercontext — not MYSAPSSO2), `csrf_token`,
`owner{pid,started_at,hostname,command}`, timestamps, and `locks[]`
records `{object_type,object_name,object_uri,handle,handle_sha256,
acquired_at,acquired_by_pid,jar_fingerprint,transport,unlock_attempts,
last_error}`.

### 2. Security

Plaintext 0600 accepted (same trust boundary as `config.json`); keystore
rejected because headless Linux often has no vault and the file backend's
passphrase requirement defeats unattended cross-process reuse, and keyring
has no atomic multi-key document semantics. Cookies/token/handles must
never appear in `-v`, tracebacks, `status`, `doctor`, or CLI progress
(the pre-batch echo of the raw handle in the write-source progress line was
a red-line violation and is fixed). Corrupt JSON → quarantine to
`.corrupt-<ts>`; wrong mode → refuse, never silent chmod; identity mismatch
→ quarantine + SM12 warning.

### 3. Failure paths

Crash (pid + start-time liveness; lock survives server-side until context
timeout — measured); server stateful timeout (local soft 600 s / hard
1800 s provisional idle thresholds, actual Basis parameters unmeasured;
authoritative detection is the write-time LOCK response); lock stolen or
SM12-deleted (no cheap positive probe — never send speculative unlocks,
learn only at LOCK/UNLOCK time); two processes (flock + owner identity);
profile/credential switch (filename per profile + identity/cred_epoch
check).

### 4. Hard red line

Never silently PUT with a suspect handle. PUT accepts only a handle from a
LOCK in the same process; a non-2xx LOCK aborts before any PUT. Thresholds
600/1800 s provisional, constants marked unverified.

### 5. Commands

`adt session begin|status|end` (would be commands 35–37). `status`: purely
local, zero HTTP, lists every recorded lock (object, acquired time, owner
liveness, handle fingerprint). `end`: refuses while a live owner holds the
flock; replays each unlock (cookie jar + handle); deletes the file only
when every unlock is confirmed; failures stay on disk with attempts and a
SM12 report. Write commands auto-manage session lifecycle; reads never
touch the file.

### 6. Error codes

No new codes (set stays at 18): local contention and write-time 403 →
LOCKED_BY_OTHER with distinguishable messages; corrupt/insecure file →
CONFIG_MISSING; CSRF unchanged.

### Mandated change A — never discard an expired context

Before overwriting top-level cookies while `locks[]` is non-empty, archive
the whole context into `stale_contexts[]`
(`{cookies,csrf_token,jar_fingerprint,archived_at,locks[]}`); `session end`
tries unlocks across the active context and all stale contexts; `status`
shows their locks as `(stale context)`; >N contexts or >24 h prompts SM12
cleanup. Rationale: local expiry is not server-side death — dropping the
cookies makes recovery impossible.

### Mandated change B — non-interactive local discard

Interactive: `[y/N]`; non-interactive: `session end --discard-local`
(name states it clears local state only), printing every discarded lock
(object + handle fingerprint) with the SM12 possible-leak warning, exit 0,
`meta.locks_possibly_leaked: N`. Without it an unrecoverable file would
permanently block every later write for the profile in agent environments.

### Offline test plan (shelved)

Atomic/0600 persistence, corruption quarantine, identity/epoch mismatch,
clock-injected thresholds, simulated crash + recovery unlock, flock
contention, the "PUT never receives a disk handle" red-line regression,
and redaction of cookie/ticket/handle in every diagnostic surface.
