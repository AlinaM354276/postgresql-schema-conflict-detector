from __future__ import annotations

from src.conflict_detector.pipeline.analyze_three_way_merge_from_ddl import (
    analyze_three_way_merge_from_ddl,
)


def test_analyze_three_way_merge_from_ddl_compatible_rename_vs_modify():
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

    result = analyze_three_way_merge_from_ddl(
        base_ddl=base_ddl,
        branch_a_ddl=branch_a_ddl,
        branch_b_ddl=branch_b_ddl,
    )

    assert len(result.rule_conflicts) == 0
    assert result.merge_attempt is not None
    assert result.merge_attempt.is_defined is True
    assert result.summary.has_any_conflicts is False


def test_analyze_three_way_merge_from_ddl_defined_case():
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
        id integer,
        email text NOT NULL
    );
    """

    result = analyze_three_way_merge_from_ddl(
        base_ddl=base_ddl,
        branch_a_ddl=branch_a_ddl,
        branch_b_ddl=branch_b_ddl,
    )

    assert result.merge_attempt is not None
    assert result.merge_attempt.is_defined is True
    assert result.merge_attempt.merged_graph is not None
