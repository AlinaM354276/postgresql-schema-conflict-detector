from __future__ import annotations

from src.conflict_detector.core.models import DropOperation, ModifyOperation, freeze_attrs
from src.conflict_detector.detection.detector import detect_conflicts
from src.conflict_detector.graph.builders import build_schema_graph
from src.conflict_detector.rules.reference_rules import (
    DropReferencedTargetVsModifyReferenceSourceRule,
)


def build_fk_graph():
    builder = build_schema_graph()

    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)

    builder.add_table("orders")
    builder.add_column("orders", "id", data_type="integer", nullable=False)
    builder.add_column("orders", "user_id", data_type="integer", nullable=False)

    builder.add_reference("orders", "user_id", "users", "id")

    return builder.build()


def test_detect_drop_referenced_target_vs_modify_reference_source_conflict():
    graph_a = build_fk_graph()
    graph_b = build_fk_graph()

    ops_a = [
        DropOperation(target="public.users.id"),
    ]
    ops_b = [
        ModifyOperation(
            target="public.orders.user_id",
            delta=freeze_attrs({"nullable": True}),
        )
    ]

    result = detect_conflicts(
        operations_a=ops_a,
        operations_b=ops_b,
        graph_a=graph_a,
        graph_b=graph_b,
        rules=[
            DropReferencedTargetVsModifyReferenceSourceRule(
                rule_id="F1_DROP_REFERENCED_TARGET_VS_MODIFY_REFERENCE_SOURCE",
                description="Drop referenced target vs modify reference source",
            )
        ],
    )

    assert len(result.conflicts) == 1
    assert result.conflicts[0].rule_id == "F1_DROP_REFERENCED_TARGET_VS_MODIFY_REFERENCE_SOURCE"


def test_no_reference_conflict_for_unrelated_columns():
    graph_a = build_fk_graph()
    graph_b = build_fk_graph()

    ops_a = [
        DropOperation(target="public.orders.id"),
    ]
    ops_b = [
        ModifyOperation(
            target="public.orders.user_id",
            delta=freeze_attrs({"nullable": True}),
        )
    ]

    result = detect_conflicts(
        operations_a=ops_a,
        operations_b=ops_b,
        graph_a=graph_a,
        graph_b=graph_b,
        rules=[
            DropReferencedTargetVsModifyReferenceSourceRule(
                rule_id="F1_DROP_REFERENCED_TARGET_VS_MODIFY_REFERENCE_SOURCE",
                description="Drop referenced target vs modify reference source",
            )
        ],
    )

    assert len(result.conflicts) == 0
    