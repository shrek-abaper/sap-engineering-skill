# Synthetic ADT fixtures (NOT real captures)

Files with a `.synthetic.xml` suffix here are **hand-constructed** from the
`abap-adt-api` client structure (github.com/marcellourbani/abap-adt-api),
not observed on a real SAP system. They exist only to exercise parser paths
the capture DEV system could not produce (e.g. an AUnit run with executed
`testMethod` nodes).

Rules:

- never used by the batch-6 byte-level `--format xml`/golden regression;
- skipped by `sanitize.py` (no real data to redact);
- when the first REAL response containing these nodes arrives, every field
  path MUST be verified against it and the synthetic fixture corrected to
  match reality. Background: `../../../docs/known-issues.md` (AUnit verification trigger).
