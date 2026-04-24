from __future__ import annotations

from src.conflict_detector.core.models import ConstraintType
from src.conflict_detector.graph.builders import build_schema_graph, build_edge
from src.conflict_detector.core.models import EdgeType
from src.conflict_detector.validation.invariants import validate_schema_invariants


def test_valid_schema_passes_invariant_validation():
    builder = build_schema_graph()

    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email", data_type="text", nullable=False)
    builder.add_constraint(
        "users",
        "pk_users",
        constraint_type=ConstraintType.PRIMARY_KEY,
    )

    graph = builder.build()

    result = validate_schema_invariants(graph)

    assert result.is_valid() is True
    assert len(result.violations) == 0


def test_column_without_owner_table_is_invalid():
    builder = build_schema_graph()

    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)

    graph = builder.build()

    # вручную добавим column без contains-edge
    orphan_builder = build_schema_graph()
    orphan_builder.graph = graph
    orphan_builder.ensure_data_type("text")
    orphan_column = orphan_builder.add_column  # just to keep style consistent

    # создаём отдельную колонку вручную без связи contains
    from src.conflict_detector.graph.builders import build_column
    column = build_column(
        table_name="ghost",
        column_name="orphan",
        schema_name="public",
        nullable=False,
    )
    graph.add_vertex(column)

    result = validate_schema_invariants(graph)

    assert result.is_valid() is False
    assert any(v.invariant_id == "INV_COLUMN_SINGLE_OWNER_TABLE" for v in result.violations)


def test_column_without_single_datatype_is_invalid():
    builder = build_schema_graph()

    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)

    graph = builder.build()

    from src.conflict_detector.graph.builders import build_column
    column = build_column(
        table_name="users",
        column_name="email",
        schema_name="public",
        nullable=False,
    )
    graph.add_vertex(column)

    contains_edge = build_edge(
        edge_type=EdgeType.CONTAINS,
        source_id="public.users",
        target_id="public.users.email",
    )
    graph.add_edge(contains_edge)

    result = validate_schema_invariants(graph)

    assert result.is_valid() is False
    assert any(v.invariant_id == "INV_COLUMN_SINGLE_DATATYPE" for v in result.violations)


def test_table_with_two_primary_keys_is_invalid():
    builder = build_schema_graph()

    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_constraint(
        "users",
        "pk_users_1",
        constraint_type=ConstraintType.PRIMARY_KEY,
    )
    builder.add_constraint(
        "users",
        "pk_users_2",
        constraint_type=ConstraintType.PRIMARY_KEY,
    )

    graph = builder.build()

    result = validate_schema_invariants(graph)

    assert result.is_valid() is False
    assert any(v.invariant_id == "INV_SINGLE_PRIMARY_KEY_PER_TABLE" for v in result.violations)
