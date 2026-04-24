from __future__ import annotations

import re
from typing import Optional


DEFAULT_SCHEMA = "public"


def strip_quotes(identifier: str) -> str:
    """
    Убирает внешние двойные кавычки с SQL-идентификатора, если они есть.
    Внутреннюю семантику quoted identifiers пока не моделируем отдельно.
    """
    identifier = identifier.strip()
    if len(identifier) >= 2 and identifier[0] == '"' and identifier[-1] == '"':
        return identifier[1:-1]
    return identifier


def normalize_identifier(name: str) -> str:
    """
    Нормализация SQL-идентификатора.

    Базовая стратегия MVP:
    - trim
    - убрать внешние двойные кавычки
    - привести к нижнему регистру

    Это соответствует типичному поведению PostgreSQL для unquoted identifiers.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Identifier must be a non-empty string")

    normalized = strip_quotes(name.strip())
    normalized = normalized.lower()

    if not normalized:
        raise ValueError("Identifier became empty after normalization")

    return normalized


def normalize_schema_name(name: Optional[str]) -> str:
    """
    Если schema не указана, используем public.
    """
    if name is None or not str(name).strip():
        return DEFAULT_SCHEMA
    return normalize_identifier(str(name))


def split_qualified_name(name: str) -> tuple[Optional[str], str]:
    """
    Разбивает имя вида:
    - users
    - public.users
    - "public"."users"

    Возвращает:
    - schema_name | None
    - local_name

    Для MVP поддерживаем максимум 2 сегмента.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Qualified name must be a non-empty string")

    raw = name.strip()

    # Упрощённая разбивка по точке.
    # Для MVP считаем, что точка не встречается внутри quoted identifier.
    parts = [part.strip() for part in raw.split(".") if part.strip()]

    if len(parts) == 1:
        return None, normalize_identifier(parts[0])

    if len(parts) == 2:
        return (
            normalize_schema_name(parts[0]),
            normalize_identifier(parts[1]),
        )

    raise ValueError(f"Unsupported qualified name format: {name}")


def normalize_table_name(
    table_name: str,
    schema_name: Optional[str] = None,
) -> str:
    """
    Возвращает canonical qualified table name:
    schema.table
    """
    parsed_schema, parsed_table = split_qualified_name(table_name)

    final_schema = normalize_schema_name(schema_name or parsed_schema)
    final_table = parsed_table

    return f"{final_schema}.{final_table}"


def normalize_column_name(name: str) -> str:
    return normalize_identifier(name)


def normalize_constraint_name(name: str) -> str:
    return normalize_identifier(name)


def normalize_index_name(name: str) -> str:
    return normalize_identifier(name)


_TYPE_ALIASES = {
    "int": "integer",
    "int4": "integer",
    "integer": "integer",
    "bigint": "bigint",
    "int8": "bigint",
    "smallint": "smallint",
    "int2": "smallint",
    "text": "text",
    "varchar": "varchar",
    "character varying": "varchar",
    "char": "char",
    "character": "char",
    "bool": "boolean",
    "boolean": "boolean",
    "serial": "serial",
    "bigserial": "bigserial",
    "timestamp": "timestamp",
    "timestamp without time zone": "timestamp",
    "timestamptz": "timestamptz",
    "timestamp with time zone": "timestamptz",
}


def collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def normalize_data_type(type_name: str) -> str:
    """
    Нормализация имени типа данных.

    MVP:
    - lower
    - collapse spaces
    - алиасы PostgreSQL типов
    - параметры типа сохраняем как есть:
      varchar(255) -> varchar(255)
      numeric(10,2) -> numeric(10,2)
    """
    if not isinstance(type_name, str) or not type_name.strip():
        raise ValueError("Data type must be a non-empty string")

    raw = collapse_spaces(type_name).lower()

    # Если есть параметры типа: varchar(255), numeric(10,2)
    if "(" in raw and raw.endswith(")"):
        base = raw[: raw.index("(")].strip()
        suffix = raw[raw.index("("):]
        normalized_base = _TYPE_ALIASES.get(base, base)
        return f"{normalized_base}{suffix}"

    return _TYPE_ALIASES.get(raw, raw)


def normalize_column_fqn(
    table_name: str,
    column_name: str,
    schema_name: Optional[str] = None,
) -> str:
    """
    Canonical fully qualified column name:
    schema.table.column
    """
    table_fqn = normalize_table_name(table_name, schema_name=schema_name)
    schema_part, table_part = split_qualified_name(table_fqn)
    assert schema_part is not None  # после normalize_table_name schema всегда есть
    column_part = normalize_column_name(column_name)
    return f"{schema_part}.{table_part}.{column_part}"


def normalize_table_and_column_reference(
    table_name: str,
    column_name: str,
    schema_name: Optional[str] = None,
) -> tuple[str, str, str]:
    """
    Возвращает canonical triple:
    (schema, table, column)
    """
    table_fqn = normalize_table_name(table_name, schema_name=schema_name)
    schema_part, table_part = split_qualified_name(table_fqn)
    assert schema_part is not None
    column_part = normalize_column_name(column_name)
    return schema_part, table_part, column_part
