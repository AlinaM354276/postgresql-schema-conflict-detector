from __future__ import annotations

import json
from pathlib import Path

from src.conflict_detector.core.result import ThreeWayMergeAnalysisResult
from src.conflict_detector.reporting.reporter import build_report
from src.conflict_detector.reporting.severity import DEFAULT_IMPACT_THRESHOLD


def build_json_report(
    result: ThreeWayMergeAnalysisResult,
    *,
    indent: int = 2,
    repo_path: str | None = None,
    branch_a: str | None = None,
    branch_b: str | None = None,
    execution_time_seconds: float | None = None,
    impact_threshold: int = DEFAULT_IMPACT_THRESHOLD,
) -> str:
    report = build_report(
        result,
        repo_path=repo_path,
        branch_a=branch_a,
        branch_b=branch_b,
        execution_time_seconds=execution_time_seconds,
        impact_threshold=impact_threshold,
    )
    return json.dumps(report, ensure_ascii=False, indent=indent)


def save_json_report(
    result: ThreeWayMergeAnalysisResult,
    output_path: str | Path,
    *,
    indent: int = 2,
    repo_path: str | None = None,
    branch_a: str | None = None,
    branch_b: str | None = None,
    execution_time_seconds: float | None = None,
    impact_threshold: int = DEFAULT_IMPACT_THRESHOLD,
) -> Path:
    path = Path(output_path)

    payload = build_json_report(
        result,
        indent=indent,
        repo_path=repo_path,
        branch_a=branch_a,
        branch_b=branch_b,
        execution_time_seconds=execution_time_seconds,
        impact_threshold=impact_threshold,
    )

    path.write_text(payload, encoding="utf-8")
    return path
