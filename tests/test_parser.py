from __future__ import annotations

import pytest

from src.conflict_detector.core.models import EdgeType, ObjectType
from src.conflict_detector.parser.ddl_parser import (
    parse_create_table_statement,
    parse_ddl_to_graph,
    split_sql_statements,
)


def test_split_sql_statements():
    sql = """
    CREATE TABLE users (
        id integer PRIMARY KEY
    );

    CREATE TABLE orders (
        id integer PRIMARY KEY
    );
    """
    statements = split_sql_statements(sql)
    assert len(statements) == 2
    assert statements[0].lower().startswith("create table")
    assert statements[1].lower().startswith("create table")


def test_parse_create_table_basic():
    sql = """
    CREATE TABLE users (
        id integer PRIMARY KEY,
        email text NOT NULL
    )
    """

    parsed = parse_create_table_statement(sql)
    graph = parsed.graph

    assert graph.get_vertex("public.users") is not None
    assert graph.get_vertex("public.users.id") is not None
    assert graph.get_vertex("public.users.email") is not None
    assert graph.get_vertex("type.integer") is not None
    assert graph.get_vertex("type.text") is not None

    email = graph.get_vertex("public.users.email")
    assert email is not None
    assert email.attr_dict()["nullable"] is False


def test_parse_create_table_with_inline_reference():
    ddl = """
    CREATE TABLE users (
        id integer PRIMARY KEY
    );

    CREATE TABLE orders (
        id integer PRIMARY KEY,
        user_id integer REFERENCES users(id)
    );
    """

    graph = parse_ddl_to_graph(ddl)

    ref_edge_id = "references:public.orders.user_id->public.users.id"
    ref_edge = graph.get_edge(ref_edge_id)

    assert ref_edge is not None
    assert ref_edge.edge_type == EdgeType.REFERENCES
    assert ref_edge.source_id == "public.orders.user_id"
    assert ref_edge.target_id == "public.users.id"


def test_parse_create_table_with_schema_qualified_name():
    sql = """
    CREATE TABLE sales.orders (
        id integer PRIMARY KEY,
        customer_email text
    )
    """

    parsed = parse_create_table_statement(sql)
    graph = parsed.graph

    assert graph.get_vertex("sales.orders") is not None
    assert graph.get_vertex("sales.orders.id") is not None
    assert graph.get_vertex("sales.orders.customer_email") is not None


def test_parse_ddl_to_graph_multiple_tables():
    ddl = """
    CREATE TABLE users (
        id integer PRIMARY KEY,
        email text NOT NULL
    );

    CREATE TABLE orders (
        id integer PRIMARY KEY,
        user_id integer REFERENCES users(id)
    );
    """

    graph = parse_ddl_to_graph(ddl)

    assert graph.get_vertex("public.users") is not None
    assert graph.get_vertex("public.orders") is not None
    assert graph.get_vertex("public.orders.user_id") is not None
    assert graph.get_edge("references:public.orders.user_id->public.users.id") is not None


def test_parse_table_level_primary_key_single_column():
    ddl = """
    CREATE TABLE users (
        id integer,
        email text,
        PRIMARY KEY (id)
    );
    """

    graph = parse_ddl_to_graph(ddl)

    pk_constraint_id = "public.users.pk_users"
    pk_constraint = graph.get_vertex(pk_constraint_id)

    assert pk_constraint is not None
    assert pk_constraint.object_type == ObjectType.CONSTRAINT
    assert pk_constraint.attr_dict()["constraint_type"] == "PRIMARY_KEY"


def test_composite_primary_key_not_supported_yet():
    ddl = """
    CREATE TABLE user_roles (
        user_id integer,
        role_id integer,
        PRIMARY KEY (user_id, role_id)
    );
    """

    with pytest.raises(ValueError):
        parse_ddl_to_graph(ddl)


def test_unsupported_statement_raises():
    ddl = """
    DROP TABLE users;
    """

    with pytest.raises(ValueError):
        parse_ddl_to_graph(ddl)
