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


ECOMMERCE_BASE = """
CREATE TABLE users (
    id integer PRIMARY KEY,
    email text NOT NULL,
    username text NOT NULL,
    status text NOT NULL,
    created_at text NOT NULL
);

CREATE TABLE products (
    id integer PRIMARY KEY,
    sku text NOT NULL,
    name text NOT NULL,
    price integer NOT NULL
);

CREATE TABLE orders (
    id integer PRIMARY KEY,
    user_id integer REFERENCES users(id),
    status text NOT NULL,
    created_at text NOT NULL
);

CREATE TABLE order_items (
    id integer PRIMARY KEY,
    order_id integer REFERENCES orders(id),
    product_id integer REFERENCES products(id),
    quantity integer NOT NULL
);

CREATE TABLE payments (
    id integer PRIMARY KEY,
    order_id integer REFERENCES orders(id),
    amount integer NOT NULL,
    status text NOT NULL
);

CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_items_product_id ON order_items(product_id);
"""


UNIVERSITY_BASE = """
CREATE TABLE students (
    id integer PRIMARY KEY,
    email text NOT NULL,
    full_name text NOT NULL,
    status text NOT NULL
);

CREATE TABLE teachers (
    id integer PRIMARY KEY,
    email text NOT NULL,
    full_name text NOT NULL
);

CREATE TABLE courses (
    id integer PRIMARY KEY,
    teacher_id integer REFERENCES teachers(id),
    title text NOT NULL,
    credits integer NOT NULL
);

CREATE TABLE enrollments (
    id integer PRIMARY KEY,
    student_id integer REFERENCES students(id),
    course_id integer REFERENCES courses(id),
    grade integer
);

CREATE TABLE exams (
    id integer PRIMARY KEY,
    course_id integer REFERENCES courses(id),
    exam_date text NOT NULL
);

CREATE INDEX idx_enrollments_student ON enrollments(student_id);
CREATE INDEX idx_enrollments_course ON enrollments(course_id);
"""


CASES = [
    Case(
        name="01 ALTER compatible: rename email vs drop NOT NULL",
        base=ECOMMERCE_BASE,
        branch_a=ECOMMERCE_BASE + """
        ALTER TABLE users RENAME COLUMN email TO email_address;
        """,
        branch_b=ECOMMERCE_BASE + """
        ALTER TABLE users ALTER COLUMN email DROP NOT NULL;
        """,
        expected_merge_defined=True,
    ),
    Case(
        name="02 ALTER conflict: drop column vs modify same column",
        base=ECOMMERCE_BASE,
        branch_a=ECOMMERCE_BASE + """
        ALTER TABLE users DROP COLUMN status;
        """,
        branch_b=ECOMMERCE_BASE + """
        ALTER TABLE users ALTER COLUMN status DROP NOT NULL;
        """,
        expected_merge_defined=False,
        expected_rule_ids=("R1_DROP_VS_MODIFY",),
    ),
    Case(
        name="03 ALTER conflict: rename column differently",
        base=ECOMMERCE_BASE,
        branch_a=ECOMMERCE_BASE + """
        ALTER TABLE products RENAME COLUMN sku TO product_code;
        """,
        branch_b=ECOMMERCE_BASE + """
        ALTER TABLE products RENAME COLUMN sku TO article;
        """,
        expected_merge_defined=False,
        expected_rule_ids=("R3_RENAME_VS_RENAME",),
    ),
    Case(
        name="04 ALTER compatible: same rename in both branches",
        base=ECOMMERCE_BASE,
        branch_a=ECOMMERCE_BASE + """
        ALTER TABLE products RENAME COLUMN sku TO product_code;
        """,
        branch_b=ECOMMERCE_BASE + """
        ALTER TABLE products RENAME COLUMN sku TO product_code;
        """,
        expected_merge_defined=True,
    ),
    Case(
        name="05 ADD COLUMN compatible: independent columns",
        base=ECOMMERCE_BASE,
        branch_a=ECOMMERCE_BASE + """
        ALTER TABLE users ADD COLUMN phone text;
        """,
        branch_b=ECOMMERCE_BASE + """
        ALTER TABLE users ADD COLUMN last_login_at text;
        """,
        expected_merge_defined=True,
    ),
    Case(
        name="06 ADD COLUMN conflict: same column different nullable",
        base=ECOMMERCE_BASE,
        branch_a=ECOMMERCE_BASE + """
        ALTER TABLE users ADD COLUMN phone text NOT NULL;
        """,
        branch_b=ECOMMERCE_BASE + """
        ALTER TABLE users ADD COLUMN phone text;
        """,
        expected_merge_defined=False,
        expected_rule_ids=("R4_NAMING_CONFLICT",),
    ),
    Case(
        name="07 ADD FK compatible: add reference in one branch",
        base="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text NOT NULL
        );

        CREATE TABLE sessions (
            id integer PRIMARY KEY,
            user_id integer,
            token text NOT NULL
        );
        """,
        branch_a="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text NOT NULL
        );

        CREATE TABLE sessions (
            id integer PRIMARY KEY,
            user_id integer,
            token text NOT NULL
        );

        ALTER TABLE sessions ADD CONSTRAINT fk_sessions_users
        FOREIGN KEY (user_id) REFERENCES users(id);
        """,
        branch_b="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text NOT NULL
        );

        CREATE TABLE sessions (
            id integer PRIMARY KEY,
            user_id integer,
            token text NOT NULL
        );
        """,
        expected_merge_defined=True,
    ),
    Case(
        name="08 Referential conflict: drop referenced column vs add FK",
        base="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text NOT NULL
        );

        CREATE TABLE sessions (
            id integer PRIMARY KEY,
            user_id integer,
            token text NOT NULL
        );
        """,
        branch_a="""
        CREATE TABLE users (
            email text NOT NULL
        );

        CREATE TABLE sessions (
            id integer PRIMARY KEY,
            user_id integer,
            token text NOT NULL
        );
        """,
        branch_b="""
        CREATE TABLE users (
            id integer PRIMARY KEY,
            email text NOT NULL
        );

        CREATE TABLE sessions (
            id integer PRIMARY KEY,
            user_id integer,
            token text NOT NULL
        );

        ALTER TABLE sessions ADD CONSTRAINT fk_sessions_users
        FOREIGN KEY (user_id) REFERENCES users(id);
        """,
        expected_merge_defined=False,
    ),
    Case(
        name="09 Index conflict: drop column vs create index on column",
        base=ECOMMERCE_BASE,
        branch_a=ECOMMERCE_BASE + """
        ALTER TABLE orders DROP COLUMN status;
        """,
        branch_b=ECOMMERCE_BASE + """
        CREATE INDEX idx_orders_status ON orders(status);
        """,
        expected_merge_defined=False,
        expected_rule_ids=("R1_REFERENTIAL_INTEGRITY",),
    ),
    Case(
        name="10 Constraint conflict: drop column vs add UNIQUE on column",
        base=ECOMMERCE_BASE,
        branch_a=ECOMMERCE_BASE + """
        ALTER TABLE users DROP COLUMN username;
        """,
        branch_b=ECOMMERCE_BASE + """
        ALTER TABLE users ADD CONSTRAINT users_username_unique UNIQUE (username);
        """,
        expected_merge_defined=False,
    ),
    Case(
        name="11 Type modify compatible: same ALTER TYPE",
        base=ECOMMERCE_BASE,
        branch_a=ECOMMERCE_BASE + """
        ALTER TABLE products ALTER COLUMN price TYPE bigint;
        """,
        branch_b=ECOMMERCE_BASE + """
        ALTER TABLE products ALTER COLUMN price TYPE bigint;
        """,
        expected_merge_defined=True,
    ),
    Case(
        name="12 Type/nullable independent compatible",
        base=ECOMMERCE_BASE,
        branch_a=ECOMMERCE_BASE + """
        ALTER TABLE products ALTER COLUMN price TYPE bigint;
        """,
        branch_b=ECOMMERCE_BASE + """
        ALTER TABLE users ALTER COLUMN email DROP NOT NULL;
        """,
        expected_merge_defined=True,
    ),
    Case(
        name="13 University compatible: rename student email vs nullable",
        base=UNIVERSITY_BASE,
        branch_a=UNIVERSITY_BASE + """
        ALTER TABLE students RENAME COLUMN email TO contact_email;
        """,
        branch_b=UNIVERSITY_BASE + """
        ALTER TABLE students ALTER COLUMN email DROP NOT NULL;
        """,
        expected_merge_defined=True,
    ),
    Case(
        name="14 University conflict: drop teacher_id vs modify teacher_id",
        base=UNIVERSITY_BASE,
        branch_a=UNIVERSITY_BASE + """
        ALTER TABLE courses DROP COLUMN teacher_id;
        """,
        branch_b=UNIVERSITY_BASE + """
        ALTER TABLE courses ALTER COLUMN teacher_id SET NOT NULL;
        """,
        expected_merge_defined=False,
        expected_rule_ids=("R1_DROP_VS_MODIFY",),
    ),
    Case(
        name="15 University conflict: different rename course title",
        base=UNIVERSITY_BASE,
        branch_a=UNIVERSITY_BASE + """
        ALTER TABLE courses RENAME COLUMN title TO course_title;
        """,
        branch_b=UNIVERSITY_BASE + """
        ALTER TABLE courses RENAME COLUMN title TO name;
        """,
        expected_merge_defined=False,
        expected_rule_ids=("R3_RENAME_VS_RENAME",),
    ),
]


def run_case(case: Case) -> bool:
    try:
        result = analyze_three_way_merge_from_ddl(
            base_ddl=case.base,
            branch_a_ddl=case.branch_a,
            branch_b_ddl=case.branch_b,
        )
    except Exception as exc:
        print(f"[ERROR] {case.name}")
        print(f"        exception={type(exc).__name__}: {exc}")
        return False

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
    print(f"       commutative={result.summary.is_commutative}")
    print(f"       rule_conflicts={sorted(actual_rule_ids)}")
    print(f"       merge_conflicts={[c.rule_id for c in result.merge_attempt.conflicts]}")
    print(f"       ops_a={len(result.operations_a)}, ops_b={len(result.operations_b)}")

    if errors:
        for error in errors:
            print(f"       ERROR: {error}")

        print("       Operations A:")
        for op in result.operations_a:
            print(f"         - {type(op).__name__}: {op}")

        print("       Operations B:")
        for op in result.operations_b:
            print(f"         - {type(op).__name__}: {op}")

        print("       Merge conflicts:")
        for conflict in result.merge_attempt.conflicts:
            print(f"         - {conflict.rule_id}: {conflict.message}")

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