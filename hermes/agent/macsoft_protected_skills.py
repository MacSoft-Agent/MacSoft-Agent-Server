"""MacSoft-owned Skill names that personal learning cannot shadow."""

from __future__ import annotations


PROTECTED_SKILL_NAMES: frozenset[str] = frozenset()


def is_protected_skill_name(name: object) -> bool:
    """Return whether *name* is reserved for a shared MacSoft Skill."""
    return isinstance(name, str) and name.strip() in PROTECTED_SKILL_NAMES
