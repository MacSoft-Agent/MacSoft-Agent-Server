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
cloud_tools = _load_module("tools", "tools.py")


class WorkflowLogicTests(unittest.TestCase):
    def test_action_identity_is_stable_and_bound_to_job_and_payload_not_progress_version(self) -> None:
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
        self.assertEqual(digest, logic.action_digest(**changed))
        changed_payload = {**values, "payload": {"amount": 201, "debtorCode": "300-A001"}}
        self.assertNotEqual(digest, logic.action_digest(**changed_payload))
        action_id = logic.stable_action_id(
            case_type=values["case_type"],
            case_id=values["case_id"],
            case_version=values["case_version"],
            action_type=values["action_type"],
            digest=digest,
        )
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
    def test_whatsapp_mutating_commands_require_workflow_approval(self) -> None:
        with patch.object(
            tools,
            "current_actor",
            return_value={"platform": "whatsapp"},
        ):
            for command_type in (
                "create-debtor",
                "create-sales-invoice",
                "update-ar-invoice",
                "void-ar-payment",
                "delete-debtor",
                "transfer-sales-order",
            ):
                self.assertTrue(
                    tools.command_requires_workflow_approval(command_type, {}),
                    command_type,
                )
            for command_type in (
                "get-debtor-detail",
                "list-ar-invoices",
                "read-ar-outstanding-documents",
                "validate-ar-payment",
            ):
                self.assertFalse(
                    tools.command_requires_workflow_approval(command_type, {}),
                    command_type,
                )

    def test_workflow_failure_is_actionable_and_reports_not_submitted(self) -> None:
        exc = store.WorkflowStoreError(
            "This consequential AutoCount command requires an approved PharmaRise workflow_context."
        )
        self.assertEqual(
            cloud_tools._safe_failure_message(exc),
            "This AutoCount write has not completed the required preview and approval.",
        )
        self.assertEqual(
            cloud_tools._workflow_failure_reason(exc),
            "workflow_approval_required",
        )
        result = json.loads(
            cloud_tools._failure(
                exc,
                reason=cloud_tools._workflow_failure_reason(exc),
                stage="workflow_authorization",
                submitted=False,
            )
        )
        self.assertEqual(result["error"]["reason"], "workflow_approval_required")
        self.assertEqual(result["stage"], "workflow_authorization")
        self.assertFalse(result["submitted"])

    def test_payment_skill_keeps_slip_intake_before_bank_matching_and_posting(self) -> None:
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
        self.assertIn("workflow_intake_payment", skill)
        self.assertIn("do not ask permission to create the pending record", skill)
        self.assertIn("initial_status=waiting_bank", skill)
        self.assertIn("Do not repeat the full Payment Slip preview", skill)
        self.assertIn("Never infer that an AutoCount invoice has zero outstanding", skill)
        self.assertIn("Exact read-only debtor/invoice checks are permitted for staff", skill)
        self.assertIn("Do not ask whether the user wants an AR receipt created", intake)
        self.assertIn("Only after acceptance", intake)
        self.assertIn("ask for fresh Knock-Off approval", intake)
        self.assertIn("administrator setup fault", skill)
        self.assertIn("Never ask a WhatsApp customer", skill)
        self.assertIn("Do not ask the user for a Debtor Code", skill)
        self.assertIn("perform exact read-only checks", intake)
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

    def test_receiving_skill_converges_po_paths_and_limits_cn_to_supplier_credit(self) -> None:
        skill_root = (
            ROOT
            / "packaging"
            / "templates"
            / "protected"
            / "runtime"
            / "skills"
            / "autocount-receiving-supplier-invoice-automation"
        )
        skill = (skill_root / "SKILL.md").read_text("utf-8")
        po = (skill_root / "references" / "po-creation-and-correction.md").read_text("utf-8")
        cn = (skill_root / "references" / "supplier-discrepancy-and-cn-follow-up.md").read_text("utf-8")
        examples = (skill_root / "references" / "examples.md").read_text("utf-8")

        self.assertIn("These three accepted paths converge", skill)
        self.assertIn("the existing PO matched", skill)
        self.assertIn("the user approved a PO correction", skill)
        self.assertIn("the user approved a new PO", skill)
        self.assertIn("continue to Batch/Expiry/Short Expiry review and PI preparation", skill)
        self.assertIn("A CN is relevant only when the supplier overcharged", skill)
        self.assertIn("A difference is not automatically a CN case", skill)
        self.assertIn("Normal-path convergence", po)
        self.assertIn("do not classify every discrepancy as a CN", cn)
        self.assertIn("Supplier undercharge is not automatically CN", examples)

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

    def test_payment_intake_preserves_attachment_and_job_in_one_tool_call(self) -> None:
        actor = {
            "platform": "whatsapp",
            "chat_id": "customer@s.whatsapp.net",
            "user_id": "user-1",
            "role": "accountant",
            "message_id": "message-1",
        }
        payment = {"id": "payment-1", "version": 1, "status": "waiting_bank"}
        archived = {
            "evidence_id": "evidence-1",
            "sha256": "abc",
            "size_bytes": 10,
            "media_type": "application/pdf",
            "original_filename": "payment.pdf",
            "stored_path": "C:/archive/evidence-1.pdf",
        }
        with patch.object(tools, "_require_actor", return_value=actor), patch.object(
            tools, "_trusted_scope", return_value=("company-a", "book-a")
        ), patch.object(tools, "_config", return_value={}), patch.object(
            tools, "trusted_media_source_key", return_value="message-1:abc"
        ), patch.object(store, "get_case_by_source", return_value=None), patch.object(
            tools, "archive_current_media", return_value=archived
        ), patch.object(store, "create_case", return_value=(payment, True)) as create, patch.object(
            store, "append_event", return_value=({"event_type": "payment_waiting_bank"}, True)
        ):
            result = json.loads(
                tools.workflow_intake_payment(
                    {
                        "source_path": "C:/cache/payment.pdf",
                        "payment_facts": {
                            "amount": "18850.00",
                            "payment_reference": "PS-25060117",
                        },
                    }
                )
            )
        self.assertTrue(result["ok"])
        self.assertTrue(result["created"])
        self.assertEqual(result["payment"]["id"], "payment-1")
        values = create.call_args.kwargs["values"]
        self.assertEqual(values["status"], "waiting_bank")
        self.assertEqual(values["working_data"]["intent"], "customer_payment_knockoff")
        self.assertEqual(
            values["working_data"]["next_required_evidence"],
            "bank_transaction_or_statement",
        )
        self.assertEqual(values["working_data"]["evidence"][0]["evidence_id"], "evidence-1")

    def test_payment_search_passes_bank_matching_filters_to_store(self) -> None:
        actor = {
            "platform": "whatsapp",
            "chat_id": "staff@s.whatsapp.net",
            "user_id": "user-1",
            "role": "accountant",
            "message_id": "message-2",
        }
        with patch.object(tools, "_require_actor", return_value=actor), patch.object(
            tools, "_trusted_scope", return_value=("company-a", "book-a")
        ), patch.object(tools, "_enforce_trusted_scope"), patch.object(
            tools, "_config", return_value={}
        ), patch.object(store, "search_cases", return_value=[]) as search:
            result = json.loads(
                tools.workflow_case_workspace(
                    {
                        "operation": "search",
                        "case_type": "payment",
                        "statuses": ["waiting_bank"],
                        "amount": "18850.00",
                        "currency": "MYR",
                        "date_from": "2025-06-01",
                        "date_to": "2025-06-07",
                        "payer": "ABC Tradex",
                        "invoice_reference": "INV-PR2505-0148",
                    }
                )
            )
        self.assertTrue(result["ok"])
        self.assertEqual(search.call_args.kwargs["statuses"], ["waiting_bank"])
        self.assertEqual(search.call_args.kwargs["amount"], "18850.00")
        self.assertEqual(search.call_args.kwargs["currency"], "MYR")
        self.assertEqual(search.call_args.kwargs["payer"], "ABC Tradex")
        self.assertEqual(
            search.call_args.kwargs["invoice_reference"], "INV-PR2505-0148"
        )

    def test_unmapped_whatsapp_inherits_one_configured_account_book(self) -> None:
        actor = {"platform": "whatsapp", "chat_id": "customer@s.whatsapp.net"}
        with tempfile.TemporaryDirectory() as temp:
            reference = Path(temp) / "account-books.md"
            reference.write_text(
                "# Account books\n\n- company_id: pharma-rise\n  account_book_id: AED_Testing\n",
                encoding="utf-8",
            )
            with patch.object(
                store, "resolve_whatsapp_identifier", return_value=None
            ), patch.object(tools, "_config", return_value={}), patch.object(
                tools, "_account_book_reference_path", return_value=reference
            ):
                tools._enforce_trusted_scope(actor, "pharma-rise", "AED_Testing")
                with self.assertRaises(store.WorkflowStoreError):
                    tools._enforce_trusted_scope(actor, "other-company", "AED_Testing")

    def test_unmapped_whatsapp_inherits_server_selected_account_book(self) -> None:
        actor = {"platform": "whatsapp", "chat_id": "customer@s.whatsapp.net"}
        config = {"companyId": "macsoftsolutions"}
        with patch.object(
            store, "resolve_whatsapp_identifier", return_value=None
        ), patch.object(tools, "_config", return_value=config):
            tools._enforce_trusted_scope(
                actor, "macsoftsolutions", "macsoftsolutions"
            )
            with self.assertRaises(store.WorkflowStoreError):
                tools._enforce_trusted_scope(actor, "other", "macsoftsolutions")

    def test_whatsapp_resolver_returns_server_selected_scope(self) -> None:
        config = {"companyId": "macsoftsolutions"}
        with patch.object(
            store, "resolve_whatsapp_identifier", return_value=None
        ), patch.object(tools, "_config", return_value=config):
            response = json.loads(
                tools.workflow_resolve_whatsapp_identifier(
                    {"identifier_type": "chat", "identifier_value": "customer@s.whatsapp.net"}
                )
            )
        self.assertTrue(response["ok"])
        self.assertEqual(response["mapping"]["company_id"], "macsoftsolutions")
        self.assertEqual(response["mapping"]["account_book_id"], "macsoftsolutions")
        self.assertEqual(
            response["mapping"]["inherited_from"], "server_autocount_configuration"
        )

    def test_current_context_keeps_external_identity_separate_from_scope(self) -> None:
        actor = {
            "platform": "whatsapp",
            "chat_id": "customer@s.whatsapp.net",
            "user_id": "yyuzhengxian",
            "role": "",
            "message_id": "message-1",
        }
        config = {"companyId": "macsoftsolutions"}
        with patch.object(tools, "current_actor", return_value=actor), patch.object(
            tools, "_config", return_value=config
        ), patch.object(store, "resolve_whatsapp_identifier", return_value=None):
            response = json.loads(tools.workflow_current_context({}))
        self.assertTrue(response["ok"])
        self.assertEqual(response["sender"]["kind"], "external")
        self.assertIsNone(response["sender"]["internal_user_id"])
        self.assertEqual(
            response["workflow_scope"],
            {"company_id": "macsoftsolutions", "account_book_id": "macsoftsolutions"},
        )

    def test_current_context_resolves_staff_by_canonical_phone_not_display_name(self) -> None:
        actor = {
            "platform": "whatsapp",
            "chat_id": "93707747491924@lid",
            "user_id": "93707747491924@lid",
            "role": "",
            "message_id": "message-1",
        }
        config = {"companyId": "macsoftsolutions"}

        def resolve(_config, *, identifier_type, identifier_value):
            if identifier_type == "user" and identifier_value == "601123389695":
                return {"internal_user_id": "user_admin"}
            return None

        with patch.object(tools, "current_actor", return_value=actor), patch.object(
            tools, "_config", return_value=config
        ), patch.object(
            tools, "_canonical_whatsapp_user_id", return_value="601123389695"
        ), patch.object(store, "resolve_whatsapp_identifier", side_effect=resolve):
            response = json.loads(tools.workflow_current_context({}))
        self.assertTrue(response["ok"])
        self.assertEqual(response["sender"]["kind"], "staff")
        self.assertEqual(response["sender"]["internal_user_id"], "user_admin")

    def test_admin_can_register_staff_with_phone_number_only(self) -> None:
        actor = {
            "platform": "whatsapp",
            "chat_id": "93707747491924@lid",
            "user_id": "user_admin",
            "role": "Admin",
            "message_id": "message-1",
        }
        registration = {
            "identifier_value": "60183144861",
            "internal_user_id": "user_admin",
            "active": True,
        }
        with patch.object(tools, "_require_actor", return_value=actor), patch.object(
            tools, "_trusted_scope", return_value=("macsoftsolutions", "macsoftsolutions")
        ), patch.object(tools, "_config", return_value={}), patch.object(
            store, "set_whatsapp_staff_phone", return_value=registration
        ) as register:
            response = json.loads(
                tools.workflow_set_staff_phone({"phone_number": "+60 18 - 314 4861"})
            )
        self.assertTrue(response["ok"])
        self.assertEqual(response["phone_number"], "60183144861")
        self.assertTrue(response["staff"])
        self.assertEqual(register.call_args.kwargs["internal_user_id"], "user_admin")

    def test_payment_skill_requires_verified_intake_and_fixed_admin_contact(self) -> None:
        skill = (
            ROOT
            / "packaging"
            / "templates"
            / "protected"
            / "runtime"
            / "skills"
            / "autocount-payment-knockoff-automation"
            / "SKILL.md"
        ).read_text("utf-8")
        self.assertIn("workflow_intake_payment", skill)
        self.assertIn("durable payment ID", skill)
        self.assertIn("+60 18-314 4861", skill)
        self.assertIn("Exact read-only debtor/invoice checks are permitted for staff", skill)

    def test_unmapped_whatsapp_does_not_guess_between_account_books(self) -> None:
        actor = {"platform": "whatsapp", "chat_id": "customer@s.whatsapp.net"}
        with tempfile.TemporaryDirectory() as temp:
            reference = Path(temp) / "account-books.md"
            reference.write_text(
                """# Account books

- company_id: pharma-rise
  account_book_id: AED_Testing
- company_id: pharma-rise
  account_book_id: AED_Production
""",
                encoding="utf-8",
            )
            with patch.object(
                store, "resolve_whatsapp_identifier", return_value=None
            ), patch.object(tools, "_config", return_value={}), patch.object(
                tools, "_account_book_reference_path", return_value=reference
            ):
                with self.assertRaisesRegex(store.WorkflowStoreError, "ambiguous"):
                    tools._enforce_trusted_scope(actor, "pharma-rise", "AED_Testing")

    def test_unmapped_whatsapp_fails_closed_for_incomplete_setup(self) -> None:
        actor = {"platform": "whatsapp", "chat_id": "customer@s.whatsapp.net"}
        with tempfile.TemporaryDirectory() as temp:
            reference = Path(temp) / "account-books.md"
            reference.write_text("- company_id: pharma-rise\n", encoding="utf-8")
            with patch.object(
                store, "resolve_whatsapp_identifier", return_value=None
            ), patch.object(tools, "_config", return_value={}), patch.object(
                tools, "_account_book_reference_path", return_value=reference
            ):
                with self.assertRaisesRegex(store.WorkflowStoreError, "missing"):
                    tools._enforce_trusted_scope(actor, "pharma-rise", "AED_Testing")

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

    def test_execution_allows_progress_version_change_but_rejects_changed_digest(self) -> None:
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
        ), patch.object(store, "find_action_event", return_value={"action_digest": digest}):
            verified = tools.verify_execution_context(
                command_type="create-ar-payment",
                payload=payload,
                context=context,
            )
        self.assertEqual(verified["verified_action_id"], action_id)

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
