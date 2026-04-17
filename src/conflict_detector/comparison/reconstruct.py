from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Set

from src.conflict_detector.comparison.delta import DeltaDetails
from src.conflict_detector.comparison.matching import FullMatchingResult
from src.conflict_detector.core.models import (
    AddOperation,
    DropOperation,
    ModifyOperation,
    Operation,
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
    """
    Возвращает только изменившиеся атрибуты объекта.
    """
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
    """
    Возвращает только изменившиеся атрибуты ребра.
    """
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


def is_rename(left: SchemaObject, right: SchemaObject) -> bool:
    """
    Rename(x -> y) iff:
    - имя изменилось
    - все остальные атрибуты совпадают
    """
    return (
        left.name != right.name
        and left.attr_without_name() == right.attr_without_name()
    )


def is_modify(left: SchemaObject, right: SchemaObject) -> bool:
    """
    Modify(x -> y) iff:
    - различаются атрибуты без учёта name
    """
    return left.attr_without_name() != right.attr_without_name()


def is_edge_related_to_rename(
    edge: SchemaEdge,
    rename_left_to_right: Dict[str, str],
) -> bool:
    """
    True, если ребро связано с объектом, который участвует в rename-паре.
    Используется для подавления add/drop edge noise при Rename.
    """
    return (
        edge.source_id in rename_left_to_right
        or edge.target_id in rename_left_to_right
        or edge.source_id in rename_left_to_right.values()
        or edge.target_id in rename_left_to_right.values()
    )


def build_rename_map(
    left_graph: SchemaGraph,
    right_graph: SchemaGraph,
    delta_details: DeltaDetails,
) -> Dict[str, str]:
    """
    Возвращает mapping left_object_id -> right_object_id
    для всех объектов, распознанных как Rename.
    """
    rename_map: Dict[str, str] = {}

    for left_id, right_id in sorted(delta_details.modified_vertex_pairs):
        left_obj = left_graph.get_vertex(left_id)
        right_obj = right_graph.get_vertex(right_id)

        if left_obj is None or right_obj is None:
            continue

        if is_rename(left_obj, right_obj):
            rename_map[left_id] = right_id

    return rename_map


def build_add_operations(
    right_graph: SchemaGraph,
    delta_details: DeltaDetails,
    rename_left_to_right: Dict[str, str],
) -> List[Operation]:
    ops: List[Operation] = []

    for vertex_id in sorted(delta_details.delta.added_vertices):
        obj = right_graph.get_vertex(vertex_id)
        if obj is None:
            continue

        ops.append(
            AddOperation(
                target=obj.object_id,
                params=freeze_attrs(obj.attr_dict()),
            )
        )

    for edge_id in sorted(delta_details.delta.added_edges):
        edge = right_graph.get_edge(edge_id)
        if edge is None:
            continue
        if is_edge_related_to_rename(edge, rename_left_to_right):
            continue

        ops.append(
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

    return ops


def build_drop_operations(
    left_graph: SchemaGraph,
    delta_details: DeltaDetails,
    rename_left_to_right: Dict[str, str],
) -> List[Operation]:
    ops: List[Operation] = []

    # Сначала drop edges, потом drop vertices.
    for edge_id in sorted(delta_details.delta.removed_edges):
        edge = left_graph.get_edge(edge_id)
        if edge is None:
            continue

        if is_edge_related_to_rename(edge, rename_left_to_right):
            continue

        ops.append(DropOperation(target=edge.edge_id))

    for vertex_id in sorted(delta_details.delta.removed_vertices):
        obj = left_graph.get_vertex(vertex_id)
        if obj is None:
            continue

        ops.append(DropOperation(target=obj.object_id))

    return ops


def build_rename_modify_operations(
    left_graph: SchemaGraph,
    right_graph: SchemaGraph,
    delta_details: DeltaDetails,
) -> List[Operation]:
    ops: List[Operation] = []

    # 1. Vertex-level rename / modify
    for left_id, right_id in sorted(delta_details.modified_vertex_pairs):
        left_obj = left_graph.get_vertex(left_id)
        right_obj = right_graph.get_vertex(right_id)
        if left_obj is None or right_obj is None:
            continue

        if is_rename(left_obj, right_obj):
            ops.append(
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
                ops.append(
                    ModifyOperation(
                        target=left_obj.object_id,
                        delta=freeze_attrs(delta),
                    )
                )

    # 2. Edge-level modifications
    # Для MVP любое изменение атрибутов ребра трактуем как ModifyOperation(edge).
    for left_id, right_id in sorted(delta_details.modified_edge_pairs):
        left_edge = left_graph.get_edge(left_id)
        right_edge = right_graph.get_edge(right_id)
        if left_edge is None or right_edge is None:
            continue

        delta = edge_attr_delta(left_edge, right_edge)
        if delta:
            ops.append(
                ModifyOperation(
                    target=left_edge.edge_id,
                    delta=freeze_attrs(delta),
                )
            )

    return ops


def operation_targets(op: Operation) -> Set[str]:
    """
    Множество объектов, которые операция непосредственно затрагивает.
    """
    if isinstance(op, AddOperation):
        return {op.target}
    if isinstance(op, DropOperation):
        return {op.target}
    if isinstance(op, ModifyOperation):
        return {op.target}
    if isinstance(op, RenameOperation):
        return {op.target}
    return set()


def build_operation_dependency_graph(
    operations: List[Operation],
    graph: SchemaGraph,
) -> Dict[int, Set[int]]:
    """
    Узлы = индексы операций.
    Ребро i -> j означает: j зависит от i и должна выполняться после i.

    Базовые правила MVP:
    - Add(prerequisite) -> Add(dependent)
    - Add(target) -> Modify/Rename(target)
    - Drop(dependent) -> Drop(prerequisite)
    """
    dep_pairs = graph.dependency_pairs()

    prerequisite_by_dependent: Dict[str, Set[str]] = defaultdict(set)
    for dependent, prerequisite in dep_pairs:
        prerequisite_by_dependent[dependent].add(prerequisite)

    op_targets: List[Set[str]] = [operation_targets(op) for op in operations]
    adjacency: Dict[int, Set[int]] = defaultdict(set)

    for i, op_i in enumerate(operations):
        for j, op_j in enumerate(operations):
            if i == j:
                continue

            targets_i = op_targets[i]
            targets_j = op_targets[j]

            if not targets_i or not targets_j:
                continue

            # Rule 1: prerequisite add before dependent add/modify/rename
            if isinstance(op_i, AddOperation):
                for t_j in targets_j:
                    prereqs = prerequisite_by_dependent.get(t_j, set())
                    if targets_i & prereqs:
                        adjacency[i].add(j)

            # Rule 2: drop dependent before drop prerequisite
            if isinstance(op_i, DropOperation) and isinstance(op_j, DropOperation):
                for t_i in targets_i:
                    prereqs = prerequisite_by_dependent.get(t_i, set())
                    if targets_j & prereqs:
                        adjacency[i].add(j)

            # Rule 3: Add(target) before Modify/Rename(target)
            if isinstance(op_i, AddOperation) and isinstance(
                op_j, (ModifyOperation, RenameOperation)
            ):
                if targets_i & targets_j:
                    adjacency[i].add(j)

    return adjacency


def topological_sort_operations(
    operations: List[Operation],
    graph: SchemaGraph,
) -> List[Operation]:
    """
    Топологическая сортировка операций.
    Если обнаружен цикл, возвращается best-effort стабильный порядок.
    """
    adjacency = build_operation_dependency_graph(operations, graph)

    indegree: Dict[int, int] = {i: 0 for i in range(len(operations))}
    for src, targets in adjacency.items():
        for dst in targets:
            indegree[dst] += 1

    queue = deque(sorted(i for i, deg in indegree.items() if deg == 0))
    result_indices: List[int] = []

    while queue:
        node = queue.popleft()
        result_indices.append(node)

        for neighbor in sorted(adjacency.get(node, set())):
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    if len(result_indices) != len(operations):
        used = set(result_indices)
        remaining = [i for i in range(len(operations)) if i not in used]
        result_indices.extend(remaining)

    return [operations[i] for i in result_indices]


def reconstruct_operations(
    left_graph: SchemaGraph,
    right_graph: SchemaGraph,
    matching: FullMatchingResult,
    delta_details: DeltaDetails,
) -> ReconstructionResult:
    """
    Главная функция реконструкции.

    MVP-версия:
    1. Add / Drop
    2. Rename / Modify
    3. Topological sort

    matching пока не используется напрямую внутри reconstruction,
    но сохраняется в сигнатуре как часть стабильного pipeline:
    graph -> matching -> delta -> reconstruct
    """
    _ = matching  # сохраняем аргумент как часть контракта pipeline

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
        build_rename_modify_operations(left_graph, right_graph, delta_details)
    )

    # Для dependency sort используем right_graph как более целевой контекст.
    ordered = topological_sort_operations(operations, right_graph)

    return ReconstructionResult(operations=ordered)
