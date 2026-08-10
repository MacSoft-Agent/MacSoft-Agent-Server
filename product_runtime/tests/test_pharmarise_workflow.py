from __future__ import annotations

import importlib.util
import json
import sys
import types
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = (
    ROOT
    / "packaging"
    / "templates"
    / "protected"
    / "runtime"
    / "plugins"
    / "macsoft-autocount"
)


def _load_module(name: str, filename: str):
    package_name = "macsoft_autocount_contract_test"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(PLUGIN)]
        sys.modules[package_name] = package
    full_name = f"{package_name}.{name}"
    spec = importlib.util.spec_from_file_location(full_name, PLUGIN / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


logic = _load_module("workflow_logic", "workflow_logic.py")
store = _load_module("workflow_store", "workflow_store.py")
evidence = _load_module("workflow_evidence", "workflow_evidence.py")
tools = _load_module("workflow_tools", "workflow_tools.py")


class WorkflowLogicTests(unittest.TestCase):
    def test_action_identity_is_stable_and_bound_to_version_and_payload(self) -> None:
        values = dict(
            case_type="payment",
            case_id="11111111-1111-1111-1111-111111111111",
            case_version=2,
            action_type="payment_knockoff",
            command_type="create-ar-payment",
            payload={"amount": 200, "debtorCode": "300-A001"},
        )
        digest = logic.action_digest(**values)
        self.assertEqual(digest, logic.action_digest(**values))
        changed = {**values, "case_version": 3}
        self.assertNotEqual(digest, logic.action_digest(**changed))
        action_id = logic.stable_action_id(
            case_type=values["case_type"],
            case_id=values["case_id"],
            case_version=values["case_version"],
            action_type=values["action_type"],
            digest=digest,
        )
        self.assertIn("-v2-", action_id)
        self.assertTrue(action_id.endswith(digest[:16]))

    def test_fifo_supports_partial_final_invoice(self) -> None:
        result = logic.fifo_allocate(
            "250.00",
            [
                {"docKey": 2, "docNo": "IV-2", "docDate": "2026-02-01", "outstandingAmount": 200},
                {"docKey": 1, "docNo": "IV-1", "docDate": "2026-01-01", "outstandingAmount": 100},
            ],
        )
        self.assertEqual([row["docNo"] for row in result["allocations"]], ["IV-1", "IV-2"])
        self.assertEqual([row["amount"] for row in result["allocations"]], ["100.00", "150.00"])
        self.assertTrue(result["allocations"][1]["partial"])
        self.assertEqual(result["unappliedAmount"], "0.00")


class WorkflowPersistenceContractTests(unittest.TestCase):
    def test_payment_skill_automatically_records_slip_before_bank_matching_and_posting(self) -> None:
        skill_root = (
            ROOT
            / "packaging"
            / "templates"
            / "protected"
            / "runtime"
            / "skills"
            / "autocount-payment-knockoff-automation"
        )
        skill = (skill_root / "SKILL.md").read_text("utf-8")
        intake = (skill_root / "references" / "payment-intake-and-pending.md").read_text("utf-8")
        examples = (skill_root / "references" / "examples.md").read_text("utf-8")
        direct = (
            ROOT
            / "packaging"
            / "templates"
            / "protected"
            / "runtime"
            / "skills"
            / "autocount-local-direct-payment-knockoff"
            / "SKILL.md"
        ).read_text("utf-8")

        self.assertIn("Payment Slip received", skill)
        self.assertIn("Bank Transaction/Statement received", skill)
        self.assertIn("automatically create or continue", skill)
        self.assertIn("Pending Bank Verification", skill)
        self.assertIn("Do not ask for permission to record", intake)
        self.assertNotIn("whether the user wants this payment recorded", skill)
        self.assertNotIn("After the user agrees", intake)
        self.assertNotIn("Would you like me to record it", intake)
        self.assertNotIn("Ask whether to record it", examples)
        self.assertNotIn("After agreement", examples)
        self.assertIn("do **not** search the AutoCount command catalog", skill)
        self.assertIn("Do not ask whether the user wants an AR receipt created", intake)
        self.assertIn("Only after an acceptable match", intake)
        self.assertIn("ask for fresh Knock-Off approval", intake)
        self.assertIn("one-time PharmaRise payment-workflow setup", skill)
        self.assertIn("Do not ask the user for a Debtor Code", skill)
        self.assertIn("search AutoCount for the debtor yourself", intake)
        self.assertIn("Never use for a newly uploaded Payment Slip", direct)

    def test_generic_autocount_skill_uses_precise_sources_and_media_guardrail(self) -> None:
        skill = (
            PLUGIN / "skills" / "autocount-operations" / "SKILL.md"
        ).read_text("utf-8")
        for url in (
            "https://api.autocount.cloud/developers/recipes.json",
            "https://api.autocount.cloud/ai/manifest.json",
            "https://api.autocount.cloud/ai/autocount-ontology.json",
            "https://api.autocount.cloud/openapi.json",
        ):
            self.assertIn(url, skill)
        self.assertIn("media could not be downloaded", skill)
        self.assertIn("Do not describe, extract, match, or post", skill)
        self.assertIn("live validator rejects", skill)

    def test_postgres_setup_and_onboarding_are_recorded_without_embedded_password(self) -> None:
        setup = (ROOT / "scripts" / "setup-pharmarise-postgres.ps1").read_text("utf-8")
        onboarding = (ROOT / "docs" / "development" / "FRESH_CLONE_SETUP.md").read_text("utf-8")
        example = json.loads(
            (ROOT / "runtime.example" / "plugins" / "macsoft-autocount" / "config.json.example").read_text("utf-8")
        )
        self.assertIn("Read-Host 'PostgreSQL administrator password' -AsSecureString", setup)
        self.assertIn("001_pharmarise_workflow.sql", setup)
        self.assertIn("setup-pharmarise-postgres.ps1", onboarding)
        self.assertEqual(example["workflowPostgresDsn"], "")
        self.assertNotIn("AdminPassword", setup)

    def test_evidence_archive_accepts_only_current_trusted_media(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "cache" / "payment-slip.pdf"
            source.parent.mkdir()
            source.write_bytes(b"%PDF-1.4\ntrusted-test")
            archive = root / "archive"
            trusted = [{"path": str(source), "media_type": "application/pdf"}]
            with patch.object(evidence, "_trusted_media", return_value=trusted):
                record = evidence.archive_current_media(
                    {"workflowEvidenceRoot": str(archive)}, source_path=str(source)
                )
                self.assertEqual(record["size_bytes"], source.stat().st_size)
                self.assertTrue(Path(record["stored_path"]).is_file())
                self.assertEqual(
                    evidence.trusted_media_source_key(message_id="wa-1", source_path=str(source)),
                    f"wa-1:{record['sha256']}",
                )
                with self.assertRaises(store.WorkflowStoreError):
                    evidence.archive_current_media(
                        {"workflowEvidenceRoot": str(archive)},
                        source_path=str(root / "not-in-message.pdf"),
                    )

    def test_whatsapp_scope_comes_from_chat_mapping(self) -> None:
        actor = {"platform": "whatsapp", "chat_id": "group@g.us"}
        with patch.object(
            store,
            "resolve_whatsapp_identifier",
            return_value={"company_id": "company-a", "account_book_id": "book-a"},
        ), patch.object(tools, "_config", return_value={}):
            tools._enforce_trusted_scope(actor, "company-a", "book-a")
            with self.assertRaises(store.WorkflowStoreError):
                tools._enforce_trusted_scope(actor, "company-b", "book-a")

    def test_migration_contains_only_approved_tables_and_append_only_event_guards(self) -> None:
        sql = (PLUGIN / "migrations" / "001_pharmarise_workflow.sql").read_text("utf-8")
        for table in (
            "payment_cases",
            "receiving_cases",
            "whatsapp_identifiers",
            "workflow_case_events",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", sql)
        self.assertEqual(sql.count("CREATE TABLE IF NOT EXISTS"), 4)
        self.assertIn("workflow_case_events_no_update", sql)
        self.assertIn("workflow_case_events_no_delete", sql)

    def test_execution_rejects_changed_case_version_or_digest(self) -> None:
        payload = {"debtorCode": "300-A001", "amount": 200}
        digest = logic.action_digest(
            case_type="payment",
            case_id="11111111-1111-1111-1111-111111111111",
            case_version=1,
            action_type="payment_knockoff",
            command_type="create-ar-payment",
            payload=payload,
        )
        action_id = logic.stable_action_id(
            case_type="payment",
            case_id="11111111-1111-1111-1111-111111111111",
            case_version=1,
            action_type="payment_knockoff",
            digest=digest,
        )
        context = {
            "case_type": "payment",
            "case_id": "11111111-1111-1111-1111-111111111111",
            "case_version": 1,
            "company_id": "company-a",
            "account_book_id": "book-a",
            "action_type": "payment_knockoff",
            "action_id": action_id,
            "action_digest": digest,
        }
        with patch.object(tools, "_config", return_value={}), patch.object(
            store, "get_case", return_value={"version": 2}
        ):
            with self.assertRaises(store.WorkflowConflictError):
                tools.verify_execution_context(
                    command_type="create-ar-payment",
                    payload=payload,
                    context=context,
                )

        changed_payload = {**payload, "amount": 201}
        with self.assertRaises(store.WorkflowConflictError):
            tools.verify_execution_context(
                command_type="create-ar-payment",
                payload=changed_payload,
                context=context,
            )

    def test_supplier_message_uses_exact_approval_and_existing_whatsapp_transport(self) -> None:
        params = {
            "company_id": "company-a",
            "account_book_id": "book-a",
            "case_id": "11111111-1111-1111-1111-111111111111",
            "case_version": 4,
            "recipient": "60123456789@s.whatsapp.net",
            "message": "Please confirm the two-unit delivery shortage.",
        }
        appended: list[str] = []

        def append_event(*args, **kwargs):
            del args
            appended.append(kwargs["event_type"])
            return {"event_type": kwargs["event_type"]}, True

        approval_module = types.ModuleType("tools.approval")
        approval_module.request_tool_approval = MagicMock(return_value={"approved": True})
        send_module = types.ModuleType("tools.send_message_tool")
        send_module._parse_target_ref = MagicMock(
            return_value=(params["recipient"], None, True)
        )
        send_module._handle_send = MagicMock(
            return_value='{"success": true, "message_id": "wa-out-1"}'
        )

        with patch.dict(
            sys.modules,
            {"tools.approval": approval_module, "tools.send_message_tool": send_module},
        ), patch.object(
            tools,
            "_require_actor",
            return_value={"user_id": "user-1", "role": "accountant", "platform": "whatsapp", "chat_id": "group@g.us"},
        ), patch.object(tools, "_enforce_trusted_scope"), patch.object(
            tools, "_config", return_value={}
        ), patch.object(store, "get_case", return_value={"version": 4}), patch.object(
            store, "find_action_event", return_value=None
        ), patch.object(store, "append_event", side_effect=append_event):
            result = json.loads(tools.workflow_send_approved_supplier_message(params))

        self.assertTrue(result["ok"])
        self.assertEqual(result["messageId"], "wa-out-1")
        self.assertEqual(
            appended,
            ["action_approved", "supplier_message_started", "supplier_message_sent"],
        )
        send_module._handle_send.assert_called_once_with(
            {
                "target": "whatsapp:60123456789@s.whatsapp.net",
                "message": "Please confirm the two-unit delivery shortage.",
            }
        )
        approval_text = approval_module.request_tool_approval.call_args.args[1]
        self.assertIn(params["recipient"], approval_text)
        self.assertIn(params["message"], approval_text)

    def test_supplier_message_does_not_retry_an_uncertain_action(self) -> None:
        params = {
            "company_id": "company-a",
            "account_book_id": "book-a",
            "case_id": "11111111-1111-1111-1111-111111111111",
            "case_version": 4,
            "recipient": "60123456789@s.whatsapp.net",
            "message": "Please confirm the two-unit delivery shortage.",
        }

        def find_event(*args, **kwargs):
            del args
            if kwargs["event_type"] == "supplier_message_started":
                return {"event_type": "supplier_message_started"}
            return None

        send_module = types.ModuleType("tools.send_message_tool")
        send_module._parse_target_ref = MagicMock(
            return_value=(params["recipient"], None, True)
        )
        send_module._handle_send = MagicMock()

        with patch.dict(
            sys.modules, {"tools.send_message_tool": send_module}
        ), patch.object(
            tools,
            "_require_actor",
            return_value={"user_id": "user-1", "role": "accountant", "platform": "whatsapp", "chat_id": "group@g.us"},
        ), patch.object(tools, "_enforce_trusted_scope"), patch.object(
            tools, "_config", return_value={}
        ), patch.object(store, "get_case", return_value={"version": 4}), patch.object(
            store, "find_action_event", side_effect=find_event
        ):
            result = json.loads(tools.workflow_send_approved_supplier_message(params))

        self.assertFalse(result["ok"])
        self.assertIn("will not be retried automatically", result["error"]["message"])
        send_module._handle_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
