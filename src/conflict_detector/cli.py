from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter

from src.conflict_detector.parser.ddl_parser import parse_ddl_to_graph
from src.conflict_detector.pipeline.analyze_three_way_merge import (
    analyze_three_way_merge_with_artifacts,
)
from src.conflict_detector.pipeline.analyze_repo import analyze_repo
from src.conflict_detector.reporting.json_report import save_json_report
from src.conflict_detector.reporting.severity import DEFAULT_IMPACT_THRESHOLD
from src.conflict_detector.reporting.text_report import build_text_report
from src.conflict_detector.visualization.graphviz_export import export_graph


def read_file(path: str | Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="schema-merge-analyzer",
        description="Semantic analysis of schema merge conflicts",
    )

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        "--base",
        help="Path to base schema DDL file",
    )

    group.add_argument(
        "--repo",
        help="Path to git repository",
    )

    parser.add_argument("--a", help="Path to branch A DDL file")
    parser.add_argument("--b", help="Path to branch B DDL file")

    parser.add_argument("--branch-a", help="Branch A name")
    parser.add_argument("--branch-b", help="Branch B name")

    parser.add_argument("--out", default=".", help="Output directory")
    parser.add_argument("--text-name", default="report.txt")
    parser.add_argument("--json-name", default="report.json")
    parser.add_argument("--quiet", action="store_true")

    parser.add_argument(
        "--no-graphs",
        action="store_true",
        help="Disable Graphviz DOT/PNG schema graph export",
    )

    parser.add_argument(
        "--impact-threshold",
        type=int,
        default=DEFAULT_IMPACT_THRESHOLD,
        help="Impact size threshold for severity escalation",
    )

    args = parser.parse_args()

    started_at = perf_counter()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    repo_path: str | None = None
    branch_a: str | None = None
    branch_b: str | None = None

    if args.base:
        if not args.a or not args.b:
            parser.error("--a and --b are required when using --base")

        base_ddl = read_file(args.base)
        a_ddl = read_file(args.a)
        b_ddl = read_file(args.b)

        base_graph = parse_ddl_to_graph(base_ddl)
        branch_a_graph = parse_ddl_to_graph(a_ddl)
        branch_b_graph = parse_ddl_to_graph(b_ddl)

        artifacts = analyze_three_way_merge_with_artifacts(
            base_graph=base_graph,
            branch_a_graph=branch_a_graph,
            branch_b_graph=branch_b_graph,
        )

        result = artifacts.result

        if not args.no_graphs:
            export_graph(
                base_graph,
                out_dir / "base_graph",
                "Base schema graph S0",
            )

            export_graph(
                branch_a_graph,
                out_dir / "branch_a_graph",
                "Branch A schema graph SA",
                reference_graph=base_graph,
                operations=artifacts.result.operations_a,
                conflicts=artifacts.result.rule_conflicts,
            )

            export_graph(
                branch_b_graph,
                out_dir / "branch_b_graph",
                "Branch B schema graph SB",
                reference_graph=base_graph,
                operations=artifacts.result.operations_b,
                conflicts=artifacts.result.rule_conflicts,
            )

            path_ab = artifacts.result.merge_attempt.path_ab
            path_ba = artifacts.result.merge_attempt.path_ba

            if (
                    path_ab.graph is not None
                    and path_ab.is_constructed
                    and path_ab.invariant_result.is_valid()
            ):
                export_graph(
                    path_ab.graph,
                    out_dir / "merge_ab_graph",
                    "Valid merge path AB: DeltaB(DeltaA(S0))",
                    conflicts=artifacts.result.rule_conflicts
                              + artifacts.result.merge_attempt.conflicts,
                )

            if (
                    path_ba.graph is not None
                    and path_ba.is_constructed
                    and path_ba.invariant_result.is_valid()
            ):
                export_graph(
                    path_ba.graph,
                    out_dir / "merge_ba_graph",
                    "Valid merge path BA: DeltaA(DeltaB(S0))",
                    conflicts=artifacts.result.rule_conflicts
                              + artifacts.result.merge_attempt.conflicts,
                )

    else:
        if not args.branch_a or not args.branch_b:
            parser.error("--branch-a and --branch-b are required when using --repo")

        repo_path = str(args.repo)
        branch_a = args.branch_a
        branch_b = args.branch_b

        result = analyze_repo(
            repo_path=args.repo,
            branch_a=args.branch_a,
            branch_b=args.branch_b,
        )

    execution_time_seconds = perf_counter() - started_at

    json_path = out_dir / args.json_name
    text_path = out_dir / args.text_name

    save_json_report(
        result,
        json_path,
        repo_path=repo_path,
        branch_a=branch_a,
        branch_b=branch_b,
        execution_time_seconds=execution_time_seconds,
        impact_threshold=args.impact_threshold,
    )

    text_report = build_text_report(
        result,
        repo_path=repo_path,
        branch_a=branch_a,
        branch_b=branch_b,
        execution_time_seconds=execution_time_seconds,
        impact_threshold=args.impact_threshold,
    )

    with open(text_path, "w", encoding="utf-8") as f:
        f.write(text_report)

    if not args.quiet:
        print(text_report)
        print(f"\nReports saved to: {out_dir}")

        if args.base and not args.no_graphs:
            print("Schema graphs saved:")
            print(f"- {out_dir / 'base_graph.dot'}")
            print(f"- {out_dir / 'branch_a_graph.dot'}")
            print(f"- {out_dir / 'branch_b_graph.dot'}")


if __name__ == "__main__":
    main()
