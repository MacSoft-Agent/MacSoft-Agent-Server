"""MacSoft-owned Skill names that personal learning cannot shadow."""

from __future__ import annotations


PROTECTED_SKILL_NAMES = frozenset(
    {
        "pharmarise-company-configuration",
        "autocount-payment-knockoff-automation",
        "autocount-local-direct-payment-knockoff",
        "autocount-receiving-supplier-invoice-automation",
        "autocount-local-direct-purchase-invoice",
    }
)


def is_protected_skill_name(name: object) -> bool:
    """Return whether *name* is reserved for a shared MacSoft Skill."""
    return isinstance(name, str) and name.strip() in PROTECTED_SKILL_NAMES
