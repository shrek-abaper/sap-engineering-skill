"""Batch 2 tests for the pure ADT payload parsers.

Fully offline: parsers read only the sanitized fixtures under
skills/sap-adt-cli/tests/fixtures/ and are compared against golden/*.json.
No HTTP, config or clock access anywhere in lib/parsers.
"""
import ast
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "sap-adt-cli" / "scripts"
FIXTURES = ROOT / "skills" / "sap-adt-cli" / "tests" / "fixtures"
GOLDEN = FIXTURES / "golden"

sys.path.insert(0, str(SCRIPTS))

from lib.parsers import (  # noqa: E402
    common,
    fields,
    findings,
    objects,
    records,
    rows,
    scalar,
    source,
)

# (parser module, input fixture, golden file)
GOLDEN_CASES = [
    (fields, "get-table.VBAK.s4hana.xml", "fields.VBAK.json"),
    (fields, "get-table.T001.s4hana.xml", "fields.T001.json"),
    (fields, "get-structure.VBAKKOM.s4hana.xml", "fields.VBAKKOM.json"),
    (objects, "search-object.CL_GUI_WILDCARD.xml", "objects.search-hits.json"),
    (objects, "search-object.empty.xml", "objects.search-empty.json"),
    (objects, "get-package.SABP_UNIT.asxml.xml", "objects.package.json"),
    (rows, "run-sql.t100.raw.xml", "rows.t100.json"),
    (records, "list-transports.empty.xml", "records.empty.json"),
    (findings, "syntax-check.CL_GUI.clean.xml", "findings.clean.json"),
    (findings, "syntax-check.SAPMV45A.warnings.xml", "findings.warnings.json"),
    (scalar, "get-type-info.MATNR.dtel.xml", "scalar.typeinfo-matnr.json"),
    (scalar, "get-type-info.MATNR18.dtel.xml", "scalar.typeinfo-matnr18.json"),
    (scalar, "get-type-info.CHAR10.domain.xml", "scalar.domain-char10.json"),
    (scalar, "get-transaction.VA01.xml", "scalar.transaction-va01.json"),
]


class GoldenParserTests(unittest.TestCase):
    def test_all_goldens_match(self):
        covered = set()
        for module, fixture_name, golden_name in GOLDEN_CASES:
            with self.subTest(golden=golden_name):
                payload = (FIXTURES / fixture_name).read_bytes()
                expected = json.loads((GOLDEN / golden_name).read_text(encoding="utf-8"))
                self.assertEqual(module.parse(payload), expected)
                covered.add(golden_name)
        # Guard against orphan goldens left behind after renames.
        on_disk = {p.name for p in GOLDEN.glob("*.json")}
        self.assertEqual(on_disk - covered, {"source.get-class.json"})

    def test_source_is_verbatim_and_line_counted(self):
        raw = (FIXTURES / "get-class.CL_GUI_FRONTEND_SERVICES.abap").read_bytes()
        out = source.parse(raw)
        self.assertEqual(out["source"].encode("utf-8"), raw,
                         "source parse must be byte-for-byte reversible")
        golden = json.loads((GOLDEN / "source.get-class.json").read_text())
        self.assertEqual(out["line_count"], golden["line_count"])
        self.assertEqual(
            hashlib.sha256(out["source"].encode("utf-8")).hexdigest(),
            golden["source_sha256"],
        )
        # CRLF wire endings survive untouched (text-mode redirection depends on it)
        self.assertIn("\r\n", out["source"])


class EmptyResultTests(unittest.TestCase):
    def test_empty_search_is_success_shape(self):
        out = objects.parse((FIXTURES / "search-object.empty.xml").read_bytes())
        self.assertEqual(out, {"objects": []})

    def test_empty_transport_tree(self):
        out = records.parse((FIXTURES / "list-transports.empty.xml").read_bytes())
        self.assertEqual(out, {"transports": []})

    def test_clean_syntax_check(self):
        out = findings.parse((FIXTURES / "syntax-check.CL_GUI.clean.xml").read_bytes())
        self.assertEqual(out, {"findings": []})

    def test_rows_rectangular_pivot(self):
        out = rows.parse((FIXTURES / "run-sql.t100.raw.xml").read_bytes())
        self.assertEqual(len(out["columns"]), 3)
        self.assertEqual(len(out["rows"]), 5)
        self.assertTrue(all(len(r) == 3 for r in out["rows"]))

    def test_findings_carry_line_and_normalized_severity(self):
        out = findings.parse(
            (FIXTURES / "syntax-check.SAPMV45A.warnings.xml").read_bytes()
        )
        self.assertTrue(out["findings"])
        for f in out["findings"]:
            self.assertIn(f["severity"], {"error", "warning", "info"})
            self.assertIsInstance(f["line"], int)
            self.assertIn("#start=", f["uri"])


class ParseErrorTests(unittest.TestCase):
    def test_malformed_xml_raises_parse_error(self):
        for module in (objects, rows, records, findings, scalar, fields):
            with self.subTest(module=module.__name__):
                with self.assertRaises(common.ParseError):
                    module.parse(b"<?xml version='1.0'?><unclosed>")

    def test_unknown_root_raises(self):
        bogus = b'<?xml version="1.0"?><somethingElse xmlns="x"/>'
        with self.assertRaises(common.ParseError):
            objects.parse(bogus)
        with self.assertRaises(common.ParseError):
            rows.parse(bogus)
        with self.assertRaises(common.ParseError):
            scalar.parse(bogus)

    def test_older_field_xml_explicitly_rejected_for_now(self):
        # Batch 3 adds field-metadata XML once an ECC fixture exists.
        with self.assertRaises(common.ParseError):
            fields.parse(b'<?xml version="1.0"?><fields><field name="MANDT"/></fields>')

    def test_garbage_ddl_raises(self):
        with self.assertRaises(common.ParseError):
            fields.parse(b"define structure x { no closing brace")


FORBIDDEN_IMPORTS = {
    "requests", "urllib3", "http", "http.client", "socket",
    "lib.client", "lib.config", "lib.handlers", "lib.credentials",
}


class ParserPurityTests(unittest.TestCase):
    def test_parsers_use_only_stdlib_and_common(self):
        pkg = SCRIPTS / "lib" / "parsers"
        for path in pkg.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                    self.assertFalse(
                        FORBIDDEN_IMPORTS & set(names),
                        f"{path.name} imports forbidden module",
                    )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    root = node.module.split(".")[0]
                    self.assertNotIn(
                        root, FORBIDDEN_IMPORTS,
                        f"{path.name} imports {node.module}",
                    )
                    if node.module.startswith("lib") and node.module != "lib.parsers.common":
                        self.fail(f"{path.name} may only import lib.parsers.common")


if __name__ == "__main__":
    unittest.main()
