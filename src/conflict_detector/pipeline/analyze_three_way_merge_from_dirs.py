from __future__ import annotations

from pathlib import Path

from src.conflict_detector.core.result import ThreeWayMergeAnalysisResult
from src.conflict_detector.extract.directory_extractor import (
    extract_schemas_from_directories,
)
from src.conflict_detector.pipeline.analyze_three_way_merge_from_ddl import (
    analyze_three_way_merge_from_ddl,
)


def analyze_three_way_merge_from_dirs(
    base_dir: str | Path,
    branch_a_dir: str | Path,
    branch_b_dir: str | Path,
) -> ThreeWayMergeAnalysisResult:
    extracted = extract_schemas_from_directories(
        base_dir=base_dir,
        branch_a_dir=branch_a_dir,
        branch_b_dir=branch_b_dir,
    )

    return analyze_three_way_merge_from_ddl(
        base_ddl=extracted.base_ddl,
        branch_a_ddl=extracted.branch_a_ddl,
        branch_b_ddl=extracted.branch_b_ddl,
    )
