from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set

from src.conflict_detector.comparison.delta import DeltaDetails
from src.conflict_detector.comparison.matching import FullMatchingResult
from src.conflict_detector.core.models import (
    AddOperation,
    DropOperation,
    EdgeType,
    ModifyOperation,
    ObjectType,
    Operation,
    ReferenceChangeType,
    ReferenceOperation,
    RenameOperation,
    SchemaEdge,
    SchemaObject,
    freeze_attrs,
)
from src.conflict_detector.graph.schema_graph import SchemaGraph


@dataclass
class ReconstructionResult:
    operations: List[Operation]

    def __iter__(self):
        return iter(self.operations)

    def __len__(self) -> int:
        return len(self.operations)


def object_attr_delta(left: SchemaObject, right: SchemaObject) -> Dict[str, object]:
    left_attrs = left.attr_dict()
    right_attrs = right.attr_dict()

    changed: Dict[str, object] = {}
    all_keys = set(left_attrs.keys()) | set(right_attrs.keys())

    for key in all_keys:
        left_value = left_attrs.get(key)
        right_value = right_attrs.get(key)
        if left_value != right_value:
            changed[key] = right_value

    return changed


def edge_attr_delta(left: SchemaEdge, right: SchemaEdge) -> Dict[str, object]:
    left_attrs = left.attr_dict()
    right_attrs = right.attr_dict()

    changed: Dict[str, object] = {}
    all_keys = set(left_attrs.keys()) | set(right_attrs.keys())

    for key in all_keys:
        left_value = left_attrs.get(key)
        right_value = right_attrs.get(key)
        if left_value != right_value:
            changed[key] = right_value

    return changed


def is_builtin_data_type(obj: SchemaObject) -> bool:
    return (
        obj.object_type == ObjectType.DATA_TYPE
        and obj.attr_dict().get("builtin") is True
    )


def is_builtin_data_type_id(object_id: str, graph: SchemaGraph) -> bool:
    obj = graph.get_vertex(object_id)
    return obj is not None and is_builtin_data_type(obj)


def is_edge_connected_to_builtin_data_type(
    edge: SchemaEdge,
    graph: SchemaGraph,
) -> bool:
    return (
        is_builtin_data_type_id(edge.source_id, graph)
        or is_builtin_data_type_id(edge.target_id, graph)
    )


def is_rename(left: SchemaObject, right: SchemaObject) -> bool:
    return (
        left.name != right.name
        and left.attr_without_name() == right.attr_without_name()
    )


def is_modify(left: SchemaObject, right: SchemaObject) -> bool:
    return left.attr_without_name() != right.attr_without_name()


def is_edge_related_to_rename(
    edge: SchemaEdge,
    rename_left_to_right: Dict[str, str],
) -> bool:
    return (
        edge.source_id in rename_left_to_right
        or edge.target_id in rename_left_to_right
        or edge.source_id in rename_left_to_right.values()
        or edge.target_id in rename_left_to_right.values()
    )


def edge_to_reference_operation(
    edge: SchemaEdge,
    change_type: ReferenceChangeType,
) -> ReferenceOperation | None:
    if edge.edge_type != EdgeType.REFERENCES:
        return None

    return ReferenceOperation(
        source=edge.source_id,
        target=edge.target_id,
        change_type=change_type,
    )


def build_rename_map(
    left_graph: SchemaGraph,
    right_graph: SchemaGraph,
    delta_details: DeltaDetails,
) -> Dict[str, str]:
    rename_map: Dict[str, str] = {}

    for left_id, right_id in sorted(delta_details.modified_vertex_pairs):
        left_obj = left_graph.get_vertex(left_id)
        right_obj = right_graph.get_vertex(right_id)

        if left_obj is None or right_obj is None:
            continue

        if is_builtin_data_type(left_obj) or is_builtin_data_type(right_obj):
            continue

        if is_rename(left_obj, right_obj):
            rename_map[left_id] = right_id

    return rename_map


def build_add_operations(
    right_graph: SchemaGraph,
    delta_details: DeltaDetails,
    rename_left_to_right: Dict[str, str],
) -> List[Operation]:
    operations: List[Operation] = []

    for vertex_id in sorted(delta_details.delta.added_vertices):
        obj = right_graph.get_vertex(vertex_id)
        if obj is None:
            continue

        # Builtin PostgreSQL DataType — служебная вершина графа,
        # но не самостоятельная операция эволюции.
        if is_builtin_data_type(obj):
            continue

        operations.append(
            AddOperation(
                target=obj.object_id,
                params=freeze_attrs(
                    {
                        "object_type": obj.object_type.value,
                        **obj.attr_dict(),
                    }
                ),
            )
        )

    for edge_id in sorted(delta_details.delta.added_edges):
        edge = right_graph.get_edge(edge_id)
        if edge is None:
            continue

        if is_edge_related_to_rename(edge, rename_left_to_right):
            continue

        # typedAs к builtin DataType НЕ пропускаем:
        # при Add(Column) это ребро необходимо для валидного графа.
        # Сама вершина type.text создаётся служебно в apply.py.
        if (
            is_edge_connected_to_builtin_data_type(edge, right_graph)
            and edge.edge_type != EdgeType.TYPED_AS
        ):
            continue

        reference_op = edge_to_reference_operation(
            edge=edge,
            change_type=ReferenceChangeType.ADD,
        )
        if reference_op is not None:
            operations.append(reference_op)
            continue

        operations.append(
            AddOperation(
                target=edge.edge_id,
                params=freeze_attrs(
                    {
                        "edge_type": edge.edge_type.value,
                        "source_id": edge.source_id,
                        "target_id": edge.target_id,
                        **edge.attr_dict(),
                    }
                ),
            )
        )

    return operations


def build_drop_operations(
    left_graph: SchemaGraph,
    delta_details: DeltaDetails,
    rename_left_to_right: Dict[str, str],
) -> List[Operation]:
    operations: List[Operation] = []

    for edge_id in sorted(delta_details.delta.removed_edges):
        edge = left_graph.get_edge(edge_id)
        if edge is None:
            continue

        if is_edge_related_to_rename(edge, rename_left_to_right):
            continue

        # typedAs к builtin DataType НЕ пропускаем:
        # при Drop(Column) это ребро должно быть удалено как часть удаления колонки.
        if (
            is_edge_connected_to_builtin_data_type(edge, left_graph)
            and edge.edge_type != EdgeType.TYPED_AS
        ):
            continue

        reference_op = edge_to_reference_operation(
            edge=edge,
            change_type=ReferenceChangeType.DROP,
        )
        if reference_op is not None:
            operations.append(reference_op)
            continue

        operations.append(DropOperation(target=edge.edge_id))

    for vertex_id in sorted(delta_details.delta.removed_vertices):
        obj = left_graph.get_vertex(vertex_id)
        if obj is None:
            continue

        # Builtin PostgreSQL DataType не удаляется как объект схемы.
        if is_builtin_data_type(obj):
            continue

        operations.append(DropOperation(target=obj.object_id))

    return operations


def build_rename_modify_operations(
    left_graph: SchemaGraph,
    right_graph: SchemaGraph,
    delta_details: DeltaDetails,
) -> List[Operation]:
    operations: List[Operation] = []

    for left_id, right_id in sorted(delta_details.modified_vertex_pairs):
        left_obj = left_graph.get_vertex(left_id)
        right_obj = right_graph.get_vertex(right_id)

        if left_obj is None or right_obj is None:
            continue

        if is_builtin_data_type(left_obj) or is_builtin_data_type(right_obj):
            continue

        if is_rename(left_obj, right_obj):
            operations.append(
                RenameOperation(
                    target=left_obj.object_id,
                    new_name=right_obj.name,
                )
            )
            continue

        if is_modify(left_obj, right_obj):
            delta = object_attr_delta(left_obj, right_obj)
            delta.pop("name", None)

            if delta:
                operations.append(
                    ModifyOperation(
                        target=left_obj.object_id,
                        delta=freeze_attrs(delta),
                    )
                )

    for left_id, right_id in sorted(delta_details.modified_edge_pairs):
        left_edge = left_graph.get_edge(left_id)
        right_edge = right_graph.get_edge(right_id)

        if left_edge is None or right_edge is None:
            continue

        if (
            is_edge_connected_to_builtin_data_type(left_edge, left_graph)
            and left_edge.edge_type != EdgeType.TYPED_AS
        ):
            continue

        delta = edge_attr_delta(left_edge, right_edge)
        if delta:
            operations.append(
                ModifyOperation(
                    target=left_edge.edge_id,
                    delta=freeze_attrs(delta),
                )
            )

    return operations


def operation_priority(operation: Operation) -> int:
    if isinstance(operation, AddOperation):
        params = dict(operation.params)
        if {"edge_type", "source_id", "target_id"}.issubset(params.keys()):
            return 20
        return 10

    if isinstance(operation, ReferenceOperation):
        if operation.change_type == ReferenceChangeType.DROP:
            return 5
        return 30

    if isinstance(operation, ModifyOperation):
        return 40

    if isinstance(operation, RenameOperation):
        return 50

    if isinstance(operation, DropOperation):
        if "->" in operation.target or ":" in operation.target:
            return 60
        return 70

    return 100


def operation_targets(operation: Operation) -> Set[str]:
    if isinstance(operation, AddOperation):
        return {operation.target}
    if isinstance(operation, DropOperation):
        return {operation.target}
    if isinstance(operation, ModifyOperation):
        return {operation.target}
    if isinstance(operation, RenameOperation):
        return {operation.target}
    if isinstance(operation, ReferenceOperation):
        return {operation.source, operation.target}
    return set()


def topological_sort_operations(
    operations: List[Operation],
    graph: SchemaGraph,
) -> List[Operation]:
    _ = graph

    return sorted(
        operations,
        key=lambda op: (
            operation_priority(op),
            str(op),
        ),
    )


def reconstruct_operations(
    left_graph: SchemaGraph,
    right_graph: SchemaGraph,
    matching: FullMatchingResult,
    delta_details: DeltaDetails,
) -> ReconstructionResult:
    _ = matching

    operations: List[Operation] = []

    rename_left_to_right = build_rename_map(
        left_graph=left_graph,
        right_graph=right_graph,
        delta_details=delta_details,
    )

    operations.extend(
        build_add_operations(
            right_graph=right_graph,
            delta_details=delta_details,
            rename_left_to_right=rename_left_to_right,
        )
    )
    operations.extend(
        build_drop_operations(
            left_graph=left_graph,
            delta_details=delta_details,
            rename_left_to_right=rename_left_to_right,
        )
    )
    operations.extend(
        build_rename_modify_operations(
            left_graph=left_graph,
            right_graph=right_graph,
            delta_details=delta_details,
        )
    )

    ordered = topological_sort_operations(operations, right_graph)
    return ReconstructionResult(operations=ordered)
