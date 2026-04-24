from __future__ import annotations

from io import StringIO

from src.conflict_detector.core.result import ThreeWayMergeAnalysisResult


def build_text_report(result: ThreeWayMergeAnalysisResult) -> str:
    buffer = StringIO()

    buffer.write("Schema Merge Conflict Analysis Report\n")
    buffer.write("=====================================\n\n")

    buffer.write("Operations A\n")
    buffer.write("------------\n")
    if result.operations_a:
        for op in result.operations_a:
            buffer.write(f"- {op}\n")
    else:
        buffer.write("No operations.\n")

    buffer.write("\nOperations B\n")
    buffer.write("------------\n")
    if result.operations_b:
        for op in result.operations_b:
            buffer.write(f"- {op}\n")
    else:
        buffer.write("No operations.\n")

    buffer.write("\nRule Conflicts\n")
    buffer.write("--------------\n")
    if result.rule_conflicts:
        for conflict in result.rule_conflicts:
            buffer.write(
                f"- [{conflict.severity.value}] {conflict.rule_id}: "
                f"{conflict.message}\n"
            )
            buffer.write(f"  objects: {conflict.object_ids}\n")
    else:
        buffer.write("No rule conflicts.\n")

    buffer.write("\nMerge Attempt\n")
    buffer.write("-------------\n")
    buffer.write(f"defined: {result.merge_attempt.is_defined}\n")

    if result.merge_attempt.error_message:
        buffer.write(f"error: {result.merge_attempt.error_message}\n")

    buffer.write(
        f"invariant violations: "
        f"{len(result.merge_attempt.invariant_result.violations)}\n"
    )

    if result.merge_attempt.conflicts:
        buffer.write("\nMerge-level conflicts:\n")
        for conflict in result.merge_attempt.conflicts:
            buffer.write(
                f"- [{conflict.severity.value}] {conflict.rule_id}: "
                f"{conflict.message}\n"
            )

    buffer.write("\nSummary\n")
    buffer.write("-------\n")
    buffer.write(f"total rule conflicts: {result.summary.total_rule_conflicts}\n")
    buffer.write(f"merge defined: {result.summary.merge_defined}\n")
    buffer.write(
        f"invariant violations count: "
        f"{result.summary.invariant_violations_count}\n"
    )
    buffer.write(f"has any conflicts: {result.summary.has_any_conflicts}\n")

    return buffer.getvalue()
