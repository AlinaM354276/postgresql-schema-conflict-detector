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
from src.conflict_detector.pipeline.analyze_three_way_merge_from_dirs import (
    analyze_three_way_merge_from_dirs,
)
from src.conflict_detector.reporting.reporter import build_report
from src.conflict_detector.reporting.severity import DEFAULT_IMPACT_THRESHOLD


def analyze_repo(
    repo_path: str | Path | None = None,
    branch_a: str | None = None,
    branch_b: str | None = None,
    *,
    base_dir: str | Path | None = None,
    branch_a_dir: str | Path | None = None,
    branch_b_dir: str | Path | None = None,
) -> ThreeWayMergeAnalysisResult:
    """
    Analyze schema merge either from a Git repository or from three directories.

    Git mode:
        analyze_repo(repo_path=..., branch_a=..., branch_b=...)

    Directory mode:
        analyze_repo(base_dir=..., branch_a_dir=..., branch_b_dir=...)
    """

    if base_dir is not None or branch_a_dir is not None or branch_b_dir is not None:
        if base_dir is None or branch_a_dir is None or branch_b_dir is None:
            raise ValueError(
                "Directory mode requires base_dir, branch_a_dir and branch_b_dir."
            )

        return analyze_three_way_merge_from_dirs(
            base_dir=base_dir,
            branch_a_dir=branch_a_dir,
            branch_b_dir=branch_b_dir,
        )

    if repo_path is None or branch_a is None or branch_b is None:
        raise ValueError(
            "Git mode requires repo_path, branch_a and branch_b."
        )

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
    repo_path: str | Path | None = None,
    branch_a: str | None = None,
    branch_b: str | None = None,
    *,
    base_dir: str | Path | None = None,
    branch_a_dir: str | Path | None = None,
    branch_b_dir: str | Path | None = None,
    impact_threshold: int = DEFAULT_IMPACT_THRESHOLD,
) -> Dict[str, Any]:
    started_at = perf_counter()

    result = analyze_repo(
        repo_path=repo_path,
        branch_a=branch_a,
        branch_b=branch_b,
        base_dir=base_dir,
        branch_a_dir=branch_a_dir,
        branch_b_dir=branch_b_dir,
    )

    execution_time_seconds = perf_counter() - started_at

    report_context: Dict[str, Any] = {
        "execution_time_seconds": execution_time_seconds,
        "impact_threshold": impact_threshold,
    }

    if base_dir is not None:
        report_context.update(
            {
                "repo_path": str(base_dir),
                "branch_a": str(branch_a_dir),
                "branch_b": str(branch_b_dir),
            }
        )
    else:
        report_context.update(
            {
                "repo_path": str(repo_path),
                "branch_a": branch_a,
                "branch_b": branch_b,
            }
        )

    return build_report(
        result,
        **report_context,
    )
