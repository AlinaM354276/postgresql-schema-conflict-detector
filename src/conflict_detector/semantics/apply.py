from __future__ import annotations

from copy import deepcopy
from typing import Dict, Iterable, Tuple

from src.conflict_detector.core.models import (
    AddOperation,
    DropOperation,
    EdgeType,
    ModifyOperation,
    ObjectType,
    Operation,
    RenameOperation,
    SchemaEdge,
    SchemaObject,
    freeze_attrs,
)
from src.conflict_detector.graph.schema_graph import SchemaGraph


def clone_graph(graph: SchemaGraph) -> SchemaGraph:
    """
    Глубокая копия графа схемы.
    """
    return deepcopy(graph)


def attrs_with_updated_name(obj: SchemaObject, new_name: str) -> Dict[str, object]:
    attrs = obj.attr_dict().copy()
    attrs["name"] = new_name
    return attrs


def attrs_with_delta(obj: SchemaObject, delta: Dict[str, object]) -> Dict[str, object]:
    attrs = obj.attr_dict().copy()
    attrs.update(delta)
    return attrs


def rebuild_object(
    original: SchemaObject,
    *,
    new_object_id: str | None = None,
    new_name: str | None = None,
    new_attrs: Dict[str, object] | None = None,
) -> SchemaObject:
    """
    Перестраивает объект того же класса с обновлёнными полями.
    """
    object_id = new_object_id if new_object_id is not None else original.object_id
    name = new_name if new_name is not None else original.name
    attrs = new_attrs if new_attrs is not None else original.attr_dict()

    return type(original)(
        object_id=object_id,
        object_type=original.object_type,
        name=name,
        attributes=freeze_attrs(attrs),
    )


def rebuild_edge(
    original: SchemaEdge,
    *,
    new_edge_id: str | None = None,
    new_source_id: str | None = None,
    new_target_id: str | None = None,
    new_attrs: Dict[str, object] | None = None,
) -> SchemaEdge:
    """
    Перестраивает ребро с обновлёнными полями.
    """
    edge_id = new_edge_id if new_edge_id is not None else original.edge_id
    source_id = new_source_id if new_source_id is not None else original.source_id
    target_id = new_target_id if new_target_id is not None else original.target_id
    attrs = new_attrs if new_attrs is not None else original.attr_dict()

    return SchemaEdge(
        edge_id=edge_id,
        edge_type=original.edge_type,
        source_id=source_id,
        target_id=target_id,
        attributes=freeze_attrs(attrs),
    )


def parse_object_type(value: str) -> ObjectType:
    """
    Преобразование строки в ObjectType.
    Поддерживает значения вида 'Table'/'COLUMN' и т.п.
    """
    for item in ObjectType:
        if item.value == value or item.name == value:
            return item
    raise ValueError(f"Unknown object type: {value}")


def parse_edge_type(value: str) -> EdgeType:
    for item in EdgeType:
        if item.value == value or item.name == value:
            return item
    raise ValueError(f"Unknown edge type: {value}")


def make_schema_object_from_add(op: AddOperation) -> SchemaObject:
    """
    Создаёт SchemaObject из AddOperation.
    Для вершин ожидает наличие:
    - object_type
    - name
    """
    params = dict(op.params)

    object_type_raw = params.pop("object_type", None)
    name = params.get("name")

    if object_type_raw is None:
        raise ValueError(f"AddOperation for object '{op.target}' misses object_type")
    if name is None:
        raise ValueError(f"AddOperation for object '{op.target}' misses name")

    object_type = parse_object_type(object_type_raw)

    return SchemaObject(
        object_id=op.target,
        object_type=object_type,
        name=name,
        attributes=freeze_attrs(params),
    )


def make_schema_edge_from_add(op: AddOperation) -> SchemaEdge:
    """
    Создаёт SchemaEdge из AddOperation.
    Для ребра ожидает:
    - edge_type
    - source_id
    - target_id
    """
    params = dict(op.params)

    edge_type_raw = params.pop("edge_type", None)
    source_id = params.pop("source_id", None)
    target_id = params.pop("target_id", None)

    if edge_type_raw is None or source_id is None or target_id is None:
        raise ValueError(f"AddOperation for edge '{op.target}' misses required params")

    edge_type = parse_edge_type(edge_type_raw)

    return SchemaEdge(
        edge_id=op.target,
        edge_type=edge_type,
        source_id=source_id,
        target_id=target_id,
        attributes=freeze_attrs(params),
    )


def is_edge_add_operation(op: AddOperation) -> bool:
    params = dict(op.params)
    return {"edge_type", "source_id", "target_id"}.issubset(set(params.keys()))


def apply_add_operation(graph: SchemaGraph, op: AddOperation) -> SchemaGraph:
    new_graph = clone_graph(graph)

    if is_edge_add_operation(op):
        edge = make_schema_edge_from_add(op)
        new_graph.add_edge(edge)
        return new_graph

    obj = make_schema_object_from_add(op)
    new_graph.add_vertex(obj)
    return new_graph


def remove_edge_from_indexes(graph: SchemaGraph, edge_id: str, edge: SchemaEdge) -> None:
    if edge.source_id in graph.outgoing:
        graph.outgoing[edge.source_id].discard(edge_id)
    if edge.target_id in graph.incoming:
        graph.incoming[edge.target_id].discard(edge_id)


def apply_drop_operation(graph: SchemaGraph, op: DropOperation) -> SchemaGraph:
    new_graph = clone_graph(graph)

    # Сначала пытаемся удалить ребро
    edge = new_graph.get_edge(op.target)
    if edge is not None:
        remove_edge_from_indexes(new_graph, op.target, edge)
        del new_graph.edges[op.target]
        return new_graph

    # Затем удаляем вершину и все инцидентные рёбра
    obj = new_graph.get_vertex(op.target)
    if obj is None:
        raise ValueError(f"Cannot drop unknown object or edge: {op.target}")

    incident_edge_ids = set(new_graph.outgoing.get(op.target, set())) | set(new_graph.incoming.get(op.target, set()))
    for edge_id in list(incident_edge_ids):
        current_edge = new_graph.get_edge(edge_id)
        if current_edge is None:
            continue
        remove_edge_from_indexes(new_graph, edge_id, current_edge)
        del new_graph.edges[edge_id]

    new_graph.outgoing.pop(op.target, None)
    new_graph.incoming.pop(op.target, None)
    del new_graph.vertices[op.target]

    return new_graph


def apply_modify_operation(graph: SchemaGraph, op: ModifyOperation) -> SchemaGraph:
    new_graph = clone_graph(graph)

    # Сначала пробуем как вершину
    obj = new_graph.get_vertex(op.target)
    if obj is not None:
        delta = dict(op.delta)
        updated_attrs = attrs_with_delta(obj, delta)
        updated_obj = rebuild_object(obj, new_attrs=updated_attrs)
        new_graph.vertices[op.target] = updated_obj
        return new_graph

    # Затем как ребро
    edge = new_graph.get_edge(op.target)
    if edge is not None:
        delta = dict(op.delta)
        updated_attrs = edge.attr_dict().copy()
        updated_attrs.update(delta)
        updated_edge = rebuild_edge(edge, new_attrs=updated_attrs)
        new_graph.edges[op.target] = updated_edge
        return new_graph

    raise ValueError(f"Cannot modify unknown object or edge: {op.target}")


def replace_edge_indexes_for_rename(
    graph: SchemaGraph,
    old_edge_id: str,
    new_edge: SchemaEdge,
) -> None:
    old_edge = graph.edges[old_edge_id]
    remove_edge_from_indexes(graph, old_edge_id, old_edge)

    del graph.edges[old_edge_id]
    graph.edges[new_edge.edge_id] = new_edge
    graph.outgoing[new_edge.source_id].add(new_edge.edge_id)
    graph.incoming[new_edge.target_id].add(new_edge.edge_id)


def rename_object_id(old_object_id: str, new_name: str) -> str:
    """
    Для MVP считаем, что object_id имеет вид qualified.name
    и rename заменяет только последний сегмент.
    """
    parts = old_object_id.split(".")
    if not parts:
        raise ValueError(f"Invalid object id: {old_object_id}")
    parts[-1] = new_name
    return ".".join(parts)


def rename_edge_id_for_vertex(edge: SchemaEdge, old_vertex_id: str, new_vertex_id: str) -> str:
    return edge.edge_id.replace(old_vertex_id, new_vertex_id)


def apply_rename_operation(graph: SchemaGraph, op: RenameOperation) -> SchemaGraph:
    new_graph = clone_graph(graph)

    obj = new_graph.get_vertex(op.target)
    if obj is None:
        raise ValueError(f"Cannot rename unknown object: {op.target}")

    new_object_id = rename_object_id(obj.object_id, op.new_name)
    new_attrs = attrs_with_updated_name(obj, op.new_name)
    renamed_obj = rebuild_object(
        obj,
        new_object_id=new_object_id,
        new_name=op.new_name,
        new_attrs=new_attrs,
    )

    # Собираем инцидентные рёбра
    incident_edge_ids = set(new_graph.outgoing.get(obj.object_id, set())) | set(new_graph.incoming.get(obj.object_id, set()))
    updated_edges: list[tuple[str, SchemaEdge]] = []

    for edge_id in incident_edge_ids:
        edge = new_graph.get_edge(edge_id)
        if edge is None:
            continue

        new_source_id = edge.source_id
        new_target_id = edge.target_id

        if edge.source_id == obj.object_id:
            new_source_id = new_object_id
        if edge.target_id == obj.object_id:
            new_target_id = new_object_id

        new_edge_id = rename_edge_id_for_vertex(edge, obj.object_id, new_object_id)
        updated_edge = rebuild_edge(
            edge,
            new_edge_id=new_edge_id,
            new_source_id=new_source_id,
            new_target_id=new_target_id,
        )
        updated_edges.append((edge_id, updated_edge))

    # Удаляем старую вершину
    del new_graph.vertices[obj.object_id]
    new_graph.outgoing.pop(obj.object_id, None)
    new_graph.incoming.pop(obj.object_id, None)

    # Добавляем новую
    new_graph.vertices[new_object_id] = renamed_obj
    new_graph.outgoing.setdefault(new_object_id, set())
    new_graph.incoming.setdefault(new_object_id, set())

    # Обновляем рёбра
    for old_edge_id, updated_edge in updated_edges:
        replace_edge_indexes_for_rename(new_graph, old_edge_id, updated_edge)

    return new_graph


def apply_operation(graph: SchemaGraph, op: Operation) -> SchemaGraph:
    if isinstance(op, AddOperation):
        return apply_add_operation(graph, op)
    if isinstance(op, DropOperation):
        return apply_drop_operation(graph, op)
    if isinstance(op, ModifyOperation):
        return apply_modify_operation(graph, op)
    if isinstance(op, RenameOperation):
        return apply_rename_operation(graph, op)

    raise NotImplementedError(f"Unsupported operation type: {type(op).__name__}")


def apply_operations(graph: SchemaGraph, operations: Iterable[Operation]) -> SchemaGraph:
    current = clone_graph(graph)
    for op in operations:
        current = apply_operation(current, op)
    return current
