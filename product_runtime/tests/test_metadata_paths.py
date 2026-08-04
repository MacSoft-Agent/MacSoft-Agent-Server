from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

from macsoft_runtime.compatibility import assess_pre_start_compatibility
from macsoft_runtime.metadata import load_product_metadata
from macsoft_runtime.paths import resolve_development_paths, resolve_packaged_paths


class ProductMetadataAndPathsTests(unittest.TestCase):
    def test_metadata_uses_independent_product_version(self) -> None:
        root = Path(__file__).resolve().parents[2]
        source = json.loads((root / "product.json").read_text("utf-8"))
        metadata = load_product_metadata(root)
        self.assertEqual(metadata.product, "MacSoft Agent")
        self.assertEqual(source["product_version"], "0.1.6")
        self.assertEqual(source["build_id"], "macsoft-agent-0.1.6-stable.20260804.1")
        self.assertEqual(source["runtime_base_version"], "v2026.7.7.2")
        self.assertEqual(
            source["runtime_base_commit"],
            "79f12748022817a7c4f3fee747e45e9e6979214a",
        )
        self.assertEqual(source["data_schema_version"], 1)
        self.assertEqual(metadata.product_version, source["product_version"])
        self.assertEqual(metadata.build_id, source["build_id"])
        self.assertEqual(len(metadata.runtime_base_commit), 40)
        self.assertEqual(metadata.runtime_contract_version, 1)
        self.assertEqual(metadata.runtime_metadata_schema_version, 1)
        self.assertEqual(
            metadata.update_manifest_url,
            "https://github.com/MacSoft-Agent/MacSoft-Agent-Releases/releases/latest/download/"
            "macsoft-agent-stable-manifest-v1.json",
        )
        self.assertEqual(
            metadata.update_manifest_public_key,
            "MCowBQYDK2VwAyEANuklnSpzDv32q5qf+JtDKlIOD1hvADK0GX9yo5cgddg=",
        )
        self.assertGreater(len(base64.b64decode(metadata.update_manifest_public_key, validate=True)), 0)

    def test_development_paths_stay_under_project_root(self) -> None:
        root = Path(__file__).resolve().parents[2]
        paths = resolve_development_paths(root)
        metadata = load_product_metadata(root)
        self.assertEqual(paths.runtime_root, root / "runtime")
        self.assertEqual(paths.server_data_root, root / "server")
        self.assertFalse(paths.is_packaged)
        self.assertEqual(
            assess_pre_start_compatibility(paths, metadata)["status"],
            "accepted",
        )

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

    def test_manifest_public_key_must_be_non_empty_or_null(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = json.loads((Path(__file__).resolve().parents[2] / "product.json").read_text("utf-8"))
            source["update_manifest_public_key"] = " "
            (root / "product.json").write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "base64 SPKI"):
                load_product_metadata(root)

    def test_runtime_compatibility_metadata_is_strict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = json.loads(
                (Path(__file__).resolve().parents[2] / "product.json").read_text("utf-8")
            )
            source["runtime_base_commit"] = "not-a-commit"
            (root / "product.json").write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Git SHA"):
                load_product_metadata(root)


if __name__ == "__main__":
    unittest.main()
