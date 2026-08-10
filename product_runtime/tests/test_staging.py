from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from macsoft_runtime.compatibility import expected_runtime_metadata, load_runtime_metadata
from macsoft_runtime.metadata import load_product_metadata
from macsoft_runtime.staging import (
    _ignore_ai,
    _ignore_site_packages,
    _ignore_templates,
    audit_staging,
)


class StagingAuditTests(unittest.TestCase):
    def test_template_copy_includes_approved_workflows(self) -> None:
        root = Path(__file__).resolve().parents[2]
        skills = root / "packaging" / "templates" / "protected" / "runtime" / "skills"
        ignored_skills = _ignore_templates(str(skills), [item.name for item in skills.iterdir()])
        self.assertIn("autocount-bank-reconciliation", ignored_skills)
        self.assertNotIn("pharmarise-company-configuration", ignored_skills)
        self.assertNotIn("autocount-payment-knockoff-automation", ignored_skills)
        self.assertNotIn("autocount-receiving-supplier-invoice-automation", ignored_skills)
        self.assertNotIn("macsoft-chart-dashboard", ignored_skills)
        self.assertNotIn("web-design-engineer", ignored_skills)

        plugin = (
            root
            / "packaging"
            / "templates"
            / "protected"
            / "runtime"
            / "plugins"
            / "macsoft-autocount"
        )
        ignored_plugin = _ignore_templates(str(plugin), [item.name for item in plugin.iterdir()])
        self.assertNotIn("workflow_tools.py", ignored_plugin)
        self.assertNotIn("migrations", ignored_plugin)
        self.assertNotIn("tools.py", ignored_plugin)
        self.assertNotIn("skills", ignored_plugin)

        mutable_skills = root / "packaging" / "templates" / "runtime" / "skills"
        ignored_mutable = _ignore_templates(
            str(mutable_skills), [item.name for item in mutable_skills.iterdir()]
        )
        self.assertIn("pharmarise-company-configuration", ignored_mutable)

    def test_template_allowlist_matches_protected_resource_manifest(self) -> None:
        import json
        from macsoft_runtime.staging import PACKAGED_SKILL_DIRECTORIES

        root = Path(__file__).resolve().parents[2]
        manifest = json.loads(
            (root / "packaging" / "templates" / "protected-resources.json").read_text(
                encoding="utf-8"
            )
        )
        skill_tree = next(
            item
            for item in manifest["directories"]
            if item["destination"] == "runtime/skills"
        )
        self.assertEqual(
            set(skill_tree["include_directories"]),
            PACKAGED_SKILL_DIRECTORIES,
        )

    def test_runtime_declaration_is_included_in_ai_service_payload(self) -> None:
        ignored = _ignore_ai(
            "C:/source/hermes",
            ["macsoft-runtime.json", "node_modules", ".git"],
        )
        self.assertNotIn("macsoft-runtime.json", ignored)
        self.assertIn("node_modules", ignored)
        self.assertIn(".git", ignored)

        root = Path(__file__).resolve().parents[2]
        metadata = load_product_metadata(root)
        detected = load_runtime_metadata(root / "hermes" / "macsoft-runtime.json")
        self.assertEqual(detected, expected_runtime_metadata(metadata))

    def test_clean_templates_do_not_contain_development_state(self) -> None:
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temp:
            staging = Path(temp)
            import shutil

            shutil.copytree(
                root / "packaging" / "templates",
                staging / "templates",
                ignore=_ignore_templates,
            )
            self.assertEqual(audit_staging(staging, root), [])

    def test_development_database_and_git_metadata_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            staging = Path(temp)
            (staging / ".git").mkdir()
            (staging / "server").mkdir()
            (staging / "server" / "macsoft-server.db").write_bytes(b"state")
            issues = audit_staging(staging, Path("C:/MacSoft-Agent"))
            self.assertTrue(any("Git metadata" in issue for issue in issues))
            self.assertTrue(any("Forbidden state" in issue for issue in issues))

    def test_whatsapp_credentials_and_runtime_env_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            staging = Path(temp)
            session = staging / "accidental-runtime" / "platforms" / "whatsapp" / "session"
            session.mkdir(parents=True)
            (session / "creds.json").write_text('{"private":"credential"}', encoding="utf-8")
            (staging / "accidental-runtime" / ".env").write_text(
                "WHATSAPP_ALLOWED_USERS=*\n",
                encoding="utf-8",
            )

            issues = audit_staging(staging, Path("C:/MacSoft-Agent"))

            self.assertTrue(any("WhatsApp credential" in issue for issue in issues))
            self.assertTrue(any("Runtime environment file" in issue for issue in issues))

    def test_runtime_databases_logs_and_pairing_state_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            staging = Path(temp)
            runtime = staging / "accidental-runtime"
            (runtime / "pairing").mkdir(parents=True)
            (runtime / "logs").mkdir()
            (runtime / "pairing" / "whatsapp-approved.json").write_text("[]", encoding="utf-8")
            (runtime / "logs" / "gateway.log").write_text("private chat", encoding="utf-8")
            (runtime / "response_store.db").write_bytes(b"customer state")

            issues = audit_staging(staging, Path("C:/MacSoft-Agent"))

            self.assertTrue(any("Pairing state" in issue for issue in issues))
            self.assertTrue(any("Runtime log" in issue for issue in issues))
            self.assertTrue(any("Runtime database" in issue for issue in issues))

    def test_approved_company_workflow_and_plugin_module_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            staging = Path(temp)
            skill = staging / "templates" / "runtime" / "skills" / "pharmarise-company-configuration"
            plugin = staging / "templates" / "protected" / "runtime" / "plugins" / "macsoft-autocount"
            skill.mkdir(parents=True)
            plugin.mkdir(parents=True)
            (skill / "SKILL.md").write_text("workflow", encoding="utf-8")
            (plugin / "workflow_tools.py").write_text("workflow", encoding="utf-8")

            issues = audit_staging(staging, Path("C:/MacSoft-Agent"))

            self.assertFalse(any("Excluded company workflow" in issue for issue in issues))
            self.assertFalse(any("Excluded AutoCount workflow module" in issue for issue in issues))

    def test_editable_python_install_metadata_is_excluded_and_rejected(self) -> None:
        names = [
            "__editable__.hermes_agent-0.18.2.pth",
            "__editable___hermes_agent_0_18_2_finder.py",
            "direct_url.json",
            "local-package.egg-link",
            "pywin32.pth",
        ]
        ignored = _ignore_site_packages("site-packages", names)
        self.assertEqual(
            ignored,
            {
                "__editable__.hermes_agent-0.18.2.pth",
                "__editable___hermes_agent_0_18_2_finder.py",
                "direct_url.json",
                "local-package.egg-link",
            },
        )

        with tempfile.TemporaryDirectory() as temp:
            staging = Path(temp)
            site_packages = staging / "python" / "Lib" / "site-packages"
            site_packages.mkdir(parents=True)
            (site_packages / "__editable__.hermes_agent-0.18.2.pth").write_text(
                "import editable_finder\n",
                encoding="utf-8",
            )
            (site_packages / "direct_url.json").write_text(
                '{"url":"file:///C:/MacSoft-Agent/hermes"}',
                encoding="utf-8",
            )
            issues = audit_staging(staging, Path("C:/MacSoft-Agent"))
            self.assertTrue(any("Editable Python install metadata" in issue for issue in issues))
            self.assertTrue(any("Development Python path" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
