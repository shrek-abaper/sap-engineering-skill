"""Batch 9.2: release-transport readback, --dry-run, new error codes."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "sap-adt-cli" / "scripts"))

from lib import errors  # noqa: E402
from test_sap_adt_cli_config import load_cli_module  # noqa: E402


def _env(r):
    t = r.output
    return json.loads(t[t.find("{"):])


TR_D = """<?xml version="1.0" encoding="utf-8"?>
<tm:root xmlns:tm="http://www.sap.com/cts/adt/tm" xmlns:adtcore="http://www.sap.com/adt/core">
 <tm:request tm:number="DEVK900001" tm:owner="DEVELOPER" tm:status="D" tm:desc="Dry run TR"/>
</tm:root>"""

TR_R = TR_D.replace('tm:status="D"', 'tm:status="R"')

RELEASE_OK = """<?xml version="1.0" encoding="utf-8"?>
<tm:root xmlns:tm="http://www.sap.com/cts/adt/tm" xmlns:chkrun="http://www.sap.com/adt/checkrun">
 <tm:releasereports>
  <chkrun:checkReport chkrun:reporter="abapCheckRun" chkrun:status="released" chkrun:statusText="Released"/>
 </tm:releasereports>
</tm:root>"""

RELEASE_FAIL = """<?xml version="1.0" encoding="utf-8"?>
<tm:root xmlns:tm="http://www.sap.com/cts/adt/tm" xmlns:chkrun="http://www.sap.com/adt/checkrun">
 <tm:releasereports>
  <chkrun:checkReport chkrun:reporter="abapCheckRun" chkrun:status="abortrelapifail" chkrun:statusText="Failed">
   <chkrun:checkMessageList>
    <chkrun:checkMessage chkrun:type="E" chkrun:shortText="ATC error"/>
   </chkrun:checkMessageList>
  </chkrun:checkReport>
 </tm:releasereports>
</tm:root>"""


class ErrorCodeTests(unittest.TestCase):
    def test_closed_set_has_eighteen_and_exit_1(self):
        self.assertEqual(len(errors.ALL_CODES), 18)
        for code in (errors.RELEASE_UNVERIFIED, errors.RELEASE_REJECTED):
            self.assertIn(code, errors.ALL_CODES)
            self.assertEqual(errors.EXIT_CODE_MAP[code], 1)
        self.assertIn("Do NOT re-release", errors.DEFAULT_HINTS[errors.RELEASE_UNVERIFIED])


class ReleaseHandlerTests(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()
        self.handlers = sys.modules["lib.handlers"]

        class FakeConfig:
            profile_name = "dev"
            username = "DEVELOPER"
            environment = "dev"
            environment_source = "inferred"
            from_environment = False
            allow_write = True
            allow_transport = True
            write_source = "profile"
            transport_source = "profile"
            is_production = False
            env_write_requested = False
            env_transport_requested = False

            def base_url(self):
                return "https://sap-dev.example.com:8000"

        self.cfg = FakeConfig()

    def _patch_requests(self, responses):
        # responses keyed by URL fragment; callable receives (url, method)
        calls = []

        class R:
            def __init__(self, content, headers=None):
                self.content = content if isinstance(content, bytes) else content.encode()
                self.text = self.content.decode()
                self.headers = headers or {}

        def fake(url, method="GET", **kw):
            calls.append((method, url))
            return R(responses(url, method))

        return calls, patch.object(self.handlers, "make_adt_request", side_effect=fake), \
            patch.object(self.handlers, "get_config", return_value=self.cfg)

    def test_dry_run_does_not_post(self):
        def resp(url, method):
            self.assertEqual(method, "GET")
            return TR_D
        calls, pm, pc = self._patch_requests(resp)
        pc.start(); pm.start()
        self.addCleanup(pc.stop); self.addCleanup(pm.stop)
        r = self.handlers.release_transport("DEVK900001", dry_run=True)
        self.assertFalse(r.is_error)
        self.assertTrue(r.meta["dry_run"])
        self.assertTrue(r.meta["release_possible"])
        self.assertEqual(r.data["transport"]["status"], "D")
        self.assertTrue(all(m == "GET" for m, _ in calls))

    def test_nonexistent_tr_is_object_not_found(self):
        # Transport organizer reports missing requests as HTTP 400
        # ADT_TM_COMMON_EXCEPTION, not 404.
        from lib.client import AdtHttpError
        def fake(url, method="GET", **kw):
            raise AdtHttpError(
                "HTTP 400: Task/request DEVK999999 does not exist in system ECD",
                status=400)
        with patch.object(self.handlers, "get_config", return_value=self.cfg), \
                patch.object(self.handlers, "make_adt_request", side_effect=fake):
            r = self.handlers.release_transport("DEVK999999", dry_run=True)
        self.assertTrue(r.is_error)
        self.assertEqual(r.error_code, errors.OBJECT_NOT_FOUND)

    def test_dry_run_invalid_trkorr(self):
        calls, pm, pc = self._patch_requests(lambda u, m: TR_D)
        pc.start(); pm.start()
        self.addCleanup(pc.stop); self.addCleanup(pm.stop)
        r = self.handlers.release_transport("BAD")
        self.assertTrue(r.is_error)
        self.assertEqual(r.error_code, errors.BAD_REQUEST)

    def test_release_polls_until_R(self):
        # Initial preflight GET -> D; poll 1 -> D; poll 2 -> R
        gets = {"n": 0}

        def resp(url, method):
            if method == "POST":
                return RELEASE_OK
            gets["n"] += 1
            return TR_R if gets["n"] >= 3 else TR_D

        calls, pm, pc = self._patch_requests(resp)
        pc.start()
        pm.start()
        self.addCleanup(pc.stop); self.addCleanup(pm.stop)
        r = self.handlers.release_transport(
            "DEVK900001", sleep=lambda s: None, poll_interval=0)
        self.assertFalse(r.is_error, r.text)
        self.assertEqual(r.data["transport"]["status"], "R")
        self.assertEqual(r.meta["poll_attempts"], 2)
        self.assertIn("POST", [m for m, _ in calls])

    def test_release_report_failure_is_rejected(self):
        calls, pm, pc = self._patch_requests(
            lambda u, m: RELEASE_FAIL if m == "POST" else TR_D)
        pc.start(); pm.start()
        self.addCleanup(pc.stop); self.addCleanup(pm.stop)
        r = self.handlers.release_transport(
            "DEVK900001", sleep=lambda s: None, poll_interval=0)
        self.assertTrue(r.is_error)
        self.assertEqual(r.error_code, errors.RELEASE_REJECTED)
        self.assertIn("ATC error", r.text)

    def test_status_D_after_timeout_is_rejected(self):
        calls, pm, pc = self._patch_requests(lambda u, m: RELEASE_OK if m == "POST" else TR_D)
        pc.start(); pm.start()
        self.addCleanup(pc.stop); self.addCleanup(pm.stop)
        r = self.handlers.release_transport(
            "DEVK900001", sleep=lambda s: None,
            poll_interval=0, timeout=-1)
        self.assertTrue(r.is_error)
        self.assertEqual(r.error_code, errors.RELEASE_REJECTED)

    def test_readback_failure_is_unverified_not_rejected(self):
        gets = {"n": 0}

        def resp(url, method):
            if method == "POST":
                return RELEASE_OK
            gets["n"] += 1
            if gets["n"] == 1:
                return TR_D  # preflight
            raise self.handlers.AdtHttpError("boom", status=500)  # poll

        calls, pm, pc = self._patch_requests(resp)
        pc.start(); pm.start()
        self.addCleanup(pc.stop); self.addCleanup(pm.stop)
        r = self.handlers.release_transport(
            "DEVK900001", sleep=lambda s: None, poll_interval=0, timeout=10)
        self.assertTrue(r.is_error)
        self.assertEqual(r.error_code, errors.RELEASE_UNVERIFIED)


class ReleaseCliTests(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()
        self.handlers = sys.modules["lib.handlers"]

        class Cfg:
            profile_name = "dev"
            username = "DEVELOPER"
            environment = "dev"
            environment_source = "inferred"
            from_environment = False
            allow_write = True
            allow_transport = True
            write_source = "profile"
            transport_source = "profile"
            is_production = False

        self.cfg = Cfg()

    def _invoke(self, *args, result):
        with patch.object(self.cli, "load_config", return_value=self.cfg), \
                patch.object(self.handlers, "release_transport", return_value=result):
            return CliRunner().invoke(self.cli.cli, ["release-transport", *args])

    def test_dry_run_envelope(self):
        result = self.handlers.AdtResult(
            kind="records",
            data={"transport": {"trkorr": "DEVK900001", "status": "D"}},
            object={"type": "transport", "name": "DEVK900001"},
            meta={"dry_run": True, "release_possible": True})
        r = self._invoke("DEVK900001", "--dry-run", result=result)
        self.assertEqual(r.exit_code, 0, r.output)
        self.assertTrue(_env(r)["meta"]["dry_run"])

    def test_unverified_exit_1(self):
        result = self.handlers.AdtResult(
            text="unknown", is_error=True, error_code=errors.RELEASE_UNVERIFIED)
        r = self._invoke("DEVK900001", "--yes", result=result)
        self.assertEqual(r.exit_code, 1)
        self.assertEqual(_env(r)["error"]["code"], "RELEASE_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
