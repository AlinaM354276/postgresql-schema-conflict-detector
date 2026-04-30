from __future__ import annotations

from pathlib import Path

from src.conflict_detector.pipeline.analyze_three_way_merge_from_dirs import (
    analyze_three_way_merge_from_dirs,
)


def write_schema(dir_path: Path, content: str):
    file = dir_path / "schema.sql"
    file.write_text(content, encoding="utf-8")


def test_analyze_three_way_merge_from_dirs():
    # pytest injects tmp_path only if argument exists, so keep helper separate
    pass


def test_analyze_three_way_merge_from_dirs_compatible_rename_modify(tmp_path: Path):
    base_dir = tmp_path / "base"
    a_dir = tmp_path / "a"
    b_dir = tmp_path / "b"

    base_dir.mkdir()
    a_dir.mkdir()
    b_dir.mkdir()

    write_schema(
        base_dir,
        """
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text NOT NULL
        );
        """,
    )

    write_schema(
        a_dir,
        """
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email_address text NOT NULL
        );
        """,
    )

    write_schema(
        b_dir,
        """
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text
        );
        """,
    )

    result = analyze_three_way_merge_from_dirs(
        base_dir=base_dir,
        branch_a_dir=a_dir,
        branch_b_dir=b_dir,
    )

    assert len(result.rule_conflicts) == 0
    assert result.merge_attempt.is_defined is True
    assert result.summary.has_any_conflicts is False
