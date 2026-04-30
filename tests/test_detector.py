from __future__ import annotations

from src.conflict_detector.comparison.reconstruct import RenameOperation
from src.conflict_detector.core.models import (
    DropOperation,
    ModifyOperation,
    freeze_attrs,
)
from src.conflict_detector.detection.detector import detect_conflicts
from src.conflict_detector.graph.builders import build_schema_graph
from src.conflict_detector.rules.basic_rules import BASIC_RULES


def build_dummy_graph():
    builder = build_schema_graph()
    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email", data_type="text", nullable=False)
    return builder.build()


def test_detect_drop_vs_modify_conflict():
    graph_a = build_dummy_graph()
    graph_b = build_dummy_graph()

    ops_a = [DropOperation(target="public.users.email")]
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
        rules=BASIC_RULES,
    )

    assert len(result.conflicts) == 1
    assert result.conflicts[0].rule_id == "R1_DROP_VS_MODIFY"


def test_detect_drop_vs_rename_conflict():
    graph_a = build_dummy_graph()
    graph_b = build_dummy_graph()

    ops_a = [DropOperation(target="public.users.email")]
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
        rules=BASIC_RULES,
    )

    assert len(result.conflicts) == 1
    assert result.conflicts[0].rule_id == "R2_DROP_VS_RENAME"


def test_detect_rename_vs_rename_conflict():
    graph_a = build_dummy_graph()
    graph_b = build_dummy_graph()

    ops_a = [
        RenameOperation(
            target="public.users.email",
            new_name="email_address",
        )
    ]
    ops_b = [
        RenameOperation(
            target="public.users.email",
            new_name="user_email",
        )
    ]

    result = detect_conflicts(
        operations_a=ops_a,
        operations_b=ops_b,
        graph_a=graph_a,
        graph_b=graph_b,
        rules=BASIC_RULES,
    )

    assert len(result.conflicts) == 1
    assert result.conflicts[0].rule_id == "R3_RENAME_VS_RENAME"


def test_detect_modify_vs_modify_conflict():
    graph_a = build_dummy_graph()
    graph_b = build_dummy_graph()

    ops_a = [
        ModifyOperation(
            target="public.users.email",
            delta=freeze_attrs({"nullable": True}),
        )
    ]
    ops_b = [
        ModifyOperation(
            target="public.users.email",
            delta=freeze_attrs({"default": "unknown@example.com"}),
        )
    ]

    result = detect_conflicts(
        operations_a=ops_a,
        operations_b=ops_b,
        graph_a=graph_a,
        graph_b=graph_b,
        rules=BASIC_RULES,
    )

    assert len(result.conflicts) == 1
    assert result.conflicts[0].rule_id == "R4_MODIFY_VS_MODIFY"


def test_detect_no_conflict_for_rename_vs_non_identity_modify():
    graph_a = build_dummy_graph()
    graph_b = build_dummy_graph()

    ops_a = [
        RenameOperation(
            target="public.users.email",
            new_name="email_address",
        )
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
        rules=BASIC_RULES,
    )

    assert len(result.conflicts) == 0


def test_detect_no_conflict_for_identical_modify():
    graph_a = build_dummy_graph()
    graph_b = build_dummy_graph()

    delta = freeze_attrs({"nullable": True})

    ops_a = [
        ModifyOperation(
            target="public.users.email",
            delta=delta,
        )
    ]
    ops_b = [
        ModifyOperation(
            target="public.users.email",
            delta=delta,
        )
    ]

    result = detect_conflicts(
        operations_a=ops_a,
        operations_b=ops_b,
        graph_a=graph_a,
        graph_b=graph_b,
        rules=BASIC_RULES,
    )

    assert len(result.conflicts) == 0


def test_detect_no_conflict_for_identical_rename():
    graph_a = build_dummy_graph()
    graph_b = build_dummy_graph()

    ops_a = [
        RenameOperation(
            target="public.users.email",
            new_name="email_address",
        )
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
        rules=BASIC_RULES,
    )

    assert len(result.conflicts) == 0
