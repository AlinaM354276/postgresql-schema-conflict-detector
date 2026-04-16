from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple

from src.conflict_detector.core.models import Conflict, Operation, SeverityLevel


@dataclass(frozen=True)
class ConflictSummary:
    total: int
    by_severity: Dict[SeverityLevel, int]
    has_conflicts: bool
    has_critical: bool

    @staticmethod
    def build(conflicts: Iterable[Conflict]) -> "ConflictSummary":
        conflicts_list = list(conflicts)

        by_severity: Dict[SeverityLevel, int] = {
            level: 0 for level in SeverityLevel
        }

        for c in conflicts_list:
            by_severity[c.severity] += 1

        has_critical = by_severity.get(SeverityLevel.CRITICAL, 0) > 0

        return ConflictSummary(
            total=len(conflicts_list),
            by_severity=by_severity,
            has_conflicts=len(conflicts_list) > 0,
            has_critical=has_critical,
        )


@dataclass(frozen=True)
class BranchAnalysis:
    operations: Tuple[Operation, ...]

    def __len__(self) -> int:
        return len(self.operations)


@dataclass(frozen=True)
class MergeAnalysisResult:
    """
    Финальный результат анализа трёхстороннего merge.

    Содержит:
    - операции ветки A
    - операции ветки B
    - найденные конфликты
    - агрегированную сводку
    """

    operations_a: Tuple[Operation, ...]
    operations_b: Tuple[Operation, ...]
    conflicts: Tuple[Conflict, ...]
    summary: ConflictSummary

    @staticmethod
    def build(
        operations_a: Iterable[Operation],
        operations_b: Iterable[Operation],
        conflicts: Iterable[Conflict],
    ) -> "MergeAnalysisResult":
        ops_a = tuple(operations_a)
        ops_b = tuple(operations_b)
        conflicts_tuple = tuple(conflicts)

        summary = ConflictSummary.build(conflicts_tuple)

        return MergeAnalysisResult(
            operations_a=ops_a,
            operations_b=ops_b,
            conflicts=conflicts_tuple,
            summary=summary,
        )
    