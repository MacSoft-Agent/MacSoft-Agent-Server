from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from macsoft_runtime.metadata import load_product_metadata
from macsoft_runtime.paths import resolve_development_paths, resolve_packaged_paths


class ProductMetadataAndPathsTests(unittest.TestCase):
    def test_metadata_uses_independent_product_version(self) -> None:
        root = Path(__file__).resolve().parents[2]
        metadata = load_product_metadata(root)
        self.assertEqual(metadata.product, "MacSoft Agent")
        self.assertEqual(metadata.product_version, "0.1.0")
        self.assertEqual(len(metadata.runtime_base_commit), 40)
        self.assertIsNone(metadata.update_manifest_url)

    def test_development_paths_stay_under_project_root(self) -> None:
        root = Path(__file__).resolve().parents[2]
        paths = resolve_development_paths(root)
        self.assertEqual(paths.runtime_root, root / "runtime")
        self.assertEqual(paths.server_data_root, root / "server")
        self.assertFalse(paths.is_packaged)

    def test_packaged_paths_separate_program_and_mutable_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            program_root = (base / "Program").resolve()
            data_root = (base / "Data").resolve()
            paths = resolve_packaged_paths(program_root, data_root)
            self.assertTrue(paths.is_packaged)
            self.assertTrue(paths.python_executable.is_relative_to(program_root))
            self.assertTrue(paths.runtime_root.is_relative_to(data_root))
            self.assertTrue(paths.server_database.is_relative_to(data_root))
            self.assertFalse(paths.runtime_root.is_relative_to(program_root))

    def test_manifest_url_must_be_https_or_null(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = json.loads((Path(__file__).resolve().parents[2] / "product.json").read_text("utf-8"))
            source["update_manifest_url"] = "http://updates.example.test/manifest.json"
            (root / "product.json").write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                load_product_metadata(root)


if __name__ == "__main__":
    unittest.main()
