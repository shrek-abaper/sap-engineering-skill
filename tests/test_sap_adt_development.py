"""Offline protocol and safety regressions for development primitives."""
import base64
import json
import sys
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from click.testing import CliRunner

from test_sap_adt_cli_config import load_cli_module

CLASS_URI = "/sap/bc/adt/oo/classes/zdev_probe"
CORE = "http://www.sap.com/adt/core"
CHECK = "http://www.sap.com/adt/checkrun"
EDMX = ('<edmx:Edmx xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx">'
        '<EntityContainer xmlns="http://docs.oasis-open.org/odata/ns/edm">'
        '<EntitySet Name="Items"/></EntityContainer></edmx:Edmx>')


class Response:
    def __init__(self, content="", status=200):
        self.content = content.encode() if isinstance(content, str) else content
        self.text = self.content.decode(errors="replace")
        self.status_code = status
        self.closed = False

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.content), chunk_size):
            yield self.content[offset:offset + chunk_size]

    def close(self):
        self.closed = True


class Base(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()
        self.dev = self.cli.development
        self.rap = self.cli.rap
        self.h = self.cli.handlers
        self.sw = self.cli.source_write
        self.client = self.cli.adt_client
        p = patch.object(self.h, "_base", return_value="https://sap.example.invalid")
        p.start()
        self.addCleanup(p.stop)


class CandidateTests(Base):
    def report(self, status="processed", message="", uri=CLASS_URI):
        return (f'<c:checkRunReports xmlns:c="{CHECK}"><c:checkReport '
                f'c:reporter="abapCheckRun" c:triggeringUri="{uri}" c:status="{status}">'
                f'{message}</c:checkReport></c:checkRunReports>')

    def test_artifact_binds_part_uri_and_canonical_utf8(self):
        with patch.object(self.client, "make_adt_request",
                          return_value=Response(self.report())) as request:
            r = self.dev.check_candidate(CLASS_URI, "a  \r\n\n", part="testclasses", stateful=True)
        self.assertEqual(r.data["status"], "passed")
        kw = request.call_args.kwargs
        self.assertEqual(kw["params"], {"reporters": "abapCheckRun"})
        root = ET.fromstring(kw["data"])
        artifact = root.find(f".//{{{CHECK}}}artifact")
        self.assertEqual(artifact.get(f"{{{CHECK}}}uri"), CLASS_URI + "/includes/testclasses")
        self.assertEqual(base64.b64decode(artifact[0].text), b"a")
        self.assertEqual(kw["extra_headers"]["X-sap-adt-sessiontype"], "stateful")

    def test_failure_empty_unknown_and_foreign_report_never_pass(self):
        cases = [
            ("<empty/>", "unavailable"),
            (self.report(status="aborted"), "unavailable"),
            (self.report(uri="/other"), "unavailable"),
            (self.report(message='<c:checkMessage c:type="X" c:shortText="unknown"/>'), "unavailable"),
            (self.report(message='<c:checkMessage c:type="E" c:shortText="bad" c:uri="/x#start=3,1"/>'), "failed"),
        ]
        for xml, status in cases:
            with self.subTest(status=status, xml=xml), patch.object(
                    self.client, "make_adt_request", return_value=Response(xml)):
                r = self.dev.check_candidate(CLASS_URI, "bad")
                self.assertTrue(r.is_error)
                self.assertEqual(r.data["status"], status)

    def test_http_failure_preserves_unavailable_evidence(self):
        with patch.object(self.client, "make_adt_request",
                          side_effect=self.client.AdtHttpError("HTTP 403", status=403)):
            r = self.dev.check_candidate(CLASS_URI, "a")
        self.assertEqual(r.data["status"], "unavailable")
        self.assertEqual(r.error_code, "AUTH_FAILED")


class PartWriterTests(Base):
    def plan(self, **kw):
        return self.sw.WritePlan(
            "class", "ZDEV_PROBE", None, CLASS_URI, None, True,
            {"url": "https://sap.example.invalid", "client": "100", "user": "DEV"},
            "old", "new", **kw)

    def test_plan_hash_binds_part_and_precheck_option(self):
        plans = [self.plan(), self.plan(part="testclasses"),
                 self.plan(part="definitions"), self.plan(check_before_write=True)]
        self.assertEqual(len({p.plan_sha256 for p in plans}), 4)
        with self.assertRaises(ValueError):
            self.sw.WritePlan("program", "ZP", None, "/sap/bc/adt/programs/programs/zp",
                              None, False, {}, "", "x", part="testclasses")

    def test_part_write_locks_parent_reads_selected_part_and_activates_parent(self):
        plan = self.plan(part="testclasses")
        with patch.object(self.h, "lock_object", return_value=self.h.AdtResult(text="H")) as lock, \
                patch.object(self.h, "read_source_main", side_effect=[
                    self.h.AdtResult(text="old"), self.h.AdtResult(text="new"),
                    self.h.AdtResult(text="new")]) as read, \
                patch.object(self.h, "put_source", return_value=self.h.AdtResult()) as put, \
                patch.object(self.h, "unlock_object", return_value=self.h.AdtResult()) as unlock, \
                patch.object(self.h, "activate_object", return_value=self.h.AdtResult()) as activate, \
                patch.object(self.h, "object_version", return_value=self.h.AdtResult(text="active")):
            r = self.sw.execute(plan, current_content_sha256=lambda: plan.content_sha256)
        self.assertIsNone(r.final_decision())
        lock.assert_called_once_with(CLASS_URI)
        unlock.assert_called_once_with(CLASS_URI, "H")
        activate.assert_called_once_with("class", "ZDEV_PROBE", group=None)
        self.assertTrue(all(c.kwargs["part"] == "testclasses" for c in read.call_args_list))
        put.assert_called_once_with(CLASS_URI, "new", "H", transport=None, part="testclasses")
        self.assertEqual(read.call_args.kwargs["version"], "active")

    def test_failed_or_unavailable_precheck_never_puts_and_always_unlocks(self):
        for status in ("failed", "unavailable"):
            plan = self.plan(check_before_write=True)
            with self.subTest(status=status), \
                    patch.object(self.h, "lock_object", return_value=self.h.AdtResult(text="H")), \
                    patch.object(self.h, "read_source_main", return_value=self.h.AdtResult(text="old")), \
                    patch.object(self.dev, "check_candidate", return_value=self.h.AdtResult(
                        kind="findings", data={"status": status}, is_error=True)), \
                    patch.object(self.h, "put_source") as put, \
                    patch.object(self.h, "activate_object") as activate, \
                    patch.object(self.h, "unlock_object", return_value=self.h.AdtResult()) as unlock:
                r = self.sw.execute(plan, current_content_sha256=lambda: plan.content_sha256)
            self.assertEqual(r.outcome, "not_written")
            put.assert_not_called()
            activate.assert_not_called()
            unlock.assert_called_once()

    def test_wire_source_part_does_not_change_parent_uri(self):
        with patch.object(self.h, "make_adt_request", return_value=Response("source")) as request:
            self.h.read_source_main(CLASS_URI, part="definitions")
            self.assertTrue(request.call_args.args[0].endswith("/includes/definitions"))
            self.h.put_source(CLASS_URI, "x", "H", part="implementations")
            self.assertTrue(request.call_args.args[0].endswith("/includes/implementations"))

    def test_missing_include_requires_explicit_plan_and_parent_metadata(self):
        missing = self.h.AdtResult(is_error=True, error_code="OBJECT_NOT_FOUND")
        xml = f'<abapClass xmlns:c="{CORE}" c:type="CLAS/OC" c:name="ZDEV_PROBE"/>'
        with patch.object(self.h, "read_source_main", return_value=missing), \
                patch.object(self.client, "make_adt_request", return_value=Response(xml)) as request:
            r = self.dev.part_baseline(CLASS_URI, "testclasses")
            self.assertTrue(r.is_error)
            request.assert_not_called()
            r = self.dev.part_baseline(CLASS_URI, "testclasses", allow_missing=True)
            self.assertFalse(r.is_error)
            self.assertTrue(r.meta["absent"])
        declared = xml.replace("/>", '<include includeType="testclasses"/></abapClass>')
        with patch.object(self.h, "read_source_main", return_value=missing), \
                patch.object(self.client, "make_adt_request", return_value=Response(declared)):
            self.assertTrue(self.dev.part_baseline(
                CLASS_URI, "testclasses", allow_missing=True).is_error)

    def test_unknown_include_generation_does_not_put_and_reports_incomplete(self):
        plan = self.plan(part="testclasses", create_part=True, baseline_absent=True)
        plan.baseline = ""
        with patch.object(self.h, "lock_object", return_value=self.h.AdtResult(text="H")), \
                patch.object(self.dev, "part_baseline", return_value=self.h.AdtResult(
                    text="", meta={"absent": True})), \
                patch.object(self.dev, "generate_part", side_effect=self.client.AdtHttpError("ReadTimeout")) as generate, \
                patch.object(self.h, "put_source") as put, \
                patch.object(self.h, "unlock_object", return_value=self.h.AdtResult()) as unlock:
            r = self.sw.execute(plan, current_content_sha256=lambda: plan.content_sha256)
        self.assertEqual(r.outcome, "incomplete")
        self.assertEqual(r.part_creation["status"], "unknown")
        generate.assert_called_once()
        put.assert_not_called()
        unlock.assert_called_once()

    def test_absence_to_empty_part_drift_blocks_generation_even_when_hash_matches(self):
        plan = self.plan(part="testclasses", create_part=True, baseline_absent=True)
        plan.baseline = ""
        with patch.object(self.h, "lock_object", return_value=self.h.AdtResult(text="H")), \
                patch.object(self.dev, "part_baseline", return_value=self.h.AdtResult(text="")), \
                patch.object(self.dev, "generate_part") as generate, \
                patch.object(self.h, "put_source") as put, \
                patch.object(self.h, "unlock_object", return_value=self.h.AdtResult()):
            r = self.sw.execute(plan, current_content_sha256=lambda: plan.content_sha256)
        self.assertEqual(r.final_decision().code, "BASELINE_CHANGED")
        generate.assert_not_called()
        put.assert_not_called()


class CreationTests(Base):
    def plan(self, kind="class", **kw):
        with patch.object(self.dev, "_absent"), patch.object(
                self.dev, "_dependencies", return_value={"package": {"name": "$TMP"}, "transport": None}):
            return self.dev.creation_plan(kind, "$ZDEV_PROBE" if kind == "package" else "ZDEV_PROBE", package="$TMP",
                                          description="Development probe", target={"url": "https://sap.example.invalid", "user": "DEV"},
                                          **kw)

    def test_native_creation_payloads_and_no_implicit_source_or_activation(self):
        for kind, tag in (("class", "abapClass"), ("interface", "abapInterface"),
                          ("program", "abapProgram"), ("package", "package")):
            plan = self.plan(kind, **({"software_component": "LOCAL"} if kind == "package" else {}))
            root = ET.fromstring(plan["body"])
            self.assertTrue(root.tag.endswith("}" + tag))
            self.assertEqual(root.get(f"{{{CORE}}}name"), "$ZDEV_PROBE" if kind == "package" else "ZDEV_PROBE")
            self.assertEqual(plan["source_write"], "not_requested")
            self.assertEqual(plan["activation"], "not_requested")
            if kind == "package":
                layer = next(e for e in root.iter() if e.tag.endswith("}transportLayer"))
                self.assertEqual(next(iter(layer.attrib.values())), "")

    def test_namespace_and_description_xml_are_escaped(self):
        with patch.object(self.dev, "_absent"), patch.object(self.dev, "_dependencies", return_value={}):
            plan = self.dev.creation_plan("class", "/ABC/ZTEST", package="$TMP",
                                          description='A & "B"', target={})
        self.assertTrue(plan["object"]["uri"].endswith("%2Fabc%2Fztest".lower().replace("%2f", "%2F")))
        self.assertEqual(ET.fromstring(plan["body"]).get(f"{{{CORE}}}description"), 'A & "B"')

    def test_policy_rejects_bad_names_missing_transport_and_implicit_components(self):
        for kw in ({"name": "CL_STANDARD"}, {"package": "ZPKG"}, {"name": "Z../X"},
                   {"kind": "package"}, {"description": ""}):
            args = dict(kind="class", name="ZDEV_PROBE", package="$TMP",
                        description="Probe", target={})
            args.update(kw)
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                self.dev.creation_plan(**args)

    def test_existing_object_and_auth_failure_are_not_absence(self):
        with patch.object(self.dev, "metadata", return_value={}):
            with self.assertRaisesRegex(ValueError, "already exists"):
                self.dev._absent(CLASS_URI)
        with patch.object(self.dev, "metadata",
                          side_effect=self.client.AdtHttpError("forbidden", status=403)):
            with self.assertRaises(self.client.AdtHttpError):
                self.dev._absent(CLASS_URI)

    def test_create_once_readback_and_dependency_drift(self):
        plan = self.plan()
        got = {"name": "ZDEV_PROBE", "type": "CLAS/OC", "description": plan["description"],
               "package": "$TMP", "version": "inactive"}
        with patch.object(self.dev, "_absent"), \
                patch.object(self.dev, "_dependencies", return_value=plan["dependencies"]), \
                patch.object(self.client, "prepare_csrf"), \
                patch.object(self.dev, "metadata", return_value=got), \
                patch.object(self.client, "make_adt_request", return_value=Response(status=201)) as request:
            r = self.dev.create(plan)
        self.assertFalse(r.is_error, r.text)
        self.assertEqual(r.data["readback"]["status"], "verified")
        request.assert_called_once()
        self.assertFalse(request.call_args.kwargs["retry_csrf"])
        self.assertFalse(request.call_args.kwargs["allow_redirects"])
        with patch.object(self.dev, "_absent"), \
                patch.object(self.dev, "_dependencies", return_value={"changed": True}), \
                patch.object(self.client, "make_adt_request") as request:
            r = self.dev.create(plan)
        self.assertEqual(r.error_code, "BASELINE_CHANGED")
        request.assert_not_called()

    def test_unknown_post_or_mismatched_readback_never_replay_or_delete(self):
        plan = self.plan()
        for failure in ("timeout", "readback"):
            with self.subTest(failure=failure), patch.object(self.dev, "_absent"), \
                    patch.object(self.dev, "_dependencies", return_value=plan["dependencies"]), \
                    patch.object(self.client, "prepare_csrf"), \
                    patch.object(self.dev, "metadata", return_value={}), \
                    patch.object(self.client, "make_adt_request") as request:
                if failure == "timeout":
                    request.side_effect = self.client.AdtHttpError("ReadTimeout")
                else:
                    request.return_value = Response(status=201)
                r = self.dev.create(plan)
            self.assertEqual(r.error_code, "WRITE_INCOMPLETE")
            self.assertEqual(r.data["outcome"], "incomplete")
            request.assert_called_once()

    def test_transport_dependency_must_be_existing_and_modifiable(self):
        parent = {"name": "ZPKG", "type": "DEVC/K"}
        for status in ("D", "R"):
            with self.subTest(status=status), patch.object(self.dev, "metadata", return_value=parent), \
                    patch.object(self.h, "transport_preflight", return_value=(
                        self.h.AdtResult(), {"status": status, "trkorr": "DEVK900001"})):
                if status == "D":
                    got = self.dev._dependencies("class", "ZPKG", "DEVK900001")
                    self.assertEqual(got["transport"]["status"], "D")
                else:
                    with self.assertRaisesRegex(ValueError, "modifiable"):
                        self.dev._dependencies("class", "ZPKG", "DEVK900001")

    def test_program_subtype_must_match_executable_report(self):
        plan = self.plan("program")
        with patch.object(self.dev, "_absent"), \
                patch.object(self.dev, "_dependencies", return_value=plan["dependencies"]), \
                patch.object(self.client, "prepare_csrf"), \
                patch.object(self.client, "make_adt_request", return_value=Response(status=201)), \
                patch.object(self.dev, "metadata", return_value={
                    "name": "ZDEV_PROBE", "type": "PROG/P", "package": "$TMP",
                    "description": plan["description"], "program_type": "M"}):
            r = self.dev.create(plan)
        self.assertEqual(r.error_code, "WRITE_INCOMPLETE")
        self.assertEqual(r.data["create"]["status"], "accepted")


class RapTests(Base):
    def test_runtime_url_rejects_foreign_origin_and_operation_shapes_before_http(self):
        cases = ["https://evil.invalid/sap/opu/odata/S/", "//evil.invalid/S/",
                 "/sap/opu/odata/S/?x=y", "/sap/opu/odata/S/#x", "/sap/bc/adt/",
                 "/sap/opu/odata/S/../Action", "/sap/opu/odata/S/DoIt()",
                 "/sap/opu/odata/S/%2fAction", "/sap/opu/odata/S/%252e%252e",
                 "https://user@SAP.example.invalid/sap/opu/odata/S/"]
        for url in cases:
            with self.subTest(url=url), patch.object(self.client, "make_adt_request") as request:
                r = self.rap.read_odata(url)
                self.assertTrue(r.is_error)
                request.assert_not_called()

    def test_metadata_then_declared_collection_top_budget_and_no_next_link_follow(self):
        responses = [Response(EDMX), Response(json.dumps({
            "value": [{"ID": 1}, {"ID": 2}], "@odata.nextLink": "https://evil.invalid/next"}))]
        with patch.object(self.client, "make_adt_request", side_effect=responses) as request:
            r = self.rap.read_odata("/sap/opu/odata4/S/", entity_set="Items", top=1)
        self.assertFalse(r.is_error, r.text)
        self.assertEqual(r.data["rows"], [[1]])
        self.assertTrue(r.data["truncated"])
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args.kwargs["params"], {"$top": 1})
        self.assertTrue(all(not c.kwargs["allow_redirects"] for c in request.call_args_list))
        self.assertTrue(all(response.closed for response in responses))

    def test_v2_collection_and_metadata_only(self):
        for entity in (None, "Items"):
            responses = [Response(EDMX), Response('{"d":{"results":[{"ID":1}],"__next":"/next"}}')]
            with patch.object(self.client, "make_adt_request", side_effect=responses) as request:
                r = self.rap.read_odata("/sap/opu/odata/S/", entity_set=entity)
            self.assertFalse(r.is_error, r.text)
            self.assertEqual(request.call_count, 1 if entity is None else 2)
            self.assertEqual(r.kind, "scalar" if entity is None else "rows")

    def test_same_origin_default_https_port_is_accepted(self):
        with patch.object(self.client, "make_adt_request", return_value=Response(EDMX)):
            r = self.rap.read_odata("https://sap.example.invalid:443/sap/opu/odata/S/")
        self.assertFalse(r.is_error, r.text)

    def test_undeclared_entity_or_action_never_requested(self):
        with patch.object(self.client, "make_adt_request", return_value=Response(EDMX)) as request:
            r = self.rap.read_odata("/sap/opu/odata/S/", entity_set="DangerousFunction")
        self.assertTrue(r.is_error)
        request.assert_called_once()

    def test_redirect_malformed_and_oversized_responses_are_not_empty_success(self):
        for response in (Response("", status=302), Response("<html/>"), Response("x" * 2048)):
            with self.subTest(response=response), patch.object(
                    self.client, "make_adt_request", return_value=response):
                r = self.rap.read_odata("/sap/opu/odata/S/", max_bytes=1024)
            self.assertTrue(r.is_error)
            self.assertTrue(response.closed)

    def test_streamed_http_error_body_is_bounded_and_closed(self):
        response = Response(b"x" * 10000, status=500)
        cfg = type("Cfg", (), {"password": "secret", "username": "DEV"})()
        exc = self.client.requests.HTTPError(response=response)
        error = self.client._wrap_error(exc, cfg, "GET", "https://sap.example.invalid/",
                                         stream=True)
        self.assertTrue(response.closed)
        self.assertLess(len(str(error)), 600)

    def test_binding_group_evidence_and_unavailable_runtime_are_explicit(self):
        binding = (f'<s:serviceBinding xmlns:s="http://www.sap.com/adt/ddic/ServiceBindings" '
                   f'xmlns:c="{CORE}" c:name="ZBIND" c:type="SRVB/SVB">'
                   '<s:published>false</s:published><s:binding s:type="ODATA" s:version="V4"/>'
                   '<s:services s:name="ZSERVICE"><s:content s:version="0001">'
                   '<s:serviceDefinition c:name="ZSDEF"/></s:content></s:services></s:serviceBinding>')
        group = '<serviceGroup published="true"><services serviceUrl="/sap/opu/odata4/S/"/></serviceGroup>'
        with patch.object(self.client, "make_adt_request",
                          side_effect=[Response(binding), Response(group)]) as request:
            r = self.rap.get_object("srvb", "ZBIND")
        self.assertFalse(r.is_error, r.text)
        self.assertEqual(r.data["status"]["published"], "false")
        self.assertEqual(r.data["services"][0]["runtime"][0]["serviceUrl"], "/sap/opu/odata4/S/")
        self.assertFalse(r.meta["partial"])
        self.assertEqual(request.call_args.kwargs["params"]["srvdname"], "ZSDEF")
        with patch.object(self.client, "make_adt_request", side_effect=[
                Response(binding), self.client.AdtHttpError("forbidden", status=403)]):
            r = self.rap.get_object("srvb", "ZBIND")
        self.assertTrue(r.meta["partial"])
        self.assertTrue(r.data["services"][0]["evidence_gaps"])

    def test_v2_group_service_list_and_redirect_gap(self):
        binding = (f'<s:serviceBinding xmlns:s="http://www.sap.com/adt/ddic/ServiceBindings" '
                   f'xmlns:c="{CORE}" c:name="ZBIND" c:type="SRVB/SVB" s:published="true">'
                   '<s:binding s:type="ODATA" s:version="V2"/>'
                   '<s:services s:name="ZSERVICE"><s:content s:version="0001">'
                   '<s:serviceDefinition c:name="ZSDEF"/></s:content></s:services></s:serviceBinding>')
        group = '<serviceList><services published="true" serviceUrl="/sap/opu/odata/S/"/></serviceList>'
        for response, partial in ((Response(group), False), (Response(group, status=302), True)):
            with self.subTest(partial=partial), patch.object(
                    self.client, "make_adt_request", side_effect=[Response(binding), response]):
                r = self.rap.get_object("srvb", "ZBIND")
            self.assertEqual(r.meta["partial"], partial)
            self.assertEqual(r.data["status"]["published"], "true")


class CliSafetyTests(Base):
    def test_create_and_write_xml_refused_before_network(self):
        from test_sap_adt_cli_write_source import CliTests
        for command in (["create-object", "class", "ZTEST", "--package", "$TMP",
                         "--description", "Probe", "--dry-run"],
                        ["write-source", "class", "ZTEST", "--file", "-", "--dry-run"]):
            with self.subTest(command=command), \
                    patch.object(self.cli, "load_config", return_value=CliTests.Cfg()), \
                    patch.object(self.client, "make_adt_request") as request, \
                    patch.object(self.h, "make_adt_request") as handler_request:
                r = CliRunner().invoke(self.cli.cli, ["--format", "xml", *command])
            self.assertNotEqual(r.exit_code, 0)
            request.assert_not_called()
            handler_request.assert_not_called()

    def test_create_denied_by_default_and_hash_required_before_http(self):
        from test_sap_adt_cli_write_source import CliTests
        for allowed in (False, True):
            cfg = CliTests.Cfg()
            cfg.allow_write = allowed
            with patch.object(self.cli, "load_config", return_value=cfg), \
                    patch.object(self.client, "make_adt_request") as request:
                r = CliRunner().invoke(self.cli.cli, [
                    "create-object", "class", "ZTEST", "--package", "$TMP",
                    "--description", "Probe", "--yes"])
            self.assertEqual(r.exit_code, 3)
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
