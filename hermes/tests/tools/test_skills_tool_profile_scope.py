"""Regression tests for profile-scoped skills_tool path resolution."""

import importlib
import json
from pathlib import Path


def _write_skill(root: Path, category: str, name: str, description: str) -> Path:
    skill_dir = root / "skills" / category / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"---\n\n"
        f"# {name}\n\n"
        f"Loaded from {description}.\n",
        encoding="utf-8",
    )
    return skill_dir


def _reload_skills_tool(import_home: Path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(import_home))
    import tools.skills_tool as skills_tool

    return importlib.reload(skills_tool)


def test_skill_view_uses_live_profile_home_after_module_import(tmp_path, monkeypatch):
    """skill_view should not stay pinned to HERMES_HOME from import time."""
    default_home = tmp_path / "default-home"
    profile_home = tmp_path / "profiles" / "orchestrator"
    _write_skill(default_home, "autonomous-ai-agents", "default-only", "default home")
    profile_skill_dir = _write_skill(
        profile_home,
        "software-development",
        "kanban-orchestrator-operations",
        "orchestrator profile",
    )

    skills_tool = _reload_skills_tool(default_home, monkeypatch)
    assert skills_tool.SKILLS_DIR == default_home / "skills"

    monkeypatch.setenv("HERMES_HOME", str(profile_home))

    result = json.loads(
        skills_tool.skill_view("kanban-orchestrator-operations", preprocess=False)
    )

    assert result["success"] is True
    assert result["name"] == "kanban-orchestrator-operations"
    assert Path(result["skill_dir"]) == profile_skill_dir
    assert "orchestrator profile" in result["content"]


def test_skills_list_uses_live_profile_home_after_module_import(tmp_path, monkeypatch):
    """skills_list should list the active profile skills, not the import-time root."""
    default_home = tmp_path / "default-home"
    profile_home = tmp_path / "profiles" / "orchestrator"
    _write_skill(default_home, "autonomous-ai-agents", "default-only", "default home")
    _write_skill(
        profile_home,
        "software-development",
        "kanban-orchestrator-operations",
        "orchestrator profile",
    )

    skills_tool = _reload_skills_tool(default_home, monkeypatch)
    monkeypatch.setenv("HERMES_HOME", str(profile_home))

    result = json.loads(skills_tool.skills_list())
    names = {skill["name"] for skill in result["skills"]}

    assert result["success"] is True
    assert "kanban-orchestrator-operations" in names
    assert "default-only" not in names


def test_explicit_skills_dir_monkeypatch_still_wins(tmp_path, monkeypatch):
    """Existing tests can still override tools.skills_tool.SKILLS_DIR directly."""
    default_home = tmp_path / "default-home"
    profile_home = tmp_path / "profiles" / "orchestrator"
    patched_root = tmp_path / "patched"
    patched_skill_dir = _write_skill(
        patched_root,
        "software-development",
        "patched-skill",
        "patched skills dir",
    )
    _write_skill(
        profile_home,
        "software-development",
        "profile-skill",
        "orchestrator profile",
    )

    skills_tool = _reload_skills_tool(default_home, monkeypatch)
    monkeypatch.setenv("HERMES_HOME", str(profile_home))
    monkeypatch.setattr(skills_tool, "SKILLS_DIR", patched_root / "skills")

    result = json.loads(skills_tool.skill_view("patched-skill", preprocess=False))

    assert result["success"] is True
    assert Path(result["skill_dir"]) == patched_skill_dir


def test_protected_external_skill_wins_over_profile_collision(tmp_path, monkeypatch):
    default_home = tmp_path / "default-home"
    profile_home = tmp_path / "profiles" / "orchestrator"
    external_root = tmp_path / "protected-skills"
    name = "autocount-payment-knockoff-automation"
    _write_skill(profile_home, "learned", name, "profile shadow")
    external_skill = external_root / name
    external_skill.mkdir(parents=True)
    (external_skill / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: protected product skill\n---\n\n"
        "# Protected product workflow\n",
        encoding="utf-8",
    )
    (profile_home / "config.yaml").write_text(
        "skills:\n"
        "  external_dirs:\n"
        f"    - {external_root.as_posix()}\n",
        encoding="utf-8",
    )

    skills_tool = _reload_skills_tool(default_home, monkeypatch)
    monkeypatch.setenv("HERMES_HOME", str(profile_home))
    skills_tool._SKILLS_CACHE.clear()

    listed = json.loads(skills_tool.skills_list())
    matching = [skill for skill in listed["skills"] if skill["name"] == name]
    assert len(matching) == 1
    viewed = json.loads(skills_tool.skill_view(name))
    assert Path(viewed["skill_dir"]) == external_skill

    viewed = json.loads(skills_tool.skill_view(name, preprocess=False))
    assert viewed["success"] is True
    assert Path(viewed["skill_dir"]) == external_skill
    assert "Protected product workflow" in viewed["content"]
