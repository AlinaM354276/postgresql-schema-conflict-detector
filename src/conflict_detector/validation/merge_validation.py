from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from src.conflict_detector.core.models import Conflict, SeverityLevel, freeze_attrs
from src.conflict_detector.graph.schema_graph import SchemaGraph
from src.conflict_detector.validation.invariants import (
    InvariantCheckResult,
    InvariantViolation,
    validate_schema_invariants,
)


@dataclass(frozen=True)
class MergeValidationResult:
    is_valid: bool
    invariant_result: InvariantCheckResult
    conflicts: Tuple[Conflict, ...]


def invariant_violation_to_conflict(violation: InvariantViolation) -> Conflict:
    """
    R7. Semantic incompatibility.

    Merge-level invariant violations считаем реализацией R7:
    структура merge-кандидата построена, но итоговая схема нарушает
    семантические/целостностные ограничения.
    """
    return Conflict(
        rule_id="R7_SEMANTIC_INCOMPATIBILITY",
        message=(
            "Merged schema violates semantic or integrity invariant: "
            f"{violation.message}"
        ),
        object_ids=violation.object_ids,
        severity=SeverityLevel.CRITICAL,
        metadata=freeze_attrs(
            {
                "kind": "semantic_incompatibility",
                "invariant_id": violation.invariant_id,
            }
        ),
    )


def validate_merge_candidate(graph: SchemaGraph) -> MergeValidationResult:
    """
    Проверяет merge-кандидат через инварианты схемы.

    Нарушения инвариантов отображаются в R7_SEMANTIC_INCOMPATIBILITY.
    """
    invariant_result = validate_schema_invariants(graph)
    conflicts = tuple(
        invariant_violation_to_conflict(violation)
        for violation in invariant_result.violations
    )

    return MergeValidationResult(
        is_valid=invariant_result.is_valid(),
        invariant_result=invariant_result,
        conflicts=conflicts,
    )
