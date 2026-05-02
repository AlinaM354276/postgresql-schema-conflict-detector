from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Set, Tuple

from src.conflict_detector.comparison.matching import FullMatchingResult
from src.conflict_detector.core.models import Delta
from src.conflict_detector.graph.builders import canonical_data_type_name
from src.conflict_detector.graph.schema_graph import SchemaGraph


@dataclass(frozen=True)
class DeltaDetails:
    """
    Расширенная форма дельты:
    кроме Delta хранит пары изменённых объектов для последующей классификации.
    """
    delta: Delta
    modified_vertex_pairs: FrozenSet[Tuple[str, str]]
    modified_edge_pairs: FrozenSet[Tuple[str, str]]

    def is_empty(self) -> bool:
        return self.delta.is_empty()


def normalize_type_spec(value: object) -> object:
    """
    Нормализует SQL-спецификацию типа для сравнения.

    Нужно, чтобы:
    - INT и integer считались одинаковыми;
    - VARCHAR(128) и VARCHAR(255) считались разными;
    - VARCHAR ( 255 ) и varchar(255) считались одинаковыми.
    """
    if value is None:
        return None

    raw = " ".join(str(value).strip().lower().split())

    aliases = {
        "int": "integer",
        "int4": "integer",
        "int8": "bigint",
        "bool": "boolean",
        "character varying": "varchar",
    }

    if "(" not in raw:
        return aliases.get(raw, canonical_data_type_name(raw))

    # нормализация пробелов вокруг скобок и запятых
    raw = raw.replace(" (", "(")
    raw = raw.replace("( ", "(")
    raw = raw.replace(" )", ")")
    raw = raw.replace(" ,", ",")
    raw = raw.replace(", ", ",")

    if raw.startswith("character varying("):
        return "varchar" + raw.removeprefix("character varying")

    if raw.startswith("varchar("):
        return raw

    if raw.startswith("numeric("):
        return raw

    if raw.startswith("decimal("):
        return raw

    if raw.startswith("char("):
        return raw

    if raw.startswith("character("):
        return "char" + raw.removeprefix("character")

    return raw


def normalize_attr_value(key: str, value: object) -> object:
    if key == "data_type":
        return canonical_data_type_name(str(value))

    if key == "data_type_raw":
        return normalize_type_spec(value)

    return value


def normalized_attrs(attrs: Dict[str, object]) -> Dict[str, object]:
    """
    Нормализует атрибуты перед сравнением.

    Важно:
    data_type_raw НЕ игнорируется, потому что именно он хранит параметры типа:
    varchar(128), varchar(255), numeric(10,2) и т.д.
    """
    return {
        key: normalize_attr_value(key, value)
        for key, value in attrs.items()
    }


def attributes_changed(
    left_attrs: Dict[str, object],
    right_attrs: Dict[str, object],
) -> bool:
    return normalized_attrs(left_attrs) != normalized_attrs(right_attrs)


def edge_endpoint_missing_in_right(
    edge_id: str,
    left_graph: SchemaGraph,
    right_graph: SchemaGraph,
) -> bool:
    edge = left_graph.get_edge(edge_id)
    if edge is None:
        return False

    return (
        right_graph.get_vertex(edge.source_id) is None
        or right_graph.get_vertex(edge.target_id) is None
    )


def edge_endpoint_missing_in_left(
    edge_id: str,
    left_graph: SchemaGraph,
    right_graph: SchemaGraph,
) -> bool:
    edge = right_graph.get_edge(edge_id)
    if edge is None:
        return False

    return (
        left_graph.get_vertex(edge.source_id) is None
        or left_graph.get_vertex(edge.target_id) is None
    )


def compute_vertex_delta(
    left_graph: SchemaGraph,
    right_graph: SchemaGraph,
    matching: FullMatchingResult,
) -> Tuple[Set[str], Set[str], Set[Tuple[str, str]]]:
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
    removed_edges: Set[str] = set()
    added_edges: Set[str] = set()
    modified_edge_pairs: Set[Tuple[str, str]] = set()

    for left_id, left_edge in left_graph.edges.items():
        # Если ребро исчезло только потому, что исчезла вершина,
        # отдельный Drop(edge) не нужен: Drop(vertex) сам удаляет incident edges.
        if edge_endpoint_missing_in_right(left_id, left_graph, right_graph):
            continue

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
        # Если ребро появилось только потому, что появилась вершина,
        # оно будет восстановлено через Add(Column/Constraint/Index).
        if edge_endpoint_missing_in_left(right_id, left_graph, right_graph):
            continue

        if not matching.edge_matching.is_matched_right(right_id):
            added_edges.add(right_id)

    return removed_edges, added_edges, modified_edge_pairs


def compute_modified_attributes_pairs(
    modified_vertex_pairs: Set[Tuple[str, str]],
    modified_edge_pairs: Set[Tuple[str, str]],
) -> FrozenSet[Tuple[str, str]]:
    all_pairs = set(modified_vertex_pairs)
    all_pairs.update(modified_edge_pairs)
    return frozenset(sorted(all_pairs))


def compute_delta(
    left_graph: SchemaGraph,
    right_graph: SchemaGraph,
    matching: FullMatchingResult,
) -> DeltaDetails:
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
