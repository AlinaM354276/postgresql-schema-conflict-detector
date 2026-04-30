from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.conflict_detector.core.models import ObjectType, SchemaObject
from src.conflict_detector.graph.schema_graph import SchemaGraph


@dataclass(frozen=True)
class MatchPair:
    left_id: str
    right_id: str


@dataclass
class MatchingResult:
    """
    Результат сопоставления объектов и рёбер двух графов.

    left_to_right и right_to_left поддерживаются одновременно,
    чтобы быстро проверять взаимно-однозначное соответствие.
    """
    left_to_right: Dict[str, str] = field(default_factory=dict)
    right_to_left: Dict[str, str] = field(default_factory=dict)

    def add(self, left_id: str, right_id: str) -> None:
        if left_id in self.left_to_right:
            raise ValueError(f"Left object already matched: {left_id}")
        if right_id in self.right_to_left:
            raise ValueError(f"Right object already matched: {right_id}")

        self.left_to_right[left_id] = right_id
        self.right_to_left[right_id] = left_id

    def get_right(self, left_id: str) -> Optional[str]:
        return self.left_to_right.get(left_id)

    def get_left(self, right_id: str) -> Optional[str]:
        return self.right_to_left.get(right_id)

    def is_matched_left(self, left_id: str) -> bool:
        return left_id in self.left_to_right

    def is_matched_right(self, right_id: str) -> bool:
        return right_id in self.right_to_left

    def pairs(self) -> List[MatchPair]:
        return [MatchPair(l, r) for l, r in self.left_to_right.items()]


def comparable_attributes(left: SchemaObject, right: SchemaObject) -> bool:
    """
    Атрибутивная сопоставимость.

    Мягкий критерий:
    - тип объекта должен совпадать;
    - сравниваются все атрибуты, кроме идентифицирующих/контекстных.
    """
    if left.object_type != right.object_type:
        return False

    left_attrs = left.attr_dict().copy()
    right_attrs = right.attr_dict().copy()

    ignored_keys = {"name", "schema", "table", "owner"}
    for key in ignored_keys:
        left_attrs.pop(key, None)
        right_attrs.pop(key, None)

    return left_attrs == right_attrs


def stable_owner_key(obj: SchemaObject) -> str:
    """
    Возвращает контекст объекта для strong matching.

    Проблема старого варианта:
    (Column, id) ошибочно склеивал users.id и orders.id.

    Поэтому для колонок, ограничений и индексов учитывается table/schema-контекст.
    """
    attrs = obj.attr_dict()

    if obj.object_type in {ObjectType.COLUMN, ObjectType.CONSTRAINT, ObjectType.INDEX}:
        schema = str(attrs.get("schema", ""))
        table = str(attrs.get("table", ""))
        return f"{schema}.{table}"

    if obj.object_type == ObjectType.TABLE:
        return str(attrs.get("schema", ""))

    return ""


def strong_name_key(obj: SchemaObject) -> Tuple[str, str, str]:
    """
    Сильный ключ для очевидного matching:
    (тип, owner/context, имя).

    Это защищает от homonym problem:
    одинаковые имена в разных таблицах не должны считаться одним объектом.
    """
    return obj.object_type.value, stable_owner_key(obj), obj.name


def structure_signature(
    graph: SchemaGraph,
    object_id: str,
) -> Tuple[str, str, Tuple[str, ...], Tuple[str, ...]]:
    """
    Структурная сигнатура объекта:
    - тип объекта;
    - имя;
    - типы входящих рёбер;
    - типы исходящих рёбер.
    """
    obj = graph.get_vertex(object_id)
    if obj is None:
        raise ValueError(f"Unknown vertex: {object_id}")

    incoming_types = tuple(
        sorted(edge.edge_type.value for edge in graph.edges_to(object_id))
    )
    outgoing_types = tuple(
        sorted(edge.edge_type.value for edge in graph.edges_from(object_id))
    )

    return (
        obj.object_type.value,
        obj.name,
        incoming_types,
        outgoing_types,
    )


def edge_signature(
    graph: SchemaGraph,
    edge_id: str,
    vertex_matching: MatchingResult,
    side: str,
) -> Optional[Tuple[str, str, str]]:
    """
    Возвращает сигнатуру ребра, приведённую к уже сопоставленным вершинам.

    side:
    - left: source/target должны быть сопоставлены в right ids;
    - right: source/target должны быть сопоставлены в left ids.
    """
    edge = graph.get_edge(edge_id)
    if edge is None:
        raise ValueError(f"Unknown edge: {edge_id}")

    if side == "left":
        mapped_source = vertex_matching.get_right(edge.source_id)
        mapped_target = vertex_matching.get_right(edge.target_id)
    elif side == "right":
        mapped_source = vertex_matching.get_left(edge.source_id)
        mapped_target = vertex_matching.get_left(edge.target_id)
    else:
        raise ValueError("side must be 'left' or 'right'")

    if mapped_source is None or mapped_target is None:
        return None

    return (edge.edge_type.value, mapped_source, mapped_target)


def match_vertices(
    left_graph: SchemaGraph,
    right_graph: SchemaGraph,
) -> MatchingResult:
    """
    Сопоставление вершин:
    1. strong matching по (type, owner/context, name);
    2. мягкое structure/attribute matching для rename-кандидатов.
    """
    result = MatchingResult()

    left_vertices = list(left_graph.vertices.values())
    right_vertices = list(right_graph.vertices.values())

    right_by_strong_key: Dict[Tuple[str, str, str], List[str]] = {}
    for obj in right_vertices:
        right_by_strong_key.setdefault(strong_name_key(obj), []).append(obj.object_id)

    for left_obj in left_vertices:
        key = strong_name_key(left_obj)
        candidates = right_by_strong_key.get(key, [])

        if len(candidates) == 1:
            candidate_id = candidates[0]
            if not result.is_matched_right(candidate_id):
                right_obj = right_graph.get_vertex(candidate_id)
                if right_obj is not None:
                    result.add(left_obj.object_id, candidate_id)

    unmatched_left = [
        vertex
        for vertex in left_vertices
        if not result.is_matched_left(vertex.object_id)
    ]
    unmatched_right = [
        vertex
        for vertex in right_vertices
        if not result.is_matched_right(vertex.object_id)
    ]

    for left_obj in unmatched_left:
        candidates: List[SchemaObject] = []
        left_sig = structure_signature(left_graph, left_obj.object_id)
        left_owner = stable_owner_key(left_obj)

        for right_obj in unmatched_right:
            if result.is_matched_right(right_obj.object_id):
                continue

            if left_obj.object_type != right_obj.object_type:
                continue

            if stable_owner_key(right_obj) != left_owner:
                continue

            if not comparable_attributes(left_obj, right_obj):
                continue

            right_sig = structure_signature(right_graph, right_obj.object_id)

            if (
                left_sig[0] == right_sig[0]
                and left_sig[2] == right_sig[2]
                and left_sig[3] == right_sig[3]
            ):
                candidates.append(right_obj)

        if len(candidates) == 1:
            result.add(left_obj.object_id, candidates[0].object_id)

    return result


def match_edges(
    left_graph: SchemaGraph,
    right_graph: SchemaGraph,
    vertex_matching: MatchingResult,
) -> MatchingResult:
    """
    Сопоставление рёбер выполняется после сопоставления вершин.

    Рёбра сопоставляются по:
    - типу ребра;
    - уже сопоставленным source/target.
    """
    result = MatchingResult()

    right_edge_index: Dict[Tuple[str, str, str], List[str]] = {}

    for right_edge in right_graph.edges.values():
        sig = edge_signature(
            graph=right_graph,
            edge_id=right_edge.edge_id,
            vertex_matching=vertex_matching,
            side="right",
        )
        if sig is not None:
            right_edge_index.setdefault(sig, []).append(right_edge.edge_id)

    for left_edge in left_graph.edges.values():
        sig = edge_signature(
            graph=left_graph,
            edge_id=left_edge.edge_id,
            vertex_matching=vertex_matching,
            side="left",
        )
        if sig is None:
            continue

        candidates = right_edge_index.get(sig, [])

        if len(candidates) == 1:
            candidate_id = candidates[0]
            if not result.is_matched_right(candidate_id):
                result.add(left_edge.edge_id, candidate_id)

    return result


@dataclass
class FullMatchingResult:
    vertex_matching: MatchingResult
    edge_matching: MatchingResult

    def get_right_for_any(self, left_id: str) -> Optional[str]:
        return (
            self.vertex_matching.get_right(left_id)
            or self.edge_matching.get_right(left_id)
        )

    def get_left_for_any(self, right_id: str) -> Optional[str]:
        return (
            self.vertex_matching.get_left(right_id)
            or self.edge_matching.get_left(right_id)
        )


def build_matching(
    left_graph: SchemaGraph,
    right_graph: SchemaGraph,
) -> FullMatchingResult:
    """
    Полное matching двух графов:
    1. match vertices;
    2. match edges.
    """
    vertex_matching = match_vertices(left_graph, right_graph)
    edge_matching = match_edges(left_graph, right_graph, vertex_matching)

    return FullMatchingResult(
        vertex_matching=vertex_matching,
        edge_matching=edge_matching,
    )
