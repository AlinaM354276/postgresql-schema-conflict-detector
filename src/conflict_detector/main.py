from __future__ import annotations

from pprint import pprint

from src.conflict_detector.graph.builders import build_schema_graph
from src.conflict_detector.pipeline.analyze_merge import analyze_merge_with_artifacts


def build_base_graph():
    builder = build_schema_graph()

    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email", data_type="text", nullable=False)

    return builder.build()


def build_branch_a_graph():
    """
    Ветка A:
    users.email -> users.email_address
    Это rename.
    """
    builder = build_schema_graph()

    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column(
        "users",
        "email_address",
        data_type="text",
        nullable=False,
    )

    return builder.build()


def build_branch_b_graph():
    """
    Ветка B:
    users.email меняется по атрибутам:
    nullable=False -> nullable=True
    Это modify.
    """
    builder = build_schema_graph()

    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column(
        "users",
        "email",
        data_type="text",
        nullable=True,
    )

    return builder.build()


def print_operations(title: str, operations):
    print(f"\n{title}")
    print("-" * len(title))
    for op in operations:
        print(op)


def print_conflicts(conflicts):
    print("\nConflicts")
    print("---------")
    if not conflicts:
        print("No conflicts found.")
        return

    for idx, conflict in enumerate(conflicts, start=1):
        print(f"{idx}. [{conflict.severity.value}] {conflict.rule_id}")
        print(f"   message: {conflict.message}")
        print(f"   objects: {conflict.object_ids}")
        if conflict.operation_a is not None:
            print(f"   op_a: {conflict.operation_a}")
        if conflict.operation_b is not None:
            print(f"   op_b: {conflict.operation_b}")


def print_summary(summary):
    print("\nSummary")
    print("-------")
    print(f"total conflicts: {summary.total}")
    print(f"has conflicts: {summary.has_conflicts}")
    print(f"has critical: {summary.has_critical}")
    print("by severity:")
    for level, count in summary.by_severity.items():
        print(f"  {level.value}: {count}")


def main():
    base_graph = build_base_graph()
    branch_a_graph = build_branch_a_graph()
    branch_b_graph = build_branch_b_graph()

    artifacts = analyze_merge_with_artifacts(
        base_graph=base_graph,
        branch_a_graph=branch_a_graph,
        branch_b_graph=branch_b_graph,
    )

    print("\n=== BRANCH A: MATCHING ===")
    pprint(artifacts.branch_a.matching.vertex_matching.left_to_right)
    pprint(artifacts.branch_a.matching.edge_matching.left_to_right)

    print("\n=== BRANCH A: DELTA ===")
    pprint(artifacts.branch_a.delta_details)

    print("\n=== BRANCH B: MATCHING ===")
    pprint(artifacts.branch_b.matching.vertex_matching.left_to_right)
    pprint(artifacts.branch_b.matching.edge_matching.left_to_right)

    print("\n=== BRANCH B: DELTA ===")
    pprint(artifacts.branch_b.delta_details)

    print_operations("Operations A", artifacts.result.operations_a)
    print_operations("Operations B", artifacts.result.operations_b)
    print_conflicts(artifacts.result.conflicts)
    print_summary(artifacts.result.summary)


if __name__ == "__main__":
    main()