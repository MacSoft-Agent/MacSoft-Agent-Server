from __future__ import annotations

import os
import json
import tempfile
import unittest
from pathlib import Path
import yaml

from hermes_constants import reset_hermes_home_override, set_hermes_home_override
from agent import curator, curator_backup
from tools import skill_manager_tool
from tools import skill_usage


class MacSoftProgressSkillTests(unittest.TestCase):
    def test_protected_workflow_skill_cannot_be_created_in_profile_scope(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root) / "profiles"
            home = root / "prof_0123456789abcdef0123456789abcdef"
            (home / "skills" / "learned").mkdir(parents=True)
            (home / "config.yaml").write_text("{}\n", encoding="utf-8")
            previous = os.environ.get("MACSOFT_PROFILE_ROOT")
            os.environ["MACSOFT_PROFILE_ROOT"] = str(root)
            token = set_hermes_home_override(home)
            try:
                protected_name = "autocount-payment-knockoff-automation"
                guard = skill_manager_tool._macsoft_progress_skill_guard(protected_name)
                self.assertIsNotNone(guard)
                self.assertFalse(guard["success"])
                result = json.loads(
                    skill_manager_tool.skill_manage(
                        action="create",
                        name=protected_name,
                        content=(
                            f"---\nname: {protected_name}\n"
                            "description: shadow\n---\nshadow"
                        ),
                    )
                )
                self.assertFalse(result["success"])
                self.assertIn("protected MacSoft workflow Skill", result["error"])
                self.assertFalse((home / "skills" / "learned" / protected_name).exists())
            finally:
                reset_hermes_home_override(token)
                if previous is None:
                    os.environ.pop("MACSOFT_PROFILE_ROOT", None)
                else:
                    os.environ["MACSOFT_PROFILE_ROOT"] = previous

    def test_device_profile_writes_use_learned_root_and_reject_private_skill_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root) / "profiles"
            home = root / "prof_0123456789abcdef0123456789abcdef"
            private_skill = home / "skills" / "private" / "uploaded" / "SKILL.md"
            private_skill.parent.mkdir(parents=True)
            private_skill.write_text("---\nname: uploaded\ndescription: private\n---\nprivate", encoding="utf-8")

            previous = os.environ.get("MACSOFT_PROFILE_ROOT")
            os.environ["MACSOFT_PROFILE_ROOT"] = str(root)
            token = set_hermes_home_override(home)
            try:
                self.assertEqual(skill_manager_tool._skills_dir(), home / "skills" / "learned")
                self.assertEqual(skill_usage._skills_dir(), home / "skills" / "learned")
                self.assertEqual(curator._state_file(), home / "skills" / "learned" / ".curator_state")
                self.assertEqual(curator_backup._skills_dir(), home / "skills" / "learned")
                guard = skill_manager_tool._macsoft_progress_skill_guard("uploaded")
                self.assertIsNotNone(guard)
                self.assertFalse(guard["success"])
            finally:
                reset_hermes_home_override(token)
                if previous is None:
                    os.environ.pop("MACSOFT_PROFILE_ROOT", None)
                else:
                    os.environ["MACSOFT_PROFILE_ROOT"] = previous

    def test_progress_skill_cannot_shadow_shared_skill(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            base = Path(raw_root)
            root = base / "profiles"
            home = root / "prof_0123456789abcdef0123456789abcdef"
            shared = base / "shared-skills"
            shared_skill = shared / "company-policy" / "SKILL.md"
            shared_skill.parent.mkdir(parents=True)
            shared_skill.write_text("---\nname: company-policy\n---\n", encoding="utf-8")
            home.mkdir(parents=True)
            (home / "config.yaml").write_text(
                yaml.safe_dump({"skills": {"external_dirs": [str(shared)]}}),
                encoding="utf-8",
            )

            previous = os.environ.get("MACSOFT_PROFILE_ROOT")
            os.environ["MACSOFT_PROFILE_ROOT"] = str(root)
            token = set_hermes_home_override(home)
            try:
                guard = skill_manager_tool._macsoft_progress_skill_guard("company-policy")
                self.assertIsNotNone(guard)
                self.assertFalse(guard["success"])
                result = json.loads(
                    skill_manager_tool.skill_manage(
                        action="create",
                        name="company-policy",
                        content="---\nname: company-policy\n---\nshadow",
                    )
                )
                self.assertFalse(result["success"])
                self.assertFalse((home / "skills" / "learned" / "company-policy").exists())
            finally:
                reset_hermes_home_override(token)
                if previous is None:
                    os.environ.pop("MACSOFT_PROFILE_ROOT", None)
                else:
                    os.environ["MACSOFT_PROFILE_ROOT"] = previous

    def test_background_review_hard_denies_autocount_write_tool(self) -> None:
        from hermes_cli.plugins import (
            _get_pre_tool_call_directive_details,
            clear_thread_tool_whitelist,
            set_thread_tool_whitelist,
        )
        from model_tools import get_tool_definitions

        allowed = {
            item["function"]["name"]
            for item in get_tool_definitions(
                enabled_toolsets=["memory", "skills"], quiet_mode=True
            )
        }
        self.assertNotIn("autocount_execute_command", allowed)
        set_thread_tool_whitelist(allowed)
        try:
            directive = _get_pre_tool_call_directive_details(
                "autocount_execute_command", {}
            )
            self.assertEqual(directive.action, "block")
        finally:
            clear_thread_tool_whitelist()

    def test_progress_skill_mutation_creates_backup_and_native_audit(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root) / "profiles"
            home = root / "prof_0123456789abcdef0123456789abcdef"
            (home / "skills" / "learned").mkdir(parents=True)
            (home / "config.yaml").write_text("{}\n", encoding="utf-8")
            previous = os.environ.get("MACSOFT_PROFILE_ROOT")
            os.environ["MACSOFT_PROFILE_ROOT"] = str(root)
            token = set_hermes_home_override(home)
            try:
                result = json.loads(
                    skill_manager_tool.skill_manage(
                        action="create",
                        name="learned-example",
                        content=(
                            "---\nname: learned-example\n"
                            "description: learned\n---\nProcedure"
                        ),
                    )
                )
                self.assertTrue(result["success"])
                audits = list((home / "logs" / "skill-change-audit").glob("audit_*.json"))
                self.assertEqual(len(audits), 1)
                audit = json.loads(audits[0].read_text(encoding="utf-8"))
                self.assertEqual(audit["change_source"], "skill_manage_create")
                self.assertEqual(audit["result"], "succeeded")
                self.assertTrue(audit["backup_id"])
                self.assertTrue((home / "skills" / "learned" / ".curator_backups").is_dir())

                edited = json.loads(
                    skill_manager_tool.skill_manage(
                        action="edit",
                        name="learned-example",
                        content=(
                            "---\nname: learned-example\n"
                            "description: learned\n---\nUpdated procedure"
                        ),
                    )
                )
                self.assertTrue(edited["success"])
                latest = max(
                    (home / "logs" / "skill-change-audit").glob("audit_*.json"),
                    key=lambda path: path.stat().st_mtime,
                )
                latest_audit = json.loads(latest.read_text(encoding="utf-8"))
                from agent.macsoft_profile_mutations import _hash_tree

                self.assertEqual(
                    latest_audit["new_hash"],
                    _hash_tree(home / "skills" / "learned"),
                )
                self.assertEqual(
                    skill_usage.load_usage()["learned-example"]["patch_count"], 1
                )
            finally:
                reset_hermes_home_override(token)
                if previous is None:
                    os.environ.pop("MACSOFT_PROFILE_ROOT", None)
                else:
                    os.environ["MACSOFT_PROFILE_ROOT"] = previous

    def test_progress_skill_can_archive_restore_and_rollback_without_touching_private(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root) / "profiles"
            home = root / "prof_0123456789abcdef0123456789abcdef"
            (home / "skills" / "learned").mkdir(parents=True)
            private = home / "skills" / "private" / "uploaded" / "SKILL.md"
            private.parent.mkdir(parents=True)
            private.write_text("private skill", encoding="utf-8")
            (home / "config.yaml").write_text("{}\n", encoding="utf-8")
            previous = os.environ.get("MACSOFT_PROFILE_ROOT")
            os.environ["MACSOFT_PROFILE_ROOT"] = str(root)
            token = set_hermes_home_override(home)
            try:
                created = json.loads(
                    skill_manager_tool.skill_manage(
                        action="create",
                        name="learned-reports",
                        content=(
                            "---\nname: learned-reports\n"
                            "description: learned reports\n---\nversion one"
                        ),
                    )
                )
                self.assertTrue(created["success"])
                skill_usage.mark_agent_created("learned-reports")
                skill_usage.set_pinned("learned-reports", True)

                archived, _ = skill_usage.archive_skill("learned-reports")
                self.assertTrue(archived)
                self.assertTrue(
                    (home / "skills" / "learned" / ".archive" / "learned-reports" / "SKILL.md").is_file()
                )
                self.assertEqual(private.read_text(encoding="utf-8"), "private skill")

                restored, _ = skill_usage.restore_skill("learned-reports")
                self.assertTrue(restored)
                skill_path = home / "skills" / "learned" / "learned-reports" / "SKILL.md"
                self.assertIn("version one", skill_path.read_text(encoding="utf-8"))

                snapshot = curator_backup.snapshot_skills(reason="before-edit")
                self.assertIsNotNone(snapshot)
                edited = json.loads(
                    skill_manager_tool.skill_manage(
                        action="edit",
                        name="learned-reports",
                        content=(
                            "---\nname: learned-reports\n"
                            "description: learned reports\n---\nversion two"
                        ),
                    )
                )
                self.assertTrue(edited["success"])
                rolled_back, _, _ = curator_backup.rollback(snapshot.name if snapshot else None)
                self.assertTrue(rolled_back)
                self.assertIn("version one", skill_path.read_text(encoding="utf-8"))
                self.assertEqual(private.read_text(encoding="utf-8"), "private skill")
            finally:
                reset_hermes_home_override(token)
                if previous is None:
                    os.environ.pop("MACSOFT_PROFILE_ROOT", None)
                else:
                    os.environ["MACSOFT_PROFILE_ROOT"] = previous


if __name__ == "__main__":
    unittest.main()
