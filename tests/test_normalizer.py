from __future__ import annotations

import pytest

from src.conflict_detector.parser.normalizer import (
    DEFAULT_SCHEMA,
    normalize_column_fqn,
    normalize_column_name,
    normalize_data_type,
    normalize_identifier,
    normalize_schema_name,
    normalize_table_and_column_reference,
    normalize_table_name,
    split_qualified_name,
)


def test_normalize_identifier_basic():
    assert normalize_identifier("Users") == "users"
    assert normalize_identifier("  EMAIL  ") == "email"


def test_normalize_identifier_strips_quotes():
    assert normalize_identifier('"Users"') == "users"
    assert normalize_identifier('"EmailAddress"') == "emailaddress"


def test_normalize_schema_name_defaults_to_public():
    assert normalize_schema_name(None) == DEFAULT_SCHEMA
    assert normalize_schema_name("") == DEFAULT_SCHEMA
    assert normalize_schema_name("Public") == "public"


def test_split_qualified_name_single_part():
    schema_name, local_name = split_qualified_name("users")
    assert schema_name is None
    assert local_name == "users"


def test_split_qualified_name_two_parts():
    schema_name, local_name = split_qualified_name("public.users")
    assert schema_name == "public"
    assert local_name == "users"


def test_normalize_table_name_without_schema():
    assert normalize_table_name("Users") == "public.users"


def test_normalize_table_name_with_schema_inside_name():
    assert normalize_table_name("Sales.Orders") == "sales.orders"


def test_normalize_table_name_with_explicit_schema_argument():
    assert normalize_table_name("Orders", schema_name="Sales") == "sales.orders"


def test_normalize_column_name():
    assert normalize_column_name("Email") == "email"


def test_normalize_column_fqn():
    assert normalize_column_fqn("Users", "Email") == "public.users.email"
    assert normalize_column_fqn("sales.orders", "OrderID") == "sales.orders.orderid"


def test_normalize_table_and_column_reference():
    schema_name, table_name, column_name = normalize_table_and_column_reference(
        "Sales.Orders",
        "CustomerID",
    )
    assert schema_name == "sales"
    assert table_name == "orders"
    assert column_name == "customerid"


def test_normalize_data_type_aliases():
    assert normalize_data_type("INT") == "integer"
    assert normalize_data_type("BOOLEAN") == "boolean"
    assert normalize_data_type("character varying") == "varchar"
    assert normalize_data_type("timestamp without time zone") == "timestamp"
    assert normalize_data_type("timestamp with time zone") == "timestamptz"


def test_normalize_data_type_with_parameters():
    assert normalize_data_type("VARCHAR(255)") == "varchar(255)"
    assert normalize_data_type("character varying(100)") == "varchar(100)"
    assert normalize_data_type("NUMERIC(10,2)") == "numeric(10,2)"


def test_invalid_identifier_raises():
    with pytest.raises(ValueError):
        normalize_identifier("")

    with pytest.raises(ValueError):
        normalize_identifier("   ")


def test_invalid_qualified_name_raises():
    with pytest.raises(ValueError):
        split_qualified_name("a.b.c")
