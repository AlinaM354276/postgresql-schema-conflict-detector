from __future__ import annotations

import json

from src.conflict_detector.pipeline.analyze_three_way_merge_from_ddl import (
    analyze_three_way_merge_from_ddl,
)
from src.conflict_detector.reporting.json_report import build_json_report
from src.conflict_detector.reporting.reporter import build_report


def build_sample_result():
    base_ddl = """
    CREATE TABLE users (
        id integer PRIMARY KEY,
        email text NOT NULL
    );
    """

    branch_a_ddl = """
    CREATE TABLE users (
        id integer PRIMARY KEY,
        email_address text NOT NULL
    );
    """

    branch_b_ddl = """
    CREATE TABLE users (
        id integer PRIMARY KEY,
        email text
    );
    """

    return analyze_three_way_merge_from_ddl(
        base_ddl=base_ddl,
        branch_a_ddl=branch_a_ddl,
        branch_b_ddl=branch_b_ddl,
    )


def test_build_report_contains_main_sections():
    result = build_sample_result()
    report = build_report(result)

    assert "operations_a" in report
    assert "operations_b" in report
    assert "rule_conflicts" in report
    assert "merge_attempt" in report
    assert "summary" in report


def test_build_report_contains_expected_conflict():
    result = build_sample_result()
    report = build_report(result)

    assert len(report["rule_conflicts"]) == 1
    assert report["rule_conflicts"][0]["rule_id"] == "R6_RENAME_VS_MODIFY"

    assert report["merge_attempt"]["is_defined"] is False
    assert len(report["merge_attempt"]["merge_conflicts"]) == 1
    assert report["merge_attempt"]["merge_conflicts"][0]["rule_id"] == "M1_MERGE_UNDEFINED"


def test_build_json_report_is_valid_json():
    result = build_sample_result()
    payload = build_json_report(result)

    parsed = json.loads(payload)

    assert isinstance(parsed, dict)
    assert parsed["summary"]["merge_defined"] is False
    assert parsed["summary"]["has_any_conflicts"] is True
