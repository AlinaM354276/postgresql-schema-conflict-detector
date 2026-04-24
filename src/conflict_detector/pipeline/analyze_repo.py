from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

from src.conflict_detector.core.result import ThreeWayMergeAnalysisResult
from src.conflict_detector.extract.git_extract import extract_schemas_from_directories
from src.conflict_detector.pipeline.analyze_three_way_merge_from_ddl import (
    analyze_three_way_merge_from_ddl,
)
from src.conflict_detector.reporting.reporter import build_report


def analyze_repo(
    base_dir: str | Path,
    branch_a_dir: str | Path,
    branch_b_dir: str | Path,
) -> ThreeWayMergeAnalysisResult:
    """
    Repo-level analysis pipeline.

    Шаги:
    1. Извлечь DDL из трёх директорий.
    2. Выполнить three-way merge analysis.
    3. Вернуть структурированный результат анализа.
    """
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


def analyze_repo_to_report(
    base_dir: str | Path,
    branch_a_dir: str | Path,
    branch_b_dir: str | Path,
) -> Dict[str, Any]:
    """
    Repo-level pipeline с готовым сериализованным report.
    """
    result = analyze_repo(
        base_dir=base_dir,
        branch_a_dir=branch_a_dir,
        branch_b_dir=branch_b_dir,
    )
    return build_report(result)
