# Changelog

## [1.2.0] — 2026-05-26

### Fixed

- **Online Transport Mode — proactive auto-collection**: The SKILL now proactively runs `scripts/tr_collector.py collect {TR_ID} --output-dir reports/{TR_ID}_package/` using available shell tools when a TR ID is identified and no pre-assembled package exists. Previously, the SKILL waited passively for the user to run the script. Fallback to Offline Local Mode is triggered only when credentials are absent, the connection fails, or shell execution is unavailable.

- **TR subdirectory always created**: Reports are now saved to `reports/{TR_ID}_package/` in all review modes (Online Transport, Offline Package, Offline Local). Previously, Offline Local Mode saved directly to `reports/`, breaking the TR-scoped artifact grouping. The subdirectory is created automatically; users are never asked to create it manually.

- **Required Actions (§6) scope restricted to human-only items**: The `§6 Required Actions Before Release` section of the report now explicitly excludes SKILL-executable tasks. Object list retrieval and source code fetching via `tr_collector.py` must not appear as Required Actions. Only tasks requiring human intervention (code fixes, manual test execution, UAT sign-off, business approval, prerequisite TR deployment) are listed. A SKILL BOUNDARY note was added to `references/report-format.md §1 Section 6` and `references/human-loop.md §6` to enforce this rule.

- **`human-loop.md §1.3` — object list removed as human trigger**: Object list retrieval is a SKILL responsibility (auto-fetched via `tr_collector.py`), not a human confirmation trigger. Removed from the Evidence-Based Triggers table. Syntax check remains a human trigger for Offline modes with a clarification that Online Transport Mode should attempt ADT fetch first.

- **Required Actions vs. Human Confirmation boundary documented**: Added `references/human-loop.md §6` — a new section that clearly defines the difference between `§6 Required Actions` (human performs an action) and `§7 Human Confirmation Checklist` (human signs off on a finding), preventing AI from conflating the two.

### Changed

- `references/report-format.md §3 Save Location`: Replaced conditional two-rule layout with a single always-create-subdir rule keyed on review mode.
- `references/review-modes.md §1.3 Online Transport Mode flow`: Step 2 changed from "tell user what to collect, wait for evidence" to "proactively run `tr_collector.py collect`; degrade to Offline Local Mode on failure."
- All patched `references/*.md` headers bumped from `v1.0.0` to `v1.2.0`.

---

## [1.1.0] — 2026-05-26

### Added

- **Step 0.5 — TR ID Extraction**: Scan input for a Transport Request ID (pattern: 3–4 uppercase letters + K + 6 digits) before proceeding. Ask the user if none is found. Cap Evidence Level at LOW if no TR ID exists.
- **Step 1 — Credential Verification Block**: When Online Transport Mode is detected, explicitly check credential availability and handle two failure cases: (1) no credentials found → guide setup via `.env` or interactive configure; (2) credentials configured but connection fails → fall back to Offline Local Mode with a link to `references/sap-connectivity.md §11`.
- **Step 1.5 — Review Scope Selection**: Human-in-the-loop confirmation before review begins. User selects (A) Code Quality Review or (B) Functional + Code Quality Review. Option B requires a functional specification; if absent, prompt for one or record an `EVIDENCE_GAP HIGH` finding and restrict the decision accordingly.
- **`references/sap-connectivity.md §11` — Local File Fallback Guide**: Step-by-step export guide for when SAP connection fails. Covers SE01 → SE38/SE24/SE37 export workflow by object type, expected directory structure, `object_list.txt` format, and Evidence Level table for manual export results.
- **`references/report-format.md §9.1` — Object List Summary marked mandatory**: Every report must include a complete object list in Appendix §9.1, listing every TR object by type, name, and whether its source was reviewed.

### Changed

- Step sequence updated: Step 0 → **Step 0.5** → Step 1 → **Step 1.5** → Step 2–7. All existing steps preserved; new steps are additive.

---

## [1.0.0] — 2026-05-20

Initial release.

### Features

- **3 review modes**: Offline Package Mode (preferred), Offline Local Mode, Online Transport Mode via `tr_collector.py` CLI
- **10 review dimensions**: Code Quality, Performance, Security, Authorization, Transaction Consistency, Integration Impact, Transport Completeness, Functional Alignment, Release Readiness, Evidence Gap
- **Evidence Level framework**: HIGH / MEDIUM / LOW / UNKNOWN with strict GO gates (LOW evidence blocks GO and CONDITIONAL_GO)
- **Release Decision Policy**: GO / CONDITIONAL_GO / NO_GO / NEED_MORE_EVIDENCE with non-negotiable rules
- **`scripts/tr_collector.py` CLI**: `configure`, `ping`, `collect` commands; 3-level credential priority (`.env` → `~/.sap-transport-gate/config.json` → env vars); E071 fallback when `/objects` ADT endpoint returns 404
- **10 reference files**: `review-modes.md`, `review-dimensions.md`, `decision-policy.md`, `report-format.md`, `abap-security-rules.md`, `abap-quality-rules.md`, `abap-report-template.md`, `sap-connectivity.md`, `human-loop.md`, `regression-tests.md`
- **Hard constraints**: No SAP login, no transport execution, no evidence fabrication, Evidence Level LOW → no GO
