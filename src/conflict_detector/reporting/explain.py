from __future__ import annotations

from typing import Dict

from src.conflict_detector.core.models import Conflict


RULE_EXPLANATIONS: Dict[str, Dict[str, str]] = {
    "R1_DROP_VS_MODIFY": {
        "type": "Structural conflict",
        "title": "Drop vs Modify",
        "description": (
            "Object is deleted in one branch and modified in another branch."
        ),
        "reason": (
            "After applying operations, modification is attempted on a non-existent object."
        ),
        "consequence": (
            "Operations are non-commutative. Merge is undefined."
        ),
    },
    "R3_RENAME_VS_RENAME": {
        "type": "Semantic conflict",
        "title": "Rename vs Rename",
        "description": (
            "Object is renamed differently in two branches."
        ),
        "reason": (
            "There is no unique mapping between resulting object identities."
        ),
        "consequence": (
            "Merge cannot determine final object name."
        ),
    },
    "R5_ADD_VS_ADD": {
        "type": "Semantic conflict",
        "title": "Add vs Add",
        "description": (
            "Same object is added differently in two branches."
        ),
        "reason": (
            "Conflicting definitions detected for the same object."
        ),
        "consequence": (
            "Ambiguous object definition prevents merge."
        ),
    },
    "I1_DROP_COLUMN_VS_ADD_INDEX": {
        "type": "Dependency conflict",
        "title": "Drop Column vs Add Index",
        "description": (
            "Column is dropped in one branch while an index is created on it in another branch."
        ),
        "reason": (
            "Index depends on a column that no longer exists."
        ),
        "consequence": (
            "Schema invariants are violated. Merge is undefined."
        ),
    },
}


def explain_conflict(conflict: Conflict) -> Dict[str, str]:
    rule_info = RULE_EXPLANATIONS.get(conflict.rule_id, None)

    if rule_info is None:
        return {
            "type": "Unknown",
            "title": conflict.rule_id,
            "description": conflict.message,
            "reason": "No explanation available.",
            "consequence": "Unknown impact.",
        }

    return {
        "type": rule_info["type"],
        "title": rule_info["title"],
        "description": rule_info["description"],
        "reason": rule_info["reason"],
        "consequence": rule_info["consequence"],
    }
