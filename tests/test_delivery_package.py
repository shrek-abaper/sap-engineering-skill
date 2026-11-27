"""Delivery evidence integrity, declared scope and fail-closed completeness."""
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
from test_sap_adt_cli_config import load_cli_module


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.cli, config = load_cli_module()
        from sap_adt import artifacts, delivery, policy
        self.a, self.m = artifacts, delivery
        self.target = policy.target(config.SapConfig("https://a.invalid", "U", "secret", "100"))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tr = "DEVK900001"

    def package(self, kind, doc, *, extras=None, gaps=None, target=None, suffix=""):
        path = self.root / (kind + suffix + ".zip")
        assets = {self.m.PRIMARY[kind]: doc, **(extras or {})}
        self.a.write_package(path, "git-change-set" if kind == "git" else kind, assets,
                             context={"target": target or self.target, "transport": self.tr}, gaps=gaps)
        return f"{kind}={path}"

    def complete_inputs(self):
        return [
            self.package("transport", {"target": self.target, "transport": self.tr},
                         extras={"sources/ZCL_A.abap": b"source"}),
            self.package("unit", {"summary": {"status": "passed", "executed": 1},
                                  "gate": {"status": "passed"}}),
            self.package("quality", {"target": self.target, "gate": {"status": "passed"},
                                     "engines": [{"engine": "syntax", "status": "passed"}]}),
            self.package("git", {"transport": self.tr, "transport_verified": True}),
        ]

    def pack(self, assets, **kwargs):
        return self.m.pack("REQ-123", [self.tr], assets, self.target["fingerprint"],
                           self.root / "delivery.zip", **kwargs)

    def test_complete_declared_assets_are_hashed_and_preserved_without_replay(self):
        assets = self.complete_inputs()
        with patch.object(self.cli, "load_config", side_effect=AssertionError("offline package")):
            data = self.pack(assets)
        self.assertEqual(data["assembly"]["status"], "complete_within_declared_assets")
        self.assertFalse(data["assembly"]["release_approval"])
        with ZipFile(self.root / "delivery.zip") as archive:
            self.assertEqual(len([n for n in archive.namelist() if n.startswith("evidence/")]), 4)
        with self.assertRaises(FileExistsError):
            self.pack(assets)

    def test_delivery_cli_is_offline_and_returns_a_local_write_envelope(self):
        import json
        from click.testing import CliRunner
        args = ["-f", "json", "delivery", "pack", "REQ-123", "--transport", self.tr,
                "--target-fingerprint", self.target["fingerprint"],
                "--output-file", str(self.root / "cli-delivery.zip")]
        for asset in self.complete_inputs():
            args.extend(["--asset", asset])
        with patch.object(self.cli, "load_config", side_effect=AssertionError("offline only")) as load:
            result = CliRunner().invoke(self.cli.cli, args)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertFalse(load.called)
        envelope = json.loads(result.output)
        self.assertEqual(envelope["meta"]["operation"]["type"], "local_write")
        self.assertEqual(envelope["data"]["assembly"]["status"], "complete_within_declared_assets")

    def test_missing_assets_and_zero_executed_unit_tests_never_produce_complete_delivery(self):
        asset = self.package("unit", {"summary": {"status": "not_run", "executed": 0},
                                      "gate": {"status": "passed"}})
        result = self.pack([asset])
        codes = {g["code"] for g in result["evidence_gaps"]}
        self.assertIn("UNIT_EXECUTION_NOT_PROVEN", codes)
        self.assertIn("TRANSPORT_EVIDENCE_MISSING", codes)
        self.assertIn("REQUIRED_EVIDENCE_MISSING", codes)
        self.assertEqual(result["assembly"]["status"], "incomplete")

    def test_modified_archive_content_is_rejected_before_output_creation(self):
        selected = self.package("transport", {"transport": self.tr})
        path = Path(selected.split("=", 1)[1])
        with ZipFile(path) as old:
            contents = {n: old.read(n) for n in old.namelist()}
        contents["transport.json"] = b"{}"
        with ZipFile(path, "w") as archive:
            for name, raw in contents.items():
                archive.writestr(name, raw)
        with self.assertRaisesRegex(ValueError, "hash/size mismatch"):
            self.pack([selected])
        self.assertFalse((self.root / "delivery.zip").exists())

    def test_cross_environment_or_transport_artifacts_are_not_mixed(self):
        from sap_adt.config import SapConfig
        from sap_adt import policy
        other = policy.target(SapConfig("https://b.invalid", "U", "secret", "200"))
        selected = self.package("transport", {"transport": self.tr}, target=other)
        with self.assertRaisesRegex(ValueError, "SAP target"):
            self.pack([selected])
        other_tr = self.package("transport", {"transport": "DEVK900002"}, suffix="-other-tr")
        with self.assertRaisesRegex(ValueError, "outside"):
            self.pack([other_tr])

    def test_archive_repackaging_cannot_hide_a_known_stale_capture_time(self):
        stale = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        selected = self.package("configuration", {"target": self.target, "captured_at": stale})
        result = self.pack([selected], required=["configuration"])
        self.assertIn("ARTIFACT_STALE_OR_FUTURE_DATED", {g["code"] for g in result["evidence_gaps"]})

    def test_unsafe_members_and_duplicate_category_claims_are_rejected(self):
        selected = self.package("transport", {"transport": self.tr})
        path = Path(selected.split("=", 1)[1])
        with ZipFile(path, "a") as archive:
            archive.writestr("../escape.abap", b"no extraction")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            self.pack([selected])
        first = self.package("quality", {"gate": {"status": "passed"}, "engines": []})
        with self.assertRaisesRegex(ValueError, "multiple evidence categories"):
            self.pack([first, first])

    def test_legacy_transport_layout_gets_a_hashed_target_bound_wrapper(self):
        from sap_adt.transport import collector
        from sap_adt.config import SapConfig
        source = self.root / "sources"
        source.mkdir()
        (source / "CLAS_ZCL_A.abap").write_text("source")
        manifest = {"meta": {"tr_id": self.tr}, "objects": [
            {"source_file": "sources/CLAS_ZCL_A.abap", "source_fetched": True}]}
        cfg = SapConfig("https://a.invalid", "U", "secret", "100")
        output = self.root / "transport.zip"
        collector.bundle(output, self.root, manifest, cfg)
        doc, index = self.m._package(output.read_bytes(), "transport")
        self.assertEqual(doc["target"], self.target)
        self.assertFalse(index["partial"])
