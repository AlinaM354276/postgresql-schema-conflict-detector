from src.conflict_detector.pipeline.analyze_repo import analyze_repo
from src.conflict_detector.reporting.json_report import save_json_report

result = analyze_repo(
    base_dir="examples/r1/base",
    branch_a_dir="examples/r1/branch_a",
    branch_b_dir="examples/r1/branch_b",
)

save_json_report(result, "conflict_case_report.json")

print("merge defined:", result.summary.merge_defined)
print("rule conflicts:", result.summary.total_rule_conflicts)
print("has conflicts:", result.summary.has_any_conflicts)

for conflict in result.rule_conflicts:
    print(conflict.rule_id, conflict.severity.value, conflict.message)

print("report saved to conflict_case_report.json")
