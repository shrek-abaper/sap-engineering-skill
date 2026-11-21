"""Expanded creation contracts, XML definitions and one-object deletion."""
import importlib
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from test_sap_adt_cli_config import load_cli_module
from test_sap_adt_development import Response


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()
        self.l = importlib.import_module("sap_adt.adt.lifecycle")
        self.d, self.h, self.c = self.cli.development, self.cli.handlers, self.cli.adt_client
        self.core = self.d.CORE
        p = patch.object(self.h, "_base", return_value="https://sap.example.invalid")
        p.start()
        self.addCleanup(p.stop)

    def test_new_creation_namespaces_and_function_container(self):
        for kind in ("include", "function-group", "function", "function-include", "domain",
                     "data-element", "structure", "table", "cds", "dcl", "bdef", "srvd"):
            with self.subTest(kind=kind), patch.object(self.d, "_absent"), \
                    patch.object(self.d, "_dependencies", return_value={}), \
                    patch.object(self.l, "negotiate_mime", return_value="known/xml"), \
                    patch.object(self.d, "metadata", return_value={
                        "name": "ZGROUP", "type": "FUGR/F", "package": "$TMP"}):
                plan = self.d.creation_plan(kind, "LZGROUPF01" if kind == "function-include" else "ZTEST",
                    package="$TMP", description="Test",
                    target={"user": "DEV"}, group="ZGROUP" if kind.startswith("function") and kind != "function-group" else None)
            root = ET.fromstring(plan["body"])
            self.assertEqual(root.get(f"{{{self.core}}}type"), self.d.SPECS[kind][1])
            if kind in ("function", "function-include"):
                self.assertIsNone(root.find(f"{{{self.core}}}packageRef"))
                self.assertIsNone(root.get(f"{{{self.core}}}language"))
                self.assertIsNone(root.get(f"{{{self.core}}}responsible"))
                self.assertEqual(root.find(f"{{{self.core}}}containerRef").get(f"{{{self.core}}}name"), "ZGROUP")
            if kind in ("structure", "table", "bdef"):
                self.assertEqual(root.tag, "{http://www.sap.com/wbobj/blue}blueSource")
            if kind == "domain":
                self.assertEqual(root.tag, "{http://www.sap.com/dictionary/domain}domain")

    def test_discovery_negotiates_known_version_and_never_guesses(self):
        result = self.h.AdtResult(data={"collections": [{
            "href": "/sap/bc/adt/functions/groups",
            "content_types": ["application/vnd.sap.adt.functions.groups.v2+xml"]}]})
        with patch.object(self.h, "discovery", return_value=result):
            self.assertEqual(self.l.negotiate_mime("function-group"),
                             "application/vnd.sap.adt.functions.groups.v2+xml")
            with self.assertRaisesRegex(ValueError, "does not advertise"):
                self.l.negotiate_mime("table")
        result.data["collections"] = [{
            "href": "/sap/bc/adt/functions/groups/{groupname}/fmodules",
            "content_types": ["application/vnd.sap.adt.functions.fmodules.v2+xml"]}]
        with patch.object(self.h, "discovery", return_value=result):
            self.assertEqual(self.l.negotiate_mime("function"),
                             "application/vnd.sap.adt.functions.fmodules.v2+xml")
        result.data["collections"] = [{"href": "/sap/bc/adt/functions/groups", "content_types": [],
                                      "templates": result.data["collections"]}]
        with patch.object(self.h, "discovery", return_value=result):
            self.assertEqual(self.l.negotiate_mime("function"),
                             "application/vnd.sap.adt.functions.fmodules.v2+xml")

    def test_function_include_customer_name_is_bound_to_customer_parent(self):
        self.assertTrue(self.d.customer_name("function-include", "LZGROUPF01", "ZGROUP"))
        for kind, name, group in (("include", "LZGROUPF01", None),
                                  ("function-include", "LSGROUPF01", "SGROUP"),
                                  ("function-include", "LZOTHERF01", "ZGROUP"),
                                  ("function-include", "LZGROUPF_EXTRA", "ZGROUP"),
                                  ("function-include", "ZTEST", "ZGROUP")):
            with self.subTest(kind=kind, name=name):
                self.assertFalse(self.d.customer_name(kind, name, group))

    def test_srvb_requires_explicit_category_and_never_publishes(self):
        with patch.object(self.d, "_absent"), patch.object(self.d, "_dependencies", return_value={}), \
                patch.object(self.l, "negotiate_mime", return_value="known/xml"), \
                patch.object(self.d, "metadata", return_value={"name": "ZSERVICE", "type": "SRVD/SRV"}):
            kwargs = dict(package="$TMP", description="Test", target={}, service_definition="ZSERVICE",
                          binding_protocol="V4")
            with self.assertRaises(ValueError):
                self.d.creation_plan("srvb", "ZBIND", **kwargs)
            plan = self.d.creation_plan("srvb", "ZBIND", binding_category="1", **kwargs)
        self.assertNotIn("publish", plan["body"].lower())
        root = ET.fromstring(plan["body"])
        binding = next(e for e in root if e.tag.endswith("}binding"))
        self.assertEqual(binding.get("{http://www.sap.com/adt/ddic/ServiceBindings}category"), "1")
        for xml in ("<binding/>", "<binding published='true'/>"):
            with self.assertRaises(ValueError):
                self.l._unpublished(ET.fromstring(xml))

    def _domain(self, datatype="CHAR", description="Test"):
        return ET.fromstring(f'<d:domain xmlns:d="http://www.sap.com/dictionary/domain" '
            f'xmlns:c="{self.core}" c:name="ZTEST" c:type="DOMA/DD" c:description="{description}">'
            f'<c:packageRef c:name="$TMP"/><d:content><d:typeInformation d:datatype="{datatype}"/>'
            '</d:content></d:domain>')

    def test_domain_storage_changes_and_srvb_updates_are_blocked(self):
        before = self._domain()
        with patch.object(self.l, "_read", return_value=before), \
                patch.object(self.d, "metadata", return_value={"package": "$TMP"}), \
                patch.object(self.d, "_dependencies"):
            with self.assertRaisesRegex(ValueError, "storage-type"):
                self.l.plan("domain", "ZTEST", target={}, content=ET.tostring(self._domain("NUMC")).decode())
            for kind in ("table", "function-group", "package"):
                spec = self.d.SPECS[kind]
                ns = spec[2] if spec[2].startswith("http:") else "http://www.sap.com/adt/" + spec[2]
                root = ET.Element(f"{{{ns}}}{spec[3]}", {f"{{{self.core}}}name": "ZTEST",
                                                       f"{{{self.core}}}type": spec[1]})
                with patch.object(self.l, "_read", return_value=root), self.assertRaises(ValueError):
                    self.l.plan(kind, "ZTEST", target={}, delete=True)

    def test_definition_put_has_lock_readback_unlock_and_no_source_endpoint(self):
        root = self._domain()
        xml = ET.tostring(root, encoding="unicode")
        with patch.object(self.l, "_read", return_value=root), \
                patch.object(self.d, "metadata", return_value={"package": "$TMP"}), \
                patch.object(self.d, "_dependencies"), \
                patch.object(self.l, "negotiate_mime", return_value="domain/xml"):
            plan = self.l.plan("domain", "ZTEST", target={}, content=xml)
        with patch.object(self.l, "_read", return_value=root), \
                patch.object(self.c, "prepare_csrf"), \
                patch.object(self.h, "lock_object", return_value=self.h.AdtResult(text="H")), \
                patch.object(self.h, "unlock_object", return_value=self.h.AdtResult()) as unlock, \
                patch.object(self.c, "make_adt_request", return_value=Response(status=204)) as request:
            result = self.l.execute(plan)
        self.assertFalse(result.is_error, result.text)
        self.assertEqual(result.data["readback"], "verified")
        self.assertEqual(request.call_args.kwargs["method"], "PUT")
        self.assertTrue(request.call_args.args[0].endswith("/ddic/domains/ztest"))
        self.assertFalse(request.call_args.kwargs["retry_csrf"])
        unlock.assert_called_once()

    def test_initial_domain_storage_can_be_populated_only_without_active_version(self):
        root = self._domain("")
        content = ET.tostring(self._domain(), encoding="unicode")
        with patch.object(self.l, "_read", side_effect=[
                root, self.c.AdtHttpError("object does not exist", status=404)]), \
                patch.object(self.d, "metadata", return_value={"package": "$TMP"}), \
                patch.object(self.d, "_dependencies"), \
                patch.object(self.l, "negotiate_mime", return_value="domain/xml"):
            plan = self.l.plan("domain", "ZTEST", target={}, content=content)
        self.assertEqual(plan["action"], "write-definition")
        root.set(f"{{{self.core}}}version", "new")
        with patch.object(self.l, "_read", return_value=root), \
                patch.object(self.d, "metadata", return_value={"package": "$TMP"}), \
                patch.object(self.d, "_dependencies"), \
                patch.object(self.l, "negotiate_mime", return_value="domain/xml"):
            self.assertEqual(self.l.plan("domain", "ZTEST", target={}, content=content)["action"],
                             "write-definition")

    def _definition_plan(self):
        root = self._domain()
        return root, {
            "object": {"uri": "/sap/bc/adt/ddic/domains/ztest", "type": "domain", "name": "ZTEST"},
            "action": "write-definition", "baseline_sha256": self.l.digest(self.l._tree(root)),
            "content": ET.tostring(root, encoding="unicode"), "transport": None,
            "content_type": "domain/xml"}

    def test_definition_drift_and_uncertain_lock_never_send_a_put(self):
        root, plan = self._definition_plan()
        changed = self._domain(description="Changed")
        for mode in ("baseline_drift", "in_lock_drift", "missing_handle", "interrupted"):
            with self.subTest(mode=mode), patch.object(self.l, "_read", return_value=root) as read, \
                    patch.object(self.c, "prepare_csrf"), \
                    patch.object(self.h, "lock_object", return_value=self.h.AdtResult(text="H")) as lock, \
                    patch.object(self.h, "unlock_object", return_value=self.h.AdtResult()) as unlock, \
                    patch.object(self.c, "make_adt_request") as request:
                if mode == "baseline_drift":
                    read.return_value = changed
                elif mode == "in_lock_drift":
                    read.side_effect = [root, changed]
                elif mode == "missing_handle":
                    lock.return_value = self.h.AdtResult(is_error=True, text="no handle")
                else:
                    lock.side_effect = KeyboardInterrupt
                result = self.l.execute(plan)
            self.assertTrue(result.is_error)
            self.assertEqual(result.data["mutation"], "not_attempted")
            self.assertEqual(result.error_code, "BASELINE_CHANGED" if "drift" in mode else "WRITE_INCOMPLETE")
            self.assertEqual(result.data["outcome"], "not_changed" if "drift" in mode else "incomplete")
            self.assertEqual(unlock.call_count, int(mode == "in_lock_drift"))
            request.assert_not_called()

    def test_uncertain_unlock_preserves_verified_write_and_reports_incomplete(self):
        root, plan = self._definition_plan()
        for cause in (None, TimeoutError("unknown"), KeyboardInterrupt()):
            with self.subTest(cause=cause), patch.object(self.l, "_read", return_value=root), \
                    patch.object(self.c, "prepare_csrf"), \
                    patch.object(self.h, "lock_object", return_value=self.h.AdtResult(text="H")), \
                    patch.object(self.h, "unlock_object", return_value=self.h.AdtResult(
                        is_error=True, text="timeout", error_code="NETWORK_ERROR"), side_effect=cause), \
                    patch.object(self.c, "make_adt_request", return_value=Response(status=204)) as request:
                result = self.l.execute(plan)
            self.assertEqual(result.error_code, "WRITE_INCOMPLETE")
            self.assertEqual(result.data["mutation"], "accepted")
            self.assertEqual(result.data["readback"], "verified")
            self.assertEqual(result.data["unlock"], "unknown")
            self.assertEqual(result.data["outcome"], "incomplete")
            request.assert_called_once()

    def test_existing_table_source_and_schema_activation_are_refused(self):
        sw = self.cli.source_write
        plan = sw.WritePlan("table", "ZTEST", None, "/sap/bc/adt/ddic/tables/ztest",
                            None, True, {}, "old", "new")
        with patch.object(self.h, "read_source_main", return_value=self.h.AdtResult(text="old")), \
                patch.object(self.h, "lock_object") as lock:
            result = sw.execute(plan, current_content_sha256=lambda: plan.content_sha256)
        self.assertIsNotNone(result.final_decision())
        lock.assert_not_called()
        with patch.object(self.h, "read_source_main", side_effect=[
                self.h.AdtResult(text="old"), self.h.AdtResult(text="new")]), \
                patch.object(self.h, "make_adt_request") as request:
            result = self.h.activate_objects([{"type": "table", "name": "ZTEST"}])
        self.assertTrue(result.is_error)
        request.assert_not_called()

    def test_table_requires_identity_matched_new_metadata_even_under_lock(self):
        uri = "/sap/bc/adt/ddic/tables/ztest"
        for version in ("new", "active", "inactive", None):
            with self.subTest(version=version), patch.object(self.d, "metadata", return_value={
                    "version": version, "type": "TABL/DT", "name": "ZTEST"}):
                self.assertEqual(self.d.table_is_new(uri), version == "new")
        for name, kind in (("ZOTHER", "TABL/DT"), ("ZTEST", "TABL/DS")):
            with patch.object(self.d, "metadata", return_value={
                    "version": "new", "type": kind, "name": name}):
                self.assertFalse(self.d.table_is_new(uri))
        plan = self.cli.source_write.WritePlan("table", "ZTEST", None, uri,
                                               None, False, {}, "old", "new")
        with patch.object(self.d, "table_is_new", side_effect=[True, False]), \
                patch.object(self.h, "read_source_main", return_value=self.h.AdtResult(text="old")), \
                patch.object(self.h, "lock_object", return_value=self.h.AdtResult(text="H")), \
                patch.object(self.h, "unlock_object", return_value=self.h.AdtResult()) as unlock, \
                patch.object(self.h, "put_source") as put:
            report = self.cli.source_write.execute(plan, current_content_sha256=lambda: plan.content_sha256)
        self.assertIsNotNone(report.final_decision())
        put.assert_not_called()
        unlock.assert_called_once()

    def test_deletion_unknown_never_replays_and_absence_must_be_verified(self):
        root = self._domain()
        plan = {"object": {"uri": "/sap/bc/adt/ddic/domains/ztest"}, "action": "delete",
                "transport": None, "baseline_sha256": self.l.digest(self.l._tree(root))}
        for mode in ("timeout", "still_exists", "absent"):
            with self.subTest(mode=mode), patch.object(self.c, "prepare_csrf"), \
                    patch.object(self.l, "_read") as read, \
                    patch.object(self.c, "make_adt_request") as request:
                read.return_value = root
                request.return_value = Response("<deletionResult><object isDeleted='true'/></deletionResult>")
                if mode == "timeout":
                    request.side_effect = TimeoutError("unknown")
                if mode == "absent":
                    read.side_effect = [root, self.c.AdtHttpError("object does not exist", status=404)]
                result = self.l.execute(plan)
            self.assertEqual(result.is_error, mode != "absent", result.text)
            request.assert_called_once()
            self.assertFalse(request.call_args.kwargs["allow_redirects"])


if __name__ == "__main__":
    unittest.main()
