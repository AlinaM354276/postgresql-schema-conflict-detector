from __future__ import annotations

from src.conflict_detector.core.models import (
    DropOperation,
    ModifyOperation,
    RenameOperation,
    freeze_attrs,
)
from src.conflict_detector.graph.builders import build_schema_graph
from src.conflict_detector.merge.three_way_merge import build_merge_candidate


def build_base_graph():
    builder = build_schema_graph()
    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email", data_type="text", nullable=False)
    return builder.build()


def test_merge_candidate_defined_for_rename_then_modify():
    base_graph = build_base_graph()

    ops_a = (
        RenameOperation(
            target="public.users.email",
            new_name="email_address",
        ),
    )

    ops_b = (
        ModifyOperation(
            target="public.users.email",
            delta=freeze_attrs({"nullable": True}),
        ),
    )

    result = build_merge_candidate(
        base_graph=base_graph,
        operations_a=ops_a,
        operations_b=ops_b,
    )

    assert result.is_defined is True
    assert result.merged_graph is not None

    merged_email = result.merged_graph.get_vertex("public.users.email_address")
    assert merged_email is not None
    assert merged_email.attr_dict()["nullable"] is True


def test_merge_candidate_defined_for_rewritten_modify_after_rename():
    base_graph = build_base_graph()

    ops_a = (
        RenameOperation(
            target="public.users.email",
            new_name="email_address",
        ),
    )

    ops_b = (
        ModifyOperation(
            target="public.users.email",
            delta=freeze_attrs({"nullable": True}),
        ),
    )

    result = build_merge_candidate(
        base_graph=base_graph,
        operations_a=ops_a,
        operations_b=ops_b,
    )

    assert result.is_defined is True
    assert result.merged_graph is not None

    merged_email = result.merged_graph.get_vertex("public.users.email_address")
    assert merged_email is not None
    assert merged_email.attr_dict()["nullable"] is True


def test_merge_candidate_detects_invariant_violation():
    base_graph = build_base_graph()

    ops_a = (
        DropOperation(target="typedAs:public.users.email->type.text"),
    )

    ops_b = tuple()

    result = build_merge_candidate(
        base_graph=base_graph,
        operations_a=ops_a,
        operations_b=ops_b,
    )

    assert result.is_defined is False
    assert result.merged_graph is not None
    assert len(result.invariant_result.violations) > 0
