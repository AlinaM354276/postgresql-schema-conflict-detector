from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from src.conflict_detector.core.models import ConstraintType, EdgeType, ObjectType
from src.conflict_detector.graph.schema_graph import SchemaGraph


@dataclass(frozen=True)
class InvariantViolation:
    invariant_id: str
    message: str
    object_ids: Tuple[str, ...]


@dataclass(frozen=True)
class InvariantCheckResult:
    violations: Tuple[InvariantViolation, ...]

    def is_valid(self) -> bool:
        return len(self.violations) == 0


def check_column_has_single_owner_table(graph: SchemaGraph) -> List[InvariantViolation]:
    violations: List[InvariantViolation] = []

    for column in graph.find_vertices_by_type(ObjectType.COLUMN):
        incoming_contains = [
            edge for edge in graph.edges_to(column.object_id)
            if edge.edge_type == EdgeType.CONTAINS
        ]

        if len(incoming_contains) != 1:
            violations.append(
                InvariantViolation(
                    invariant_id="INV_COLUMN_SINGLE_OWNER_TABLE",
                    message="Column must belong to exactly one table.",
                    object_ids=(column.object_id,),
                )
            )

    return violations


def check_column_has_single_datatype(graph: SchemaGraph) -> List[InvariantViolation]:
    violations: List[InvariantViolation] = []

    for column in graph.find_vertices_by_type(ObjectType.COLUMN):
        typed_as_edges = [
            edge for edge in graph.edges_from(column.object_id)
            if edge.edge_type == EdgeType.TYPED_AS
        ]

        if len(typed_as_edges) != 1:
            violations.append(
                InvariantViolation(
                    invariant_id="INV_COLUMN_SINGLE_DATATYPE",
                    message="Column must have exactly one data type.",
                    object_ids=(column.object_id,),
                )
            )

    return violations


def check_references_target_existing_column(graph: SchemaGraph) -> List[InvariantViolation]:
    violations: List[InvariantViolation] = []

    for edge in graph.find_edges_by_type(EdgeType.REFERENCES):
        source = graph.get_vertex(edge.source_id)
        target = graph.get_vertex(edge.target_id)

        if source is None or target is None:
            violations.append(
                InvariantViolation(
                    invariant_id="INV_REFERENCES_EXISTING_COLUMNS",
                    message="Reference must connect existing source and target columns.",
                    object_ids=(edge.edge_id,),
                )
            )
            continue

        if source.object_type != ObjectType.COLUMN or target.object_type != ObjectType.COLUMN:
            violations.append(
                InvariantViolation(
                    invariant_id="INV_REFERENCES_EXISTING_COLUMNS",
                    message="Reference must connect column to column.",
                    object_ids=(edge.edge_id, edge.source_id, edge.target_id),
                )
            )

    return violations


def check_single_primary_key_per_table(graph: SchemaGraph) -> List[InvariantViolation]:
    violations: List[InvariantViolation] = []

    for table in graph.find_vertices_by_type(ObjectType.TABLE):
        pk_constraints = []

        outgoing_constraints = [
            edge for edge in graph.edges_from(table.object_id)
            if edge.edge_type == EdgeType.HAS_CONSTRAINT
        ]

        for edge in outgoing_constraints:
            constraint = graph.get_vertex(edge.target_id)
            if constraint is None:
                continue

            attrs = constraint.attr_dict()
            if attrs.get("constraint_type") == ConstraintType.PRIMARY_KEY.value:
                pk_constraints.append(constraint.object_id)

        if len(pk_constraints) > 1:
            violations.append(
                InvariantViolation(
                    invariant_id="INV_SINGLE_PRIMARY_KEY_PER_TABLE",
                    message="Table must not have more than one primary key constraint.",
                    object_ids=tuple([table.object_id, *sorted(pk_constraints)]),
                )
            )

    return violations


def validate_schema_invariants(graph: SchemaGraph) -> InvariantCheckResult:
    violations: List[InvariantViolation] = []

    violations.extend(check_column_has_single_owner_table(graph))
    violations.extend(check_column_has_single_datatype(graph))
    violations.extend(check_references_target_existing_column(graph))
    violations.extend(check_single_primary_key_per_table(graph))

    return InvariantCheckResult(violations=tuple(violations))
