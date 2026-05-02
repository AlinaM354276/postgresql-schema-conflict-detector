from __future__ import annotations

from typing import Dict

from src.conflict_detector.core.models import Conflict


RULE_EXPLANATIONS: Dict[str, Dict[str, str]] = {
    "R1_REFERENTIAL_INTEGRITY": {
        "type": "Referential integrity conflict",
        "title": "R1. Referential integrity conflict",
        "description": (
            "One branch drops an object that is used directly or transitively "
            "by an operation in another branch."
        ),
        "reason": (
            "The second operation depends on an object removed by the first branch."
        ),
        "consequence": (
            "The merge may produce invalid references or broken dependent objects."
        ),
    },
    "R2_TYPE_INCONSISTENCY": {
        "type": "Type inconsistency conflict",
        "title": "R2. Type inconsistency",
        "description": (
            "One branch changes a column type while another branch adds or modifies "
            "a dependent object assuming the old type."
        ),
        "reason": (
            "Foreign keys, indexes, and constraints may no longer be valid after "
            "the type change."
        ),
        "consequence": (
            "The resulting schema may violate type compatibility requirements."
        ),
    },
    "R3_DANGLING_REFERENCE": {
        "type": "Dangling reference conflict",
        "title": "R3. Dangling reference",
        "description": (
            "A branch adds a reference to an object that is absent or dropped "
            "in another branch."
        ),
        "reason": (
            "The reference source or target does not exist in the merged schema."
        ),
        "consequence": (
            "The merge result violates reference well-formedness."
        ),
    },
    "R4_NAMING_CONFLICT": {
        "type": "Naming / correspondence conflict",
        "title": "R4. Naming conflict",
        "description": (
            "The same object identity or name is introduced with different definitions."
        ),
        "reason": (
            "Equal names do not imply semantic equivalence."
        ),
        "consequence": (
            "The merge cannot decide which object definition is correct."
        ),
    },
    "R5_RENAME_AWARE_CONFLICT": {
        "type": "Rename-aware conflict",
        "title": "R5. Rename-aware conflict",
        "description": (
            "A rename operation conflicts with another operation that uses the old "
            "identity or creates a colliding identity."
        ),
        "reason": (
            "The correspondence between old and new object identities is ambiguous "
            "or inconsistent."
        ),
        "consequence": (
            "The merge may lose identity preservation or create duplicate objects."
        ),
    },
    "R6_TRANSITIVE_DEPENDENCY_CONFLICT": {
        "type": "Dependency-induced conflict",
        "title": "R6. Transitive dependency conflict",
        "description": (
            "Operations have intersecting transitive impact sets and are not known "
            "to be compatible."
        ),
        "reason": (
            "The conflict is induced through dependency chains rather than only "
            "through direct target equality."
        ),
        "consequence": (
            "The operations may be non-commutative or produce different merge results."
        ),
    },
    "R7_SEMANTIC_INCOMPATIBILITY": {
        "type": "Semantic incompatibility",
        "title": "R7. Semantic incompatibility",
        "description": (
            "The merged schema violates semantic or integrity invariants."
        ),
        "reason": (
            "The merge candidate is not valid under schema well-formedness or "
            "integrity constraints."
        ),
        "consequence": (
            "The merge result must be rejected or manually resolved."
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
