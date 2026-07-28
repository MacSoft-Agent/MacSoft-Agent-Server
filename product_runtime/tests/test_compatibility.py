from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from macsoft_runtime.compatibility import (
    assess_live_compatibility,
    assess_pre_start_compatibility,
    expected_runtime_metadata,
)
from macsoft_runtime.metadata import ProductMetadata
from macsoft_runtime.paths import resolve_packaged_paths


METADATA = ProductMetadata(
    product="MacSoft Agent",
    product_version="0.1.0",
    channel="stable",
    runtime_base_version="v-test",
    runtime_base_commit="1" * 40,
    runtime_contract_version=1,
    runtime_metadata_schema_version=1,
    build_date="2026-07-28",
    build_id="test",
    data_schema_version=1,
    protected_resource_version=1,
    update_manifest_url=None,
)


class RuntimeCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.paths = resolve_packaged_paths(root / "Program", root / "Data")
        self.paths.ai_program_root.mkdir(parents=True)
        self.expected = expected_runtime_metadata(METADATA)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_declaration(self, value: object) -> None:
        (self.paths.ai_program_root / "macsoft-runtime.json").write_text(
            json.dumps(value),
            encoding="utf-8",
        )

    def test_exact_independent_declaration_is_accepted(self) -> None:
        self.write_declaration(self.expected)

        result = assess_pre_start_compatibility(self.paths, METADATA)

        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["phase"], "pre_start")
        self.assertEqual(result["detected"], self.expected)
        self.assertEqual(result["mismatched_fields"], [])

    def test_missing_or_malformed_declaration_fails_closed(self) -> None:
        missing = assess_pre_start_compatibility(self.paths, METADATA)
        self.assertEqual(missing["status"], "rejected")
        self.assertEqual(missing["error_code"], "runtime_declaration_invalid")

        self.write_declaration({"runtime": "hermes-agent"})
        malformed = assess_pre_start_compatibility(self.paths, METADATA)
        self.assertEqual(malformed["status"], "rejected")
        self.assertEqual(malformed["detected"], None)

    def test_any_expected_field_mismatch_is_rejected(self) -> None:
        mismatched = dict(self.expected)
        mismatched["runtime_base_commit"] = "2" * 40
        self.write_declaration(mismatched)

        result = assess_pre_start_compatibility(self.paths, METADATA)

        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["error_code"], "runtime_metadata_mismatch")
        self.assertEqual(result["mismatched_fields"], ["runtime_base_commit"])

    def test_live_health_must_repeat_the_runtime_owned_declaration(self) -> None:
        accepted = assess_live_compatibility(
            self.expected,
            {"status": "ok", "macsoft_runtime": self.expected},
        )
        self.assertEqual(accepted["status"], "accepted")
        self.assertEqual(accepted["phase"], "post_start")

        rejected = assess_live_compatibility(self.expected, {"status": "ok"})
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["error_code"], "runtime_health_metadata_invalid")


if __name__ == "__main__":
    unittest.main()
