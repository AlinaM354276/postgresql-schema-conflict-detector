from __future__ import annotations

from src.conflict_detector.core.models import ModifyOperation, RenameOperation
from src.conflict_detector.graph.builders import build_schema_graph
from src.conflict_detector.pipeline.analyze_merge import analyze_merge


def build_base_graph():
    builder = build_schema_graph()
    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email", data_type="text", nullable=False)
    return builder.build()


def build_branch_a_graph():
    builder = build_schema_graph()
    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email_address", data_type="text", nullable=False)
    return builder.build()


def build_branch_b_graph():
    builder = build_schema_graph()
    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email", data_type="text", nullable=True)
    return builder.build()


def test_pipeline_compatible_rename_vs_modify_has_no_conflict():
    result = analyze_merge(
        base_graph=build_base_graph(),
        branch_a_graph=build_branch_a_graph(),
        branch_b_graph=build_branch_b_graph(),
    )

    assert result.summary.total == 0
    assert result.summary.has_conflicts is False


def test_pipeline_returns_expected_operations_for_branches():
    result = analyze_merge(
        base_graph=build_base_graph(),
        branch_a_graph=build_branch_a_graph(),
        branch_b_graph=build_branch_b_graph(),
    )

    assert len(result.operations_a) == 1
    assert len(result.operations_b) == 1


def test_pipeline_branch_b_has_modify_for_email():
    result = analyze_merge(
        base_graph=build_base_graph(),
        branch_a_graph=build_branch_a_graph(),
        branch_b_graph=build_branch_b_graph(),
    )

    assert any(
        isinstance(op, ModifyOperation) and op.target == "public.users.email"
        for op in result.operations_b
    )


def test_pipeline_branch_a_has_rename_for_email():
    result = analyze_merge(
        base_graph=build_base_graph(),
        branch_a_graph=build_branch_a_graph(),
        branch_b_graph=build_branch_b_graph(),
    )

    assert any(
        isinstance(op, RenameOperation)
        and op.target == "public.users.email"
        and op.new_name == "email_address"
        for op in result.operations_a
    )


def test_pipeline_exposes_branch_artifacts():
    result = analyze_merge(
        base_graph=build_base_graph(),
        branch_a_graph=build_branch_a_graph(),
        branch_b_graph=build_branch_b_graph(),
    )

    assert result.operations_a is not None
    assert result.operations_b is not None
    assert result.conflicts is not None
    assert result.summary is not None


def test_pipeline_branch_a_rename_has_no_edge_noise():
    result = analyze_merge(
        base_graph=build_base_graph(),
        branch_a_graph=build_branch_a_graph(),
        branch_b_graph=build_branch_b_graph(),
    )

    assert len(result.operations_a) == 1
    assert isinstance(result.operations_a[0], RenameOperation)
