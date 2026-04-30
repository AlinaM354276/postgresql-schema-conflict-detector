from __future__ import annotations

from pathlib import Path

from src.conflict_detector.pipeline.analyze_repo import (
    analyze_repo,
    analyze_repo_to_report,
)


def write_schema(dir_path: Path, filename: str, content: str) -> None:
    file_path = dir_path / filename
    file_path.write_text(content, encoding="utf-8")


def test_analyze_repo_compatible_rename_vs_modify(tmp_path: Path):
    base_dir = tmp_path / "base"
    branch_a_dir = tmp_path / "branch_a"
    branch_b_dir = tmp_path / "branch_b"

    base_dir.mkdir()
    branch_a_dir.mkdir()
    branch_b_dir.mkdir()

    write_schema(
        base_dir,
        "schema.sql",
        """
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text NOT NULL
        );
        """,
    )

    write_schema(
        branch_a_dir,
        "schema.sql",
        """
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email_address text NOT NULL
        );
        """,
    )

    write_schema(
        branch_b_dir,
        "schema.sql",
        """
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text
        );
        """,
    )

    result = analyze_repo(
        base_dir=base_dir,
        branch_a_dir=branch_a_dir,
        branch_b_dir=branch_b_dir,
    )

    assert len(result.rule_conflicts) == 0
    assert result.merge_attempt.is_defined is True
    assert result.summary.has_any_conflicts is False


def test_analyze_repo_to_report_returns_serialized_structure(tmp_path: Path):
    base_dir = tmp_path / "base"
    branch_a_dir = tmp_path / "branch_a"
    branch_b_dir = tmp_path / "branch_b"

    base_dir.mkdir()
    branch_a_dir.mkdir()
    branch_b_dir.mkdir()

    write_schema(
        base_dir,
        "schema.sql",
        """
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text NOT NULL
        );
        """,
    )

    write_schema(
        branch_a_dir,
        "schema.sql",
        """
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email_address text NOT NULL
        );
        """,
    )

    write_schema(
        branch_b_dir,
        "schema.sql",
        """
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text
        );
        """,
    )

    report = analyze_repo_to_report(
        base_dir=base_dir,
        branch_a_dir=branch_a_dir,
        branch_b_dir=branch_b_dir,
    )

    assert isinstance(report, dict)
    assert "operations_a" in report
    assert "operations_b" in report
    assert "rule_conflicts" in report
    assert "merge_attempt" in report
    assert "summary" in report

    assert report["summary"]["has_any_conflicts"] is False
    assert report["summary"]["merge_defined"] is True


def test_analyze_repo_handles_multiple_sql_files(tmp_path: Path):
    base_dir = tmp_path / "base"
    branch_a_dir = tmp_path / "branch_a"
    branch_b_dir = tmp_path / "branch_b"

    base_dir.mkdir()
    branch_a_dir.mkdir()
    branch_b_dir.mkdir()

    write_schema(
        base_dir,
        "users.sql",
        """
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text NOT NULL
        );
        """,
    )

    write_schema(
        branch_a_dir,
        "users_part1.sql",
        """
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email_address text NOT NULL
        );
        """,
    )

    write_schema(
        branch_b_dir,
        "users_part1.sql",
        """
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text
        );
        """,
    )

    result = analyze_repo(
        base_dir=base_dir,
        branch_a_dir=branch_a_dir,
        branch_b_dir=branch_b_dir,
    )

    assert len(result.rule_conflicts) == 0
    assert result.merge_attempt.is_defined is True
