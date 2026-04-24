from __future__ import annotations

from src.conflict_detector.core.result import ThreeWayMergeAnalysisResult
from src.conflict_detector.parser.ddl_parser import parse_ddl_to_graph
from src.conflict_detector.pipeline.analyze_three_way_merge import (
    analyze_three_way_merge,
)


def analyze_three_way_merge_from_ddl(
    base_ddl: str,
    branch_a_ddl: str,
    branch_b_ddl: str,
) -> ThreeWayMergeAnalysisResult:
    base_graph = parse_ddl_to_graph(base_ddl)
    branch_a_graph = parse_ddl_to_graph(branch_a_ddl)
    branch_b_graph = parse_ddl_to_graph(branch_b_ddl)

    return analyze_three_way_merge(
        base_graph=base_graph,
        branch_a_graph=branch_a_graph,
        branch_b_graph=branch_b_graph,
    )
