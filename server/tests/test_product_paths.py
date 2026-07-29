from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from macsoft.config import load_config
from macsoft.db import _resolve_db_path
from macsoft.product import product_version


CONFIG = """\
server:\n  host: \"127.0.0.1\"\n  port: 8787\n
database:\n  path: \"./data/macsoft-server.db\"\n
hermes:\n  home: \"../runtime\"\n  api_base_url: \"http://127.0.0.1:8642\"\n  api_key: \"local-test\"\n  request_timeout_seconds: 30\n
models:\n  default_model: \"server-default\"\n  fallback_model: \"server-fallback\"\n
runtime:\n  mode: \"minimal\"\n
autocount:\n  enabled: false\n  catalog_path: \"./catalog.json\"\n
"""


class ProductPathTests(unittest.TestCase):
    def test_environment_config_and_database_are_relative_to_data_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path = Path(temp) / "server" / "macsoft-server.yaml"
            config_path.parent.mkdir()
            config_path.write_text(CONFIG, encoding="utf-8")
            with patch.dict("os.environ", {"MACSOFT_SERVER_CONFIG": str(config_path)}):
                config = load_config()
            expected_db_path = (config_path.parent / "data" / "macsoft-server.db").resolve()
            self.assertEqual(_resolve_db_path(config), expected_db_path)

    def test_product_version_comes_from_authoritative_metadata(self) -> None:
        root = Path(__file__).resolve().parents[2]
        expected = json.loads((root / "product.json").read_text("utf-8"))["product_version"]
        with patch.dict("os.environ", {"MACSOFT_PRODUCT_METADATA": str(root / "product.json")}):
            self.assertEqual(product_version(), expected)

    def test_host_owned_hermes_api_key_overrides_preserved_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path = Path(temp) / "macsoft-server.yaml"
            config_path.write_text(CONFIG, encoding="utf-8")
            with patch.dict(
                "os.environ",
                {
                    "MACSOFT_SERVER_CONFIG": str(config_path),
                    "MACSOFT_HERMES_API_KEY": "host-owned-key",
                },
            ):
                config = load_config()
            self.assertEqual(config.hermes.api_key, "host-owned-key")


if __name__ == "__main__":
    unittest.main()
