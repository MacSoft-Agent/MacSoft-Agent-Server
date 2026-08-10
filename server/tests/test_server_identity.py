from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from macsoft.db import get_server_id, init_db
from macsoft.gateway.routes_health import router


def test_config(path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        database=SimpleNamespace(path=str(path)),
        server=SimpleNamespace(host="127.0.0.1", port=8787),
        runtime=SimpleNamespace(mode="test"),
        autocount=SimpleNamespace(enabled=False),
    )


class ServerIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "server.db"
        self.config = test_config(self.database)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_identity_is_generated_once_and_survives_reopen(self) -> None:
        init_db(self.config)
        first = get_server_id(self.config)
        UUID(first)

        init_db(self.config)
        self.assertEqual(get_server_id(self.config), first)

    def test_identity_survives_database_backup_restore(self) -> None:
        init_db(self.config)
        original = get_server_id(self.config)
        restored_database = Path(self.temp.name) / "restored.db"
        shutil.copy2(self.database, restored_database)
        restored_config = test_config(restored_database)

        self.assertEqual(get_server_id(restored_config), original)

    def test_health_exposes_the_persisted_server_identity(self) -> None:
        init_db(self.config)
        app = FastAPI()
        app.state.config = self.config
        app.state.product_version = "test-version"
        app.state.server_id = get_server_id(self.config)
        app.include_router(router)

        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["server_id"], get_server_id(self.config))


if __name__ == "__main__":
    unittest.main()
