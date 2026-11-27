"""Watt packaging shares one core and never owns the legacy command."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_watt


class WattDistributionTests(unittest.TestCase):
    def test_native_module_entry_uses_launcher_identity(self):
        result = subprocess.run(
            [sys.executable, "-m", "sap_adt", "--version"],
            env={**os.environ, "_SAP_ADT_COMMAND": "sap-watt"},
            capture_output=True, encoding="utf-8", check=True,
        )
        self.assertTrue(result.stdout.startswith("sap-watt, version "), result.stdout)
        self.assertFalse(result.stderr)

    def test_staged_entry_pins_core_and_extras_without_bundling_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text('version = "1.6.7"\n')
            shutil.copytree(ROOT / "packaging", root / "packaging")
            shutil.copy2(ROOT / "LICENSE", root / "LICENSE")
            stage = build_watt.stage(root)
            metadata = (stage / "pyproject.toml").read_text()
            self.assertIn('version = "1.6.7"', metadata)
            self.assertIn('"sap-adt-cli==1.6.7"', metadata)
            self.assertIn('"sap-adt-cli[keystore,file]==1.6.7"', metadata)
            self.assertIn('sap-watt = "sap_watt:main"', metadata)
            self.assertNotIn('\nsap-adt =', metadata)
            self.assertEqual(
                {p.name for p in stage.iterdir()},
                {"pyproject.toml", "sap_watt.py", "README.md", "LICENSE"})

    def test_entry_version_help_and_json_match_legacy_contract(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "packaging" / "python")
        env.pop("_SAP_ADT_COMMAND", None)
        watt = [sys.executable, "-m", "sap_watt"]
        legacy = [sys.executable, "-m", "sap_adt.cli"]
        for args in (["--version"], ["--help"], ["transport", "--help"]):
            new = subprocess.run(watt + args, env=env, capture_output=True, encoding="utf-8", check=True)
            old = subprocess.run(legacy + args, env=env, capture_output=True, encoding="utf-8", check=True)
            self.assertEqual(new.stdout.replace("sap-watt", "sap-adt"), old.stdout)
            self.assertFalse(new.stderr)
        new = subprocess.run(watt + ["--format", "json", "not-a-command"],
                             env=env, capture_output=True, encoding="utf-8")
        old = subprocess.run(legacy + ["--format", "json", "not-a-command"],
                             env=env, capture_output=True, encoding="utf-8")
        self.assertEqual(new.returncode, old.returncode)
        self.assertEqual(json.loads(new.stderr), json.loads(old.stderr))
        self.assertFalse(new.stdout)

    def test_unconfigured_watt_points_to_an_installed_command(self):
        with tempfile.TemporaryDirectory() as home:
            env = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith(("SAP_", "_SAP_ADT_"))}
            env.update({"PYTHONPATH": str(ROOT / "packaging" / "python"),
                        "HOME": home, "USERPROFILE": home})
            result = subprocess.run(
                [sys.executable, "-m", "sap_watt", "status"], env=env,
                capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 2, result.stderr)
        error = json.loads(result.stderr)["error"]
        self.assertIn("sap-watt configure", error["message"])
        self.assertIn("sap-watt configure", error["hint"])


if __name__ == "__main__":
    unittest.main()
