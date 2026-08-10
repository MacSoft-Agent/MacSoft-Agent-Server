from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml


DEFAULT_PLUGIN_DIR = (
    Path(__file__).resolve().parents[2]
    / "packaging"
    / "templates"
    / "protected"
    / "runtime"
    / "plugins"
    / "macsoft-autocount"
)
PLUGIN_DIR = Path(os.environ.get("MACSOFT_AUTOCOUNT_PLUGIN_TEST_ROOT", str(DEFAULT_PLUGIN_DIR)))
PACKAGE_NAME = "macsoft_autocount_runtime_tests"

spec = importlib.util.spec_from_file_location(
    PACKAGE_NAME,
    PLUGIN_DIR / "__init__.py",
    submodule_search_locations=[str(PLUGIN_DIR)],
)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load the active AutoCount plugin for tests.")
plugin = importlib.util.module_from_spec(spec)
sys.modules[PACKAGE_NAME] = plugin
spec.loader.exec_module(plugin)
tools = importlib.import_module(f"{PACKAGE_NAME}.tools")


class AutoCountNativePolicyTests(unittest.TestCase):
    def test_policy_is_injected_for_macsoft_channels_only(self) -> None:
        api_policy = plugin._inject_policy(platform="api_server")["context"]
        whatsapp_policy = plugin._inject_policy(platform="whatsapp")["context"]
        self.assertEqual(api_policy, whatsapp_policy)
        self.assertIsNone(plugin._inject_policy(platform="telegram"))
        self.assertIn("write_file", api_policy)
        self.assertIn("terminal", api_policy)
        self.assertIn("https://api.autocount.cloud/v1/commands", api_policy)
        self.assertIn("commandTimeoutSeconds (7200 seconds)", api_policy)
        self.assertNotIn("autocount_get_connector_status", api_policy)
        self.assertNotIn("autocount_execute_command", api_policy)

    def test_profile_connection_store_supports_multiple_companies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            connection_dir = home / "autocount"
            connection_dir.mkdir()
            (connection_dir / "connections.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "defaultCompanyId": "company-a",
                        "connections": {
                            "company-a": {
                                "baseUrl": "https://api.autocount.cloud",
                                "apiKey": "key-a",
                                "connectorId": "connector-a",
                                "companyId": "company-a",
                            },
                            "company-b": {
                                "baseUrl": "https://api.autocount.cloud",
                                "apiKey": "key-b",
                                "connectorId": "connector-b",
                                "companyId": "company-b",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(tools, "_active_hermes_home", return_value=home):
                self.assertEqual(tools._load_config()["companyId"], "company-a")
                self.assertEqual(tools._load_config("company-b")["connectorId"], "connector-b")

    def test_plugin_exposes_no_generic_autocount_model_tools(self) -> None:
        class Context:
            def __init__(self):
                self.tools: list[str] = []
                self.hooks: list[str] = []
                self.skills: list[str] = []

            def register_tool(self, *, name, **kwargs):
                del kwargs
                self.tools.append(name)

            def register_hook(self, name, handler):
                del handler
                self.hooks.append(name)

            def register_skill(self, name, path):
                del path
                self.skills.append(name)

        context = Context()
        plugin.register(context)
        self.assertFalse(any(name.startswith("autocount_") for name in context.tools))
        self.assertEqual(len(context.tools), 6)
        self.assertEqual(context.hooks, ["pre_llm_call"])
        self.assertEqual(context.skills, [])
        manifest = yaml.safe_load((PLUGIN_DIR / "plugin.yaml").read_text(encoding="utf-8"))
        self.assertEqual(set(manifest["provides_tools"]), set(context.tools))

    def test_plugin_contains_no_generic_query_schema_or_validator_module(self) -> None:
        names = {path.name for path in PLUGIN_DIR.glob("*.py")}
        self.assertNotIn("schemas.py", names)
        self.assertNotIn("validator.py", names)
        self.assertEqual(
            names,
            {
                "__init__.py",
                "tools.py",
                "workflow_evidence.py",
                "workflow_logic.py",
                "workflow_schemas.py",
                "workflow_store.py",
                "workflow_tools.py",
            },
        )


if __name__ == "__main__":
    unittest.main()
