from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from src.conflict_detector.core.models import Conflict, Operation, SeverityLevel, freeze_attrs
from src.conflict_detector.graph.schema_graph import SchemaGraph
from src.conflict_detector.semantics.apply import apply_operations
from src.conflict_detector.validation.invariants import (
    InvariantCheckResult,
    validate_schema_invariants,
)


@dataclass(frozen=True)
class MergeAttemptResult:
    is_defined: bool
    merged_graph: Optional[SchemaGraph]
    invariant_result: InvariantCheckResult
    conflicts: Tuple[Conflict, ...]
    error_message: Optional[str] = None


def make_merge_undefined_conflict(message: str) -> Conflict:
    return Conflict(
        rule_id="M1_MERGE_UNDEFINED",
        message=message,
        object_ids=tuple(),
        severity=SeverityLevel.CRITICAL,
        metadata=freeze_attrs({"kind": "merge_undefined"}),
    )


def make_invariant_violation_conflicts(
    invariant_result: InvariantCheckResult,
) -> Tuple[Conflict, ...]:
    conflicts = []

    for violation in invariant_result.violations:
        conflicts.append(
            Conflict(
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
        )

    return tuple(conflicts)


def build_merge_candidate(
    base_graph: SchemaGraph,
    operations_a: Tuple[Operation, ...],
    operations_b: Tuple[Operation, ...],
) -> MergeAttemptResult:
    """
    Строит merge candidate граф по консервативной схеме:
    1. применяем ops_a к S0
    2. затем применяем ops_b к результату
    3. валидируем инварианты

    Если применение операций или инварианты не проходят,
    merge считается не определённым.
    """
    try:
        after_a = apply_operations(base_graph, operations_a)
        merged = apply_operations(after_a, operations_b)
    except Exception as exc:
        conflict = make_merge_undefined_conflict(
            f"Merge candidate cannot be constructed: {exc}"
        )
        return MergeAttemptResult(
            is_defined=False,
            merged_graph=None,
            invariant_result=InvariantCheckResult(violations=tuple()),
            conflicts=(conflict,),
            error_message=str(exc),
        )

    invariant_result = validate_schema_invariants(merged)
    if not invariant_result.is_valid():
        invariant_conflicts = make_invariant_violation_conflicts(invariant_result)
        return MergeAttemptResult(
            is_defined=False,
            merged_graph=merged,
            invariant_result=invariant_result,
            conflicts=invariant_conflicts,
            error_message="Merged graph violates schema invariants.",
        )

    return MergeAttemptResult(
        is_defined=True,
        merged_graph=merged,
        invariant_result=invariant_result,
        conflicts=tuple(),
        error_message=None,
    )
