from __future__ import annotations

from io import StringIO
from typing import Any

from src.conflict_detector.core.models import Conflict
from src.conflict_detector.core.result import ThreeWayMergeAnalysisResult
from src.conflict_detector.reporting.explain import explain_conflict
from src.conflict_detector.reporting.operation_explain import explain_operation
from src.conflict_detector.reporting.reporter import build_report
from src.conflict_detector.reporting.severity import DEFAULT_IMPACT_THRESHOLD


def _format_conflict(conflict: Conflict) -> str:
    explanation = explain_conflict(conflict)

    buffer = StringIO()
    buffer.write(f"- [{conflict.severity.value}] {explanation['title']}\n")
    buffer.write(f"  Rule: {conflict.rule_id}\n")
    buffer.write(f"  Type: {explanation['type']}\n")
    buffer.write(f"  Objects: {conflict.object_ids}\n")
    buffer.write(f"  Description: {explanation['description']}\n")
    buffer.write(f"  Reason: {explanation['reason']}\n")
    buffer.write(f"  Consequence: {explanation['consequence']}\n")

    if conflict.metadata:
        buffer.write(f"  Metadata: {conflict.metadata}\n")

    return buffer.getvalue()


def _format_operation(op: object) -> str:
    try:
        explanation = explain_operation(op)
        return f"- {explanation}\n"
    except Exception:
        return f"- {op}\n"


def _format_operations_section(title: str, operations: tuple) -> str:
    buffer = StringIO()
    buffer.write(title + "\n")
    buffer.write("-" * len(title) + "\n")

    if operations:
        for op in operations:
            buffer.write(_format_operation(op))
    else:
        buffer.write("No operations.\n")

    return buffer.getvalue()


def _format_metadata(metadata: dict[str, Any]) -> str:
    buffer = StringIO()
    buffer.write("Metadata\n")
    buffer.write("--------\n")
    buffer.write(f"timestamp: {metadata.get('timestamp')}\n")
    buffer.write(f"repo: {metadata.get('repo')}\n")
    buffer.write(f"branch A: {metadata.get('branch_a')}\n")
    buffer.write(f"branch B: {metadata.get('branch_b')}\n")
    buffer.write(f"execution time seconds: {metadata.get('execution_time_seconds')}\n")
    buffer.write(f"impact threshold: {metadata.get('impact_threshold')}\n")
    return buffer.getvalue()


def _format_severity_distribution(distribution: dict[str, int]) -> str:
    buffer = StringIO()
    buffer.write("Severity Distribution\n")
    buffer.write("---------------------\n")

    for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        buffer.write(f"{level}: {distribution.get(level, 0)}\n")

    return buffer.getvalue()


def _format_report_conflict(conflict: dict[str, Any]) -> str:
    buffer = StringIO()
    buffer.write(f"- [{conflict.get('severity')}] {conflict.get('rule_id')}\n")
    buffer.write(f"  Message: {conflict.get('message')}\n")
    buffer.write(f"  Objects: {conflict.get('object_ids')}\n")

    metadata = conflict.get("metadata")
    if metadata:
        buffer.write(f"  Metadata: {metadata}\n")

    return buffer.getvalue()


def build_text_report(
    result: ThreeWayMergeAnalysisResult,
    *,
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

    buffer = StringIO()

    buffer.write("Schema Merge Conflict Analysis Report\n")
    buffer.write("=====================================\n\n")

    buffer.write(_format_metadata(report["metadata"]))
    buffer.write("\n")

    buffer.write(_format_operations_section("Operations A", result.operations_a))
    buffer.write("\n")
    buffer.write(_format_operations_section("Operations B", result.operations_b))
    buffer.write("\n")

    buffer.write("Rule Conflicts\n")
    buffer.write("--------------\n")
    if report["rule_conflicts"]:
        for conflict in report["rule_conflicts"]:
            buffer.write(_format_report_conflict(conflict))
            buffer.write("\n")
    else:
        buffer.write("No rule conflicts.\n")

    buffer.write("\nMerge Attempt\n")
    buffer.write("-------------\n")
    merge_attempt = report["merge_attempt"]
    buffer.write(f"defined: {merge_attempt['is_defined']}\n")
    buffer.write(f"commutative indicator: {merge_attempt['is_commutative']}\n")

    if merge_attempt["error_message"]:
        buffer.write(f"error: {merge_attempt['error_message']}\n")

    for label, path in merge_attempt["paths"].items():
        if path is None:
            continue

        buffer.write(f"\nPath {label}\n")
        buffer.write(f"  constructed: {path['is_constructed']}\n")
        buffer.write(f"  invariant violations: {len(path['invariant_violations'])}\n")

        if path["invariant_violations"]:
            buffer.write("  invariant violation details:\n")
            for violation in path["invariant_violations"]:
                buffer.write(
                    f"    - {violation.get('invariant_id')}: "
                    f"{violation.get('message')}; "
                    f"objects={violation.get('object_ids')}\n"
                )

        if path["error_message"]:
            buffer.write(f"  error: {path['error_message']}\n")

    if merge_attempt["merge_conflicts"]:
        buffer.write("\nMerge-level conflicts and indicators:\n")
        for conflict in merge_attempt["merge_conflicts"]:
            buffer.write(_format_report_conflict(conflict))
            buffer.write("\n")

    buffer.write("\n")
    buffer.write(_format_severity_distribution(report["severity_distribution"]))

    summary = report["summary"]

    buffer.write("\nSummary\n")
    buffer.write("-------\n")
    buffer.write(f"total rule conflicts: {summary['total_rule_conflicts']}\n")
    buffer.write(f"total merge conflicts: {summary['total_merge_conflicts']}\n")
    buffer.write(f"total conflicts: {summary['total_conflicts']}\n")
    buffer.write(f"critical conflicts: {summary['critical_conflicts']}\n")
    buffer.write(f"high conflicts: {summary['high_conflicts']}\n")
    buffer.write(f"medium conflicts: {summary['medium_conflicts']}\n")
    buffer.write(f"low conflicts: {summary['low_conflicts']}\n")
    buffer.write(f"merge defined: {summary['merge_defined']}\n")
    buffer.write(f"merge blocked: {summary['merge_blocked']}\n")
    buffer.write(f"is commutative: {summary['is_commutative']}\n")
    buffer.write(
        "invariant violations count: "
        f"{summary['invariant_violations_count']}\n"
    )
    buffer.write(f"has any conflicts: {summary['has_any_conflicts']}\n")
    buffer.write(f"has critical conflicts: {summary['has_critical']}\n")

    return buffer.getvalue()
