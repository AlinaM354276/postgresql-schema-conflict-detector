from src.conflict_detector.core.models import (
    ModifyOperation,
    freeze_attrs,
)
from src.conflict_detector.detection.detector import detect_conflicts
from src.conflict_detector.graph.builders import build_schema_graph
from src.conflict_detector.rules.basic_rules import BASIC_RULES


def build_graph_with_referenced_index():
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

    builder.add_index(
        table_name="orders",
        index_name="idx_orders_user_id",
        columns="user_id",
    )

    return builder.build()


def test_r6_detects_transitive_dependency_closure_conflict():
    graph_a = build_graph_with_referenced_index()
    graph_b = build_graph_with_referenced_index()

    operations_a = [
        ModifyOperation(
            target="public.users.id",
            delta=freeze_attrs({"nullable": True}),
        )
    ]

    operations_b = [
        ModifyOperation(
            target="public.orders.idx_orders_user_id",
            delta=freeze_attrs({"columns": "user_id,id"}),
        )
    ]

    result = detect_conflicts(
        operations_a=operations_a,
        operations_b=operations_b,
        graph_a=graph_a,
        graph_b=graph_b,
        rules=BASIC_RULES,
    )

    assert any(
        conflict.rule_id == "R6_TRANSITIVE_DEPENDENCY_CONFLICT"
        for conflict in result.conflicts
    )