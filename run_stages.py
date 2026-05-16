from pathlib import Path

from src.conflict_detector.parser.ddl_parser import parse_ddl_to_graph
from src.conflict_detector.pipeline.analyze_three_way_merge import (
    analyze_three_way_merge_with_artifacts,
)


def read_sql(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def print_operations(title, operations):
    print("\n" + title)
    print("-" * len(title))

    if not operations:
        print("No operations.")
        return

    for op in operations:
        print(f"- {op}")


def print_conflicts(title, conflicts):
    print("\n" + title)
    print("-" * len(title))

    if not conflicts:
        print("No conflicts.")
        return

    for conflict in conflicts:
        print(f"- [{conflict.severity.value}] {conflict.rule_id}")
        print(f"  {conflict.message}")
        print(f"  Objects: {list(conflict.object_ids)}")


def main():
    base_sql = read_sql("examples/r5/base/schema.sql")
    branch_a_sql = read_sql("examples/r5/branch_a/schema.sql")
    branch_b_sql = read_sql("examples/r5/branch_b/schema.sql")

    print("STAGE 1. Build schema graphs")
    print("----------------------------")

    base_graph = parse_ddl_to_graph(base_sql)
    branch_a_graph = parse_ddl_to_graph(branch_a_sql)
    branch_b_graph = parse_ddl_to_graph(branch_b_sql)

    print(f"S0: vertices={len(base_graph.vertices)}, edges={len(base_graph.edges)}")
    print(f"SA: vertices={len(branch_a_graph.vertices)}, edges={len(branch_a_graph.edges)}")
    print(f"SB: vertices={len(branch_b_graph.vertices)}, edges={len(branch_b_graph.edges)}")

    artifacts = analyze_three_way_merge_with_artifacts(
        base_graph=base_graph,
        branch_a_graph=branch_a_graph,
        branch_b_graph=branch_b_graph,
    )

    print("\nSTAGE 2. Reconstruct operations")
    print("-------------------------------")

    print_operations(
        "Delta A = Reconstruct(S0, SA)",
        artifacts.branch_a.reconstruction.operations,
    )

    print_operations(
        "Delta B = Reconstruct(S0, SB)",
        artifacts.branch_b.reconstruction.operations,
    )

    print("\nSTAGE 3. Detect conflicts")
    print("-------------------------")

    print_conflicts(
        "Rule conflicts = Conflicts(Delta A, Delta B)",
        artifacts.detection.conflicts,
    )

    print("\nSTAGE 4. Merge analysis")
    print("-----------------------")

    merge = artifacts.merge_attempt

    print(f"Merge defined: {merge.is_defined}")
    print(f"Commutative: {merge.is_commutative}")
    print(f"Error: {merge.error_message}")

    print("\nPath AB = DeltaB(DeltaA(S0))")
    print(f"constructed: {merge.path_ab.is_constructed}")
    print(f"invariant valid: {merge.path_ab.invariant_result.is_valid()}")
    print(f"error: {merge.path_ab.error_message}")

    print("\nPath BA = DeltaA(DeltaB(S0))")
    print(f"constructed: {merge.path_ba.is_constructed}")
    print(f"invariant valid: {merge.path_ba.invariant_result.is_valid()}")
    print(f"error: {merge.path_ba.error_message}")

    print_conflicts(
        "Merge-level conflicts",
        merge.conflicts,
    )


if __name__ == "__main__":
    main()
