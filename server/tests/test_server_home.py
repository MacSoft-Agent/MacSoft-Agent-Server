from __future__ import annotations

import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch
import yaml
from macsoft.config import (
    AppConfig,
    AutoCountSettings,
    DatabaseSettings,
    HermesSettings,
    ModelSettings,
    RuntimeSettings,
    ServerSettings,
)
from macsoft.gateway.routes_admin import router as admin_router
from macsoft.server_home import (
    ensure_server_home,
    read_or_create_server_context_snapshot,
    read_shareable_server_context,
)


def _config(root: Path) -> AppConfig:
    return AppConfig(
        config_path=str(root / "macsoft-server.yaml"),
        database=DatabaseSettings(path=str(root / "macsoft.db")),
        hermes=HermesSettings(
            profile_root=str(root / "runtime" / "profiles"),
            home=str(root / "runtime"),
            api_base_url="http://127.0.0.1:8642",
            api_key="test-key",
            request_timeout_seconds=30,
        ),
        server=ServerSettings(host="127.0.0.1", port=8787),
        models=ModelSettings(default_model="test", fallback_model="test"),
        runtime=RuntimeSettings(mode="test"),
        autocount=AutoCountSettings(enabled=False, catalog_path=""),
    )


def _server_env(config: AppConfig):
    return patch.dict(
        os.environ,
        {"HERMES_HOME": config.hermes.home, "MACSOFT_PROFILE_ROOT": config.hermes.profile_root},
    )


class ServerHomeTests(unittest.TestCase):
    def test_provisions_one_native_server_home(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = _config(Path(temporary))
            with _server_env(config):
                home = ensure_server_home(config)
            self.assertEqual(home, Path(temporary) / "runtime" / "admin")
            for relative in (
                "config.yaml", "memories/USER.md", "memories/MEMORY.md",
                "skills", "sessions", "logs", "curator", "backups",
            ):
                self.assertTrue((home / relative).exists(), relative)
            self.assertFalse((Path(temporary) / "runtime" / "global-staging").exists())

    def test_admin_provider_uses_server_request_timeout_without_losing_provider_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = _config(Path(temporary))
            runtime = Path(config.hermes.home)
            runtime.mkdir(parents=True)
            (runtime / "config.yaml").write_text(
                yaml.safe_dump(
                    {
                        "model": {"provider": "openai-codex", "default": "gpt-5.4"},
                        "providers": {
                            "openai-codex": {"device_profile": "customer-profile"},
                        },
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            admin = runtime / "admin"
            admin.mkdir()
            (admin / "config.yaml").write_text(
                yaml.safe_dump(
                    {"providers": {"another-provider": {"request_timeout_seconds": 91}}},
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            with _server_env(config):
                home = ensure_server_home(config)

            admin_config = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
            self.assertEqual(admin_config["providers"]["openai-codex"]["request_timeout_seconds"], 30)
            self.assertEqual(admin_config["providers"]["openai-codex"]["stale_timeout_seconds"], 30)
            self.assertEqual(admin_config["providers"]["openai-codex"]["device_profile"], "customer-profile")
            self.assertEqual(admin_config["providers"]["another-provider"]["request_timeout_seconds"], 91)

    def test_shareable_context_contains_memory_but_not_skill_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = _config(Path(temporary))
            with _server_env(config):
                home = ensure_server_home(config)
                (home / "memories" / "MEMORY.md").write_text("Validate totals before export.", encoding="utf-8")
                skill = home / "skills" / "reconciliation" / "SKILL.md"
                skill.parent.mkdir(parents=True)
                skill.write_text("# Reconciliation\nCheck both ledgers.", encoding="utf-8")
                context = read_shareable_server_context(config)
            self.assertIn("Validate totals before export.", context or "")
            self.assertNotIn("Check both ledgers.", context or "")

    def test_removed_global_learning_routes_are_not_registered(self) -> None:
        paths = {route.path for route in admin_router.routes}
        self.assertFalse(any(path.startswith("/api/admin/global-learning") for path in paths))

    def test_client_session_keeps_first_server_context_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = _config(Path(temporary))
            with _server_env(config):
                home = ensure_server_home(config)
                profile = Path(config.hermes.profile_root) / ("prof_" + "a" * 32)
                (profile / "sessions").mkdir(parents=True)
                (home / "memories" / "MEMORY.md").write_text("first version", encoding="utf-8")
                first = read_or_create_server_context_snapshot(
                    config,
                    profile_id=profile.name,
                    session_id="sess_" + "b" * 32,
                )
                (home / "memories" / "MEMORY.md").write_text("second version", encoding="utf-8")
                second = read_or_create_server_context_snapshot(
                    config,
                    profile_id=profile.name,
                    session_id="sess_" + "b" * 32,
                )
            self.assertEqual(first, second)
            self.assertIn("first version", second or "")
            self.assertNotIn("second version", second or "")


if __name__ == "__main__":
    unittest.main()
