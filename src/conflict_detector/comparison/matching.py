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


IDENTITY_OR_CONTEXT_KEYS = {
    "name",
    "schema",
    "table",
    "owner",
    "object_id",
}


def comparable_attr_dict(obj: SchemaObject) -> Dict[str, object]:
    attrs = obj.attr_dict().copy()
    for key in IDENTITY_OR_CONTEXT_KEYS:
        attrs.pop(key, None)
    return attrs


def comparable_attributes(left: SchemaObject, right: SchemaObject) -> bool:
    """
    Строгая атрибутивная сопоставимость.

    Используется для очевидных rename-кандидатов.
    """
    if left.object_type != right.object_type:
        return False

    return comparable_attr_dict(left) == comparable_attr_dict(right)


def stable_owner_key(obj: SchemaObject) -> str:
    """
    Контекст объекта для matching.

    Для колонок, ограничений и индексов учитывается table/schema-контекст,
    чтобы users.id и orders.id не сопоставлялись друг с другом.
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
    Сильный ключ для обычного matching:
    (тип, owner/context, имя).
    """
    return obj.object_type.value, stable_owner_key(obj), obj.name


def structure_signature(
    graph: SchemaGraph,
    object_id: str,
) -> Tuple[str, Tuple[str, ...], Tuple[str, ...]]:
    """
    Структурная сигнатура объекта БЕЗ имени.

    Важно:
    имя не включается специально, иначе rename превращается в Drop + Add.
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
        incoming_types,
        outgoing_types,
    )


def attr_similarity(left: SchemaObject, right: SchemaObject) -> int:
    """
    Простая оценка похожести атрибутов.

    Нужна, чтобы rename + modify всё равно сопоставлялся как один объект,
    а не как Drop старого объекта + Add нового объекта.
    """
    left_attrs = comparable_attr_dict(left)
    right_attrs = comparable_attr_dict(right)

    keys = set(left_attrs.keys()) | set(right_attrs.keys())

    if not keys:
        return 0

    return sum(
        1
        for key in keys
        if left_attrs.get(key) == right_attrs.get(key)
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
    2. мягкое matching для rename-кандидатов;
    3. поддержка rename + modify.
    """
    result = MatchingResult()

    left_vertices = list(left_graph.vertices.values())
    right_vertices = list(right_graph.vertices.values())

    right_by_strong_key: Dict[Tuple[str, str, str], List[str]] = {}
    for obj in right_vertices:
        right_by_strong_key.setdefault(strong_name_key(obj), []).append(obj.object_id)

    # 1. Очевидное сопоставление по имени.
    for left_obj in left_vertices:
        key = strong_name_key(left_obj)
        candidates = right_by_strong_key.get(key, [])

        if len(candidates) == 1:
            candidate_id = candidates[0]
            if not result.is_matched_right(candidate_id):
                right_obj = right_graph.get_vertex(candidate_id)
                if right_obj is not None:
                    result.add(left_obj.object_id, candidate_id)

    # 2. Rename / rename+modify matching.
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
        scored_candidates: List[Tuple[int, str]] = []

        left_sig = structure_signature(left_graph, left_obj.object_id)
        left_owner = stable_owner_key(left_obj)

        for right_obj in unmatched_right:
            if result.is_matched_right(right_obj.object_id):
                continue

            if left_obj.object_type != right_obj.object_type:
                continue

            if stable_owner_key(right_obj) != left_owner:
                continue

            right_sig = structure_signature(right_graph, right_obj.object_id)

            if left_sig != right_sig:
                continue

            score = attr_similarity(left_obj, right_obj)

            # Строгий rename получает большой бонус.
            if comparable_attributes(left_obj, right_obj):
                score += 100

            scored_candidates.append((score, right_obj.object_id))

        if not scored_candidates:
            continue

        scored_candidates.sort(reverse=True)
        best_score, best_id = scored_candidates[0]

        # Если два кандидата одинаково хороши, matching неоднозначен.
        if len(scored_candidates) > 1 and scored_candidates[1][0] == best_score:
            continue

        result.add(left_obj.object_id, best_id)

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
