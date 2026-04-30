from __future__ import annotations

from src.conflict_detector.graph.builders import build_schema_graph
from src.conflict_detector.pipeline.analyze_three_way_merge import (
    analyze_three_way_merge,
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


def test_analyze_three_way_merge_compatible_rename_and_modify():
    result = analyze_three_way_merge(
        base_graph=build_base_graph(),
        branch_a_graph=build_branch_a_graph(),
        branch_b_graph=build_branch_b_graph(),
    )

    assert len(result.rule_conflicts) == 0
    assert result.merge_attempt is not None
    assert result.merge_attempt.is_defined is True
    assert result.merge_attempt.merged_graph is not None
    assert result.summary.has_any_conflicts is False

    merged_email = result.merge_attempt.merged_graph.get_vertex(
        "public.users.email_address"
    )
    assert merged_email is not None
    assert merged_email.attr_dict()["nullable"] is True


def test_analyze_three_way_merge_with_artifacts_exposes_all_layers():
    result = analyze_three_way_merge(
        base_graph=build_base_graph(),
        branch_a_graph=build_branch_a_graph(),
        branch_b_graph=build_branch_b_graph(),
    )

    assert result.operations_a
    assert result.operations_b
    assert result.merge_attempt is not None
    assert result.summary is not None


def test_analyze_three_way_merge_defined_case():
    base_graph = build_base_graph()

    builder_a = build_schema_graph()
    builder_a.add_table("users")
    builder_a.add_column("users", "id", data_type="integer", nullable=False)
    builder_a.add_column("users", "email_address", data_type="text", nullable=False)
    branch_a_graph = builder_a.build()

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

    merged_email = result.merge_attempt.merged_graph.get_vertex(
        "public.users.email_address"
    )
    assert merged_email is not None

    merged_id = result.merge_attempt.merged_graph.get_vertex("public.users.id")
    assert merged_id is not None
    assert merged_id.attr_dict()["nullable"] is True
