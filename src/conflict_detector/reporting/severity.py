from __future__ import annotations

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
    if conflict.rule_id == "R7_SEMANTIC_INCOMPATIBILITY":
        return True

    if conflict.rule_id.startswith("M2_"):
        return True

    metadata = dict(conflict.metadata or {})
    return metadata.get("kind") in {
        "invariant_violation",
        "semantic_incompatibility",
    }


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
    if conflict.rule_id in {
        "R1_REFERENTIAL_INTEGRITY",
        "R3_DANGLING_REFERENCE",
        "R7_SEMANTIC_INCOMPATIBILITY",
    }:
        return SeverityLevel.CRITICAL

    if conflict.rule_id in {
        "R2_TYPE_INCONSISTENCY",
        "R4_NAMING_CONFLICT",
    }:
        return SeverityLevel.HIGH

    if conflict.rule_id in {
        "R5_RENAME_AWARE_CONFLICT",
        "R6_TRANSITIVE_DEPENDENCY_CONFLICT",
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

    # R1, R3, R7 критические по смыслу.
    if conflict.rule_id in {
        "R1_REFERENTIAL_INTEGRITY",
        "R3_DANGLING_REFERENCE",
        "R7_SEMANTIC_INCOMPATIBILITY",
    }:
        return SeverityLevel.CRITICAL

    # R2 должен оставаться HIGH.
    # Большой impact не должен превращать несовместимость типов в CRITICAL,
    # иначе отчёт становится слишком шумным.
    if conflict.rule_id == "R2_TYPE_INCONSISTENCY":
        return SeverityLevel.HIGH

    if conflict.rule_id == "R4_NAMING_CONFLICT":
        return SeverityLevel.HIGH

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
