from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = ROOT / "packaging" / "templates" / "protected" / "runtime" / "skills"
MUTABLE_SKILLS_ROOT = ROOT / "packaging" / "templates" / "runtime" / "skills"


def read_frontmatter(path: Path) -> tuple[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 4 or lines[0].strip() != "---":
        raise AssertionError(f"missing frontmatter: {path}")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise AssertionError(f"unterminated frontmatter: {path}") from exc
    values = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        if separator:
            values[key.strip()] = value.strip().strip('"')
    return values.get("name", ""), values.get("description", "")


class SkillPackageTests(unittest.TestCase):
    concise_skills = {
        "macsoft-chart-dashboard",
        "macsoft-chart-visualization",
        "kpi-dashboard-design",
        "data-storytelling",
        "web-design-engineer",
    }
    expected = concise_skills

    def test_packaged_top_level_skill_inventory_is_an_explicit_allowlist(self) -> None:
        manifest = __import__("json").loads(
            (ROOT / "packaging" / "templates" / "protected-resources.json").read_text(
                encoding="utf-8"
            )
        )
        skill_tree = next(
            item
            for item in manifest["directories"]
            if item["destination"] == "runtime/skills"
        )
        self.assertEqual(set(skill_tree["include_directories"]), self.expected)

    def test_selected_skills_have_valid_metadata_and_expected_references(self) -> None:
        self.assertTrue(SKILLS_ROOT.is_dir())
        self.assertTrue(self.expected <= {item.name for item in SKILLS_ROOT.iterdir()})
        for directory_name in self.expected:
            skill_dir = SKILLS_ROOT / directory_name
            skill_md = skill_dir / "SKILL.md"
            self.assertTrue(skill_md.is_file(), directory_name)
            name, description = read_frontmatter(skill_md)
            self.assertEqual(name, directory_name)
            self.assertTrue(description.endswith("."), directory_name)
            if directory_name in self.concise_skills:
                self.assertLessEqual(len(description), 60, directory_name)

        dashboard_refs = SKILLS_ROOT / "macsoft-chart-dashboard" / "references"
        self.assertEqual(
            {path.name for path in dashboard_refs.iterdir()},
            {
                "skill-routing.md",
                "data-integrity.md",
                "html-runtime.md",
                "echarts-implementation.md",
            },
        )

    def test_referenced_files_are_present(self) -> None:
        for skill_md in SKILLS_ROOT.glob("*/SKILL.md"):
            text = skill_md.read_text(encoding="utf-8")
            for relative_path in set(re.findall(r"`(references/[A-Za-z0-9_./-]+)`", text)):
                referenced = skill_md.parent / relative_path
                mutable_reference = MUTABLE_SKILLS_ROOT / skill_md.parent.name / relative_path
                self.assertTrue(
                    referenced.is_file()
                    or referenced.is_dir()
                    or mutable_reference.is_file()
                    or mutable_reference.is_dir(),
                    relative_path,
                )

    def test_provenance_records_fixed_sources(self) -> None:
        provenance = ROOT / "third_party" / "agent-skills" / "THIRD_PARTY_SKILLS.md"
        text = provenance.read_text(encoding="utf-8")
        for sha in (
            "b43ddb6543885d55ded2815b5aab75b17643f416",
            "c4b82b0ad771190355eb8e204b1329732a18449a",
            "aaf9a82f5efd73e87cc0998edc398e75bfc35901",
        ):
            self.assertIn(sha, text)
        for license_name in (
            "antvis-LICENSE.txt",
            "wshobson-agents-LICENSE.txt",
            "garden-skills-LICENSE.txt",
        ):
            self.assertTrue((provenance.parent / license_name).is_file())

    def test_dashboard_skill_requires_html_and_forbids_preview_claims(self) -> None:
        text = (SKILLS_ROOT / "macsoft-chart-dashboard" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("<!doctype html>", text)
        self.assertIn("</html>", text)
        self.assertIn("Do not claim that an artifact was", text)
        self.assertIn("Do not use an HTML/report", text)
        self.assertIn("command as a chart data source", text)

    def test_bank_reconciliation_source_uses_live_connector_contract(self) -> None:
        text = (
            SKILLS_ROOT / "autocount-bank-reconciliation" / "SKILL.md"
        ).read_text(encoding="utf-8")
        for command_type in (
            "list-gl-bank-cash-accounts",
            "list-gl-bank-reconciliation-uncleared",
            "validate-gl-bank-reconciliation",
            "create-gl-bank-reconciliation",
            "get-gl-bank-reconciliation",
        ):
            self.assertIn(command_type, text)
        self.assertIn('"actualBalance": 2900', text)
        self.assertIn('"selectedBankTransKeys": [1, 2]', text)
        self.assertIn("send `payload` as a quoted JSON string", text)
        self.assertIn("explicit confirmation before saving", text)
        self.assertIn("Report success only when", text)

if __name__ == "__main__":
    unittest.main()
