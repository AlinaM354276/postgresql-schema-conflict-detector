from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable, Tuple

from src.conflict_detector.core.models import EdgeType
from src.conflict_detector.graph.schema_graph import SchemaGraph


@dataclass(frozen=True)
class DependencyTrace:
    target: str
    path: Tuple[str, ...]


@dataclass(frozen=True)
class DependencyClosure:
    roots: Tuple[str, ...]
    affected_objects: Tuple[str, ...]
    traces: Tuple[DependencyTrace, ...]

    def as_set(self) -> set[str]:
        return set(self.affected_objects)


SEMANTIC_DEPENDENCY_EDGES = {
    EdgeType.CONTAINS,
    EdgeType.HAS_CONSTRAINT,
    EdgeType.HAS_INDEX,
    EdgeType.REFERENCES,
}


def is_dependency_edge(edge_type: EdgeType) -> bool:
    return edge_type in SEMANTIC_DEPENDENCY_EDGES


def dependency_neighbors(
    graph: SchemaGraph,
    object_id: str,
) -> tuple[str, ...]:
    neighbors: set[str] = set()

    for edge in graph.edges_from(object_id):
        if is_dependency_edge(edge.edge_type):
            neighbors.add(edge.target_id)

    for edge in graph.edges_to(object_id):
        if is_dependency_edge(edge.edge_type):
            neighbors.add(edge.source_id)

    return tuple(sorted(neighbors))


def compute_dependency_closure(
    graph: SchemaGraph,
    roots: Iterable[str],
    *,
    max_depth: int = 6,
) -> DependencyClosure:
    normalized_roots = tuple(sorted(set(roots)))

    visited: set[str] = set(normalized_roots)
    paths: dict[str, tuple[str, ...]] = {
        root: (root,)
        for root in normalized_roots
    }

    queue: deque[tuple[str, int]] = deque(
        (root, 0)
        for root in normalized_roots
    )

    while queue:
        current_id, depth = queue.popleft()

        if depth >= max_depth:
            continue

        for neighbor_id in dependency_neighbors(graph, current_id):
            if neighbor_id in visited:
                continue

            visited.add(neighbor_id)
            paths[neighbor_id] = (
                *paths[current_id],
                neighbor_id,
            )

            queue.append(
                (
                    neighbor_id,
                    depth + 1,
                )
            )

    return DependencyClosure(
        roots=normalized_roots,
        affected_objects=tuple(sorted(visited)),
        traces=tuple(
            DependencyTrace(
                target=target,
                path=path,
            )
            for target, path in sorted(paths.items())
        ),
    )