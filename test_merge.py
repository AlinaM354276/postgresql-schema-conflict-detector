from dataclasses import dataclass
from typing import Optional

from src.conflict_detector.pipeline.analyze_three_way_merge_from_ddl import (
    analyze_three_way_merge_from_ddl,
)


@dataclass
class Case:
    name: str
    base: str
    branch_a: str
    branch_b: str
    expected_merge_defined: Optional[bool] = None
    expected_rule_ids: tuple[str, ...] = ()


CASES = [
    Case(
        name="01 Rename + Modify compatible",
        base="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text NOT NULL
        );
        """,
        branch_a="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email_address text NOT NULL
        );
        """,
        branch_b="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text
        );
        """,
        expected_merge_defined=True,
    ),
    Case(
        name="02 Drop vs Modify conflict",
        base="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text NOT NULL
        );
        """,
        branch_a="""
        CREATE TABLE users (
            id integer PRIMARY KEY
        );
        """,
        branch_b="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text
        );
        """,
        expected_merge_defined=False,
        expected_rule_ids=("R1_DROP_VS_MODIFY",),
    ),
    Case(
        name="03 Rename vs Rename different",
        base="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text NOT NULL
        );
        """,
        branch_a="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email_address text NOT NULL
        );
        """,
        branch_b="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            contact_email text NOT NULL
        );
        """,
        expected_merge_defined=False,
        expected_rule_ids=("R3_RENAME_VS_RENAME",),
    ),
    Case(
        name="04 Same Rename both branches",
        base="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text NOT NULL
        );
        """,
        branch_a="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email_address text NOT NULL
        );
        """,
        branch_b="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email_address text NOT NULL
        );
        """,
        expected_merge_defined=True,
    ),
    Case(
        name="05 Same Modify both branches",
        base="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text NOT NULL
        );
        """,
        branch_a="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text
        );
        """,
        branch_b="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text
        );
        """,
        expected_merge_defined=True,
    ),
    Case(
        name="06 Add column one branch",
        base="""
        CREATE TABLE users (
            id integer PRIMARY KEY
        );
        """,
        branch_a="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text
        );
        """,
        branch_b="""
        CREATE TABLE users (
            id integer PRIMARY KEY
        );
        """,
        expected_merge_defined=True,
    ),
    Case(
        name="07 Same Add both branches",
        base="""
        CREATE TABLE users (
            id integer PRIMARY KEY
        );
        """,
        branch_a="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text
        );
        """,
        branch_b="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text
        );
        """,
        expected_merge_defined=True,
    ),
    Case(
        name="08 Different Add both branches",
        base="""
        CREATE TABLE users (
            id integer PRIMARY KEY
        );
        """,
        branch_a="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text NOT NULL
        );
        """,
        branch_b="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text
        );
        """,
        expected_merge_defined=False,
        expected_rule_ids=("R5_ADD_VS_ADD",),
    ),
    Case(
        name="09 Add FK ReferenceOperation",
        base="""
        CREATE TABLE users (
            id integer PRIMARY KEY
        );

        CREATE TABLE orders (
            id integer PRIMARY KEY,
            user_id integer
        );
        """,
        branch_a="""
        CREATE TABLE users (
            id integer PRIMARY KEY
        );

        CREATE TABLE orders (
            id integer PRIMARY KEY,
            user_id integer REFERENCES users(id)
        );
        """,
        branch_b="""
        CREATE TABLE users (
            id integer PRIMARY KEY
        );

        CREATE TABLE orders (
            id integer PRIMARY KEY,
            user_id integer
        );
        """,
        expected_merge_defined=True,
    ),
]


def run_case(case: Case) -> bool:
    result = analyze_three_way_merge_from_ddl(
        base_ddl=case.base,
        branch_a_ddl=case.branch_a,
        branch_b_ddl=case.branch_b,
    )

    actual_merge_defined = result.summary.merge_defined
    actual_rule_ids = {conflict.rule_id for conflict in result.rule_conflicts}

    ok = True
    errors = []

    if case.expected_merge_defined is not None:
        if actual_merge_defined != case.expected_merge_defined:
            ok = False
            errors.append(
                f"merge_defined expected {case.expected_merge_defined}, "
                f"got {actual_merge_defined}"
            )

    for rule_id in case.expected_rule_ids:
        if rule_id not in actual_rule_ids:
            ok = False
            errors.append(f"missing expected rule: {rule_id}")

    status = "PASS" if ok else "FAIL"

    print(f"[{status}] {case.name}")
    print(f"       merge_defined={actual_merge_defined}")
    print(f"       rules={sorted(actual_rule_ids)}")

    if errors:
        for error in errors:
            print(f"       ERROR: {error}")

    return ok


def main() -> None:
    passed = 0

    for case in CASES:
        if run_case(case):
            passed += 1

    total = len(CASES)
    print()
    print(f"Passed: {passed}/{total}")

    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
