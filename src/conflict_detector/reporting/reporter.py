from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from src.conflict_detector.core.models import Conflict
from src.conflict_detector.core.result import ThreeWayMergeAnalysisResult
from src.conflict_detector.detection.detector import InterferencePair
from src.conflict_detector.reporting.severity import (
    DEFAULT_IMPACT_THRESHOLD,
    evaluate_conflicts,
)


def _freeze_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        raw = asdict(value)
        return {k: _freeze_to_dict(v) for k, v in raw.items()}

    if isinstance(value, dict):
        return {str(k): _freeze_to_dict(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_freeze_to_dict(v) for v in value]

    if isinstance(value, frozenset):
        if all(isinstance(item, tuple) and len(item) == 2 for item in value):
            return {str(k): _freeze_to_dict(v) for k, v in sorted(value)}
        return [_freeze_to_dict(v) for v in sorted(value)]

    if hasattr(value, "value"):
        return value.value

    return value


def serialize_conflict(conflict: Conflict) -> Dict[str, Any]:
    return {
        "rule_id": conflict.rule_id,
        "message": conflict.message,
        "object_ids": list(conflict.object_ids),
        "severity": conflict.severity.value,
        "operation_a": _freeze_to_dict(conflict.operation_a),
        "operation_b": _freeze_to_dict(conflict.operation_b),
        "metadata": _freeze_to_dict(conflict.metadata),
    }


def serialize_operations(operations: Iterable[Any]) -> List[Dict[str, Any]]:
    return [_freeze_to_dict(op) for op in operations]


def serialize_interference_pair(pair: InterferencePair) -> Dict[str, Any]:
    return {
        "operation_a": _freeze_to_dict(pair.operation_a),
        "operation_b": _freeze_to_dict(pair.operation_b),
        "shared_impact": list(pair.shared_impact),
    }


def _serialize_merge_path(path: Any) -> Dict[str, Any] | None:
    if path is None:
        return None

    return {
        "order": path.order,
        "is_constructed": path.is_constructed,
        "error_message": path.error_message,
        "invariant_violations": [
            _freeze_to_dict(v)
            for v in path.invariant_result.violations
        ],
        "conflicts": [serialize_conflict(c) for c in path.conflicts],
        "graph": path.graph.to_debug_dict() if path.graph is not None else None,
    }


def _group_conflicts_by_rule(
    conflicts: Iterable[Conflict],
) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for conflict in conflicts:
        grouped.setdefault(conflict.rule_id, []).append(serialize_conflict(conflict))

    return grouped


def _group_conflicts_by_severity(
    conflicts: Iterable[Conflict],
) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for conflict in conflicts:
        grouped.setdefault(conflict.severity.value, []).append(
            serialize_conflict(conflict)
        )

    return grouped


def _severity_distribution(conflicts: Iterable[Conflict]) -> Dict[str, int]:
    result = {
        "LOW": 0,
        "MEDIUM": 0,
        "HIGH": 0,
        "CRITICAL": 0,
    }

    for conflict in conflicts:
        result[conflict.severity.value] = result.get(conflict.severity.value, 0) + 1

    return result


def _build_summary(
    result: ThreeWayMergeAnalysisResult,
    all_conflicts: tuple[Conflict, ...],
) -> Dict[str, Any]:
    critical_count = sum(
        1
        for conflict in all_conflicts
        if conflict.severity.value == "CRITICAL"
    )

    high_count = sum(
        1
        for conflict in all_conflicts
        if conflict.severity.value == "HIGH"
    )

    medium_count = sum(
        1
        for conflict in all_conflicts
        if conflict.severity.value == "MEDIUM"
    )

    low_count = sum(
        1
        for conflict in all_conflicts
        if conflict.severity.value == "LOW"
    )

    return {
        "total_rule_conflicts": len(result.rule_conflicts),
        "total_merge_conflicts": len(result.merge_attempt.conflicts),
        "total_conflicts": len(all_conflicts),
        "critical_conflicts": critical_count,
        "high_conflicts": high_count,
        "medium_conflicts": medium_count,
        "low_conflicts": low_count,
        "merge_defined": result.merge_attempt.is_defined,
        "merge_blocked": (
            not result.merge_attempt.is_defined
            or critical_count > 0
        ),
        "is_commutative": result.merge_attempt.is_commutative,
        "invariant_violations_count": (
            len(result.merge_attempt.invariant_result.violations)
            if result.merge_attempt.invariant_result is not None
            else 0
        ),
        "has_any_conflicts": len(all_conflicts) > 0,
        "has_critical": critical_count > 0,
    }


def _build_metadata(
    *,
    repo_path: str | None = None,
    branch_a: str | None = None,
    branch_b: str | None = None,
    execution_time_seconds: float | None = None,
    impact_threshold: int = DEFAULT_IMPACT_THRESHOLD,
) -> Dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repo": repo_path,
        "branch_a": branch_a,
        "branch_b": branch_b,
        "execution_time_seconds": execution_time_seconds,
        "impact_threshold": impact_threshold,
    }


def build_report(
    result: ThreeWayMergeAnalysisResult,
    *,
    repo_path: str | None = None,
    branch_a: str | None = None,
    branch_b: str | None = None,
    execution_time_seconds: float | None = None,
    impact_threshold: int = DEFAULT_IMPACT_THRESHOLD,
) -> Dict[str, Any]:
    merge_attempt = result.merge_attempt

    evaluated_rule_conflicts = evaluate_conflicts(
        result.rule_conflicts,
        impact_threshold=impact_threshold,
    )

    evaluated_merge_conflicts = evaluate_conflicts(
        merge_attempt.conflicts,
        impact_threshold=impact_threshold,
    )

    all_conflicts = tuple(evaluated_rule_conflicts) + tuple(evaluated_merge_conflicts)

    return {
        "metadata": _build_metadata(
            repo_path=repo_path,
            branch_a=branch_a,
            branch_b=branch_b,
            execution_time_seconds=execution_time_seconds,
            impact_threshold=impact_threshold,
        ),
        "operations_a": serialize_operations(result.operations_a),
        "operations_b": serialize_operations(result.operations_b),
        "rule_conflicts": [
            serialize_conflict(c)
            for c in evaluated_rule_conflicts
        ],
        "interference": {
            "total_pairs": len(result.interference_pairs),
            "pairs": [
                serialize_interference_pair(pair)
                for pair in result.interference_pairs
            ],
        },
        "merge_attempt": {
            "is_defined": merge_attempt.is_defined,
            "error_message": merge_attempt.error_message,
            "is_commutative": merge_attempt.is_commutative,
            "invariant_violations": [
                _freeze_to_dict(v)
                for v in merge_attempt.invariant_result.violations
            ],
            "merge_conflicts": [
                serialize_conflict(c)
                for c in evaluated_merge_conflicts
            ],
            "paths": {
                "AB": _serialize_merge_path(merge_attempt.path_ab),
                "BA": _serialize_merge_path(merge_attempt.path_ba),
            },
            "merged_graph": (
                merge_attempt.merged_graph.to_debug_dict()
                if merge_attempt.merged_graph is not None
                else None
            ),
        },
        "conflicts_grouped": {
            "by_rule": _group_conflicts_by_rule(all_conflicts),
            "by_severity": _group_conflicts_by_severity(all_conflicts),
        },
        "severity_distribution": _severity_distribution(all_conflicts),
        "summary": _build_summary(result, all_conflicts),
    }
