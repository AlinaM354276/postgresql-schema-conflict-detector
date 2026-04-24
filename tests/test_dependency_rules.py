from __future__ import annotations

from src.conflict_detector.core.models import DropOperation, ModifyOperation, freeze_attrs
from src.conflict_detector.detection.detector import detect_conflicts
from src.conflict_detector.graph.builders import build_schema_graph
from src.conflict_detector.rules.dependency_rules import DropPrerequisiteVsModifyDependentRule
from src.conflict_detector.core.models import RenameOperation
from src.conflict_detector.rules.dependency_rules import (
    DropPrerequisiteVsModifyDependentRule,
    DropPrerequisiteVsRenameDependentRule,
)

def build_users_graph():
    builder = build_schema_graph()
    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email", data_type="text", nullable=False)
    return builder.build()


def build_independent_graph():
    builder = build_schema_graph()
    builder.add_table("users")
    builder.add_column("users", "email", data_type="text", nullable=False)

    builder.add_table("orders")
    builder.add_column("orders", "amount", data_type="integer", nullable=False)
    return builder.build()


def test_detect_drop_table_vs_modify_column_dependency_conflict():
    graph_a = build_users_graph()
    graph_b = build_users_graph()

    ops_a = [
        DropOperation(target="public.users"),
    ]
    ops_b = [
        ModifyOperation(
            target="public.users.email",
            delta=freeze_attrs({"nullable": True}),
        )
    ]

    result = detect_conflicts(
        operations_a=ops_a,
        operations_b=ops_b,
        graph_a=graph_a,
        graph_b=graph_b,
        rules=[
            DropPrerequisiteVsModifyDependentRule(
                rule_id="D1_DROP_PREREQUISITE_VS_MODIFY_DEPENDENT",
                description="Drop prerequisite vs modify dependent",
            )
        ],
    )

    assert len(result.conflicts) == 1
    assert result.conflicts[0].rule_id == "D1_DROP_PREREQUISITE_VS_MODIFY_DEPENDENT"


def test_detect_modify_column_vs_drop_table_dependency_conflict():
    graph_a = build_users_graph()
    graph_b = build_users_graph()

    ops_a = [
        ModifyOperation(
            target="public.users.email",
            delta=freeze_attrs({"nullable": True}),
        )
    ]
    ops_b = [
        DropOperation(target="public.users"),
    ]

    result = detect_conflicts(
        operations_a=ops_a,
        operations_b=ops_b,
        graph_a=graph_a,
        graph_b=graph_b,
        rules=[
            DropPrerequisiteVsModifyDependentRule(
                rule_id="D1_DROP_PREREQUISITE_VS_MODIFY_DEPENDENT",
                description="Drop prerequisite vs modify dependent",
            )
        ],
    )

    assert len(result.conflicts) == 1
    assert result.conflicts[0].rule_id == "D1_DROP_PREREQUISITE_VS_MODIFY_DEPENDENT"


def test_no_conflict_for_independent_objects():
    graph_a = build_independent_graph()
    graph_b = build_independent_graph()

    ops_a = [
        DropOperation(target="public.users"),
    ]
    ops_b = [
        ModifyOperation(
            target="public.orders.amount",
            delta=freeze_attrs({"nullable": True}),
        )
    ]

    result = detect_conflicts(
        operations_a=ops_a,
        operations_b=ops_b,
        graph_a=graph_a,
        graph_b=graph_b,
        rules=[
            DropPrerequisiteVsModifyDependentRule(
                rule_id="D1_DROP_PREREQUISITE_VS_MODIFY_DEPENDENT",
                description="Drop prerequisite vs modify dependent",
            )
        ],
    )

    assert len(result.conflicts) == 0


def test_detect_drop_table_vs_rename_column_dependency_conflict():
    graph_a = build_users_graph()
    graph_b = build_users_graph()

    ops_a = [
        DropOperation(target="public.users"),
    ]
    ops_b = [
        RenameOperation(
            target="public.users.email",
            new_name="email_address",
        )
    ]

    result = detect_conflicts(
        operations_a=ops_a,
        operations_b=ops_b,
        graph_a=graph_a,
        graph_b=graph_b,
        rules=[
            DropPrerequisiteVsRenameDependentRule(
                rule_id="D2_DROP_PREREQUISITE_VS_RENAME_DEPENDENT",
                description="Drop prerequisite vs rename dependent",
            )
        ],
    )

    assert len(result.conflicts) == 1
    assert result.conflicts[0].rule_id == "D2_DROP_PREREQUISITE_VS_RENAME_DEPENDENT"


def test_detect_rename_column_vs_drop_table_dependency_conflict():
    graph_a = build_users_graph()
    graph_b = build_users_graph()

    ops_a = [
        RenameOperation(
            target="public.users.email",
            new_name="email_address",
        )
    ]
    ops_b = [
        DropOperation(target="public.users"),
    ]

    result = detect_conflicts(
        operations_a=ops_a,
        operations_b=ops_b,
        graph_a=graph_a,
        graph_b=graph_b,
        rules=[
            DropPrerequisiteVsRenameDependentRule(
                rule_id="D2_DROP_PREREQUISITE_VS_RENAME_DEPENDENT",
                description="Drop prerequisite vs rename dependent",
            )
        ],
    )

    assert len(result.conflicts) == 1
    assert result.conflicts[0].rule_id == "D2_DROP_PREREQUISITE_VS_RENAME_DEPENDENT"
