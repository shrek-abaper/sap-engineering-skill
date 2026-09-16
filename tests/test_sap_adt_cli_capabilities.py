"""Batch 7: discovery capabilities parser and coverage matrix (offline)."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "sap-adt-cli" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib.parsers import capabilities  # noqa: E402
from lib import coverage as cov  # noqa: E402
from test_sap_adt_cli_config import load_cli_module  # noqa: E402

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<app:service xmlns:app="http://www.w3.org/2007/app"
             xmlns:atom="http://www.w3.org/2005/Atom">
 <app:workspace><atom:title>x</atom:title>
  <app:collection href="/sap/bc/adt/checkruns">
    <atom:title>Check</atom:title>
  </app:collection>
  <app:collection href="/sap/bc/adt/ddic/tables">
    <atom:title>Tables</atom:title>
    <app:accept>application/vnd.sap.adt.tables.v2+xml</app:accept>
    <app:accept>text/html</app:accept>
  </app:collection>
  <app:collection href="/sap/bc/adt/atc/checks">
    <atom:title>ATC Checks</atom:title>
    <app:accept>application/vnd.sap.adt.chkov1+xml</app:accept>
  </app:collection>
  <app:collection href="https://host.example/sap/bc/adt">
    <atom:title>Root</atom:title>
  </app:collection>
 </app:workspace>
</app:service>"""


class CapabilitiesParserTests(unittest.TestCase):
    def test_parse_collections(self):
        data = capabilities.parse(ATOM)
        c = {x["href"]: x for x in data["collections"]}
        self.assertEqual(c["/sap/bc/adt/checkruns"]["content_types"], [])
        self.assertEqual(
            c["/sap/bc/adt/ddic/tables"]["content_types"],
            ["application/vnd.sap.adt.tables.v2+xml", "text/html"],
        )
        self.assertEqual(c["/sap/bc/adt/ddic/tables"]["title"], "Tables")
        self.assertEqual(len(data["collections"]), 4)


class CoverageComputeTests(unittest.TestCase):
    def setUp(self):
        self.collections = capabilities.parse(ATOM)["collections"]

    def test_buckets(self):
        r = cov.compute_coverage(self.collections)
        # syntax-check requires /checkruns (present); get-table /ddic/tables
        self.assertIn("syntax-check", r["implemented_available"])
        self.assertIn("get-table", r["implemented_available"])
        # run-sql/where-used/resources absent in this minimal doc
        self.assertIn("run-sql", r["covered_not_available"])
        self.assertIn("where-used", r["covered_not_available"])
        # ATC present but no command uses it -> uncovered, grouped under /atc
        unc = r["available_not_covered"]
        atc = next(g for g in unc["groups"] if g["prefix"] == "/atc")
        self.assertEqual(atc["count"], 1)
        self.assertIn("/sap/bc/adt/atc/checks", atc["examples"])
        self.assertEqual(unc["total"], len(unc["collections"]))

    def test_absolute_href_grouped_without_host_in_examples(self):
        r = cov.compute_coverage(self.collections)
        root = next(g for g in r["available_not_covered"]["groups"]
                    if g["prefix"] == "(service root)")
        self.assertEqual(root["examples"], ["<system base URL>"])

    def test_local_commands_counted_separately(self):
        r = cov.compute_coverage(self.collections)
        self.assertEqual(r["local_commands"], len(cov.LOCAL_COMMANDS))
        self.assertNotIn("status", cov.COMMAND_CAPABILITIES)


class DiscoveryCliTests(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()

        class FakeResponse:
            content = ATOM
            text = ATOM.decode()

        class FakeConfig:
            def base_url(self):
                return "https://sap-dev.example.com:8000"

        self.handlers = sys.modules["lib.handlers"]
        p = patch.object(self.handlers, "get_config", return_value=FakeConfig())
        p.start()
        self.addCleanup(p.stop)
        p2 = patch.object(self.handlers, "make_adt_request", return_value=FakeResponse())
        p2.start()
        self.addCleanup(p2.stop)

    def test_discovery_envelope(self):
        r = CliRunner().invoke(self.cli.cli, ["discovery"])
        self.assertEqual(r.exit_code, 0, r.output)
        d = json.loads(r.output)
        self.assertEqual(d["kind"], "capabilities")
        self.assertEqual(d["meta"]["row_count"], 4)

    def test_emit_markdown_writes_table(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "discovery.md")
            r = CliRunner().invoke(
                self.cli.cli, ["discovery", "--emit-markdown", path]
            )
            self.assertEqual(r.exit_code, 0, r.output)
            text = open(path, encoding="utf-8").read()
        self.assertIn("GENERATED", text)
        self.assertIn("/sap/bc/adt/checkruns", text)
        self.assertIn("application/vnd.sap.adt.tables.v2+xml", text)
        # empty accept -> em dash placeholder
        self.assertIn("/sap/bc/adt/checkruns` | Check | — |", text)

    def test_doctor_coverage_json(self):
        r = CliRunner().invoke(
            self.cli.cli,
            ["--format", "json", "credentials", "doctor", "--coverage"],
        )
        self.assertEqual(r.exit_code, 0, r.output)
        d = json.loads(r.output)
        self.assertIn("implemented_available", d)
        self.assertIn("available_not_covered", d)
        self.assertIn("covered_not_available", d)
        self.assertIn("run-sql", d["covered_not_available"])


if __name__ == "__main__":
    unittest.main()
