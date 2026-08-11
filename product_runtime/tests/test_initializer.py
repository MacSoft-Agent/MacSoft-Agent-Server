from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
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
        self.assertIn("request_timeout_seconds: 7200", server)

    def test_upgrade_migrates_only_the_historical_server_timeout_default(self) -> None:
        initialize_product_data(self.paths, self.metadata)
        server = self.paths.server_config.read_text(encoding="utf-8")
        server = server.replace("request_timeout_seconds: 7200", "request_timeout_seconds: 600 # old default")
        server += "\n# customer server setting\n"
        self.paths.server_config.write_text(server, encoding="utf-8")

        initialize_product_data(self.paths, self.metadata)

        updated = self.paths.server_config.read_text(encoding="utf-8")
        self.assertIn("request_timeout_seconds: 7200 # old default", updated)
        self.assertIn("# customer server setting", updated)

        customized = updated.replace("request_timeout_seconds: 7200", "request_timeout_seconds: 3600")
        self.paths.server_config.write_text(customized, encoding="utf-8")
        initialize_product_data(self.paths, self.metadata)
        self.assertIn(
            "request_timeout_seconds: 3600 # old default",
            self.paths.server_config.read_text(encoding="utf-8"),
        )

    def test_upgrade_preserves_mutable_customer_data(self) -> None:
        initialize_product_data(self.paths, self.metadata)
        original = self.paths.runtime_config.read_text("utf-8")
        custom = original.replace("default: gpt-5.4", "default: customer-model")
        self.paths.runtime_config.write_text(custom, encoding="utf-8")
        second = initialize_product_data(self.paths, self.metadata)
        self.assertEqual(self.paths.runtime_config.read_text("utf-8"), custom)
        self.assertIn("runtime\\config.yaml" if __import__('os').name == 'nt' else "runtime/config.yaml", second.preserved)

    def test_upgrade_rebrands_only_the_known_macsoft_identity_template(self) -> None:
        initialize_product_data(self.paths, self.metadata)
        old_identity = (
            "Your name is MacSoft Agent.\n"
            "When asked who you are in English, identify yourself only as MacSoft Agent.\n"
            "When asked who you are in Chinese, identify yourself only as MacSoft 助手.\n"
            "Do not mention the underlying framework or upstream product name.\n"
        )
        self.paths.soul_file.write_text(old_identity, encoding="utf-8")

        initialize_product_data(self.paths, self.metadata)

        updated = self.paths.soul_file.read_text(encoding="utf-8")
        self.assertIn("You are Mac Soft AI Agent", updated)
        self.assertNotIn("Hermes Agent", updated)

        custom = "You are the administrator's custom company assistant.\n"
        self.paths.soul_file.write_text(custom, encoding="utf-8")
        initialize_product_data(self.paths, self.metadata)
        self.assertEqual(self.paths.soul_file.read_text(encoding="utf-8"), custom)

    def test_company_configuration_is_not_seeded_into_a_clean_install(self) -> None:
        initialize_product_data(self.paths, self.metadata)
        reference = (
            self.paths.runtime_root
            / "skills"
            / "pharmarise-company-configuration"
            / "references"
            / "account-books.md"
        )
        self.assertFalse(reference.exists())

    def test_upgrade_preserves_device_profile_tree_byte_for_byte(self) -> None:
        initialize_product_data(self.paths, self.metadata)
        profile = (
            self.paths.runtime_root
            / "profiles"
            / "prof_0123456789abcdef0123456789abcdef"
        )
        memory = profile / "memories" / "MEMORY.md"
        skill = profile / "skills" / "learned" / "reporting" / "SKILL.md"
        memory.parent.mkdir(parents=True)
        skill.parent.mkdir(parents=True)
        memory.write_bytes(b"device memory\r\n")
        skill.write_bytes(b"---\r\nname: reporting\r\n---\r\nlearned\r\n")
        before = {memory: memory.read_bytes(), skill: skill.read_bytes()}

        initialize_product_data(self.paths, self.metadata)

        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_upgrade_adds_read_only_skill_toolset_without_replacing_runtime_config(self) -> None:
        initialize_product_data(self.paths, self.metadata)
        runtime = self.paths.runtime_config.read_text("utf-8")
        runtime = runtime.replace("    - macsoft_autocount\n", "    - macsoft_autocount\n    # customer setting\n")
        runtime = runtime.replace("default: gpt-5.4", "default: customer-model")
        self.paths.runtime_config.write_text(runtime, encoding="utf-8")

        initialize_product_data(self.paths, self.metadata)

        updated = self.paths.runtime_config.read_text("utf-8")
        self.assertIn("    - skills_readonly", updated)
        self.assertIn("default: customer-model", updated)
        self.assertIn("# customer setting", updated)

    def test_upgrade_adds_restricted_whatsapp_toolsets_without_replacing_runtime_config(self) -> None:
        initialize_product_data(self.paths, self.metadata)
        runtime = self.paths.runtime_config.read_text("utf-8")
        runtime = runtime.replace("default: gpt-5.4", "default: customer-model")
        self.paths.runtime_config.write_text(runtime, encoding="utf-8")

        initialize_product_data(self.paths, self.metadata)

        updated = self.paths.runtime_config.read_text("utf-8")
        self.assertIn(
            "  whatsapp:\n    - macsoft_autocount\n    - skills_readonly",
            updated,
        )
        self.assertIn("plugin_extensible_platform_toolsets:\n  - whatsapp", updated)
        self.assertIn("default: customer-model", updated)

    def test_upgrade_synchronizes_internal_api_key_without_rewriting_other_settings(self) -> None:
        initialize_product_data(self.paths, self.metadata)
        state = json.loads((self.paths.config_root / "initialization.json").read_text("utf-8"))
        local_api_key = state["local_api_key"]
        runtime = self.paths.runtime_config.read_text("utf-8").replace(local_api_key, "stale-runtime-key")
        server = self.paths.server_config.read_text("utf-8").replace(local_api_key, "stale-server-key")
        runtime += "\n# preserved runtime comment\n"
        server = server.replace('port: 8787', 'port: 9876') + "\n# preserved server comment\n"
        self.paths.runtime_config.write_text(runtime, encoding="utf-8")
        self.paths.server_config.write_text(server, encoding="utf-8")

        second = initialize_product_data(self.paths, self.metadata)

        runtime_after = self.paths.runtime_config.read_text("utf-8")
        server_after = self.paths.server_config.read_text("utf-8")
        self.assertIn(local_api_key, runtime_after)
        self.assertIn(local_api_key, server_after)
        self.assertNotIn("stale-runtime-key", runtime_after)
        self.assertNotIn("stale-server-key", server_after)
        self.assertIn("# preserved runtime comment", runtime_after)
        self.assertIn("port: 9876", server_after)
        self.assertIn("# preserved server comment", server_after)
        self.assertIn("runtime\\config.yaml" if __import__('os').name == 'nt' else "runtime/config.yaml", second.preserved)

    def test_modified_protected_resource_is_not_overwritten(self) -> None:
        initialize_product_data(self.paths, self.metadata)
        target = self.paths.autocount_plugin_root / "validator.py"
        target.write_text("# administrator change\n", encoding="utf-8")
        second = initialize_product_data(self.paths, self.metadata)
        self.assertIn("runtime/plugins/macsoft-autocount/validator.py", second.conflicts)
        self.assertEqual(target.read_text("utf-8"), "# administrator change\n")

    def test_removed_protected_resource_is_deleted_only_when_unchanged(self) -> None:
        base_version = self.metadata.protected_resource_version
        initialize_product_data(self.paths, self.metadata)
        manifest_path = self.program / "templates" / "protected-resources.json"
        manifest = json.loads(manifest_path.read_text("utf-8"))
        destination = "runtime/plugins/macsoft-autocount/validator.py"
        target = self.paths.data_root / destination
        self.assertTrue(target.is_file())

        manifest["resources"] = [
            item for item in manifest["resources"] if item["destination"] != destination
        ]
        manifest["version"] = base_version + 1
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        removed = initialize_product_data(
            self.paths,
            replace(self.metadata, protected_resource_version=base_version + 1),
        )
        self.assertIn(destination, removed.removed_protected)
        self.assertFalse(target.exists())

    def test_protected_skill_directory_syncs_and_reconciles_safely(self) -> None:
        base_version = self.metadata.protected_resource_version
        source_root = (
            self.program
            / "templates"
            / "protected"
            / "runtime"
            / "skills"
            / "fixture-skill"
        )
        source_file = source_root / "SKILL.md"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("version one\n", encoding="utf-8")

        manifest_path = self.program / "templates" / "protected-resources.json"
        manifest = json.loads(manifest_path.read_text("utf-8"))
        skill_tree = next(
            item
            for item in manifest["directories"]
            if item["destination"] == "runtime/skills"
        )
        skill_tree["include_directories"].append("fixture-skill")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        first = initialize_product_data(self.paths, self.metadata)
        target_file = self.paths.runtime_root / "skills" / "fixture-skill" / "SKILL.md"
        self.assertIn("runtime/skills/fixture-skill/SKILL.md", first.created)
        self.assertEqual(target_file.read_text("utf-8"), "version one\n")

        # A new bundled version updates an unchanged managed file.
        source_file.write_text("version two\n", encoding="utf-8")
        manifest["version"] = base_version + 1
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        second = initialize_product_data(
            self.paths,
            replace(self.metadata, protected_resource_version=base_version + 1),
        )
        self.assertIn("runtime/skills/fixture-skill/SKILL.md", second.updated_protected)
        self.assertEqual(target_file.read_text("utf-8"), "version two\n")

        # Files outside the managed source remain untouched.
        external_file = self.paths.runtime_root / "skills" / "installed-by-admin" / "SKILL.md"
        external_file.parent.mkdir(parents=True)
        external_file.write_text("administrator skill\n", encoding="utf-8")

        # A local edit creates a conflict and is never overwritten.
        target_file.write_text("local edit\n", encoding="utf-8")
        source_file.write_text("version three\n", encoding="utf-8")
        manifest["version"] = base_version + 2
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        third = initialize_product_data(
            self.paths,
            replace(self.metadata, protected_resource_version=base_version + 2),
        )
        self.assertIn("runtime/skills/fixture-skill/SKILL.md", third.conflicts)
        self.assertEqual(target_file.read_text("utf-8"), "local edit\n")
        self.assertEqual(external_file.read_text("utf-8"), "administrator skill\n")

        # A later product update must continue to preserve the unresolved edit.
        source_file.write_text("version four\n", encoding="utf-8")
        manifest["version"] = base_version + 3
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        conflicted_update = initialize_product_data(
            self.paths,
            replace(self.metadata, protected_resource_version=base_version + 3),
        )
        self.assertIn("runtime/skills/fixture-skill/SKILL.md", conflicted_update.conflicts)
        self.assertEqual(target_file.read_text("utf-8"), "local edit\n")

        # Once the local edit is restored to the last managed content, removing
        # the source file can safely remove the obsolete managed runtime file.
        target_file.write_text("version four\n", encoding="utf-8")
        source_file.unlink()
        manifest["version"] = base_version + 4
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        fourth = initialize_product_data(
            self.paths,
            replace(self.metadata, protected_resource_version=base_version + 4),
        )
        self.assertIn("runtime/skills/fixture-skill/SKILL.md", fourth.removed_protected)
        self.assertFalse(target_file.exists())
        self.assertTrue(external_file.exists())


if __name__ == "__main__":
    unittest.main()
