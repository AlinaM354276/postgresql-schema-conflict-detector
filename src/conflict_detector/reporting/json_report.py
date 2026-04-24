from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from src.conflict_detector.core.result import ThreeWayMergeAnalysisResult
from src.conflict_detector.reporting.reporter import build_report


def build_json_report(result: ThreeWayMergeAnalysisResult, *, indent: int = 2) -> str:
    report = build_report(result)
    return json.dumps(report, ensure_ascii=False, indent=indent)


def save_json_report(
    result: ThreeWayMergeAnalysisResult,
    output_path: str | Path,
    *,
    indent: int = 2,
) -> Path:
    path = Path(output_path)
    payload = build_json_report(result, indent=indent)
    path.write_text(payload, encoding="utf-8")
    return path
