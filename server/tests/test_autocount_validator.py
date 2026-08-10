from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shutil
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
        tools = importlib.import_module(f"{PACKAGE_NAME}.tools")
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
        self.assertEqual(context.tools, [])
        self.assertEqual(context.hooks, ["pre_llm_call"])
        self.assertEqual(context.skills, [])
        manifest = yaml.safe_load((PLUGIN_DIR / "plugin.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("provides_tools", manifest)

    def test_staged_policy_only_plugin_imports_and_registers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            staged_plugin_root = Path(temporary) / "macsoft-autocount"
            staged_plugin_root.mkdir()
            for filename in ("__init__.py", "plugin.yaml"):
                shutil.copy2(PLUGIN_DIR / filename, staged_plugin_root / filename)

            package_name = "macsoft_autocount_staged_policy_tests"
            staged_spec = importlib.util.spec_from_file_location(
                package_name,
                staged_plugin_root / "__init__.py",
                submodule_search_locations=[str(staged_plugin_root)],
            )
            self.assertIsNotNone(staged_spec)
            self.assertIsNotNone(staged_spec.loader)
            staged_plugin = importlib.util.module_from_spec(staged_spec)
            sys.modules[package_name] = staged_plugin
            try:
                staged_spec.loader.exec_module(staged_plugin)

                class Context:
                    def __init__(self):
                        self.tools: list[str] = []
                        self.hooks: list[str] = []

                    def register_tool(self, *, name, **kwargs):
                        del kwargs
                        self.tools.append(name)

                    def register_hook(self, name, handler):
                        del handler
                        self.hooks.append(name)

                context = Context()
                staged_plugin.register(context)
                self.assertEqual(context.tools, [])
                self.assertEqual(context.hooks, ["pre_llm_call"])
                self.assertEqual(
                    {path.name for path in staged_plugin_root.iterdir() if path.is_file()},
                    {"__init__.py", "plugin.yaml"},
                )
            finally:
                sys.modules.pop(package_name, None)

    def test_packaged_plugin_manifest_contains_only_policy_files(self) -> None:
        protected = json.loads(
            (PLUGIN_DIR.parents[3] / "protected-resources.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            {item["destination"] for item in protected["resources"]},
            {
                "runtime/plugins/macsoft-autocount/__init__.py",
                "runtime/plugins/macsoft-autocount/plugin.yaml",
            },
        )


if __name__ == "__main__":
    unittest.main()
