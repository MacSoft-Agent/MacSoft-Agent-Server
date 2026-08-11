from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

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
tools = sys.modules[f"{PACKAGE_NAME}.tools"]
validator = sys.modules[f"{PACKAGE_NAME}.validator"]
workflow_tools = sys.modules[f"{PACKAGE_NAME}.workflow_tools"]


class AutoCountPolicyRoutingTests(unittest.TestCase):
    def test_policy_is_injected_for_macsoft_api_and_whatsapp_only(self) -> None:
        self.assertIsNotNone(plugin._inject_policy(platform="api_server"))
        self.assertIsNotNone(plugin._inject_policy(platform="whatsapp"))
        self.assertIsNone(plugin._inject_policy(platform="telegram"))


CATALOG = {
    "modules": [
        {
            "id": "sales",
            "commands": [
                {
                    "type": "create-sales-invoice",
                    "mode": "write",
                    "summary": "Create a Sales Invoice",
                }
            ],
        }
    ],
    "dictionary": {
        "commands": [
            {"type": "read-debtors", "mode": "read"},
        ]
    },
}

DESCRIPTIVE_SCHEMA = {
    "commandType": "create-sales-invoice",
    "payloadSchema": {
        "debtorCode": "required AutoCount debtor/customer code",
        "docDate": "required or optional YYYY-MM-DD document date depending on account-book numbering rules",
        "lines": "required array of item rows; items is also accepted as a compatibility alias",
        "items": "optional alias for lines",
        "remarks": "optional string",
    },
    "examplePayload": {
        "debtorCode": "D-001",
        "docDate": "2026-07-14",
        "lines": [{"itemCode": "ITEM-001", "qty": 1, "uom": "UNIT"}],
    },
    "nativePayload": {
        "supported": True,
        "sections": [
            {
                "name": "Master",
                "fields": [
                    {"name": "DebtorCode", "type": "string", "aliases": ["debtorCode"]},
                    {"name": "DocDate", "type": "string", "aliases": ["docDate"]},
                ],
            },
            {
                "name": "Details",
                "fields": [
                    {"name": "ItemCode", "type": "string", "aliases": ["itemCode"]},
                    {"name": "Qty", "type": "number", "aliases": ["qty"]},
                    {"name": "UOM", "type": "string", "aliases": ["uom"]},
                ],
            },
        ],
    },
}


def api_side_effect(method: str, path: str, **kwargs):
    del kwargs
    if method == "GET" and path == "/v1/schema/modules":
        return CATALOG
    if method == "GET" and path == "/v1/schema/commands/create-sales-invoice":
        return DESCRIPTIVE_SCHEMA
    raise AssertionError(f"Unexpected API call: {method} {path}")


class FakeResponse:
    def __init__(self, value: dict):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.value).encode("utf-8")


class AutoCountValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        tools._invalid_fingerprints.clear()
        tools._invalid_fingerprint_set.clear()

    def test_exact_catalog_command_and_valid_descriptive_payload_are_accepted(self) -> None:
        payload = {
            "debtorCode": "D-001",
            "lines": [{"itemCode": "ITEM-001", "qty": 2, "uom": "UNIT"}],
        }
        with patch.object(tools, "_request_json", side_effect=api_side_effect):
            result = json.loads(
                tools.autocount_validate_command(
                    {"command_type": "create-sales-invoice", "payload": payload}
                )
            )
        self.assertTrue(result["ok"])
        self.assertTrue(result["data"]["valid"])

    def test_guessed_command_is_rejected_with_suggestion(self) -> None:
        with patch.object(tools, "_request_json", side_effect=api_side_effect):
            result = json.loads(
                tools.autocount_validate_command(
                    {"command_type": "create_sales_invoice", "payload": {}}
                )
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "AutoCountCommandResolutionError")
        self.assertIn("create-sales-invoice", result["suggestions"])

    def test_missing_unknown_type_and_master_detail_location_errors(self) -> None:
        result = validator.validate_command_payload(
            DESCRIPTIVE_SCHEMA,
            {
                "itemCode": "WRONG-LOCATION",
                "unknownRoot": True,
                "lines": [
                    {
                        "debtorCode": "WRONG-LOCATION",
                        "itemCode": "ITEM-001",
                        "qty": "two",
                        "unknownLine": 1,
                    }
                ],
            },
        )
        self.assertFalse(result["valid"])
        self.assertEqual(
            {item["path"] for item in result["missing_fields"]},
            {"$.debtorCode"},
        )
        missing_debtor = result["missing_fields"][0]
        self.assertEqual(missing_debtor["field"], "debtorCode")
        self.assertIn("debtor", missing_debtor["description"].lower())
        self.assertIn("$.unknownRoot", {item["path"] for item in result["unknown_fields"]})
        self.assertIn("$.lines[0].unknownLine", {item["path"] for item in result["unknown_fields"]})
        self.assertIn("$.lines[0].qty", {item["path"] for item in result["type_errors"]})
        self.assertEqual(
            {item["path"] for item in result["location_errors"]},
            {"$.itemCode", "$.lines[0].debtorCode"},
        )
        self.assertNotIn("$.docDate", {item["path"] for item in result["missing_fields"]})

    def test_official_alias_satisfies_required_lines(self) -> None:
        result = validator.validate_command_payload(
            DESCRIPTIVE_SCHEMA,
            {
                "debtorCode": "D-001",
                "items": [{"itemCode": "ITEM-001", "qty": 1}],
            },
        )
        self.assertTrue(result["valid"], result)

    def test_json_schema_nested_array_enum_nullable_and_date(self) -> None:
        schema = {
            "payloadSchema": {
                "type": "object",
                "required": ["customer", "lines"],
                "properties": {
                    "customer": {
                        "type": "object",
                        "required": ["code"],
                        "properties": {"code": {"type": "string"}},
                    },
                    "docDate": {"type": "string", "format": "date"},
                    "note": {"type": "string", "nullable": True},
                    "lines": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["kind", "qty"],
                            "properties": {
                                "kind": {"type": "string", "enum": ["stock", "service"]},
                                "qty": {"type": "number"},
                            },
                        },
                    },
                },
            }
        }
        valid = validator.validate_command_payload(
            schema,
            {
                "customer": {"code": "D-001"},
                "docDate": "2026-07-14",
                "note": None,
                "lines": [{"kind": "stock", "qty": 1.5}],
            },
        )
        self.assertTrue(valid["valid"], valid)
        invalid = validator.validate_command_payload(
            schema,
            {
                "customer": {"code": "D-001", "extra": True},
                "docDate": "14/07/2026",
                "lines": [{"kind": "other", "qty": True}],
            },
        )
        self.assertFalse(invalid["valid"])
        self.assertIn("$.customer.extra", {item["path"] for item in invalid["unknown_fields"]})

    def test_invalid_execution_never_submits_and_duplicate_is_suppressed(self) -> None:
        calls: list[tuple[str, str]] = []

        def recorded(method: str, path: str, **kwargs):
            calls.append((method, path))
            return api_side_effect(method, path, **kwargs)

        params = {
            "command_type": "create-sales-invoice",
            "payload": {"debtorCode": "D-001"},
        }
        config = {
            "baseUrl": "https://autocount.invalid",
            "apiKey": "test-key",
            "connectorId": "connector",
            "companyId": "company",
        }
        with patch.object(tools, "_request_json", side_effect=recorded), patch.object(
            tools,
            "_load_config",
            return_value=config,
        ):
            first = json.loads(tools.autocount_execute_command(params))
            second = json.loads(tools.autocount_execute_command(params))
        self.assertFalse(first["ok"])
        self.assertFalse(first["submitted"])
        self.assertFalse(first["duplicateSuppressed"])
        self.assertTrue(second["duplicateSuppressed"])
        self.assertNotIn(("POST", "/v1/commands"), calls)
        self.assertFalse(any("connectors" in path for _, path in calls))

    def test_valid_existing_command_execution_keeps_non_workflow_path(self) -> None:
        calls: list[tuple[str, str]] = []

        def execute_api(method: str, path: str, **kwargs):
            calls.append((method, path))
            if path in {"/v1/schema/modules", "/v1/schema/commands/create-sales-invoice"}:
                return api_side_effect(method, path, **kwargs)
            if method == "GET" and path == "/v1/connectors/connector/status":
                return {"online": True}
            if method == "POST" and path == "/v1/commands":
                return {"status": "queued"}
            if method == "GET" and path.startswith("/v1/commands/macsoft-create-sales-invoice-"):
                return {"status": "done", "result": {"docNo": "IV-1"}}
            raise AssertionError(f"Unexpected API call: {method} {path}")

        config = {
            "baseUrl": "https://autocount.invalid",
            "apiKey": "test-key",
            "connectorId": "connector",
            "companyId": "company",
            "pollIntervalSeconds": 1,
            "commandTimeoutSeconds": 5,
        }
        params = {
            "command_type": "create-sales-invoice",
            "payload": {
                "debtorCode": "D-001",
                "lines": [{"itemCode": "ITEM-001", "qty": 1, "uom": "UNIT"}],
            },
        }
        with patch.object(tools, "_request_json", side_effect=execute_api), patch.object(
            tools, "_load_config", return_value=config
        ), patch.object(tools.time, "sleep"):
            result = json.loads(tools.autocount_execute_command(params))
        self.assertTrue(result["ok"], result)
        self.assertIn(("POST", "/v1/commands"), calls)

    def test_approved_workflow_reuses_stable_action_id_without_blind_resubmit(self) -> None:
        config = {
            "connectorId": "connector",
            "companyId": "company",
            "pollIntervalSeconds": 1,
            "commandTimeoutSeconds": 5,
        }
        context = {
            "case_type": "payment",
            "case_id": "case-1",
            "case_version": 1,
            "company_id": "company",
            "account_book_id": "book",
            "action_type": "payment_knockoff",
            "action_id": "payment-case-1-v1-action",
            "action_digest": "digest",
        }
        params = {
            "command_type": "create-ar-payment",
            "payload": {"amount": 200},
            "workflow_context": context,
        }
        calls: list[tuple[str, str]] = []

        def api(method: str, path: str, **kwargs):
            calls.append((method, path))
            if path == "/v1/connectors/connector/status":
                return {"online": True}
            if method == "GET" and path == "/v1/commands/payment-case-1-v1-action":
                return {"status": "done", "result": {"docNo": "OR-1"}}
            raise AssertionError(f"Unexpected API call: {method} {path}")

        with patch.object(tools, "_load_exact_command_schema", return_value=({}, {})), patch.object(
            tools, "validate_command_payload", return_value={"valid": True}
        ), patch.object(tools, "_load_config", return_value=config), patch.object(
            workflow_tools,
            "verify_execution_context",
            return_value={**context, "verified_action_id": context["action_id"]},
        ), patch.object(
            workflow_tools, "append_execution_event", side_effect=[({}, False), ({}, True)]
        ), patch.object(tools, "_request_json", side_effect=api):
            result = json.loads(tools.autocount_execute_command(params))
        self.assertTrue(result["ok"], result)
        self.assertNotIn(("POST", "/v1/commands"), calls)
        self.assertEqual(calls.count(("GET", "/v1/commands/payment-case-1-v1-action")), 2)

    def test_transport_retry_is_bounded_and_post_is_never_retried(self) -> None:
        config = {
            "baseUrl": "https://autocount.invalid",
            "apiKey": "test-key",
            "connectorId": "connector",
            "companyId": "company",
        }
        with patch.object(tools, "_load_config", return_value=config), patch.object(
            tools.time,
            "sleep",
        ), patch.object(
            tools,
            "urlopen",
            side_effect=[URLError("temporary"), FakeResponse({"ok": True})],
        ) as opened:
            self.assertEqual(tools._request_json("GET", "/test"), {"ok": True})
            self.assertEqual(opened.call_count, 2)
            self.assertTrue(
                all(call.kwargs["timeout"] >= 120 for call in opened.call_args_list)
            )

        with patch.object(tools, "_load_config", return_value=config), patch.object(
            tools,
            "urlopen",
            side_effect=URLError("temporary"),
        ) as opened:
            with self.assertRaises(tools.AutoCountToolError):
                tools._request_json("POST", "/v1/commands", body={})
            self.assertEqual(opened.call_count, 1)

    def test_tool_failure_does_not_expose_paths_credentials_or_transport_body(self) -> None:
        with patch.object(
            tools,
            "_load_config",
            side_effect=tools.AutoCountToolError(
                r"AutoCount config not found: C:\private\config.json Bearer secret-token"
            ),
        ):
            result = tools.autocount_get_connector_status()
        self.assertNotIn("C:\\private", result)
        self.assertNotIn("secret-token", result)
        self.assertIn("AutoCount configuration is unavailable", result)

    def test_plugin_has_no_command_specific_python_file(self) -> None:
        names = {path.name for path in PLUGIN_DIR.glob("*.py")}
        self.assertEqual(
            names,
            {
                "__init__.py", "schemas.py", "tools.py", "validator.py",
                "workflow_evidence.py", "workflow_logic.py", "workflow_schemas.py",
                "workflow_store.py", "workflow_tools.py",
            },
        )

    def test_plugin_registers_one_generic_validator_tool(self) -> None:
        class Context:
            def __init__(self):
                self.tools: list[str] = []
                self.skills: list[str] = []

            def register_tool(self, *, name, **kwargs):
                del kwargs
                self.tools.append(name)

            def register_hook(self, *args, **kwargs):
                del args, kwargs

            def register_skill(self, name, path):
                self.skills.append(name)
                self.assert_path = path

        context = Context()
        plugin.register(context)
        self.assertEqual(context.tools.count("autocount_validate_command"), 1)
        self.assertEqual(len(context.tools), 14)
        self.assertEqual(context.skills, ["autocount-operations"])
        manifest = yaml.safe_load((PLUGIN_DIR / "plugin.yaml").read_text(encoding="utf-8"))
        self.assertEqual(set(manifest["provides_tools"]), set(context.tools))


if __name__ == "__main__":
    unittest.main()
