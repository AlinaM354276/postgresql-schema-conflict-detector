from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from src.conflict_detector.core.models import (
    Conflict,
    Operation,
    SeverityLevel,
    freeze_attrs,
)
from src.conflict_detector.graph.schema_graph import SchemaGraph
from src.conflict_detector.semantics.apply import apply_operations
from src.conflict_detector.semantics.operation_compatibility import (
    rewrite_operations_after_prior_renames,
)
from src.conflict_detector.validation.invariants import InvariantCheckResult
from src.conflict_detector.validation.merge_validation import validate_merge_candidate


@dataclass(frozen=True)
class MergePathResult:
    order: str
    is_constructed: bool
    graph: Optional[SchemaGraph]
    invariant_result: InvariantCheckResult
    conflicts: Tuple[Conflict, ...]
    error_message: Optional[str] = None


@dataclass(frozen=True)
class MergeAttemptResult:
    is_defined: bool
    merged_graph: Optional[SchemaGraph]
    invariant_result: InvariantCheckResult
    conflicts: Tuple[Conflict, ...]
    error_message: Optional[str] = None
    path_ab: Optional[MergePathResult] = None
    path_ba: Optional[MergePathResult] = None
    is_commutative: Optional[bool] = None


def _empty_invariant_result() -> InvariantCheckResult:
    return InvariantCheckResult(violations=tuple())


def make_merge_undefined_conflict(message: str, *, order: str | None = None) -> Conflict:
    metadata = {"kind": "merge_undefined"}
    if order is not None:
        metadata["order"] = order

    return Conflict(
        rule_id="M1_MERGE_UNDEFINED",
        message=message,
        object_ids=tuple(),
        severity=SeverityLevel.CRITICAL,
        metadata=freeze_attrs(metadata),
    )


def make_non_commutative_conflict() -> Conflict:
    return Conflict(
        rule_id="M3_NON_COMMUTATIVE_OPERATIONS",
        message=(
            "Operation compositions ΔA∘ΔB and ΔB∘ΔA produce different "
            "schema graphs. This is treated as a potential semantic conflict "
            "indicator; final merge validity is decided by construction and "
            "invariant validation."
        ),
        object_ids=tuple(),
        severity=SeverityLevel.MEDIUM,
        metadata=freeze_attrs({"kind": "non_commutativity_indicator"}),
    )


def canonical_graph_signature(graph: SchemaGraph) -> tuple:
    vertices = tuple(
        sorted(
            (
                vertex.object_id,
                vertex.object_type.value,
                vertex.name,
                tuple(sorted(vertex.attr_dict().items())),
            )
            for vertex in graph.vertices.values()
        )
    )
    edges = tuple(
        sorted(
            (
                edge.edge_id,
                edge.edge_type.value,
                edge.source_id,
                edge.target_id,
                tuple(sorted(edge.attr_dict().items())),
            )
            for edge in graph.edges.values()
        )
    )
    return vertices, edges


def graphs_are_equivalent(left: SchemaGraph, right: SchemaGraph) -> bool:
    return canonical_graph_signature(left) == canonical_graph_signature(right)


def build_merge_path(
    base_graph: SchemaGraph,
    first_operations: Tuple[Operation, ...],
    second_operations: Tuple[Operation, ...],
    *,
    order: str,
) -> MergePathResult:
    try:
        after_first = apply_operations(base_graph, first_operations)
        normalized_second = rewrite_operations_after_prior_renames(
            operations=second_operations,
            prior_operations=first_operations,
        )
        merged = apply_operations(after_first, normalized_second)
    except Exception as exc:
        conflict = make_merge_undefined_conflict(
            f"Merge path {order} cannot be constructed: {exc}",
            order=order,
        )
        return MergePathResult(
            order=order,
            is_constructed=False,
            graph=None,
            invariant_result=_empty_invariant_result(),
            conflicts=(conflict,),
            error_message=str(exc),
        )

    validation_result = validate_merge_candidate(merged)
    if not validation_result.is_valid:
        return MergePathResult(
            order=order,
            is_constructed=True,
            graph=merged,
            invariant_result=validation_result.invariant_result,
            conflicts=validation_result.conflicts,
            error_message=f"Merge path {order} violates schema invariants.",
        )

    return MergePathResult(
        order=order,
        is_constructed=True,
        graph=merged,
        invariant_result=validation_result.invariant_result,
        conflicts=tuple(),
        error_message=None,
    )


def _choose_primary_valid_path(
    path_ab: MergePathResult,
    path_ba: MergePathResult,
) -> Optional[MergePathResult]:
    if path_ab.is_constructed and path_ab.invariant_result.is_valid():
        return path_ab
    if path_ba.is_constructed and path_ba.invariant_result.is_valid():
        return path_ba
    return None


def build_merge_candidate(
    base_graph: SchemaGraph,
    operations_a: Tuple[Operation, ...],
    operations_b: Tuple[Operation, ...],
) -> MergeAttemptResult:
    path_ab = build_merge_path(
        base_graph=base_graph,
        first_operations=operations_a,
        second_operations=operations_b,
        order="AB",
    )
    path_ba = build_merge_path(
        base_graph=base_graph,
        first_operations=operations_b,
        second_operations=operations_a,
        order="BA",
    )

    conflicts = list(path_ab.conflicts) + list(path_ba.conflicts)

    both_constructed = path_ab.is_constructed and path_ba.is_constructed
    both_valid = (
        path_ab.invariant_result.is_valid()
        and path_ba.invariant_result.is_valid()
    )

    is_commutative: Optional[bool] = None
    if path_ab.graph is not None and path_ba.graph is not None:
        is_commutative = graphs_are_equivalent(path_ab.graph, path_ba.graph)
        if not is_commutative:
            conflicts.append(make_non_commutative_conflict())

    diagnostic_graph = path_ab.graph or path_ba.graph

    if not both_constructed or not both_valid:
        invariant_result = (
            path_ab.invariant_result
            if path_ab.invariant_result.violations
            else path_ba.invariant_result
        )

        return MergeAttemptResult(
            is_defined=False,
            merged_graph=diagnostic_graph,
            invariant_result=invariant_result,
            conflicts=tuple(conflicts),
            error_message=(
                "Merge is undefined: at least one composition order "
                "cannot be constructed or violates schema invariants."
            ),
            path_ab=path_ab,
            path_ba=path_ba,
            is_commutative=is_commutative,
        )

    if is_commutative is False:
        return MergeAttemptResult(
            is_defined=False,
            merged_graph=diagnostic_graph,
            invariant_result=path_ab.invariant_result,
            conflicts=tuple(conflicts),
            error_message=(
                "Merge is undefined: operation compositions AB and BA "
                "produce non-equivalent schema graphs."
            ),
            path_ab=path_ab,
            path_ba=path_ba,
            is_commutative=is_commutative,
        )

    return MergeAttemptResult(
        is_defined=True,
        merged_graph=path_ab.graph,
        invariant_result=path_ab.invariant_result,
        conflicts=tuple(conflicts),
        error_message=None,
        path_ab=path_ab,
        path_ba=path_ba,
        is_commutative=is_commutative,
    )
