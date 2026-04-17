from __future__ import annotations

from src.conflict_detector.graph.builders import build_schema_graph
from src.conflict_detector.pipeline.analyze_merge import (
    analyze_merge,
    analyze_merge_with_artifacts,
)


def build_base_graph():
    builder = build_schema_graph()

    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email", data_type="text", nullable=False)

    return builder.build()


def build_branch_a_graph():
    """
    Ветка A:
    email -> email_address
    """
    builder = build_schema_graph()

    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email_address", data_type="text", nullable=False)

    return builder.build()


def build_branch_b_graph():
    """
    Ветка B:
    email nullable=False -> nullable=True
    """
    builder = build_schema_graph()

    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email", data_type="text", nullable=True)

    return builder.build()


def test_pipeline_detects_rename_vs_modify_conflict():
    base_graph = build_base_graph()
    branch_a_graph = build_branch_a_graph()
    branch_b_graph = build_branch_b_graph()

    result = analyze_merge(
        base_graph=base_graph,
        branch_a_graph=branch_a_graph,
        branch_b_graph=branch_b_graph,
    )

    assert result.summary.total == 1
    assert result.summary.has_conflicts is True
    assert len(result.conflicts) == 1
    assert result.conflicts[0].rule_id == "R6_RENAME_VS_MODIFY"


def test_pipeline_returns_expected_operations_for_branches():
    base_graph = build_base_graph()
    branch_a_graph = build_branch_a_graph()
    branch_b_graph = build_branch_b_graph()

    artifacts = analyze_merge_with_artifacts(
        base_graph=base_graph,
        branch_a_graph=branch_a_graph,
        branch_b_graph=branch_b_graph,
    )

    ops_a = artifacts.result.operations_a
    ops_b = artifacts.result.operations_b

    op_types_a = {type(op).__name__ for op in ops_a}
    op_types_b = {type(op).__name__ for op in ops_b}

    assert "RenameOperation" in op_types_a
    assert "ModifyOperation" in op_types_b


def test_pipeline_branch_b_has_modify_for_email():
    base_graph = build_base_graph()
    branch_a_graph = build_branch_a_graph()
    branch_b_graph = build_branch_b_graph()

    artifacts = analyze_merge_with_artifacts(
        base_graph=base_graph,
        branch_a_graph=branch_a_graph,
        branch_b_graph=branch_b_graph,
    )

    modify_ops_b = [
        op for op in artifacts.result.operations_b
        if type(op).__name__ == "ModifyOperation"
    ]

    assert len(modify_ops_b) == 1
    assert modify_ops_b[0].target == "public.users.email"
    assert ("nullable", True) in modify_ops_b[0].delta


def test_pipeline_branch_a_has_rename_for_email():
    base_graph = build_base_graph()
    branch_a_graph = build_branch_a_graph()
    branch_b_graph = build_branch_b_graph()

    artifacts = analyze_merge_with_artifacts(
        base_graph=base_graph,
        branch_a_graph=branch_a_graph,
        branch_b_graph=branch_b_graph,
    )

    rename_ops_a = [
        op for op in artifacts.result.operations_a
        if type(op).__name__ == "RenameOperation"
    ]

    assert len(rename_ops_a) == 1
    assert rename_ops_a[0].target == "public.users.email"
    assert rename_ops_a[0].new_name == "email_address"


def test_pipeline_exposes_branch_artifacts():
    base_graph = build_base_graph()
    branch_a_graph = build_branch_a_graph()
    branch_b_graph = build_branch_b_graph()

    artifacts = analyze_merge_with_artifacts(
        base_graph=base_graph,
        branch_a_graph=branch_a_graph,
        branch_b_graph=branch_b_graph,
    )

    assert artifacts.branch_a.matching is not None
    assert artifacts.branch_a.delta_details is not None
    assert artifacts.branch_a.reconstruction is not None

    assert artifacts.branch_b.matching is not None
    assert artifacts.branch_b.delta_details is not None
    assert artifacts.branch_b.reconstruction is not None

    assert artifacts.detection is not None
    assert artifacts.result is not None


def test_pipeline_branch_a_rename_has_no_edge_noise():
    base_graph = build_base_graph()
    branch_a_graph = build_branch_a_graph()
    branch_b_graph = build_branch_b_graph()

    artifacts = analyze_merge_with_artifacts(
        base_graph=base_graph,
        branch_a_graph=branch_a_graph,
        branch_b_graph=branch_b_graph,
    )

    noisy_ops = [
        op for op in artifacts.result.operations_a
        if hasattr(op, "target") and (
            op.target.startswith("contains:")
            or op.target.startswith("typedAs:")
        )
    ]

    assert len(noisy_ops) == 0
