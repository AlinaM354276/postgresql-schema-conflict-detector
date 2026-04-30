from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, Iterable, List, Set, Tuple

from src.conflict_detector.core.models import EdgeType, ObjectType, SchemaEdge, SchemaObject
from src.conflict_detector.graph.schema_graph import SchemaGraph


DependencyGraph = Dict[str, Set[str]]


def _add_dependency(
    dep: DependencyGraph,
    prerequisite: str,
    dependent: str,
) -> None:
    dep.setdefault(prerequisite, set()).add(dependent)
    dep.setdefault(dependent, set())


def _parse_columns(raw: object) -> Tuple[str, ...]:
    if raw is None:
        return tuple()

    return tuple(
        part.strip()
        for part in str(raw).split(",")
        if part.strip()
    )


def _column_id(schema: str, table: str, column: str) -> str:
    return f"{schema}.{table}.{column}"


def _is_expression_column(column: str) -> bool:
    return "(" in column or ")" in column or " " in column


def _add_edge_based_dependencies(dep: DependencyGraph, edge: SchemaEdge) -> None:
    dep.setdefault(edge.edge_id, set())
    dep.setdefault(edge.source_id, set())
    dep.setdefault(edge.target_id, set())

    # Ребро зависит от своих концов.
    _add_dependency(dep, edge.source_id, edge.edge_id)
    _add_dependency(dep, edge.target_id, edge.edge_id)

    if edge.edge_type == EdgeType.CONTAINS:
        # Column зависит от Table.
        _add_dependency(dep, edge.source_id, edge.target_id)

    elif edge.edge_type == EdgeType.TYPED_AS:
        # Column зависит от DataType.
        _add_dependency(dep, edge.target_id, edge.source_id)

    elif edge.edge_type == EdgeType.HAS_CONSTRAINT:
        # Constraint зависит от владельца Table/Column.
        _add_dependency(dep, edge.source_id, edge.target_id)

    elif edge.edge_type == EdgeType.HAS_INDEX:
        # Index зависит от Table.
        _add_dependency(dep, edge.source_id, edge.target_id)

    elif edge.edge_type == EdgeType.REFERENCES:
        # Source-column зависит от referenced target-column.
        _add_dependency(dep, edge.target_id, edge.source_id)


def _add_attribute_based_dependencies(dep: DependencyGraph, obj: SchemaObject) -> None:
    attrs = obj.attr_dict()
    schema = str(attrs.get("schema", "public"))
    table = attrs.get("table")

    if obj.object_type == ObjectType.INDEX:
        columns = _parse_columns(attrs.get("columns"))

        if table:
            for column in columns:
                if _is_expression_column(column):
                    continue

                col_id = _column_id(schema, str(table), column)
                _add_dependency(dep, col_id, obj.object_id)

    if obj.object_type == ObjectType.CONSTRAINT:
        columns = _parse_columns(attrs.get("columns"))

        if table:
            for column in columns:
                if _is_expression_column(column):
                    continue

                col_id = _column_id(schema, str(table), column)
                _add_dependency(dep, col_id, obj.object_id)


def build_dependency_graph(graph: SchemaGraph) -> DependencyGraph:
    dep: DependencyGraph = defaultdict(set)

    for vertex_id in graph.vertices:
        dep.setdefault(vertex_id, set())

    for edge_id in graph.edges:
        dep.setdefault(edge_id, set())

    for edge in graph.edges.values():
        _add_edge_based_dependencies(dep, edge)

    for obj in graph.vertices.values():
        _add_attribute_based_dependencies(dep, obj)

    return {key: set(value) for key, value in dep.items()}


def merge_dependency_graphs(*graphs: SchemaGraph) -> DependencyGraph:
    merged: DependencyGraph = defaultdict(set)

    for graph in graphs:
        dep = build_dependency_graph(graph)
        for key, values in dep.items():
            merged.setdefault(key, set()).update(values)

    return {key: set(value) for key, value in merged.items()}


def compute_transitive_closure(dep: DependencyGraph) -> DependencyGraph:
    closure: DependencyGraph = {node: set() for node in dep}

    for start in dep:
        visited: Set[str] = set()
        queue = deque(dep.get(start, set()))

        while queue:
            current = queue.popleft()

            if current in visited:
                continue

            visited.add(current)

            for nxt in dep.get(current, set()):
                if nxt not in visited:
                    queue.append(nxt)

        closure[start] = visited

    return closure


def find_dependency_path(
    dep: DependencyGraph,
    source: str,
    target: str,
) -> List[str]:
    if source == target:
        return [source]

    queue = deque([(source, [source])])
    visited = {source}

    while queue:
        current, path = queue.popleft()

        for nxt in dep.get(current, set()):
            if nxt in visited:
                continue

            next_path = [*path, nxt]

            if nxt == target:
                return next_path

            visited.add(nxt)
            queue.append((nxt, next_path))

    return []


def explain_dependency_intersection(
    dep: DependencyGraph,
    sources_a: Iterable[str],
    sources_b: Iterable[str],
    intersection: Iterable[str],
) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}

    for common in intersection:
        for src in sources_a:
            path = find_dependency_path(dep, src, common)
            if path:
                result[f"A:{src}->{common}"] = path

        for src in sources_b:
            path = find_dependency_path(dep, src, common)
            if path:
                result[f"B:{src}->{common}"] = path

    return result
