"""Acceptance #5: the committed gitleaks config must block a hardcoded
secret landing in production paths (and allow the tests/docs exceptions).

Skipped when the gitleaks binary is not installed locally; CI installs it.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / ".gitleaks.toml"


@unittest.skipUnless(shutil.which("gitleaks"), "gitleaks binary not installed")
class GitleaksHookTests(unittest.TestCase):
    def run_gitleaks(self, source: Path):
        report = source / "_gitleaks_report.json"
        proc = subprocess.run(
            ["gitleaks", "detect", "--no-git", "--config", str(CONFIG),
             "--source", str(source), "--exit-code", "1",
             "--report-path", str(report), "--report-format", "json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        import json as _json
        try:
            proc.findings = _json.loads(report.read_text()) if report.exists() else []
        except ValueError:
            proc.findings = []
        return proc

    def test_hardcoded_password_in_production_path_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "leak.py").write_text(
                'password = "SuperS3cretPw!"\n', encoding="utf-8"
            )
            result = self.run_gitleaks(root)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(
                "sap-adt-hardcoded-secret",
                [f.get("RuleID") for f in result.findings],
            )

    def test_same_secret_under_tests_and_docs_is_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "tests").mkdir()
            (root / "tests" / "fixture.py").write_text(
                'password = "SuperS3cretPw!"\n', encoding="utf-8"
            )
            (root / "README.md").write_text(
                'SAP_PASSWORD="SuperS3cretPw!"\n', encoding="utf-8"
            )
            result = self.run_gitleaks(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_clean_source_passes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "clean.py").write_text(
                'password = os.environ["SAP_ADT_DEV_PASSWORD"]\n',
                encoding="utf-8",
            )
            result = self.run_gitleaks(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
