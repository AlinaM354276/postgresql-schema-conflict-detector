from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Iterable, List

from src.conflict_detector.core.models import Conflict
from src.conflict_detector.core.result import ThreeWayMergeAnalysisResult


def _freeze_to_dict(value: Any) -> Any:
    """
    Рекурсивно приводит dataclass / tuple / frozenset к JSON-friendly виду.
    """
    if is_dataclass(value):
        raw = asdict(value)
        return {k: _freeze_to_dict(v) for k, v in raw.items()}

    if isinstance(value, dict):
        return {str(k): _freeze_to_dict(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_freeze_to_dict(v) for v in value]

    if isinstance(value, frozenset):
        # metadata / attrs представлены как frozenset(tuple)
        if all(isinstance(item, tuple) and len(item) == 2 for item in value):
            return {str(k): _freeze_to_dict(v) for k, v in sorted(value)}
        return [_freeze_to_dict(v) for v in sorted(value)]

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


def build_report(result: ThreeWayMergeAnalysisResult) -> Dict[str, Any]:
    merge_attempt = result.merge_attempt

    return {
        "operations_a": serialize_operations(result.operations_a),
        "operations_b": serialize_operations(result.operations_b),
        "rule_conflicts": [serialize_conflict(c) for c in result.rule_conflicts],
        "merge_attempt": {
            "is_defined": merge_attempt.is_defined,
            "error_message": merge_attempt.error_message,
            "invariant_violations": [
                _freeze_to_dict(v) for v in merge_attempt.invariant_result.violations
            ],
            "merge_conflicts": [
                serialize_conflict(c) for c in merge_attempt.conflicts
            ],
            "merged_graph": (
                merge_attempt.merged_graph.to_debug_dict()
                if merge_attempt.merged_graph is not None
                else None
            ),
        },
        "summary": _freeze_to_dict(result.summary),
    }
