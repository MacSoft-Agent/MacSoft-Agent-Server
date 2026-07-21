from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from macsoft_runtime.initializer import initialize_product_data
from macsoft_runtime.metadata import load_product_metadata
from macsoft_runtime.paths import resolve_packaged_paths


class FirstRunInitializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.source = Path(__file__).resolve().parents[2]
        self.program = self.base / "Program"
        self.data = self.base / "Data"
        self.program.mkdir()
        (self.program / "product.json").write_bytes((self.source / "product.json").read_bytes())
        self._copy_tree(self.source / "packaging" / "templates", self.program / "templates")
        self.paths = resolve_packaged_paths(self.program, self.data)
        self.metadata = load_product_metadata(self.program)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _copy_tree(self, source: Path, destination: Path) -> None:
        import shutil

        shutil.copytree(source, destination)

    def test_first_run_creates_clean_state_and_random_local_key(self) -> None:
        result = initialize_product_data(self.paths, self.metadata)
        self.assertTrue(result.created)
        runtime = self.paths.runtime_config.read_text("utf-8")
        server = self.paths.server_config.read_text("utf-8")
        state = json.loads((self.paths.config_root / "initialization.json").read_text("utf-8"))
        self.assertNotIn("${MACSOFT_LOCAL_API_KEY}", runtime)
        self.assertIn(state["local_api_key"], runtime)
        self.assertIn(state["local_api_key"], server)
        self.assertEqual(json.loads((self.paths.autocount_plugin_root / "config.json").read_text("utf-8"))["apiKey"], "")
        self.assertFalse((self.paths.runtime_root / "auth.json").exists())
        self.assertEqual(self.paths.server_database.stat().st_size, 0)

    def test_upgrade_preserves_mutable_customer_data(self) -> None:
        initialize_product_data(self.paths, self.metadata)
        custom = "customer setting\n"
        self.paths.runtime_config.write_text(custom, encoding="utf-8")
        second = initialize_product_data(self.paths, self.metadata)
        self.assertEqual(self.paths.runtime_config.read_text("utf-8"), custom)
        self.assertIn("runtime\\config.yaml" if __import__('os').name == 'nt' else "runtime/config.yaml", second.preserved)

    def test_modified_protected_resource_is_not_overwritten(self) -> None:
        initialize_product_data(self.paths, self.metadata)
        target = self.paths.autocount_plugin_root / "validator.py"
        target.write_text("# administrator change\n", encoding="utf-8")
        second = initialize_product_data(self.paths, self.metadata)
        self.assertIn("runtime/plugins/macsoft-autocount/validator.py", second.conflicts)
        self.assertEqual(target.read_text("utf-8"), "# administrator change\n")


if __name__ == "__main__":
    unittest.main()
