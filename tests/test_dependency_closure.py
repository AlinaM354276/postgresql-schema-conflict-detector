from src.conflict_detector.graph.builders import build_schema_graph
from src.conflict_detector.semantics.dependency_closure import (
    compute_dependency_closure,
)


def test_dependency_closure_includes_table_columns():
    builder = build_schema_graph()
    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email", data_type="text", nullable=False)

    graph = builder.build()

    closure = compute_dependency_closure(
        graph,
        roots=["public.users"],
    )

    assert "public.users" in closure.as_set()
    assert "public.users.id" in closure.as_set()
    assert "public.users.email" in closure.as_set()


def test_dependency_closure_follows_foreign_key_reference():
    builder = build_schema_graph()

    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)

    builder.add_table("orders")
    builder.add_column("orders", "id", data_type="integer", nullable=False)
    builder.add_column("orders", "user_id", data_type="integer", nullable=True)

    builder.add_reference(
        source_table="orders",
        source_column="user_id",
        target_table="users",
        target_column="id",
    )

    graph = builder.build()

    closure = compute_dependency_closure(
        graph,
        roots=["public.users.id"],
    )

    assert "public.orders.user_id" in closure.as_set()