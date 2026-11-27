"""Read-only local Git evidence, explicit mapping, and serialization boundaries."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from test_sap_adt_cli_config import load_cli_module


class GitBridgeTests(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()
        from sap_adt import git_bridge
        self.m = git_bridge
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        (self.root / "src").mkdir()
        self.source = "src/zcl_a.clas.abap"
        (self.root / self.source).write_text("CLASS zcl_a DEFINITION. ENDCLASS.\n")
        (self.root / ".abapgit.xml").write_text("<abapGit/>")
        self.git("add", ".")
        self.git("commit", "-qm", "Initial")
        self.manifest = {"schema_version": 1, "transport": "DEVK900001",
                         "objects": [{"pgmid": "R3TR", "type": "CLAS", "name": "ZCL_A",
                                      "files": [self.source]}]}
        self.mapping = self.root / "mapping.json"
        self.mapping.write_text(json.dumps(self.manifest))

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              capture_output=True).stdout

    def test_status_uses_explicit_repo_and_decodes_rename_records(self):
        original = "src/old name.clas.abap"
        self.git("mv", self.source, original)
        with patch.dict(os.environ, {"GIT_DIR": "/invalid/external/git"}):
            state = self.m.status(self.root)
        renamed = next(c for c in state["changes"] if c.get("original_path"))
        self.assertEqual(renamed["path"], original)
        self.assertEqual(renamed["original_path"], self.source)

    def test_untracked_object_file_is_exported_without_fake_transport_verification(self):
        extra = "src/new.clas.abap"
        (self.root / extra).write_text("new")
        self.manifest["objects"][0]["files"] = [extra]
        self.mapping.write_text(json.dumps(self.manifest))
        out = self.root / "evidence.zip"
        result = self.m.export(self.root, "DEVK900001", self.mapping, out)
        self.assertFalse(result["transport_verified"])
        self.assertFalse(result["serialization"]["server_abapgit_serialization"])
        with ZipFile(out) as archive:
            self.assertEqual(archive.read("files/" + extra), b"new")

    def test_commit_export_does_not_mix_working_tree_bytes_or_config(self):
        (self.root / self.source).write_text("uncommitted source")
        (self.root / ".abapgit.xml").write_text("uncommitted config")
        out = self.root / "commit.zip"
        self.m.export(self.root, "DEVK900001", self.mapping, out, commit="HEAD")
        with ZipFile(out) as archive:
            self.assertNotEqual(archive.read("files/" + self.source), b"uncommitted source")
            self.assertEqual(archive.read("files/.abapgit.xml"), b"<abapGit/>")

    def test_mapping_rejects_traversal_and_ambiguous_file_ownership(self):
        for files in (["../outside.abap"], [self.source, self.source]):
            self.manifest["objects"][0]["files"] = files
            self.mapping.write_text(json.dumps(self.manifest))
            with self.assertRaises(ValueError):
                self.m.mapping(self.root, "DEVK900001", self.mapping)

    def test_cli_status_never_loads_sap_credentials(self):
        from click.testing import CliRunner
        with patch.object(self.cli, "load_config", side_effect=AssertionError("local Git only")) as load:
            result = CliRunner().invoke(self.cli.cli, ["-f", "json", "git", "status", "--repo", str(self.root)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertFalse(load.called)
        self.assertTrue(json.loads(result.output)["ok"])

    def test_online_mapping_records_target_and_never_accepts_an_absent_object(self):
        from sap_adt.config import SapConfig
        from sap_adt.transport import analysis
        cfg = SapConfig("https://example.invalid", "U", "secret", "100")
        obj = self.manifest["objects"][0]
        with patch.object(analysis, "objects", return_value=([obj], [], [])):
            good = self.m.mapping(self.root, "DEVK900001", self.mapping,
                                  verify_transport=True, config=cfg)
        self.assertTrue(good["transport_verified"])
        self.assertEqual(good["target"]["client"], "100")
        with patch.object(analysis, "objects", return_value=([], [], [])):
            bad = self.m.mapping(self.root, "DEVK900001", self.mapping,
                                 verify_transport=True, config=cfg)
        self.assertFalse(bad["transport_verified"])
