"""Release manifest must ship the desktop installer for the current CLI."""
import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_manifest  # noqa: E402
import check_release  # noqa: E402


class DesktopInstallerManifestTests(unittest.TestCase):
    def build_fixture(self, root, with_installer):
        (root / "pyproject.toml").write_text('version = "1.5.3"\n')
        (root / "compatibility.json").write_text('{"plugin_version": "1.2.7"}')
        (root / "packaging").mkdir()
        (root / "packaging" / "targets.json").write_text('{"targets": {}}')
        dist = root / "dist"
        for directory in ("runtime", "installers", "release", "skills", "plugin/.claude-plugin"):
            (dist / directory).mkdir(parents=True)
        for name in ("sap_adt_cli-1.5.3-py3-none-any.whl", "sap_adt_cli-1.5.3.tar.gz",
                     "sap_watt-1.5.3-py3-none-any.whl", "sap_watt-1.5.3.tar.gz"):
            (dist / name).write_bytes(b"python package")
        (dist / "runtime" / "sap-adt-1.5.3-windows-x86_64.zip").write_bytes(b"runtime")
        (dist / "release" / "sap-adt-cli-1.5.3.tgz").write_bytes(b"npm")
        (dist / "release" / "sap-watt-1.5.3.tgz").write_bytes(b"watt npm")
        (dist / "plugin" / ".claude-plugin" / "plugin.json").write_text('{"version": "1.2.7"}')
        (dist / "installers" / "sap-adt-1.5.2-windows-x86_64-setup.exe").write_bytes(b"old")
        if with_installer:
            (dist / "installers" / "sap-adt-1.5.3-windows-x86_64-setup.exe").write_bytes(b"installer")

    def run_manifest(self, root):
        with patch.object(build_manifest, "ROOT", root), \
             patch.object(sys, "argv", ["build_manifest.py", "--skip-npm-pack"]), \
             patch.object(build_manifest.subprocess, "run"), \
             patch.object(build_manifest, "git",
                          side_effect=lambda *args: "" if args[0] == "status" else "a" * 40):
            self.assertEqual(build_manifest.main(), 0)
        return json.loads((root / "dist" / "release" / "release-manifest.json").read_text())

    def test_current_installer_is_copied_hashed_and_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_fixture(root, with_installer=True)
            manifest = self.run_manifest(root)
            entries = [a for a in manifest["artifacts"] if a["kind"] == "installer"]
            self.assertEqual(len(entries), 1)
            entry = entries[0]
            self.assertEqual(entry["target"], "windows-x86_64")
            self.assertEqual(entry["file"], "sap-adt-1.5.3-windows-x86_64-setup.exe")
            self.assertEqual(entry["sha256"], hashlib.sha256(b"installer").hexdigest())
            release = root / "dist" / "release"
            self.assertEqual((release / entry["file"]).read_bytes(), b"installer")
            self.assertIn(f"{entry['sha256']}  {entry['file']}", (release / "SHA256SUMS").read_text())

    def test_old_installer_is_not_advertised_for_new_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_fixture(root, with_installer=False)
            manifest = self.run_manifest(root)
            self.assertFalse(any(a["kind"] == "installer" for a in manifest["artifacts"]))

    def test_both_entry_packages_ship_at_the_current_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_fixture(root, with_installer=False)
            manifest = self.run_manifest(root)
            for package in ("sap-adt-cli", "sap-watt"):
                self.assertEqual(
                    {a["kind"] for a in manifest["artifacts"] if a.get("package") == package},
                    {"wheel", "sdist", "npm"})

    def test_native_ci_verification_is_distinct_from_unverified_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_fixture(root, with_installer=False)
            (root / "packaging" / "targets.json").write_text(json.dumps({"targets": {
                "darwin-aarch64": {"status": "verified-ci"},
                "linux-x86_64": {"status": "verified-local"},
                "linux-aarch64": {"status": "planned-unverified"},
                "future-target": {"status": "unknown"},
            }}))
            self.assertEqual(self.run_manifest(root)["unverified_targets"],
                             ["linux-aarch64", "future-target"])

    def check_renamed_marketplace(self, root, manifest, live_source):
        plugins = root / ".claude-plugin"
        plugins.mkdir(exist_ok=True)
        (plugins / "plugin.json").write_text('{"version": "1.2.7"}')
        (plugins / "marketplace.json").write_text(json.dumps({
            "plugins": [{"source": live_source}]}))
        for package, staging, command in (("sap-adt-cli", "npm", "sap-adt"),
                                          ("sap-watt", "npm-watt", "sap-watt")):
            directory = root / "dist" / staging
            directory.mkdir(exist_ok=True)
            (directory / "package.json").write_text(json.dumps({
                "name": package, "version": "1.5.3", "bin": {command: "scripts/run.js"}}))
        release = root / "dist" / "release"
        (release / "release-manifest.json").write_text(json.dumps(manifest))
        with patch.object(check_release, "ROOT", root), \
             patch.object(build_manifest, "ROOT", root), \
             patch.object(sys, "argv", ["check_release.py", "--release-dir", str(release)]), \
             redirect_stdout(io.StringIO()):
            return check_release.main()

    def test_published_archive_survives_repository_rename_without_manifest_rewrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_fixture(root, with_installer=False)
            manifest = self.run_manifest(root)
            market = manifest["marketplace_candidate"]
            market["state"] = "published"
            live_source = dict(market["source"])
            market["source"]["url"] = live_source["url"].replace(
                "/shrek-abaper/sap-watt/", "/shrek-abaper/sap-engineering-skill/")
            self.assertEqual(self.check_renamed_marketplace(root, manifest, live_source), 0)

    def test_repository_rename_does_not_allow_different_asset_or_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_fixture(root, with_installer=False)
            manifest = self.run_manifest(root)
            market = manifest["marketplace_candidate"]
            market["state"] = "published"
            source = market["source"]
            for changed in (
                {**source, "url": source["url"].replace("/sap-watt/", "/other-repo/")},
                {**source, "url": source["url"] + ".different"},
                {**source, "sha256": "0" * 64},
            ):
                with self.subTest(source=changed):
                    self.assertEqual(self.check_renamed_marketplace(root, manifest, changed), 1)


if __name__ == "__main__":
    unittest.main()
