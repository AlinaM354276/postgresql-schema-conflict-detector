from __future__ import annotations

from copy import deepcopy
from typing import Dict, Iterable, Optional, Tuple

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
from src.conflict_detector.graph.builders import (
    build_data_type,
    build_edge,
    canonical_data_type_name,
    make_column_id,
    make_data_type_id,
    make_table_id,
)
from src.conflict_detector.graph.schema_graph import SchemaGraph


def clone_graph(graph: SchemaGraph) -> SchemaGraph:
    return deepcopy(graph)


def attrs_with_updated_name(obj: SchemaObject, new_name: str) -> Dict[str, object]:
    attrs = obj.attr_dict().copy()
    attrs["name"] = new_name
    return attrs


def attrs_with_delta(obj: SchemaObject, delta: Dict[str, object]) -> Dict[str, object]:
    attrs = obj.attr_dict().copy()
    attrs.update(delta)
    return attrs


def is_builtin_data_type_object(obj: SchemaObject) -> bool:
    return (
        obj.object_type == ObjectType.DATA_TYPE
        and obj.attr_dict().get("builtin") is True
    )


def rebuild_object(
    original: SchemaObject,
    *,
    new_object_id: str | None = None,
    new_name: str | None = None,
    new_attrs: Dict[str, object] | None = None,
) -> SchemaObject:
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
    params = dict(op.params)

    object_type_raw = params.pop("object_type", None)
    name = params.get("name")

    if object_type_raw is None:
        raise ValueError(f"AddOperation for object '{op.target}' misses object_type")
    if name is None:
        raise ValueError(f"AddOperation for object '{op.target}' misses name")

    object_type = parse_object_type(str(object_type_raw))

    return SchemaObject(
        object_id=op.target,
        object_type=object_type,
        name=str(name),
        attributes=freeze_attrs(params),
    )


def make_schema_edge_from_add(op: AddOperation) -> SchemaEdge:
    params = dict(op.params)

    edge_type_raw = params.pop("edge_type", None)
    source_id = params.pop("source_id", None)
    target_id = params.pop("target_id", None)

    if edge_type_raw is None or source_id is None or target_id is None:
        raise ValueError(f"AddOperation for edge '{op.target}' misses required params")

    edge_type = parse_edge_type(str(edge_type_raw))

    return SchemaEdge(
        edge_id=op.target,
        edge_type=edge_type,
        source_id=str(source_id),
        target_id=str(target_id),
        attributes=freeze_attrs(params),
    )


def is_edge_add_operation(op: AddOperation) -> bool:
    params = dict(op.params)
    return {"edge_type", "source_id", "target_id"}.issubset(set(params.keys()))


def add_edge_if_absent(graph: SchemaGraph, edge: SchemaEdge) -> None:
    existing_edge = graph.get_edge(edge.edge_id)

    if existing_edge is not None:
        if existing_edge == edge:
            return

        raise ValueError(
            f"Cannot add duplicate edge with different payload: {edge.edge_id}"
        )

    graph.add_edge(edge)


def ensure_builtin_type_for_typed_as_edge(graph: SchemaGraph, edge: SchemaEdge) -> None:
    """
    Если добавляется typedAs-ребро Column -> builtin DataType,
    а вершины DataType ещё нет, создаём её служебно.

    Это не самостоятельная операция эволюции схемы.
    """
    if edge.edge_type != EdgeType.TYPED_AS:
        return

    if graph.get_vertex(edge.target_id) is not None:
        return

    if not edge.target_id.startswith("type."):
        return

    type_name = edge.target_id.removeprefix("type.")
    graph.add_vertex(build_data_type(type_name))


def ensure_data_type_vertex(graph: SchemaGraph, data_type: str) -> str:
    canonical_type = canonical_data_type_name(data_type)
    dtype_id = make_data_type_id(canonical_type)

    if graph.get_vertex(dtype_id) is None:
        graph.add_vertex(build_data_type(canonical_type))

    return dtype_id


def ensure_column_structural_edges(graph: SchemaGraph, obj: SchemaObject) -> None:
    """
    Add(Column) должен добавлять не только вершину Column,
    но и обязательные рёбра:

    Table --contains--> Column
    Column --typedAs--> DataType

    Иначе при merge validation появляются нарушения:
    - INV_COLUMN_SINGLE_OWNER_TABLE;
    - INV_COLUMN_SINGLE_DATATYPE.
    """
    if obj.object_type != ObjectType.COLUMN:
        return

    attrs = obj.attr_dict()

    schema_name = str(attrs.get("schema", "public"))
    table_name = attrs.get("table")
    data_type = attrs.get("data_type") or attrs.get("data_type_raw")

    if table_name is None:
        raise ValueError(f"Column '{obj.object_id}' misses table attribute")

    table_id = make_table_id(
        table_name=str(table_name),
        schema_name=schema_name,
    )

    if graph.get_vertex(table_id) is None:
        raise ValueError(
            f"Cannot add column '{obj.object_id}': "
            f"missing owner table '{table_id}'"
        )

    contains_edge = build_edge(
        edge_type=EdgeType.CONTAINS,
        source_id=table_id,
        target_id=obj.object_id,
    )
    add_edge_if_absent(graph, contains_edge)

    if data_type is None:
        return

    canonical_type = canonical_data_type_name(str(data_type))
    dtype_id = ensure_data_type_vertex(graph, canonical_type)

    typed_as_edge = build_edge(
        edge_type=EdgeType.TYPED_AS,
        source_id=obj.object_id,
        target_id=dtype_id,
    )
    add_edge_if_absent(graph, typed_as_edge)


def parse_columns(raw: object) -> Tuple[str, ...]:
    if raw is None:
        return tuple()

    return tuple(
        part.strip()
        for part in str(raw).split(",")
        if part.strip()
    )


def infer_constraint_owner_id(obj: SchemaObject) -> str:
    """
    В graph builder constraint может принадлежать:
    - таблице;
    - колонке, если constraint относится к одной колонке.

    Для inline UNIQUE / NOT NULL / single-column PK обычно owner = column.
    Для composite constraints owner = table.
    """
    attrs = obj.attr_dict()

    schema_name = str(attrs.get("schema", "public"))
    table_name = attrs.get("table")

    if table_name is None:
        raise ValueError(f"Constraint '{obj.object_id}' misses table attribute")

    columns = parse_columns(attrs.get("columns"))

    if len(columns) == 1:
        return make_column_id(
            table_name=str(table_name),
            column_name=columns[0],
            schema_name=schema_name,
        )

    return make_table_id(
        table_name=str(table_name),
        schema_name=schema_name,
    )


def ensure_constraint_structural_edges(graph: SchemaGraph, obj: SchemaObject) -> None:
    """
    Add(Constraint) должен восстанавливать hasConstraint-ребро,
    если оно не было добавлено отдельной операцией.
    """
    if obj.object_type != ObjectType.CONSTRAINT:
        return

    owner_id = infer_constraint_owner_id(obj)

    if graph.get_vertex(owner_id) is None:
        raise ValueError(
            f"Cannot add constraint '{obj.object_id}': "
            f"missing owner '{owner_id}'"
        )

    edge = build_edge(
        edge_type=EdgeType.HAS_CONSTRAINT,
        source_id=owner_id,
        target_id=obj.object_id,
    )
    add_edge_if_absent(graph, edge)


def ensure_index_structural_edges(graph: SchemaGraph, obj: SchemaObject) -> None:
    """
    Add(Index) должен восстанавливать hasIndex-ребро,
    если оно не было добавлено отдельной операцией.
    """
    if obj.object_type != ObjectType.INDEX:
        return

    attrs = obj.attr_dict()

    schema_name = str(attrs.get("schema", "public"))
    table_name = attrs.get("table")

    if table_name is None:
        raise ValueError(f"Index '{obj.object_id}' misses table attribute")

    table_id = make_table_id(
        table_name=str(table_name),
        schema_name=schema_name,
    )

    if graph.get_vertex(table_id) is None:
        raise ValueError(
            f"Cannot add index '{obj.object_id}': missing table '{table_id}'"
        )

    edge = build_edge(
        edge_type=EdgeType.HAS_INDEX,
        source_id=table_id,
        target_id=obj.object_id,
    )
    add_edge_if_absent(graph, edge)


def ensure_object_structural_edges(graph: SchemaGraph, obj: SchemaObject) -> None:
    ensure_column_structural_edges(graph, obj)
    ensure_constraint_structural_edges(graph, obj)
    ensure_index_structural_edges(graph, obj)


def apply_add_operation(graph: SchemaGraph, op: AddOperation) -> SchemaGraph:
    new_graph = clone_graph(graph)

    if is_edge_add_operation(op):
        edge = make_schema_edge_from_add(op)

        ensure_builtin_type_for_typed_as_edge(new_graph, edge)
        add_edge_if_absent(new_graph, edge)

        return new_graph

    obj = make_schema_object_from_add(op)

    existing_obj = new_graph.get_vertex(obj.object_id)

    if existing_obj is not None:
        if existing_obj != obj:
            raise ValueError(
                f"Cannot add duplicate object with different payload: "
                f"{obj.object_id}"
            )

        # Даже если вершина уже есть, structural edges могли отсутствовать.
        ensure_object_structural_edges(new_graph, existing_obj)
        return new_graph

    new_graph.add_vertex(obj)

    # Важное исправление:
    # Add(Column), Add(Constraint), Add(Index) должны восстанавливать
    # обязательные структурные рёбра графа, иначе merge validation
    # видит некорректную схему.
    ensure_object_structural_edges(new_graph, obj)

    return new_graph


def remove_edge_from_indexes(graph: SchemaGraph, edge_id: str, edge: SchemaEdge) -> None:
    if edge.source_id in graph.outgoing:
        graph.outgoing[edge.source_id].discard(edge_id)
    if edge.target_id in graph.incoming:
        graph.incoming[edge.target_id].discard(edge_id)


def remove_edge(graph: SchemaGraph, edge_id: str) -> None:
    edge = graph.get_edge(edge_id)
    if edge is None:
        return

    remove_edge_from_indexes(graph, edge_id, edge)
    del graph.edges[edge_id]


def apply_drop_operation(graph: SchemaGraph, op: DropOperation) -> SchemaGraph:
    new_graph = clone_graph(graph)

    edge = new_graph.get_edge(op.target)
    if edge is not None:
        remove_edge(new_graph, op.target)
        return new_graph

    obj = new_graph.get_vertex(op.target)
    if obj is None:
        return new_graph

    if is_builtin_data_type_object(obj):
        return new_graph

    incident_edge_ids = (
        set(new_graph.outgoing.get(op.target, set()))
        | set(new_graph.incoming.get(op.target, set()))
    )

    for edge_id in list(incident_edge_ids):
        remove_edge(new_graph, edge_id)

    new_graph.outgoing.pop(op.target, None)
    new_graph.incoming.pop(op.target, None)
    del new_graph.vertices[op.target]

    return new_graph


def update_column_typed_as_edge(
    graph: SchemaGraph,
    column_id: str,
    new_data_type: str,
) -> None:
    canonical_type = canonical_data_type_name(new_data_type)
    dtype_id = ensure_data_type_vertex(graph, canonical_type)

    outgoing_typed_as = [
        edge.edge_id
        for edge in graph.edges_from(column_id)
        if edge.edge_type == EdgeType.TYPED_AS
    ]

    for edge_id in outgoing_typed_as:
        remove_edge(graph, edge_id)

    new_edge = build_edge(
        edge_type=EdgeType.TYPED_AS,
        source_id=column_id,
        target_id=dtype_id,
    )
    graph.add_edge(new_edge)


def apply_modify_operation(graph: SchemaGraph, op: ModifyOperation) -> SchemaGraph:
    new_graph = clone_graph(graph)

    obj = new_graph.get_vertex(op.target)
    if obj is not None:
        delta = dict(op.delta)

        if is_builtin_data_type_object(obj):
            return new_graph

        if obj.object_type == ObjectType.COLUMN:
            if "data_type_raw" in delta and "data_type" not in delta:
                raw_type = str(delta["data_type_raw"])
                delta["data_type"] = canonical_data_type_name(raw_type)

            if "data_type" in delta:
                raw_type = str(delta.get("data_type_raw", delta["data_type"]))
                delta["data_type"] = canonical_data_type_name(raw_type)
                delta["data_type_raw"] = raw_type

        updated_attrs = attrs_with_delta(obj, delta)
        updated_obj = rebuild_object(obj, new_attrs=updated_attrs)
        new_graph.vertices[op.target] = updated_obj

        if obj.object_type == ObjectType.COLUMN and "data_type" in delta:
            update_column_typed_as_edge(
                graph=new_graph,
                column_id=op.target,
                new_data_type=str(delta["data_type"]),
            )

        return new_graph

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
    parts = old_object_id.split(".")
    if not parts:
        raise ValueError(f"Invalid object id: {old_object_id}")

    parts[-1] = new_name
    return ".".join(parts)


def rename_edge_id_for_vertex(
    edge: SchemaEdge,
    old_vertex_id: str,
    new_vertex_id: str,
) -> str:
    return edge.edge_id.replace(old_vertex_id, new_vertex_id)


def apply_rename_operation(graph: SchemaGraph, op: RenameOperation) -> SchemaGraph:
    new_graph = clone_graph(graph)

    obj = new_graph.get_vertex(op.target)

    if obj is None:
        new_object_id = rename_object_id(op.target, op.new_name)
        already_renamed = new_graph.get_vertex(new_object_id)

        if already_renamed is not None:
            return new_graph

        raise ValueError(f"Cannot rename unknown object: {op.target}")

    if is_builtin_data_type_object(obj):
        return new_graph

    new_object_id = rename_object_id(obj.object_id, op.new_name)

    if new_object_id != obj.object_id and new_graph.get_vertex(new_object_id) is not None:
        existing = new_graph.get_vertex(new_object_id)
        if existing is not None and existing.name == op.new_name:
            return new_graph
        raise ValueError(
            f"Cannot rename '{obj.object_id}' to existing object '{new_object_id}'"
        )

    new_attrs = attrs_with_updated_name(obj, op.new_name)
    renamed_obj = rebuild_object(
        obj,
        new_object_id=new_object_id,
        new_name=op.new_name,
        new_attrs=new_attrs,
    )

    incident_edge_ids = (
        set(new_graph.outgoing.get(obj.object_id, set()))
        | set(new_graph.incoming.get(obj.object_id, set()))
    )
    updated_edges: list[tuple[str, SchemaEdge]] = []

    for edge_id in incident_edge_ids:
        edge = new_graph.get_edge(edge_id)
        if edge is None:
            continue

        new_source_id = new_object_id if edge.source_id == obj.object_id else edge.source_id
        new_target_id = new_object_id if edge.target_id == obj.object_id else edge.target_id
        new_edge_id = rename_edge_id_for_vertex(
            edge=edge,
            old_vertex_id=obj.object_id,
            new_vertex_id=new_object_id,
        )

        updated_edge = rebuild_edge(
            edge,
            new_edge_id=new_edge_id,
            new_source_id=new_source_id,
            new_target_id=new_target_id,
        )
        updated_edges.append((edge_id, updated_edge))

    del new_graph.vertices[obj.object_id]
    new_graph.outgoing.pop(obj.object_id, None)
    new_graph.incoming.pop(obj.object_id, None)

    new_graph.vertices[new_object_id] = renamed_obj
    new_graph.outgoing.setdefault(new_object_id, set())
    new_graph.incoming.setdefault(new_object_id, set())

    for old_edge_id, updated_edge in updated_edges:
        replace_edge_indexes_for_rename(new_graph, old_edge_id, updated_edge)

    return new_graph


def make_reference_edge_id(source_id: str, target_id: str) -> str:
    return f"{EdgeType.REFERENCES.value}:{source_id}->{target_id}"


def apply_reference_operation(graph: SchemaGraph, op: ReferenceOperation) -> SchemaGraph:
    new_graph = clone_graph(graph)
    edge_id = make_reference_edge_id(op.source, op.target)

    if op.change_type == ReferenceChangeType.ADD:
        existing = new_graph.get_edge(edge_id)
        if existing is not None:
            return new_graph

        edge = SchemaEdge(
            edge_id=edge_id,
            edge_type=EdgeType.REFERENCES,
            source_id=op.source,
            target_id=op.target,
            attributes=freeze_attrs({}),
        )
        new_graph.add_edge(edge)
        return new_graph

    if op.change_type == ReferenceChangeType.DROP:
        remove_edge(new_graph, edge_id)
        return new_graph

    if op.change_type == ReferenceChangeType.RETARGET:
        raise NotImplementedError("Reference retarget is not implemented yet.")

    raise ValueError(f"Unknown reference change type: {op.change_type}")


def apply_operation(graph: SchemaGraph, op: Operation) -> SchemaGraph:
    if isinstance(op, AddOperation):
        return apply_add_operation(graph, op)
    if isinstance(op, DropOperation):
        return apply_drop_operation(graph, op)
    if isinstance(op, ModifyOperation):
        return apply_modify_operation(graph, op)
    if isinstance(op, RenameOperation):
        return apply_rename_operation(graph, op)
    if isinstance(op, ReferenceOperation):
        return apply_reference_operation(graph, op)

    raise NotImplementedError(f"Unsupported operation type: {type(op).__name__}")


def apply_operations(graph: SchemaGraph, operations: Iterable[Operation]) -> SchemaGraph:
    current = clone_graph(graph)

    for op in operations:
        current = apply_operation(current, op)

    return current
