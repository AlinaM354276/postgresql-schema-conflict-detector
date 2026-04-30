from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, Dict

from src.conflict_detector.core.result import ThreeWayMergeAnalysisResult
from src.conflict_detector.extract.git_extractor import (
    extract_three_schemas_from_git,
)
from src.conflict_detector.pipeline.analyze_three_way_merge_from_ddl import (
    analyze_three_way_merge_from_ddl,
)
from src.conflict_detector.reporting.reporter import build_report
from src.conflict_detector.reporting.severity import DEFAULT_IMPACT_THRESHOLD


def analyze_repo(
    repo_path: str | Path,
    branch_a: str,
    branch_b: str,
) -> ThreeWayMergeAnalysisResult:
    extracted = extract_three_schemas_from_git(
        repo_path=repo_path,
        branch_a=branch_a,
        branch_b=branch_b,
    )

    return analyze_three_way_merge_from_ddl(
        base_ddl=extracted.base_ddl,
        branch_a_ddl=extracted.branch_a_ddl,
        branch_b_ddl=extracted.branch_b_ddl,
    )


def analyze_repo_to_report(
    repo_path: str | Path,
    branch_a: str,
    branch_b: str,
    *,
    impact_threshold: int = DEFAULT_IMPACT_THRESHOLD,
) -> Dict[str, Any]:
    started_at = perf_counter()

    result = analyze_repo(
        repo_path=repo_path,
        branch_a=branch_a,
        branch_b=branch_b,
    )

    execution_time_seconds = perf_counter() - started_at

    return build_report(
        result,
        repo_path=str(repo_path),
        branch_a=branch_a,
        branch_b=branch_b,
        execution_time_seconds=execution_time_seconds,
        impact_threshold=impact_threshold,
    )
