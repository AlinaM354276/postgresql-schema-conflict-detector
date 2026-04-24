from __future__ import annotations

from src.conflict_detector.pipeline.analyze_three_way_merge_from_ddl import (
    analyze_three_way_merge_from_ddl,
)
from src.conflict_detector.reporting.json_report import build_json_report

from src.conflict_detector.reporting.json_report import save_json_report


BASE_DDL = """
CREATE TABLE users (
    id integer PRIMARY KEY,
    email text NOT NULL
);
"""

BRANCH_A_DDL = """
CREATE TABLE users (
    id integer PRIMARY KEY,
    email_address text NOT NULL
);
"""

BRANCH_B_DDL = """
CREATE TABLE users (
    id integer PRIMARY KEY,
    email text
);
"""


def main():
    result = analyze_three_way_merge_from_ddl(
        base_ddl=BASE_DDL,
        branch_a_ddl=BRANCH_A_DDL,
        branch_b_ddl=BRANCH_B_DDL,
    )

    print(build_json_report(result))

    output_path = "report.json"
    save_json_report(result, output_path)

    print(f"Report saved to {output_path}")


if __name__ == "__main__":
    main()
