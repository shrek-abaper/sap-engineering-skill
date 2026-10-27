"""Distribution contracts: skill snapshots, self-containment, plugin payload.

These tests build into temporary directories from the repository source and
assert the packaging guarantees (spec §9, §12):

  - generated setup/compatibility snapshots exist in the source tree and are
    in sync with their single sources (offline `--check`);
  - a standalone skill snapshot contains no execution code, caches, secrets
    or raw fixtures, and every relative Markdown link resolves inside it;
  - knowledge-type skills declare that they need no CLI;
  - the plugin payload reuses the same snapshots and carries no CLI core.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_plugin  # noqa: E402
import build_skills  # noqa: E402
import sync_skill_runtime_docs  # noqa: E402

SKILLS = list(build_skills.ALLOWLIST)
LINK_RE = re.compile(r"\]\(([^)#]+)(?:#[^)]*)?\)")


def relative_links(md_file: Path):
    text = md_file.read_text(encoding="utf-8")
    for target in LINK_RE.findall(text):
        if "://" in target or target.startswith("mailto:"):
            continue
        yield target


class GeneratedSnapshotTests(unittest.TestCase):
    def test_snapshots_in_sync(self):
        self.assertEqual(sync_skill_runtime_docs.main(["--check"]), 0)

    def test_every_skill_has_snapshots_and_readme_block(self):
        compat = json.loads((ROOT / "compatibility.json").read_text(encoding="utf-8"))
        for name in SKILLS:
            with self.subTest(skill=name):
                refs = ROOT / "skills" / name / "references"
                self.assertTrue((refs / "setup.md").is_file())
                snap = json.loads(
                    (refs / "runtime-compatibility.json").read_text(encoding="utf-8"))
                self.assertEqual(snap["cli"]["compatible_versions"],
                                 compat["cli"]["compatible_versions"])
                self.assertEqual(snap["skill"]["name"], name)
                readme = (ROOT / "skills" / name / "README.md").read_text(encoding="utf-8")
                self.assertIn("BEGIN GENERATED cli-setup", readme)

    def test_check_detects_drift(self):
        # Copy the source tree pieces the tool needs, tamper, expect drift.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "docs" / "installation").mkdir(parents=True)
            (root / "docs" / "installation" / "runtime-setup.md").write_text("body")
            (root / "compatibility.json").write_text(
                (ROOT / "compatibility.json").read_text(encoding="utf-8"))
            for name in SKILLS:
                src = ROOT / "skills" / name
                dst = root / "skills" / name
                dst.mkdir(parents=True)
                (dst / "references").mkdir()
                for f in ("SKILL.md", "README.md"):
                    (dst / f).write_text((src / f).read_text(encoding="utf-8"),
                                         encoding="utf-8")
            self.assertEqual(sync_skill_runtime_docs.main(["--root", str(root)]), 0)
            self.assertEqual(
                sync_skill_runtime_docs.main(["--root", str(root), "--check"]), 0)
            setup = root / "skills" / "sap-adt-cli" / "references" / "setup.md"
            setup.write_text("tampered", encoding="utf-8")
            self.assertEqual(
                sync_skill_runtime_docs.main(["--root", str(root), "--check"]), 1)


class StandaloneSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.TemporaryDirectory()
        cls.out = Path(cls.td.name) / "skills"
        build_skills.build_all(ROOT, cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    def test_no_execution_code_or_private_files(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                skill = self.out / name
                files = [p for p in skill.rglob("*") if p.is_file()]
                names = {p.name for p in files}
                self.assertNotIn("sap_adt_cli.py", names)
                self.assertNotIn("tr_collector.py", names)
                self.assertFalse(any(n == "__pycache__" for n in names))
                self.assertFalse(any(p.suffix == ".pyc" for p in files))
                self.assertFalse(any(p.name == ".env" for p in files))
                self.assertFalse(any("fixtures/raw" in str(p) for p in files))
                self.assertFalse((skill / "tests").exists())

    def test_sap_adt_cli_snapshot_has_no_scripts_dir(self):
        self.assertFalse((self.out / "sap-adt-cli" / "scripts").exists())
        # ...but the wiki keeps its content generators.
        self.assertTrue(
            (self.out / "sap-integration-wiki" / "scripts" / "gen-idoc-template.py").is_file())

    def test_relative_links_resolve_inside_snapshot(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                skill = (self.out / name).resolve()
                for md in list(skill.glob("*.md")) + list(skill.rglob("references/*.md")):
                    for target in relative_links(md):
                        target_path = (md.parent / target).resolve()
                        self.assertTrue(
                            str(target_path).startswith(str(skill)),
                            f"{md.relative_to(skill)} links outside the skill: {target}")
                        self.assertTrue(
                            target_path.exists(),
                            f"{md.relative_to(skill)} has a broken link: {target}")

    def test_knowledge_skills_declare_no_cli(self):
        for name in ("abap-code-review", "sap-integration-wiki"):
            text = (self.out / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("Runtime requirement: none", text)


class PluginPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.TemporaryDirectory()
        cls.out = Path(cls.td.name) / "plugin"
        build_plugin.build_plugin(ROOT, cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    def test_payload_shape(self):
        self.assertTrue((self.out / ".claude-plugin" / "plugin.json").is_file())
        self.assertTrue((self.out / "compatibility.json").is_file())
        self.assertTrue((self.out / "LICENSE").is_file())
        self.assertEqual(
            sorted(p.name for p in (self.out / "skills").iterdir()), sorted(SKILLS))

    def test_plugin_version_matches_compatibility(self):
        plugin = json.loads(
            (self.out / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        compat = json.loads(
            (self.out / "compatibility.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["version"], compat["plugin_version"])

    def test_no_cli_core_or_shims_in_payload(self):
        files = [p for p in self.out.rglob("*") if p.is_file()]
        self.assertFalse(any("src/sap_adt" in str(p) for p in files))
        self.assertFalse(any(p.name in ("sap_adt_cli.py", "tr_collector.py") for p in files))
        self.assertFalse(any(p.suffix == ".py" and "skills/sap-adt-cli" in str(p)
                             for p in files))


if __name__ == "__main__":
    unittest.main()
