from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

from src.conflict_detector.core.models import Conflict, Operation, SeverityLevel
from src.conflict_detector.detection.detector import InterferencePair
from src.conflict_detector.merge.three_way_merge import MergeAttemptResult


@dataclass(frozen=True)
class ConflictSummary:
    total: int
    by_severity: Dict[SeverityLevel, int]
    has_conflicts: bool
    has_critical: bool

    @staticmethod
    def build(conflicts: Iterable[Conflict]) -> "ConflictSummary":
        conflicts_list = list(conflicts)
        by_severity: Dict[SeverityLevel, int] = {level: 0 for level in SeverityLevel}

        for conflict in conflicts_list:
            by_severity[conflict.severity] += 1

        return ConflictSummary(
            total=len(conflicts_list),
            by_severity=by_severity,
            has_conflicts=len(conflicts_list) > 0,
            has_critical=by_severity.get(SeverityLevel.CRITICAL, 0) > 0,
        )


@dataclass(frozen=True)
class BranchAnalysis:
    operations: Tuple[Operation, ...]

    def __len__(self) -> int:
        return len(self.operations)


@dataclass(frozen=True)
class MergeAnalysisResult:
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

        return MergeAnalysisResult(
            operations_a=ops_a,
            operations_b=ops_b,
            conflicts=conflicts_tuple,
            summary=ConflictSummary.build(conflicts_tuple),
        )


@dataclass(frozen=True)
class ThreeWayMergeSummary:
    total_rule_conflicts: int
    total_merge_conflicts: int
    total_conflicts: int
    by_severity: Dict[SeverityLevel, int]
    merge_defined: bool
    invariant_violations_count: int
    has_any_conflicts: bool
    has_critical: bool
    is_commutative: bool | None

    @staticmethod
    def build(
        rule_conflicts: Iterable[Conflict],
        merge_attempt: MergeAttemptResult,
    ) -> "ThreeWayMergeSummary":
        rule_conflicts_tuple = tuple(rule_conflicts)
        merge_conflicts_tuple = tuple(merge_attempt.conflicts)
        all_conflicts = rule_conflicts_tuple + merge_conflicts_tuple
        aggregate = ConflictSummary.build(all_conflicts)

        return ThreeWayMergeSummary(
            total_rule_conflicts=len(rule_conflicts_tuple),
            total_merge_conflicts=len(merge_conflicts_tuple),
            total_conflicts=len(all_conflicts),
            by_severity=aggregate.by_severity,
            merge_defined=merge_attempt.is_defined,
            invariant_violations_count=len(merge_attempt.invariant_result.violations),
            has_any_conflicts=(len(all_conflicts) > 0 or not merge_attempt.is_defined),
            has_critical=aggregate.has_critical or not merge_attempt.is_defined,
            is_commutative=merge_attempt.is_commutative,
        )


@dataclass(frozen=True)
class ThreeWayMergeAnalysisResult:
    operations_a: Tuple[Operation, ...]
    operations_b: Tuple[Operation, ...]
    rule_conflicts: Tuple[Conflict, ...]
    merge_attempt: MergeAttemptResult
    summary: ThreeWayMergeSummary
    interference_pairs: Tuple[InterferencePair, ...] = tuple()

    @staticmethod
    def build(
        operations_a: Iterable[Operation],
        operations_b: Iterable[Operation],
        rule_conflicts: Iterable[Conflict],
        merge_attempt: MergeAttemptResult,
        interference_pairs: Iterable[InterferencePair] = tuple(),
    ) -> "ThreeWayMergeAnalysisResult":
        ops_a = tuple(operations_a)
        ops_b = tuple(operations_b)
        conflicts_tuple = tuple(rule_conflicts)

        return ThreeWayMergeAnalysisResult(
            operations_a=ops_a,
            operations_b=ops_b,
            rule_conflicts=conflicts_tuple,
            merge_attempt=merge_attempt,
            summary=ThreeWayMergeSummary.build(
                rule_conflicts=conflicts_tuple,
                merge_attempt=merge_attempt,
            ),
            interference_pairs=tuple(interference_pairs),
        )
