"""Offline regression tests for the verified write-source workflow.

A small in-memory fake stands in for the ADT handlers (lock / GET / PUT /
unlock / activate), so every failure mode can be injected deterministically.
No HTTP, keystore or SAP access.
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from test_sap_adt_cli_config import load_cli_module  # noqa: E402

OLD = "REPORT zprobe.\r\nWRITE / 'old'."
NEW = "REPORT zprobe.\nWRITE / 'new'.   \n\n"
NEW_CANON = "REPORT zprobe.\nWRITE / 'new'."


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class FakeSap:
    """Minimal stateful stand-in for the handlers used by source_write."""

    def __init__(self, h, source=OLD):
        self.h = h
        source = source.replace("\r\n", "\n")   # stored LF, served CRLF
        self.inactive = source
        self.active = source
        self.locked = False
        self.calls = []
        self.lock_error = None
        self.put_error = None
        self.put_applies = True
        self.unlock_error = None
        self.read_errors = {}        # call index (stateful reads) -> error
        self.readback_override = None
        self.on_lock = None
        self.activation = None       # None = success; else AdtResult
        self.activation_applies = True
        self.corrnr = ""
        self._stateful_reads = 0

    def err(self, code, text, status=None):
        return self.h.AdtResult(text=text, is_error=True, error_code=code,
                                http_status=status)

    def read_source_main(self, uri, *, stateful=False, version=None):
        self.calls.append(("GET", stateful, version))
        if stateful:
            self._stateful_reads += 1
            if self._stateful_reads in self.read_errors:
                return self.read_errors[self._stateful_reads]
            if self._stateful_reads >= 2 and self.readback_override is not None:
                return self.h.AdtResult(text=self.readback_override)
        text = self.active if version == "active" else self.inactive
        return self.h.AdtResult(text=text.replace("\n", "\r\n"))

    def lock_object(self, uri):
        self.calls.append(("LOCK",))
        if self.on_lock:
            self.on_lock()
        if self.lock_error:
            return self.lock_error
        self.locked = True
        return self.h.AdtResult(text="HANDLE-1", meta={"corrnr": self.corrnr})

    def put_source(self, uri, content, handle, transport=None):
        self.calls.append(("PUT", content, transport))
        assert self.locked and handle == "HANDLE-1"
        if self.put_applies:
            self.inactive = content
        if self.put_error:
            return self.put_error
        return self.h.AdtResult(text="ok")

    def unlock_object(self, uri, handle):
        self.calls.append(("UNLOCK",))
        if self.unlock_error:
            return self.unlock_error
        self.locked = False
        return self.h.AdtResult(text="unlocked")

    def activate_object(self, object_type, object_name, group=None):
        self.calls.append(("ACTIVATE",))
        if self.activation_applies:
            self.active = self.inactive
        return self.activation or self.h.AdtResult(text="Activated.", meta={
            "messages": [], "inactive_objects": []})

    def object_version(self, uri):
        self.calls.append(("VERSION",))
        return self.h.AdtResult(
            text="active" if self.active == self.inactive else "inactive")

    def ops(self):
        return [c[0] for c in self.calls]

    def patches(self):
        names = ("read_source_main", "lock_object", "put_source",
                 "unlock_object", "activate_object", "object_version")
        return [patch.object(self.h, n, getattr(self, n)) for n in names]


class _Base(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()
        self.h = sys.modules["sap_adt.adt.handlers"]
        self.sw = sys.modules["sap_adt.adt.source_write"]
        self.errors = sys.modules["sap_adt.errors"]
        self.sap = FakeSap(self.h)
        for p in self.sap.patches():
            p.start()
            self.addCleanup(p.stop)

    def plan(self, content=NEW, activate=False, transport=None, **kw):
        return self.sw.WritePlan(
            object_type="program", object_name="ZPROBE", group=None,
            object_uri="/sap/bc/adt/programs/programs/zprobe",
            transport=transport, activate=activate,
            target={"url": "https://sap.example.invalid", "client": "400",
                    "user": "DEV"},
            baseline=self.sw.canonical_source(OLD),
            content=self.sw.canonical_source(content), **kw)

    def run_plan(self, plan, current=None):
        return self.sw.execute(
            plan, current_content_sha256=lambda: current or plan.content_sha256)


class CanonicalisationTests(_Base):
    def test_rules(self):
        c = self.sw.canonical_source
        self.assertEqual(c("a  \r\nb\rc\n\n\n"), "a\nb\nc")
        self.assertEqual(c("a\t\nb"), "a\t\nb")          # tabs are substantive
        self.assertNotEqual(c("A"), c("a"))              # case is substantive
        self.assertNotEqual(c(" a"), c("a"))             # leading blanks too
        self.assertEqual(self.sw.decode_local("\ufeffa".encode()), "a")
        with self.assertRaises(UnicodeDecodeError):
            self.sw.decode_local(b"\xff")
        self.assertEqual(self.sw.sha256_text(NEW_CANON), sha(NEW_CANON))


class WorkflowTests(_Base):
    def test_happy_path_with_activation_is_verified(self):
        rep = self.run_plan(self.plan(activate=True))
        self.assertIsNone(rep.final_decision())
        self.assertEqual(rep.outcome, "completed")
        self.assertEqual(rep.write["status"], "verified")
        self.assertEqual(rep.activation["status"], "verified")
        self.assertEqual(rep.unlock["status"], "accepted")
        self.assertEqual(self.sap.ops(), ["LOCK", "GET", "PUT", "GET", "UNLOCK",
                                          "ACTIVATE", "VERSION", "GET"])
        put = [c for c in self.sap.calls if c[0] == "PUT"][0]
        self.assertEqual(put[1], NEW_CANON)               # exact confirmed body

    def test_unlock_failure_preserves_primary_write_error(self):
        self.sap.put_error = self.sap.err("SERVER_ERROR", "HTTPError 400 bad", 400)
        self.sap.put_applies = False
        self.sap.unlock_error = self.sap.err("NETWORK_ERROR", "ConnectionError for POST x")
        dec = self.run_plan(self.plan()).final_decision()
        self.assertEqual(dec.code, "SERVER_ERROR")
        self.assertIn("write: HTTPError 400 bad", dec.message)
        self.assertIn("cleanup: unlock unknown", dec.message)
        self.assertEqual(dec.data["write"]["status"], "failed")
        self.assertEqual(dec.data["unlock"]["status"], "unknown")
        self.assertEqual(dec.data["outcome"], "incomplete")

    def test_unlock_failure_alone_is_not_reported_as_success(self):
        self.sap.unlock_error = self.sap.err("SERVER_ERROR", "HTTPError 500", 400)
        rep = self.run_plan(self.plan())
        dec = rep.final_decision()
        self.assertEqual(dec.code, "WRITE_INCOMPLETE")
        self.assertEqual(dec.exit_code, 3)
        self.assertEqual(rep.write["status"], "verified")
        self.assertEqual(rep.unlock["status"], "failed")

    def test_baseline_changed_under_lock_writes_nothing_and_unlocks(self):
        self.sap.on_lock = lambda: setattr(self.sap, "inactive", "REPORT other.")
        rep = self.run_plan(self.plan())
        self.assertEqual(rep.final_decision().code, "BASELINE_CHANGED")
        self.assertNotIn("PUT", self.sap.ops())
        self.assertEqual(self.sap.ops()[-1], "UNLOCK")
        self.assertEqual(rep.outcome, "not_written")

    def test_content_changed_after_confirmation_writes_nothing(self):
        rep = self.run_plan(self.plan(), current="0" * 64)
        self.assertEqual(rep.final_decision().code, "CONTENT_CHANGED")
        self.assertEqual(self.sap.calls, [])

    def test_readback_mismatch_is_failed_not_ok(self):
        self.sap.readback_override = "REPORT zprobe.\r\nWRITE / 'NEW'."
        rep = self.run_plan(self.plan(activate=True))
        dec = rep.final_decision()
        self.assertEqual(dec.code, "WRITE_INCOMPLETE")
        self.assertEqual(rep.write["status"], "failed")
        self.assertEqual(rep.write["request"], "accepted")
        self.assertEqual(rep.activation["status"], "not_attempted")
        self.assertNotIn("ACTIVATE", self.sap.ops())

    def test_readback_unavailable_is_unknown(self):
        self.sap.read_errors[2] = self.sap.err("NETWORK_ERROR", "ReadTimeout for GET x")
        rep = self.run_plan(self.plan())
        self.assertEqual(rep.final_decision().code, "WRITE_INCOMPLETE")
        self.assertEqual(rep.write["status"], "unknown")
        self.assertEqual(rep.unlock["status"], "accepted")

    def test_put_timeout_is_unknown_without_retry(self):
        self.sap.put_error = self.sap.err("NETWORK_ERROR", "ReadTimeout for PUT x")
        self.sap.put_applies = False
        rep = self.run_plan(self.plan())
        self.assertEqual(rep.final_decision().code, "WRITE_INCOMPLETE")
        self.assertEqual(rep.write["status"], "unknown")
        self.assertEqual(self.sap.ops().count("PUT"), 1)    # no blind retry
        # No rollback write of the old source either.
        self.assertTrue(all(c[1] == NEW_CANON for c in self.sap.calls if c[0] == "PUT"))

    def test_put_timeout_resolved_by_matching_readback(self):
        self.sap.put_error = self.sap.err("NETWORK_ERROR", "ReadTimeout for PUT x")
        rep = self.run_plan(self.plan())
        self.assertIsNone(rep.final_decision())
        self.assertEqual(rep.write["status"], "verified")
        self.assertEqual(rep.write["request"], "unknown")

    def test_lock_conflict_is_not_written(self):
        self.sap.lock_error = self.sap.err("LOCKED_BY_OTHER", "HTTPError 403", 403)
        rep = self.run_plan(self.plan())
        self.assertEqual(rep.final_decision().code, "LOCKED_BY_OTHER")
        self.assertEqual(rep.outcome, "not_written")
        self.assertEqual(self.sap.ops(), ["LOCK"])

    def test_transport_mismatch_with_lock_corrnr_refused(self):
        self.sap.corrnr = "ECDK900001"
        rep = self.run_plan(self.plan(transport="ECDK900002"))
        self.assertEqual(rep.final_decision().code, "BAD_REQUEST")
        self.assertNotIn("PUT", self.sap.ops())
        self.assertEqual(self.sap.ops()[-1], "UNLOCK")

    def test_activation_error_messages_are_partial(self):
        self.sap.activation_applies = False
        self.sap.activation = self.sap.err("ACTIVATION_FAILED", "E: syntax error")
        rep = self.run_plan(self.plan(activate=True))
        dec = rep.final_decision()
        self.assertEqual(dec.code, "ACTIVATION_FAILED")
        self.assertEqual(rep.write["status"], "verified")
        self.assertEqual(rep.activation["status"], "failed")
        self.assertEqual(rep.outcome, "partial")

    def test_activation_reported_ok_but_not_effective_fails(self):
        self.sap.activation_applies = False
        rep = self.run_plan(self.plan(activate=True))
        self.assertEqual(rep.final_decision().code, "ACTIVATION_FAILED")
        self.assertEqual(rep.activation["object_version"], "inactive")

    def test_activation_timeout_unreadable_is_unknown(self):
        self.sap.activation = self.sap.err("NETWORK_ERROR", "ReadTimeout for POST x")
        orig = self.sap.read_source_main

        def reads(uri, *, stateful=False, version=None):
            if version == "active":
                return self.sap.err("NETWORK_ERROR", "ReadTimeout for GET x")
            return orig(uri, stateful=stateful, version=version)

        with patch.object(self.h, "read_source_main", reads):
            rep = self.run_plan(self.plan(activate=True))
        self.assertEqual(rep.final_decision().code, "WRITE_INCOMPLETE")
        self.assertEqual(rep.activation["status"], "unknown")


class ActivationParserTests(_Base):
    def test_chkl_messages_are_errors(self):
        xml = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<chkl:messages xmlns:chkl="http://www.sap.com/abapxml/checklist">'
            '<msg objDescr="Program ZPROBE" type="E" line="2" href="/sap/bc/adt/'
            'programs/programs/zprobe/source/main#start=2,0" forceSupported="true">'
            '<shortText><txt>Statement is not defined.</txt></shortText></msg>'
            '</chkl:messages>')
        parsed = self.h.parse_activation_response(xml)
        errs = self.h.activation_errors(parsed)
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0]["text"], "Statement is not defined.")
        self.assertEqual(errs[0]["line"], "2")

    def test_real_chkl_fixture_line_from_href(self):
        # Captured from S/4HANA 2021 / Basis 7.56 (syntax error on line 3).
        xml = (Path(__file__).parent / "fixtures" / "sap_adt_cli"
               / "activate.syntax-error.chkl.xml").read_text()
        parsed = self.h.parse_activation_response(xml)
        self.assertIs(parsed["activation_executed"], False)
        err = self.h.activation_errors(parsed)[0]
        self.assertEqual(err["type"], "E")
        self.assertEqual(err["line"], "3")
        self.assertIn("THIS_IS_NOT_ABAP", err["text"])

    def test_activate_object_maps_errors_to_activation_failed(self):
        xml = ('<chkl:messages xmlns:chkl="http://www.sap.com/abapxml/checklist">'
               '<msg type="E" line="1" href="/x/source/main#start=2,0">'
               '<shortText><txt>boom</txt></shortText>'
               '</msg></chkl:messages>')

        class Resp:
            text = xml
            content = xml.encode()
            status_code = 200

        patch.stopall()
        with patch.object(self.h, "_base", return_value="https://x"), \
                patch.object(self.h, "make_adt_request", return_value=Resp()):
            r = self.h.activate_object("program", "ZPROBE")
        self.assertTrue(r.is_error)
        self.assertEqual(r.error_code, "ACTIVATION_FAILED")
        self.assertIn("line 2 boom", r.text)

    def test_unlock_exception_is_surfaced(self):
        AdtHttpError = sys.modules["sap_adt.adt.client"].AdtHttpError
        patch.stopall()
        with patch.object(self.h, "_base", return_value="https://x"), \
                patch.object(self.h, "make_adt_request",
                             side_effect=AdtHttpError("HTTPError 500 for POST x", status=500)):
            r = self.h.unlock_object("/sap/bc/adt/programs/programs/zprobe", "H")
        self.assertTrue(r.is_error)


class CliTests(_Base):
    class Cfg:
        username = "DEV"
        url = "https://sap.example.invalid"
        client = "400"
        profile_name = "dev"
        allow_write = True
        allow_transport = False
        environment = "dev"
        environment_source = "explicit"
        from_environment = False
        write_source = "profile"
        transport_source = "global"
        env_write_requested = False
        env_transport_requested = False
        is_production = False

        def base_url(self):
            return self.url

    def setUp(self):
        super().setUp()
        tmp = tempfile.NamedTemporaryFile("wb", suffix=".abap", delete=False)
        tmp.write(NEW.encode())
        tmp.close()
        self.file = tmp.name
        self.addCleanup(Path(tmp.name).unlink, missing_ok=True)

    def invoke(self, *args, tty=False, input=None):
        with patch.object(self.cli, "load_config", return_value=self.Cfg()), \
                patch.object(self.cli, "_stdin_is_tty", return_value=tty):
            return CliRunner().invoke(
                self.cli.cli,
                ["write-source", "program", "ZPROBE", "--file", self.file, *args],
                input=input)

    @staticmethod
    def envelope(r):
        return json.loads(r.stderr[r.stderr.find("{"):])

    def test_yes_without_expected_baseline_is_refused_before_http(self):
        r = self.invoke("--yes")
        self.assertEqual(r.exit_code, 3, r.output)
        self.assertEqual(self.envelope(r)["error"]["code"], "CONFIRM_REQUIRED")
        self.assertEqual(self.sap.calls, [])

    def test_yes_with_wrong_baseline_never_locks(self):
        r = self.invoke("--yes", "--expect-baseline-sha256", "a" * 64)
        self.assertEqual(r.exit_code, 3, r.output)
        env = self.envelope(r)
        self.assertEqual(env["error"]["code"], "BASELINE_CHANGED")
        self.assertEqual(env["data"]["baseline"]["sha256"], sha(self.sw.canonical_source(OLD)))
        self.assertEqual(self.sap.ops(), ["GET"])

    def test_yes_with_wrong_expected_content_never_locks(self):
        r = self.invoke("--yes", "--expect-baseline-sha256", sha(self.sw.canonical_source(OLD)),
                        "--expect-content-sha256", "b" * 64)
        self.assertEqual(r.exit_code, 3, r.output)
        self.assertEqual(self.envelope(r)["error"]["code"], "CONTENT_CHANGED")
        self.assertNotIn("LOCK", self.sap.ops())

    def test_dry_run_then_bound_yes_run_completes(self):
        r = self.invoke("--dry-run")
        self.assertEqual(r.exit_code, 0, r.output)
        data = json.loads(r.stdout)["data"]
        self.assertEqual(data["content"]["sha256"], sha(NEW_CANON))
        self.assertIn("+WRITE / 'new'.", data["diff"])
        self.assertEqual(self.sap.ops(), ["GET"])

        r = self.invoke("--yes", "--activate",
                        "--expect-baseline-sha256", data["baseline"]["sha256"],
                        "--expect-content-sha256", data["content"]["sha256"])
        self.assertEqual(r.exit_code, 0, r.output)
        out = json.loads(r.stdout)
        self.assertEqual(out["kind"], "write")
        self.assertEqual(out["data"]["outcome"], "completed")
        self.assertEqual(out["data"]["write"]["status"], "verified")
        self.assertEqual(out["data"]["activation"]["status"], "verified")

    def test_failure_envelope_carries_stage_data_and_nonzero_exit(self):
        self.sap.unlock_error = self.sap.err("SERVER_ERROR", "HTTPError 400", 400)
        r = self.invoke("--yes", "--expect-baseline-sha256",
                        sha(self.sw.canonical_source(OLD)))
        self.assertEqual(r.exit_code, 3, r.output)
        env = self.envelope(r)
        self.assertEqual(env["error"]["code"], "WRITE_INCOMPLETE")
        self.assertEqual(env["data"]["write"]["status"], "verified")
        self.assertEqual(env["data"]["unlock"]["status"], "failed")
        self.assertEqual(r.stdout, "")

    def test_file_changed_after_tty_confirmation(self):
        def confirm_and_tamper(_preview, yes=False):
            Path(self.file).write_bytes(b"REPORT zprobe.\nWRITE / 'evil'.")

        with patch.object(self.cli, "_confirm_change", confirm_and_tamper):
            r = self.invoke(tty=True)
        self.assertEqual(r.exit_code, 3, r.output)
        self.assertEqual(self.envelope(r)["error"]["code"], "CONTENT_CHANGED")
        self.assertNotIn("PUT", self.sap.ops())

    def test_non_utf8_file_is_bad_request(self):
        Path(self.file).write_bytes(b"REPORT z.\n\xff")
        r = self.invoke("--dry-run")
        self.assertEqual(r.exit_code, 1, r.output)
        self.assertEqual(self.envelope(r)["error"]["code"], "BAD_REQUEST")


if __name__ == "__main__":
    unittest.main()
