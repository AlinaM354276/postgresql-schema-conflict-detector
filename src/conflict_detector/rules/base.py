from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from src.conflict_detector.core.models import Conflict, Operation
from src.conflict_detector.graph.schema_graph import SchemaGraph
from src.conflict_detector.semantics.impact import OperationImpact


def op_target(operation: Operation) -> str | None:
    return getattr(operation, "target", None)


def same_target(operation_a: Operation, operation_b: Operation) -> bool:
    return op_target(operation_a) is not None and op_target(operation_a) == op_target(operation_b)


def targets_intersect(operation_a: Operation, operation_b: Operation) -> bool:
    targets_a = {
        value
        for value in (
            getattr(operation_a, "target", None),
            getattr(operation_a, "source", None),
        )
        if value is not None
    }
    targets_b = {
        value
        for value in (
            getattr(operation_b, "target", None),
            getattr(operation_b, "source", None),
        )
        if value is not None
    }
    return bool(targets_a & targets_b)


@dataclass(frozen=True)
class RuleContext:
    operation_a: Operation
    operation_b: Operation

    # Старые правила используют graph_a / graph_b.
    graph_a: Optional[SchemaGraph] = None
    graph_b: Optional[SchemaGraph] = None

    # Новая формальная модель этапа 3.
    base_graph: Optional[SchemaGraph] = None
    impact_a: Optional[OperationImpact] = None
    impact_b: Optional[OperationImpact] = None
    shared_impact: Tuple[str, ...] = tuple()
    dependency_trace: Optional[Dict[str, list[str]]] = None

    def has_intersection(self) -> bool:
        return bool(self.shared_impact)


@dataclass(frozen=True)
class RuleCheckResult:
    conflicts: Tuple[Conflict, ...]

    @staticmethod
    def no_match() -> "RuleCheckResult":
        return RuleCheckResult(conflicts=tuple())

    @staticmethod
    def from_conflict(conflict: Conflict) -> "RuleCheckResult":
        return RuleCheckResult(conflicts=(conflict,))

    @staticmethod
    def from_conflicts(conflicts: Tuple[Conflict, ...]) -> "RuleCheckResult":
        return RuleCheckResult(conflicts=conflicts)

    def has_conflicts(self) -> bool:
        return bool(self.conflicts)


@dataclass(frozen=True)
class BaseConflictRule:
    rule_id: str
    description: str

    def check(self, context: RuleContext) -> RuleCheckResult:
        raise NotImplementedError


# Обратная совместимость со старыми импортами:
ConflictRule = BaseConflictRule
