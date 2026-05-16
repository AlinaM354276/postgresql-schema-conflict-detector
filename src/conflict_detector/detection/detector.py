from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set, Tuple

from src.conflict_detector.core.models import Conflict, Operation, ReferenceOperation
from src.conflict_detector.graph.schema_graph import SchemaGraph
from src.conflict_detector.rules.base import ConflictRule, RuleContext, RuleCheckResult
from src.conflict_detector.rules.registry import DEFAULT_RULES
from src.conflict_detector.semantics.dependency import (
    compute_transitive_closure,
    explain_dependency_intersection,
    merge_dependency_graphs,
)
from src.conflict_detector.semantics.impact import (
    compute_impact_map,
    impact_of,
    impacts_intersect,
)

try:
    from src.conflict_detector.semantics.operation_compatibility import (
        operations_are_semantically_compatible,
    )
except Exception:
    operations_are_semantically_compatible = None


@dataclass(frozen=True)
class InterferencePair:
    operation_a: Operation
    operation_b: Operation
    shared_impact: Tuple[str, ...]


@dataclass(frozen=True)
class DetectionResult:
    conflicts: Tuple[Conflict, ...]
    interference_pairs: Tuple[InterferencePair, ...] = tuple()

    def has_conflicts(self) -> bool:
        return bool(self.conflicts)


ConflictDetectionResult = DetectionResult


def conflict_key(conflict: Conflict) -> Tuple[str, Tuple[str, ...], str, str]:
    op_a_type = type(conflict.operation_a).__name__ if conflict.operation_a else ""
    op_b_type = type(conflict.operation_b).__name__ if conflict.operation_b else ""

    return (
        conflict.rule_id,
        tuple(sorted(conflict.object_ids)),
        op_a_type,
        op_b_type,
    )


def should_skip_as_semantically_compatible(
    operation_a: Operation,
    operation_b: Operation,
) -> bool:
    if operations_are_semantically_compatible is None:
        return False

    compatibility = operations_are_semantically_compatible(
        operation_a,
        operation_b,
    )
    return compatibility.is_compatible


def iter_rule_conflicts(result: RuleCheckResult) -> Tuple[Conflict, ...]:
    if hasattr(result, "conflicts"):
        conflicts = getattr(result, "conflicts")
        if conflicts is None:
            return tuple()
        return tuple(conflicts)

    if hasattr(result, "conflict"):
        conflict = getattr(result, "conflict")
        if conflict is None:
            return tuple()
        return (conflict,)

    return tuple()


def _as_tuple(operations: Iterable[Operation]) -> Tuple[Operation, ...]:
    if isinstance(operations, tuple):
        return operations
    return tuple(operations)


def compute_interference_pairs(
    operations_a: Sequence[Operation],
    operations_b: Sequence[Operation],
    impact_map: dict[int, object],
) -> Tuple[InterferencePair, ...]:
    pairs: List[InterferencePair] = []

    for op_a in operations_a:
        for op_b in operations_b:
            shared = impacts_intersect(impact_map, op_a, op_b)

            if shared:
                pairs.append(
                    InterferencePair(
                        operation_a=op_a,
                        operation_b=op_b,
                        shared_impact=tuple(sorted(shared)),
                    )
                )

    return tuple(pairs)


def _operation_reference_signature(operation: Operation | None) -> tuple[str, str] | None:
    """
    Возвращает сигнатуру ReferenceOperation: (source, target).
    """
    if isinstance(operation, ReferenceOperation):
        return operation.source, operation.target

    return None


def _reference_signature(conflict: Conflict) -> tuple[str, str] | None:
    """
    Извлекает reference source/target из metadata или из самих операций.

    Нужно для дедупликации:
    если найден R3_DANGLING_REFERENCE, то менее специфичный R1 по той же
    ссылке не должен выводиться.
    """
    metadata = dict(conflict.metadata or {})

    source = metadata.get("reference_source_id")
    target = metadata.get("reference_target_id")

    if source is not None and target is not None:
        return str(source), str(target)

    operation_a_signature = _operation_reference_signature(conflict.operation_a)
    if operation_a_signature is not None:
        return operation_a_signature

    operation_b_signature = _operation_reference_signature(conflict.operation_b)
    if operation_b_signature is not None:
        return operation_b_signature

    return None


def _prefer_specific_conflicts(conflicts: Iterable[Conflict]) -> Tuple[Conflict, ...]:
    """
    Убирает менее специфичные конфликты.

    Если для одной FK-ссылки уже найден R3_DANGLING_REFERENCE,
    то R1_REFERENTIAL_INTEGRITY по той же FK-ссылке считается дубликатом.

    Это убирает лишний R1 в R3-сценарии:
    - Add Reference orders.user_id -> users.id
    - Drop table users
    """
    conflicts_tuple = tuple(conflicts)

    r3_reference_signatures = {
        signature
        for conflict in conflicts_tuple
        if conflict.rule_id == "R3_DANGLING_REFERENCE"
        for signature in [_reference_signature(conflict)]
        if signature is not None
    }

    filtered: List[Conflict] = []

    for conflict in conflicts_tuple:
        signature = _reference_signature(conflict)

        if (
            conflict.rule_id == "R1_REFERENTIAL_INTEGRITY"
            and signature is not None
            and signature in r3_reference_signatures
        ):
            continue

        filtered.append(conflict)

    return tuple(filtered)


class ConflictDetector:
    """
    Реализация DetectConflicts(ΔA, ΔB).

    Важно:
    правила R1-R7 упорядочены от специальных к общим.
    Поэтому для одной пары операций берём первое сработавшее правило.
    Это предотвращает ситуацию, когда R6 перекрывает R1-R5.
    """

    def __init__(
        self,
        rules: Optional[Sequence[ConflictRule]] = None,
    ) -> None:
        self.rules: Tuple[ConflictRule, ...] = tuple(rules or DEFAULT_RULES)

    def detect(
        self,
        operations_a: Iterable[Operation],
        operations_b: Iterable[Operation],
        graph_a: SchemaGraph,
        graph_b: SchemaGraph,
    ) -> DetectionResult:
        ops_a = _as_tuple(operations_a)
        ops_b = _as_tuple(operations_b)

        dep = merge_dependency_graphs(graph_a, graph_b)
        dep_closure = compute_transitive_closure(dep)

        all_operations = (*ops_a, *ops_b)
        impact_map = compute_impact_map(all_operations, dep_closure)

        interference_pairs = compute_interference_pairs(
            operations_a=ops_a,
            operations_b=ops_b,
            impact_map=impact_map,
        )

        conflicts: List[Conflict] = []
        seen: Set[Tuple[str, Tuple[str, ...], str, str]] = set()

        for operation_a in ops_a:
            for operation_b in ops_b:
                shared_impact = tuple(
                    sorted(impacts_intersect(impact_map, operation_a, operation_b))
                )

                impact_a = impact_of(impact_map, operation_a)
                impact_b = impact_of(impact_map, operation_b)

                dependency_trace = explain_dependency_intersection(
                    dep=dep,
                    sources_a=impact_a.targets,
                    sources_b=impact_b.targets,
                    intersection=shared_impact,
                )

                context = RuleContext(
                    operation_a=operation_a,
                    operation_b=operation_b,
                    graph_a=graph_a,
                    graph_b=graph_b,
                    base_graph=None,
                    impact_a=impact_a,
                    impact_b=impact_b,
                    shared_impact=shared_impact,
                    dependency_trace=dependency_trace,
                )

                if should_skip_as_semantically_compatible(operation_a, operation_b):
                    continue

                for rule in self.rules:
                    check_result = rule.check(context)
                    rule_conflicts = iter_rule_conflicts(check_result)

                    if not rule_conflicts:
                        continue

                    for conflict in rule_conflicts:
                        key = conflict_key(conflict)
                        if key in seen:
                            continue

                        seen.add(key)
                        conflicts.append(conflict)

                    # Первое сработавшее правило выигрывает.
                    break

        return DetectionResult(
            conflicts=_prefer_specific_conflicts(conflicts),
            interference_pairs=interference_pairs,
        )


def detect_conflicts(
    operations_a: Iterable[Operation],
    operations_b: Iterable[Operation],
    graph_a: SchemaGraph,
    graph_b: SchemaGraph,
    rules: Optional[Iterable[ConflictRule]] = None,
) -> DetectionResult:
    detector = ConflictDetector(
        rules=tuple(rules) if rules is not None else None,
    )

    return detector.detect(
        operations_a=operations_a,
        operations_b=operations_b,
        graph_a=graph_a,
        graph_b=graph_b,
    )
