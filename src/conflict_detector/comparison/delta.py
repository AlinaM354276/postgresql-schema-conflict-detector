from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Set, Tuple

from src.conflict_detector.comparison.matching import FullMatchingResult
from src.conflict_detector.core.models import Delta
from src.conflict_detector.graph.schema_graph import SchemaGraph


@dataclass(frozen=True)
class DeltaDetails:
    """
    Расширенная форма дельты:
    кроме Delta хранит сами пары изменённых объектов для последующей классификации.
    """
    delta: Delta
    modified_vertex_pairs: FrozenSet[Tuple[str, str]]
    modified_edge_pairs: FrozenSet[Tuple[str, str]]

    def is_empty(self) -> bool:
        return self.delta.is_empty()


def attributes_changed(left_attrs: Dict[str, object], right_attrs: Dict[str, object]) -> bool:
    return left_attrs != right_attrs


def compute_vertex_delta(
    left_graph: SchemaGraph,
    right_graph: SchemaGraph,
    matching: FullMatchingResult,
) -> Tuple[Set[str], Set[str], Set[Tuple[str, str]]]:
    """
    Возвращает:
    - removed vertices
    - added vertices
    - modified matched vertex pairs
    """
    removed_vertices: Set[str] = set()
    added_vertices: Set[str] = set()
    modified_vertex_pairs: Set[Tuple[str, str]] = set()

    for left_id, left_obj in left_graph.vertices.items():
        right_id = matching.vertex_matching.get_right(left_id)
        if right_id is None:
            removed_vertices.add(left_id)
            continue

        right_obj = right_graph.get_vertex(right_id)
        if right_obj is None:
            removed_vertices.add(left_id)
            continue

        if attributes_changed(left_obj.attr_dict(), right_obj.attr_dict()):
            modified_vertex_pairs.add((left_id, right_id))

    for right_id in right_graph.vertices.keys():
        if not matching.vertex_matching.is_matched_right(right_id):
            added_vertices.add(right_id)

    return removed_vertices, added_vertices, modified_vertex_pairs


def compute_edge_delta(
    left_graph: SchemaGraph,
    right_graph: SchemaGraph,
    matching: FullMatchingResult,
) -> Tuple[Set[str], Set[str], Set[Tuple[str, str]]]:
    """
    Возвращает:
    - removed edges
    - added edges
    - modified matched edge pairs

    Для MVP изменение edge attributes считаем edge modification.
    """
    removed_edges: Set[str] = set()
    added_edges: Set[str] = set()
    modified_edge_pairs: Set[Tuple[str, str]] = set()

    for left_id, left_edge in left_graph.edges.items():
        right_id = matching.edge_matching.get_right(left_id)
        if right_id is None:
            removed_edges.add(left_id)
            continue

        right_edge = right_graph.get_edge(right_id)
        if right_edge is None:
            removed_edges.add(left_id)
            continue

        if attributes_changed(left_edge.attr_dict(), right_edge.attr_dict()):
            modified_edge_pairs.add((left_id, right_id))

    for right_id in right_graph.edges.keys():
        if not matching.edge_matching.is_matched_right(right_id):
            added_edges.add(right_id)

    return removed_edges, added_edges, modified_edge_pairs


def compute_modified_attributes_pairs(
    modified_vertex_pairs: Set[Tuple[str, str]],
    modified_edge_pairs: Set[Tuple[str, str]],
) -> FrozenSet[Tuple[str, str]]:
    """
    Δλ — изменения атрибутов сопоставленных элементов.
    """
    all_pairs = set(modified_vertex_pairs)
    all_pairs.update(modified_edge_pairs)
    return frozenset(sorted(all_pairs))


def compute_delta(
    left_graph: SchemaGraph,
    right_graph: SchemaGraph,
    matching: FullMatchingResult,
) -> DeltaDetails:
    """
    Строит структурированную дельту:

    Diff(G_i, G_j) = (ΔV-, ΔV+, ΔE-, ΔE+, Δλ)
    """
    removed_vertices, added_vertices, modified_vertex_pairs = compute_vertex_delta(
        left_graph=left_graph,
        right_graph=right_graph,
        matching=matching,
    )

    removed_edges, added_edges, modified_edge_pairs = compute_edge_delta(
        left_graph=left_graph,
        right_graph=right_graph,
        matching=matching,
    )

    modified_pairs = compute_modified_attributes_pairs(
        modified_vertex_pairs=modified_vertex_pairs,
        modified_edge_pairs=modified_edge_pairs,
    )

    delta = Delta(
        added_vertices=frozenset(sorted(added_vertices)),
        removed_vertices=frozenset(sorted(removed_vertices)),
        added_edges=frozenset(sorted(added_edges)),
        removed_edges=frozenset(sorted(removed_edges)),
        modified_attributes=modified_pairs,
    )

    return DeltaDetails(
        delta=delta,
        modified_vertex_pairs=frozenset(sorted(modified_vertex_pairs)),
        modified_edge_pairs=frozenset(sorted(modified_edge_pairs)),
    )
