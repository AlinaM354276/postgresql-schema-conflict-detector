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
    return Conflict(
        rule_id=f"M2_{violation.invariant_id}",
        message=violation.message,
        object_ids=violation.object_ids,
        severity=SeverityLevel.CRITICAL,
        metadata=freeze_attrs(
            {
                "kind": "invariant_violation",
                "invariant_id": violation.invariant_id,
            }
        ),
    )


def validate_merge_candidate(graph: SchemaGraph) -> MergeValidationResult:
    """
    Проверяет merge-кандидат через инварианты схемы.

    Это отдельный слой над validate_schema_invariants(),
    потому что в контексте merge нарушение инварианта означает
    неопределённость результата объединения.
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
