from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter

from src.conflict_detector.pipeline.analyze_three_way_merge_from_ddl import (
    analyze_three_way_merge_from_ddl,
)
from src.conflict_detector.pipeline.analyze_repo import analyze_repo
from src.conflict_detector.reporting.json_report import save_json_report
from src.conflict_detector.reporting.severity import DEFAULT_IMPACT_THRESHOLD
from src.conflict_detector.reporting.text_report import build_text_report


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
        "--impact-threshold",
        type=int,
        default=DEFAULT_IMPACT_THRESHOLD,
        help="Impact size threshold for severity escalation",
    )

    args = parser.parse_args()

    started_at = perf_counter()

    repo_path: str | None = None
    branch_a: str | None = None
    branch_b: str | None = None

    if args.base:
        if not args.a or not args.b:
            parser.error("--a and --b are required when using --base")

        base_ddl = read_file(args.base)
        a_ddl = read_file(args.a)
        b_ddl = read_file(args.b)

        result = analyze_three_way_merge_from_ddl(
            base_ddl=base_ddl,
            branch_a_ddl=a_ddl,
            branch_b_ddl=b_ddl,
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

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

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


if __name__ == "__main__":
    main()
