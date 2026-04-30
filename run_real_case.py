from src.conflict_detector.pipeline.analyze_repo import analyze_repo
from src.conflict_detector.reporting.json_report import save_json_report

result = analyze_repo(
    base_dir="examples/real_case/base",
    branch_a_dir="examples/real_case/branch_a",
    branch_b_dir="examples/real_case/branch_b",
)

save_json_report(result, "real_case_report.json")

print("merge defined:", result.summary.merge_defined)
print("rule conflicts:", result.summary.total_rule_conflicts)
print("has conflicts:", result.summary.has_any_conflicts)
print("report saved to real_case_report.json")
