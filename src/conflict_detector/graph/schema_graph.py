from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

from src.conflict_detector.core.models import (
    EdgeType,
    ObjectType,
    SchemaEdge,
    SchemaObject,
)


ALLOWED_EDGE_SIGNATURES: dict[EdgeType, set[tuple[ObjectType, ObjectType]]] = {
    EdgeType.CONTAINS: {(ObjectType.TABLE, ObjectType.COLUMN)},
    EdgeType.TYPED_AS: {(ObjectType.COLUMN, ObjectType.DATA_TYPE)},
    EdgeType.HAS_CONSTRAINT: {
        (ObjectType.TABLE, ObjectType.CONSTRAINT),
        (ObjectType.COLUMN, ObjectType.CONSTRAINT),
    },
    EdgeType.REFERENCES: {(ObjectType.COLUMN, ObjectType.COLUMN)},
    EdgeType.HAS_INDEX: {(ObjectType.TABLE, ObjectType.INDEX)},
}


@dataclass
class SchemaGraph:
    """
    Типизированный ориентированный граф схемы.

    Поддерживает:
    - хранение объектов и рёбер
    - базовую валидацию типизации
    - доступ к соседям
    - вычисление зависимостей и транзитивного замыкания
    """
    vertices: Dict[str, SchemaObject] = field(default_factory=dict)
    edges: Dict[str, SchemaEdge] = field(default_factory=dict)
    outgoing: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    incoming: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

    def add_vertex(self, vertex: SchemaObject) -> None:
        if vertex.object_id in self.vertices:
            raise ValueError(f"Duplicate vertex id: {vertex.object_id}")
        self.vertices[vertex.object_id] = vertex

    def add_edge(self, edge: SchemaEdge) -> None:
        if edge.edge_id in self.edges:
            raise ValueError(f"Duplicate edge id: {edge.edge_id}")
        if edge.source_id not in self.vertices:
            raise ValueError(f"Missing source vertex: {edge.source_id}")
        if edge.target_id not in self.vertices:
            raise ValueError(f"Missing target vertex: {edge.target_id}")

        source_type = self.vertices[edge.source_id].object_type
        target_type = self.vertices[edge.target_id].object_type
        allowed = ALLOWED_EDGE_SIGNATURES.get(edge.edge_type, set())
        if (source_type, target_type) not in allowed:
            raise ValueError(
                f"Invalid edge typing for {edge.edge_type}: "
                f"{source_type} -> {target_type}"
            )

        self.edges[edge.edge_id] = edge
        self.outgoing[edge.source_id].add(edge.edge_id)
        self.incoming[edge.target_id].add(edge.edge_id)

    def get_vertex(self, object_id: str) -> Optional[SchemaObject]:
        return self.vertices.get(object_id)

    def get_edge(self, edge_id: str) -> Optional[SchemaEdge]:
        return self.edges.get(edge_id)

    def vertex_ids(self) -> Set[str]:
        return set(self.vertices.keys())

    def edge_ids(self) -> Set[str]:
        return set(self.edges.keys())

    def edges_from(self, vertex_id: str) -> List[SchemaEdge]:
        return [self.edges[eid] for eid in self.outgoing.get(vertex_id, set())]

    def edges_to(self, vertex_id: str) -> List[SchemaEdge]:
        return [self.edges[eid] for eid in self.incoming.get(vertex_id, set())]

    def neighbors_out(self, vertex_id: str) -> List[SchemaObject]:
        result: List[SchemaObject] = []
        for edge in self.edges_from(vertex_id):
            target = self.vertices.get(edge.target_id)
            if target is not None:
                result.append(target)
        return result

    def neighbors_in(self, vertex_id: str) -> List[SchemaObject]:
        result: List[SchemaObject] = []
        for edge in self.edges_to(vertex_id):
            source = self.vertices.get(edge.source_id)
            if source is not None:
                result.append(source)
        return result

    def find_vertices_by_type(self, object_type: ObjectType) -> List[SchemaObject]:
        return [v for v in self.vertices.values() if v.object_type == object_type]

    def find_edges_by_type(self, edge_type: EdgeType) -> List[SchemaEdge]:
        return [e for e in self.edges.values() if e.edge_type == edge_type]

    def validate(self) -> None:
        """
        Дополнительная проверка целостности графа.
        """
        for edge in self.edges.values():
            if edge.source_id not in self.vertices or edge.target_id not in self.vertices:
                raise ValueError(f"Dangling edge: {edge.edge_id}")

            source_type = self.vertices[edge.source_id].object_type
            target_type = self.vertices[edge.target_id].object_type
            allowed = ALLOWED_EDGE_SIGNATURES.get(edge.edge_type, set())

            if (source_type, target_type) not in allowed:
                raise ValueError(
                    f"Invalid edge typing for edge {edge.edge_id}: "
                    f"{source_type} -> {target_type}"
                )

    def dependency_pairs(self) -> Set[Tuple[str, str]]:
        """
        Возвращает множество пар (dependent, prerequisite).

        Интерпретация:
        объект dependent зависит от prerequisite.

        Для MVP используем следующие правила:
        - column depends on table           via CONTAINS
        - column depends on datatype       via TYPED_AS
        - constraint depends on owner      via HAS_CONSTRAINT
        - source column depends on target  via REFERENCES
        - index depends on table           via HAS_INDEX
        """
        pairs: Set[Tuple[str, str]] = set()

        for edge in self.edges.values():
            if edge.edge_type == EdgeType.CONTAINS:
                # column depends on table
                pairs.add((edge.target_id, edge.source_id))
            elif edge.edge_type == EdgeType.TYPED_AS:
                # column depends on datatype
                pairs.add((edge.source_id, edge.target_id))
            elif edge.edge_type == EdgeType.HAS_CONSTRAINT:
                # constraint depends on owner
                pairs.add((edge.target_id, edge.source_id))
            elif edge.edge_type == EdgeType.REFERENCES:
                # source column depends on target column
                pairs.add((edge.source_id, edge.target_id))
            elif edge.edge_type == EdgeType.HAS_INDEX:
                # index depends on table
                pairs.add((edge.target_id, edge.source_id))

        return pairs

    def transitive_dependencies_of(self, object_ids: Iterable[str]) -> Set[str]:
        """
        Возвращает транзитивное замыкание зависимостей для множества объектов.
        Включает сами объекты.
        """
        dep_pairs = self.dependency_pairs()
        prereq_map: Dict[str, Set[str]] = defaultdict(set)
        for dependent, prerequisite in dep_pairs:
            prereq_map[dependent].add(prerequisite)

        visited: Set[str] = set()
        queue: deque[str] = deque(object_ids)

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            for prerequisite in prereq_map.get(current, set()):
                if prerequisite not in visited:
                    queue.append(prerequisite)

        return visited

    def impact_of_targets(self, target_ids: Iterable[str]) -> Set[str]:
        """
        Для этапа 3:
        impact(op) = dep*(targets(op))

        В текущей реализации это транзитивное множество зависимостей,
        включая сами targets.
        """
        return self.transitive_dependencies_of(target_ids)

    def to_debug_dict(self) -> dict:
        return {
            "vertices": {
                vid: {
                    "type": v.object_type.value,
                    "name": v.name,
                    "attributes": v.attr_dict(),
                }
                for vid, v in self.vertices.items()
            },
            "edges": {
                eid: {
                    "type": e.edge_type.value,
                    "source": e.source_id,
                    "target": e.target_id,
                    "attributes": e.attr_dict(),
                }
                for eid, e in self.edges.items()
            },
        }

