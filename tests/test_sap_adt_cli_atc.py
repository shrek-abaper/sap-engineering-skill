"""Batch 8: ATC parser/command tests.

Real priority-3 worklist is tests/fixtures/atc.findings.xml. Priority
1/2 and exemption mapping is exercised only via synthetic fixture.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "skills" / "sap-adt-cli" / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "skills" / "sap-adt-cli" / "scripts"))

from lib.parsers import findings  # noqa: E402
from test_sap_adt_cli_config import load_cli_module  # noqa: E402


class AtcParserRealTests(unittest.TestCase):
    def test_priority3_real_worklist(self):
        d = findings.parse_atc((FIXTURES / "atc.findings.xml").read_bytes())
        m = d["_meta"]
        self.assertEqual(m["total"], 2)
        self.assertEqual(m["by_priority"], {"1": 0, "2": 0, "3": 2})
        self.assertFalse(m["result_incomplete"])
        for f in d["findings"]:
            self.assertEqual(f["severity"], "info")
            self.assertEqual(f["check_id"], "B40F4951BF4DA9EA0C414354BF505AC7")
            self.assertEqual(f["message_id"], "UNCLEAR")
            self.assertTrue(f["text"].startswith("Search problematic"))


class AtcParserSyntheticTests(unittest.TestCase):
    def setUp(self):
        self.d = findings.parse_atc(
            (FIXTURES / "synthetic" / "atc.priorities.synthetic.xml").read_bytes()
        )

    def test_priority_mapping_and_identifiers(self):
        sev = [f["severity"] for f in self.d["findings"]]
        self.assertEqual(sev, ["error", "warning", "warning"])
        m = self.d["_meta"]
        self.assertEqual(m["by_priority"], {"1": 1, "2": 2, "3": 0})
        self.assertEqual(self.d["findings"][0]["message_id"], "ERR01")
        self.assertEqual(self.d["findings"][0]["line"], 10)
        self.assertEqual(self.d["findings"][0]["source_severity"], "1")

    def test_exemption_counted_but_kept_in_full_totals(self):
        m = self.d["_meta"]
        self.assertEqual(m["exempted_count"], 1)
        exempt = [f for f in self.d["findings"] if f.get("exempted")]
        self.assertEqual(len(exempt), 1)
        # counts are full (3), not 3 - 1
        self.assertEqual(m["total"], 3)

    def test_unknown_priority_defaults_to_info_with_unparsed_entry(self):
        xml = (FIXTURES / "synthetic" / "atc.priorities.synthetic.xml").read_text()
        xml = xml.replace('priority="1"', 'priority="9"')
        d = findings.parse_atc(xml.encode())
        self.assertEqual(d["findings"][0]["severity"], "info")
        self.assertIn("finding@priority=9", d["_meta"]["unparsed_nodes"])


class AtcCommandTests(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()
        self.handlers = sys.modules["lib.handlers"]
        worklist = b"F79WORKLISTGUID0000000000000000000"
        run = (
            b'<?xml version="1.0"?><atcworklist:worklistRun '
            b'xmlns:atcworklist="http://www.sap.com/adt/atc/worklist">'
            b'<atcworklist:worklistId>W</atcworklist:worklistId>'
            b'<atcworklist:worklistTimestamp>1970-01-01T00:00:00Z'
            b'</atcworklist:worklistTimestamp></atcworklist:worklistRun>'
        )
        self.payload = (FIXTURES / "atc.findings.xml").read_bytes()

        class R:
            def __init__(self, content, text=None):
                self.content = content
                self.text = text if text is not None else content.decode()

        calls = []

        def fake(url, method="GET", **kw):
            calls.append((method, url))
            if url.endswith("/worklists"):
                return R(worklist)
            if "/atc/runs" in url:
                return R(run)
            return R(self.payload)

        class FakeConfig:
            def base_url(self):
                return "https://sap-dev.example.com:8000"

        p = patch.object(self.handlers, "get_config", return_value=FakeConfig())
        p.start(); self.addCleanup(p.stop)
        p2 = patch.object(self.handlers, "make_adt_request", side_effect=fake)
        p2.start(); self.addCleanup(p2.stop)
        self.calls = calls

    def test_run_atc_envelope(self):
        r = CliRunner().invoke(self.cli.cli, ["run-atc", "ZCL_JSON_TEST"])
        self.assertEqual(r.exit_code, 0, r.output)
        d = json.loads(r.output)
        self.assertEqual(d["kind"], "findings")
        self.assertEqual(d["meta"]["total"], 2)
        # worklist -> run -> one worklist GET
        methods = [c[0] for c in self.calls]
        self.assertEqual(methods, ["POST", "POST", "GET"])

    def test_fail_on_error_silent_for_priority3(self):
        r = CliRunner().invoke(self.cli.cli, ["run-atc", "ZCL_JSON_TEST",
                                             "--fail-on", "error"])
        self.assertEqual(r.exit_code, 0, r.output)

    def _invoke_with_payload(self, payload_bytes, *args):
        class R:
            def __init__(self, c):
                self.content = c
                self.text = c.decode(errors="replace")

        def fake(url, method="GET", **kw):
            if url.endswith("/worklists"):
                return R(b"GUID")
            if "/atc/runs" in url:
                return R(b"<run/>")
            return R(payload_bytes)

        with patch.object(self.handlers, "make_adt_request", side_effect=fake):
            return CliRunner().invoke(self.cli.cli, ["run-atc", "ZCL_DEMO", *args])

    def test_fail_on_error_exits_1_on_priority1(self):
        payload = (FIXTURES / "synthetic" / "atc.priorities.synthetic.xml").read_bytes()
        r = self._invoke_with_payload(payload, "--fail-on", "error")
        self.assertEqual(r.exit_code, 1, r.output)

    def test_exempted_priority1_does_not_fail(self):
        xml = (FIXTURES / "synthetic" / "atc.priorities.synthetic.xml").read_text()
        # mark the priority-1 finding (which already declares exemptionKind) exempt
        marker = 'atcfinding:priority="1"'
        head, tail = xml.split(marker, 1)
        tail = tail.replace('atcfinding:exemptionKind=""',
                            'atcfinding:exemptionKind="A"', 1)
        xml2 = head + marker + tail
        r = self._invoke_with_payload(xml2.encode(), "--fail-on", "error")
        # non-exempted findings are priority 2: fail-on=error stays 0
        self.assertEqual(r.exit_code, 0, r.output)


if __name__ == "__main__":
    unittest.main()
