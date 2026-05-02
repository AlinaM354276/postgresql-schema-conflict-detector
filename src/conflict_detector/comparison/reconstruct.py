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
    """
    Rename определяется по изменению имени.

    Важно:
    раньше rename требовал полного совпадения остальных атрибутов.
    Из-за этого rename + modify превращался в Drop + Add.
    """
    return left.name != right.name


def is_modify(left: SchemaObject, right: SchemaObject) -> bool:
    """
    Modify определяется по изменению атрибутов, кроме имени.
    """
    left_attrs = left.attr_without_name()
    right_attrs = right.attr_without_name()
    return left_attrs != right_attrs


def is_table_id(object_id: str) -> bool:
    return len(object_id.split(".")) == 2


def is_child_of_renamed_table(
    object_id: str,
    rename_left_to_right: Dict[str, str],
) -> bool:
    """
    Если таблица public.users переименована в public.customers,
    то дочерние объекты public.users.id / public.customers.id
    не должны дополнительно реконструироваться как Drop/Add.
    """
    for old_table_id, new_table_id in rename_left_to_right.items():
        if not is_table_id(old_table_id) or not is_table_id(new_table_id):
            continue

        old_prefix = old_table_id + "."
        new_prefix = new_table_id + "."

        if object_id.startswith(old_prefix) or object_id.startswith(new_prefix):
            return True

    return False


def is_edge_inside_renamed_table(
    edge: SchemaEdge,
    rename_left_to_right: Dict[str, str],
) -> bool:
    return (
        is_child_of_renamed_table(edge.source_id, rename_left_to_right)
        or is_child_of_renamed_table(edge.target_id, rename_left_to_right)
    )


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


def is_structural_edge(edge: SchemaEdge) -> bool:
    """
    Structural edges являются внутренней частью графового представления.

    Их НЕ нужно реконструировать как самостоятельные semantic operations:
    - contains;
    - typedAs;
    - hasConstraint;
    - hasIndex.

    Они восстанавливаются в semantics/apply.py при Add(Column/Constraint/Index)
    и удаляются автоматически при Drop(vertex).
    """
    return edge.edge_type in {
        EdgeType.CONTAINS,
        EdgeType.TYPED_AS,
        EdgeType.HAS_CONSTRAINT,
        EdgeType.HAS_INDEX,
    }


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

        if is_child_of_renamed_table(obj.object_id, rename_left_to_right):
            continue

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

        if is_edge_inside_renamed_table(edge, rename_left_to_right):
            continue

        # Structural edges не являются самостоятельными semantic operations.
        if is_structural_edge(edge):
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

        if is_edge_inside_renamed_table(edge, rename_left_to_right):
            continue

        # Structural edges не должны становиться DropOperation.
        # Drop(Column/Table/Constraint/Index) сам удалит incident edges в apply.py.
        if is_structural_edge(edge):
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

        if is_child_of_renamed_table(obj.object_id, rename_left_to_right):
            continue

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

        if is_structural_edge(left_edge):
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
    """
    Dependency-aware порядок операций.

    Для Add:
    Table -> Column -> Constraint -> Index -> Reference.

    Для Drop:
    Reference -> Index/Constraint -> Column -> Table.

    Rename table выполняется раньше дочерних операций.
    """
    if isinstance(operation, RenameOperation):
        target_parts = operation.target.split(".")

        if len(target_parts) == 2:
            return 5

        return 55

    if isinstance(operation, AddOperation):
        params = dict(operation.params)

        if {"edge_type", "source_id", "target_id"}.issubset(params.keys()):
            return 25

        object_type = params.get("object_type")

        if object_type == ObjectType.TABLE.value:
            return 10

        if object_type == ObjectType.COLUMN.value:
            return 20

        if object_type == ObjectType.DATA_TYPE.value:
            return 22

        if object_type == ObjectType.CONSTRAINT.value:
            return 30

        if object_type == ObjectType.INDEX.value:
            return 40

        return 50

    if isinstance(operation, ReferenceOperation):
        if operation.change_type == ReferenceChangeType.DROP:
            return 8
        return 80

    if isinstance(operation, DropOperation):
        target = operation.target

        if ".idx_" in target or "index" in target:
            return 10

        if ".primary_key_" in target or ".fk_" in target or ".unique_" in target:
            return 20

        if len(target.split(".")) >= 3:
            return 30

        if len(target.split(".")) == 2:
            return 40

        return 50

    if isinstance(operation, ModifyOperation):
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
    """
    Упорядочивает реконструированные операции.

    Сохраняем простую и устойчивую сортировку, чтобы не ломать apply.py.
    """
    _ = graph

    def op_params(op: Operation) -> dict:
        return dict(getattr(op, "params", {}) or {})

    def op_target(op: Operation) -> str:
        return getattr(op, "target", "")

    def op_schema(op: Operation) -> str:
        return str(op_params(op).get("schema", "public"))

    def op_table(op: Operation) -> str:
        return str(op_params(op).get("table", ""))

    def stable_key(op: Operation) -> tuple:
        return (
            operation_priority(op),
            op_schema(op),
            op_table(op),
            op_target(op),
            type(op).__name__,
        )

    return sorted(operations, key=stable_key)


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
