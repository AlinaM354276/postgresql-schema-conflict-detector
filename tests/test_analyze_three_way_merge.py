from __future__ import annotations

from src.conflict_detector.graph.builders import build_schema_graph
from src.conflict_detector.pipeline.analyze_three_way_merge import (
    analyze_three_way_merge,
    analyze_three_way_merge_with_artifacts,
)


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


def test_analyze_three_way_merge_returns_rule_conflicts_and_merge_attempt():
    base_graph = build_base_graph()
    branch_a_graph = build_branch_a_graph()
    branch_b_graph = build_branch_b_graph()

    result = analyze_three_way_merge(
        base_graph=base_graph,
        branch_a_graph=branch_a_graph,
        branch_b_graph=branch_b_graph,
    )

    assert len(result.rule_conflicts) == 1
    assert result.rule_conflicts[0].rule_id == "R6_RENAME_VS_MODIFY"

    assert result.merge_attempt is not None
    assert result.merge_attempt.is_defined is False
    assert len(result.merge_attempt.conflicts) == 1
    assert result.merge_attempt.conflicts[0].rule_id == "M1_MERGE_UNDEFINED"

    assert result.summary.total_rule_conflicts == 1
    assert result.summary.merge_defined is False
    assert result.summary.has_any_conflicts is True


def test_analyze_three_way_merge_with_artifacts_exposes_all_layers():
    base_graph = build_base_graph()
    branch_a_graph = build_branch_a_graph()
    branch_b_graph = build_branch_b_graph()

    artifacts = analyze_three_way_merge_with_artifacts(
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
    assert artifacts.merge_attempt is not None
    assert artifacts.result is not None


def test_analyze_three_way_merge_defined_case():
    base_graph = build_base_graph()

    # Ветка A: rename email -> email_address
    builder_a = build_schema_graph()
    builder_a.add_table("users")
    builder_a.add_column("users", "id", data_type="integer", nullable=False)
    builder_a.add_column("users", "email_address", data_type="text", nullable=False)
    branch_a_graph = builder_a.build()

    # Ветка B: modify независимого объекта users.id
    builder_b = build_schema_graph()
    builder_b.add_table("users")
    builder_b.add_column("users", "id", data_type="integer", nullable=True)
    builder_b.add_column("users", "email", data_type="text", nullable=False)
    branch_b_graph = builder_b.build()

    result = analyze_three_way_merge(
        base_graph=base_graph,
        branch_a_graph=branch_a_graph,
        branch_b_graph=branch_b_graph,
    )

    assert result.merge_attempt is not None
    assert result.merge_attempt.is_defined is True
    assert result.merge_attempt.merged_graph is not None
    assert result.merge_attempt.invariant_result.is_valid() is True

    merged_email = result.merge_attempt.merged_graph.get_vertex("public.users.email_address")
    assert merged_email is not None

    merged_id = result.merge_attempt.merged_graph.get_vertex("public.users.id")
    assert merged_id is not None
    assert merged_id.attr_dict()["nullable"] is True
