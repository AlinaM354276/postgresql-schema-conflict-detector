from __future__ import annotations

from src.conflict_detector.core.models import DropOperation, ModifyOperation, freeze_attrs
from src.conflict_detector.detection.detector import detect_conflicts
from src.conflict_detector.graph.builders import build_schema_graph
from src.conflict_detector.rules.registry import DEFAULT_RULES
from src.conflict_detector.core.models import RenameOperation


def build_users_graph():
    builder = build_schema_graph()
    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email", data_type="text", nullable=False)
    return builder.build()


def test_pipeline_default_rules_detect_dependency_conflict():
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
        rules=DEFAULT_RULES,
    )

    assert len(result.conflicts) == 1
    assert result.conflicts[0].rule_id == "D1_DROP_PREREQUISITE_VS_MODIFY_DEPENDENT"


def test_pipeline_default_rules_detect_drop_vs_rename_dependency_conflict():
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
        rules=DEFAULT_RULES,
    )

    assert len(result.conflicts) == 1
    assert result.conflicts[0].rule_id == "D2_DROP_PREREQUISITE_VS_RENAME_DEPENDENT"
