from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from src.conflict_detector.core.models import Conflict, SeverityLevel, freeze_attrs


SEVERITY_ORDER = {
    SeverityLevel.LOW: 0,
    SeverityLevel.MEDIUM: 1,
    SeverityLevel.HIGH: 2,
    SeverityLevel.CRITICAL: 3,
}


ORDER_TO_SEVERITY = {
    0: SeverityLevel.LOW,
    1: SeverityLevel.MEDIUM,
    2: SeverityLevel.HIGH,
    3: SeverityLevel.CRITICAL,
}


DEFAULT_IMPACT_THRESHOLD = 5


def severity_rank(level: SeverityLevel) -> int:
    return SEVERITY_ORDER[level]


def max_severity(left: SeverityLevel, right: SeverityLevel) -> SeverityLevel:
    return left if severity_rank(left) >= severity_rank(right) else right


def raise_severity(level: SeverityLevel, steps: int = 1) -> SeverityLevel:
    rank = min(3, severity_rank(level) + steps)
    return ORDER_TO_SEVERITY[rank]


def is_invariant_conflict(conflict: Conflict) -> bool:
    if conflict.rule_id.startswith("M2_"):
        return True

    metadata = dict(conflict.metadata or {})
    return metadata.get("kind") == "invariant_violation"


def is_integrity_conflict(conflict: Conflict) -> bool:
    prefixes = (
        "F",
        "C",
        "I",
        "D",
    )
    return conflict.rule_id.startswith(prefixes)


def impact_size(conflict: Conflict) -> int:
    metadata = dict(conflict.metadata or {})

    shared_impact = metadata.get("shared_impact")
    if isinstance(shared_impact, (list, tuple, set, frozenset)):
        return len(shared_impact)

    impacted_objects = metadata.get("impacted_objects")
    if isinstance(impacted_objects, (list, tuple, set, frozenset)):
        return len(impacted_objects)

    return len(tuple(conflict.object_ids))


def base_severity(conflict: Conflict) -> SeverityLevel:
    if is_invariant_conflict(conflict):
        return SeverityLevel.CRITICAL

    if conflict.rule_id in {
        "R1_DROP_VS_MODIFY",
        "R2_DROP_VS_RENAME",
        "F1_DROP_REFERENCED_TARGET_VS_MODIFY_REFERENCE_SOURCE",
        "C1_DROP_PRIMARY_KEY_VS_MODIFY_DEPENDENT",
        "I1_DROP_COLUMN_VS_ADD_INDEX",
        "D1_DROP_PREREQUISITE_VS_MODIFY_DEPENDENT",
        "D2_DROP_PREREQUISITE_VS_RENAME_DEPENDENT",
    }:
        return SeverityLevel.HIGH

    if conflict.rule_id in {
        "R3_RENAME_VS_RENAME",
        "R4_MODIFY_VS_MODIFY",
        "R5_ADD_VS_ADD",
        "R6_RENAME_VS_MODIFY",
        "M3_NON_COMMUTATIVE_OPERATIONS",
    }:
        return SeverityLevel.MEDIUM

    return conflict.severity


def evaluate_severity(
    conflict: Conflict,
    *,
    impact_threshold: int = DEFAULT_IMPACT_THRESHOLD,
) -> SeverityLevel:
    level = base_severity(conflict)

    if is_invariant_conflict(conflict):
        return SeverityLevel.CRITICAL

    if impact_size(conflict) > impact_threshold:
        level = raise_severity(level, steps=1)

    return level


def with_evaluated_severity(
    conflict: Conflict,
    *,
    impact_threshold: int = DEFAULT_IMPACT_THRESHOLD,
) -> Conflict:
    evaluated = evaluate_severity(
        conflict,
        impact_threshold=impact_threshold,
    )

    metadata = dict(conflict.metadata or {})
    metadata["base_severity"] = conflict.severity.value
    metadata["evaluated_severity"] = evaluated.value
    metadata["impact_size"] = impact_size(conflict)

    return Conflict(
        rule_id=conflict.rule_id,
        message=conflict.message,
        object_ids=conflict.object_ids,
        severity=evaluated,
        operation_a=conflict.operation_a,
        operation_b=conflict.operation_b,
        metadata=freeze_attrs(metadata),
    )


def evaluate_conflicts(
    conflicts: Iterable[Conflict],
    *,
    impact_threshold: int = DEFAULT_IMPACT_THRESHOLD,
) -> Tuple[Conflict, ...]:
    return tuple(
        with_evaluated_severity(
            conflict,
            impact_threshold=impact_threshold,
        )
        for conflict in conflicts
    )
