from __future__ import annotations

from difflib import SequenceMatcher
from typing import Optional

from src.conflict_detector.core.models import SchemaObject
from src.conflict_detector.graph.schema_graph import SchemaGraph


RENAME_THRESHOLD = 0.70


def normalized(value: Optional[str]) -> str:
    if value is None:
        return ""

    return str(value).strip().lower()


def name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(
        None,
        normalized(a),
        normalized(b),
    ).ratio()


def boolean_similarity(a: object, b: object) -> float:
    return 1.0 if a == b else 0.0


def owner_similarity(
    old_obj: SchemaObject,
    new_obj: SchemaObject,
) -> float:
    old_attrs = old_obj.attr_dict()
    new_attrs = new_obj.attr_dict()

    old_table = normalized(old_attrs.get("table"))
    new_table = normalized(new_attrs.get("table"))

    old_schema = normalized(old_attrs.get("schema"))
    new_schema = normalized(new_attrs.get("schema"))

    if old_table != new_table:
        return 0.0

    if old_schema != new_schema:
        return 0.0

    return 1.0


def datatype_similarity(
    old_obj: SchemaObject,
    new_obj: SchemaObject,
) -> float:
    old_attrs = old_obj.attr_dict()
    new_attrs = new_obj.attr_dict()

    old_type = normalized(
        old_attrs.get("data_type")
        or old_attrs.get("data_type_raw")
    )

    new_type = normalized(
        new_attrs.get("data_type")
        or new_attrs.get("data_type_raw")
    )

    return boolean_similarity(old_type, new_type)


def nullable_similarity(
    old_obj: SchemaObject,
    new_obj: SchemaObject,
) -> float:
    old_nullable = old_obj.attr_dict().get("nullable")
    new_nullable = new_obj.attr_dict().get("nullable")

    return boolean_similarity(old_nullable, new_nullable)


def neighborhood_similarity(
    graph_before: SchemaGraph,
    graph_after: SchemaGraph,
    old_obj: SchemaObject,
    new_obj: SchemaObject,
) -> float:
    old_neighbors = set()
    new_neighbors = set()

    for edge in graph_before.edges_from(old_obj.object_id):
        old_neighbors.add(edge.edge_type.value)

    for edge in graph_before.edges_to(old_obj.object_id):
        old_neighbors.add(edge.edge_type.value)

    for edge in graph_after.edges_from(new_obj.object_id):
        new_neighbors.add(edge.edge_type.value)

    for edge in graph_after.edges_to(new_obj.object_id):
        new_neighbors.add(edge.edge_type.value)

    if not old_neighbors and not new_neighbors:
        return 1.0

    intersection = len(old_neighbors & new_neighbors)
    union = len(old_neighbors | new_neighbors)

    if union == 0:
        return 0.0

    return intersection / union


def rename_candidate_score(
    graph_before: SchemaGraph,
    graph_after: SchemaGraph,
    old_obj: SchemaObject,
    new_obj: SchemaObject,
) -> float:
    if old_obj.object_type != new_obj.object_type:
        return 0.0

    owner_score = owner_similarity(old_obj, new_obj)

    if owner_score == 0.0:
        return 0.0

    old_attrs = old_obj.attr_dict()
    new_attrs = new_obj.attr_dict()

    name_score = name_similarity(
        old_attrs.get("name", ""),
        new_attrs.get("name", ""),
    )

    datatype_score = datatype_similarity(
        old_obj,
        new_obj,
    )

    nullable_score = nullable_similarity(
        old_obj,
        new_obj,
    )

    neighborhood_score = neighborhood_similarity(
        graph_before,
        graph_after,
        old_obj,
        new_obj,
    )

    score = (
        0.30 * name_score
        + 0.30 * datatype_score
        + 0.20 * nullable_score
        + 0.20 * neighborhood_score
    )

    return score


def is_probable_rename(
    graph_before: SchemaGraph,
    graph_after: SchemaGraph,
    old_obj: SchemaObject,
    new_obj: SchemaObject,
) -> bool:
    score = rename_candidate_score(
        graph_before=graph_before,
        graph_after=graph_after,
        old_obj=old_obj,
        new_obj=new_obj,
    )

    return score >= RENAME_THRESHOLD