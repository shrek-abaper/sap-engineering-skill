"""Regression cases for the read-only feeds/history contracts verified on QAS."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from click.testing import CliRunner

from sap_adt import cli, output
from sap_adt.adt import handlers as h
from sap_adt.adt.client import AdtHttpError
from sap_adt.adt.parsers import feeds, versions

BASE = "https://sap.example.com"
PROGRAM = "/sap/bc/adt/programs/programs/zexample"
HISTORY = PROGRAM + "/source/main/versions"
OLD = HISTORY + "/20200101000000/00001/content"
NEW = HISTORY + "/20200101000000/00002/content"
ACTIVE = HISTORY + "/20200101000000/00000/content"
NS = ('xmlns:a="http://www.w3.org/2005/Atom" '
      'xmlns:c="http://www.sap.com/adt/core"')
FEEDS = f"""<a:feed {NS} xmlns:f="http://www.sap.com/adt/feeds">
<a:entry><a:id>/sap/bc/adt/runtime/dumps</a:id><a:title>Dumps</a:title>
<a:content src="/sap/bc/adt/runtime/dumps" type="application/atom+xml"/>
<f:extendedData><f:attributes><f:attribute id="user">
<f:label>User</f:label><f:dataType id="string"/>
<f:operators><f:operator id="equals"/></f:operators></f:attribute>
</f:attributes><f:queryIsObligatory>false</f:queryIsObligatory></f:extendedData>
</a:entry></a:feed>"""
METADATA = f"""<object {NS}>
<a:link rel="http://www.sap.com/adt/relations/versions" href="source/main/versions"/>
<a:link rel="http://www.sap.com/adt/relations/source" href="source/main" type="text/plain"/>
</object>"""


def version_feed(items):
    entries = []
    for version, transport in items:
        entries.append(f"""<a:entry><a:id>{version}</a:id>
<a:content src="{HISTORY}/20200101000000/{version}/content" type="text/plain"/>
<a:link rel="http://www.sap.com/adt/relations/transport/request"
 href="/sap/bc/adt/cts/transportrequests/{transport}" c:name="{transport}"/>
</a:entry>""")
    return f"<a:feed {NS}>{''.join(entries)}</a:feed>"


def response(text):
    return SimpleNamespace(text=text, content=text.encode("utf-8"))


def transport(status="R", with_objects=True):
    obj = ('<t:abap_object t:pgmid="LIMU" t:type="REPS" t:name="ZEXAMPLE"/>'
           if with_objects else "")
    return f"""<t:root xmlns:t="http://www.sap.com/cts/adt/tm">
<t:request t:number="DEVK900001" t:status="{status}">
<t:task t:number="DEVK900002" t:status="{status}"/>
<t:all_objects>{obj}{obj}</t:all_objects></t:request></t:root>"""


class HandlerTests(unittest.TestCase):
    def setUp(self):
        config = SimpleNamespace(base_url=lambda: BASE)
        p = patch.object(h, "get_config", return_value=config)
        p.start()
        self.addCleanup(p.stop)

    def test_feed_schema_and_bounded_fql_page(self):
        page = f"""<a:feed {NS}><a:entry><a:id>dump1</a:id>
<a:summary type="html">&lt;pre&gt;diagnostic&lt;/pre&gt;</a:summary></a:entry>
<a:link rel="next" href="/sap/bc/adt/runtime/dumps?to=20261029000000"/>
</a:feed>"""
        query = "and ( equals ( user , TEST ) )"
        with patch.object(h, "make_adt_request",
                          side_effect=[response(FEEDS), response(page)]) as req:
            result = h.query_feed("/sap/bc/adt/runtime/dumps", query, 2)
        self.assertFalse(result.is_error, result.text)
        self.assertEqual(req.call_args.kwargs["params"], {"$top": 2, "$query": query})
        self.assertEqual(result.data["entries"][0]["summary"], "<pre>diagnostic</pre>")
        self.assertTrue(result.meta["has_more"])
        schema = feeds.parse(FEEDS.encode())["entries"][0]["schema"]["attributes"][0]
        self.assertEqual(schema["operators"], ["equals"])

    def test_feed_continuation_does_not_duplicate_top(self):
        page_uri = "/sap/bc/adt/runtime/dumps?%24top=2&to=20261029000000"
        with patch.object(h, "make_adt_request",
                          side_effect=[response(FEEDS), response(f"<a:feed {NS}/>")]) as req:
            result = h.query_feed("/sap/bc/adt/runtime/dumps", max_results=3,
                                  page_uri=page_uri)
        self.assertFalse(result.is_error, result.text)
        self.assertNotIn("$top", parse_qs(urlsplit(req.call_args.args[0]).query))
        self.assertEqual(req.call_args.kwargs["params"]["$top"], 3)

    def test_unadvertised_feed_and_cross_feed_continuation_refused(self):
        for uri, page in [
            ("/sap/bc/adt/activation", None),
            ("/sap/bc/adt/runtime/dumps", "/sap/bc/adt/activation"),
        ]:
            with self.subTest(uri=uri), patch.object(
                h, "make_adt_request", return_value=response(FEEDS)
            ) as req:
                result = h.query_feed(uri, page_uri=page)
                self.assertTrue(result.is_error)
                self.assertEqual(req.call_count, 1)

    def test_feed_overflow_does_not_skip_unreturned_entries(self):
        page = f"""<a:feed {NS}>
<a:entry><a:id>one</a:id></a:entry><a:entry><a:id>two</a:id></a:entry>
<a:link rel="next" href="/sap/bc/adt/runtime/dumps?to=20261029000000"/>
</a:feed>"""
        with patch.object(h, "make_adt_request",
                          side_effect=[response(FEEDS), response(page)]):
            result = h.query_feed("/sap/bc/adt/runtime/dumps", max_results=1)
        self.assertTrue(result.meta["truncated"])
        self.assertTrue(result.meta["has_more"])
        self.assertEqual(len(result.data["entries"]), 1)
        self.assertIsNone(result.data["next_uri"])
        self.assertIn("rerun", result.meta["hint"])

    def test_dangerous_content_uris_never_make_a_request(self):
        for uri in [
            "https://evil.example/sap/bc/adt/programs/versions/x/1/content",
            "/sap/bc/adt/%252e%252e/versions/x/1/content",
            "/sap/bc/adt/oo/classes/zexample/source/main",
            NEW + "?sap-client=999",
        ]:
            with self.subTest(uri=uri), patch.object(h, "make_adt_request") as req:
                self.assertTrue(h.get_version_source(uri).is_error)
                req.assert_not_called()

    def test_history_follows_metadata_and_marks_active(self):
        payload = version_feed([("00000", "DEVK900001"), ("00001", "OLDK900001")])
        with patch.object(h, "make_adt_request",
                          side_effect=[response(METADATA), response(payload)]) as req:
            result = h.get_versions("program", "ZEXAMPLE")
        self.assertFalse(result.is_error, result.text)
        self.assertEqual(req.call_args.args[0], BASE + HISTORY)
        self.assertTrue(result.data["versions"][0]["is_active"])
        self.assertEqual(result.data["versions"][1]["content_uri"], OLD)
        self.assertEqual(result.data["versions"][1]["transports"], ["OLDK900001"])
        self.assertFalse(result.meta["partial"])

    def test_class_separate_include_streams_and_missing_history(self):
        metadata = f"""<object {NS}>
<include name="main"><a:link rel="http://www.sap.com/adt/relations/versions"
 href="includes/main/versions"/></include>
<include name="macros"><a:link rel="http://www.sap.com/adt/relations/versions"
 href="includes/macros/versions"/></include></object>"""
        with patch.object(h, "make_adt_request", side_effect=[
            response(metadata), response(version_feed([("00001", "OLDK900001")])),
            AdtHttpError("No version service", status=404),
        ]):
            result = h.get_versions("class", "ZCL_EXAMPLE")
        self.assertFalse(result.is_error, result.text)
        self.assertEqual(len(result.data["streams"]), 2)
        self.assertEqual(result.data["versions"][0]["part"], "main")
        self.assertTrue(result.meta["partial"])
        self.assertEqual(result.data["evidence_gaps"][0]["part"], "macros")

    def test_history_limit_is_not_silently_complete(self):
        with patch.object(h, "make_adt_request", side_effect=[
            response(METADATA),
            response(version_feed([("00002", "DEVK900001"), ("00001", "OLDK900001")])),
        ]):
            result = h.get_versions("program", "ZEXAMPLE", max_results=1)
        self.assertTrue(result.meta["partial"])
        self.assertEqual(len(result.data["versions"]), 1)

    def test_version_diff_preserves_eof_and_uses_get_only(self):
        with patch.object(h, "make_adt_request",
                          side_effect=[response("old"), response("new\n")]) as req:
            result = h.diff_versions(OLD, NEW)
        diff = result.data["diffs"][0]
        self.assertTrue(diff["changed"])
        self.assertIn("-old\n\\ No newline at end of file\n+new\n", diff["diff"])
        self.assertTrue(all(c.kwargs.get("method", "GET") == "GET"
                            for c in req.call_args_list))

    def _transport_diff(self, status, history):
        ref = f"""<root {NS}><a:link rel="http://www.sap.com/cts/relations/objecturi"
href="{PROGRAM}"/></root>"""
        def request(url, **kwargs):
            path = urlsplit(url).path
            payloads = {
                "/sap/bc/adt/cts/transportrequests/DEVK900001": transport(status),
                "/sap/bc/adt/cts/transportrequests/reference": ref,
                PROGRAM: METADATA,
                HISTORY: version_feed(history),
                OLD: "old\n",
                NEW: "request snapshot\n",
                ACTIVE: "working tree\n",
                PROGRAM + "/source/main": "working tree\n",
            }
            return response(payloads[path])
        with patch.object(h, "make_adt_request", side_effect=request) as req:
            result = h.diff_transport("DEVK900001")
        self.assertFalse(result.is_error, result.text)
        self.assertTrue(all(c.kwargs.get("method", "GET") == "GET"
                            for c in req.call_args_list))
        return result, req

    def test_released_diff_uses_task_snapshot_not_active(self):
        result, req = self._transport_diff("R", [
            ("00000", "NEWK900001"), ("00002", "DEVK900002"), ("00001", "OLDK900001"),
        ])
        self.assertFalse(result.meta["partial"])
        self.assertEqual(result.meta["total_objects"], 1)
        self.assertEqual(result.data["diffs"][0]["to_uri"], NEW)
        self.assertIn("+request snapshot", result.data["diffs"][0]["diff"])
        self.assertNotIn(BASE + ACTIVE, [c.args[0] for c in req.call_args_list])

    def test_active_only_released_request_is_evidence_gap(self):
        result, _ = self._transport_diff("R", [("00000", "DEVK900001")])
        self.assertTrue(result.meta["partial"])
        self.assertEqual(result.data["diffs"], [])
        self.assertIn("not a snapshot", result.data["evidence_gaps"][0]["reason"])

    def test_modifiable_request_is_explicit_working_tree_comparison(self):
        result, _ = self._transport_diff("D", [
            ("00000", "DEVK900001"), ("00001", "OLDK900001"),
        ])
        self.assertFalse(result.meta["partial"])
        self.assertIn("not an exact transport snapshot", result.data["comparison"])
        self.assertIn("+working tree", result.data["diffs"][0]["diff"])

    def test_missing_baseline_does_not_infer_new_object(self):
        result, _ = self._transport_diff("D", [("00000", "DEVK900001")])
        self.assertTrue(result.meta["partial"])
        self.assertEqual(result.data["diffs"], [])
        self.assertIn("cannot infer", result.data["evidence_gaps"][0]["reason"])

    def test_missing_transport_uses_existing_not_found_error_contract(self):
        with patch.object(h, "make_adt_request", side_effect=AdtHttpError(
            "Task/request DEVK900001 does not exist in system", status=400,
        )):
            result = h.get_transport("DEVK900001")
        self.assertEqual(result.error_code, "OBJECT_NOT_FOUND")


class CliTests(unittest.TestCase):
    def test_partial_transport_diff_exits_nonzero_but_keeps_evidence(self):
        result = h.AdtResult(kind="diff", data={
            "diffs": [], "evidence_gaps": [{"reason": "No baseline"}],
        }, meta={"partial": True})
        with patch.object(h, "diff_transport", return_value=result):
            run = CliRunner().invoke(cli.cli, ["transport", "diff", "DEVK900001"])
        self.assertEqual(run.exit_code, 1, run.output)
        data = json.loads(run.output)
        self.assertTrue(data["ok"])
        self.assertTrue(data["meta"]["partial"])
        self.assertEqual(data["data"]["evidence_gaps"][0]["reason"], "No baseline")

    def test_text_diff_includes_evidence_gaps(self):
        result = h.AdtResult(kind="diff", data={
            "diffs": [], "evidence_gaps": [{"reason": "No baseline"}],
        })
        self.assertIn("EVIDENCE_GAP", output.render(result, "text"))


if __name__ == "__main__":
    unittest.main()
