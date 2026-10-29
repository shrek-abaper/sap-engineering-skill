"""Portable runtimes must satisfy the npm extractor's no-symlink contract."""
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_runtime


@unittest.skipIf(os.name == "nt", "tar runtimes are built on Linux/macOS")
class RuntimeArchiveTests(unittest.TestCase):
    def test_internal_framework_links_become_regular_archive_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tree = root / "sap-adt"
            version = tree / "Python.framework" / "Versions" / "3.12"
            version.mkdir(parents=True)
            (version / "Python").write_bytes(b"runtime")
            (version.parent / "Current").symlink_to("3.12", target_is_directory=True)
            (version.parent.parent / "Python").symlink_to("Versions/Current/Python")
            archive = build_runtime.archive_dir(tree, root, "runtime")
            with tarfile.open(archive) as tf:
                self.assertFalse(any(m.issym() or m.islnk() for m in tf.getmembers()))
                for name in (
                    "sap-adt/Python.framework/Python",
                    "sap-adt/Python.framework/Versions/Current/Python",
                ):
                    self.assertEqual(tf.extractfile(name).read(), b"runtime")

    def test_external_link_is_not_bundled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tree = root / "sap-adt"
            tree.mkdir()
            (root / "outside").write_bytes(b"not runtime data")
            (tree / "external").symlink_to("../outside")
            with self.assertRaisesRegex(ValueError, "escapes the runtime tree"):
                build_runtime.archive_dir(tree, root, "runtime")
            self.assertFalse((root / "runtime.tar.gz").exists())
