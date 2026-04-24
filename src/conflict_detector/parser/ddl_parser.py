from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.conflict_detector.core.models import ConstraintType, EdgeType, make_edge
from src.conflict_detector.graph.builders import build_schema_graph
from src.conflict_detector.graph.schema_graph import SchemaGraph
from src.conflict_detector.parser.normalizer import (
    normalize_column_name,
    normalize_constraint_name,
    normalize_data_type,
    normalize_table_name,
    split_qualified_name,
)


CREATE_TABLE_RE = re.compile(
    r"create\s+table\s+(?P<table>[^\(]+)\((?P<body>.*)\)\s*$",
    re.IGNORECASE | re.DOTALL,
)

INLINE_REFERENCES_RE = re.compile(
    r"""
    ^
    (?P<prefix>.*?)
    \s+references\s+
    (?P<ref_table>[a-zA-Z0-9_." ]+)
    \s*
    \(
        \s*(?P<ref_column>[a-zA-Z0-9_"]+)\s*
    \)
    (?P<suffix>.*?)
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

TABLE_PK_RE = re.compile(
    r"""
    ^
    primary\s+key
    \s*
    \(
        (?P<columns>.+)
    \)
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)


@dataclass(frozen=True)
class ParsedColumn:
    name: str
    data_type: str
    nullable: bool
    is_primary_key: bool
    reference: Optional[Tuple[str, str]] = None
    # (referenced_table_fqn, referenced_column_name)


@dataclass(frozen=True)
class ParsedTableStatement:
    graph: SchemaGraph
    references: Tuple[Tuple[str, str, str, str, str], ...]
    # (source_schema, source_table, source_column, target_table_fqn, target_column)


def split_sql_statements(sql: str) -> List[str]:
    """
    Упрощённое разбиение SQL на инструкции по ';'.
    Для MVP этого достаточно.
    """
    if not isinstance(sql, str):
        raise ValueError("SQL input must be a string")

    parts = [part.strip() for part in sql.split(";")]
    return [part for part in parts if part]


def split_top_level_commas(value: str) -> List[str]:
    """
    Разбивает строку по запятым верхнего уровня,
    игнорируя запятые внутри круглых скобок.
    """
    items: List[str] = []
    current: List[str] = []
    depth = 0

    for ch in value:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
        else:
            current.append(ch)

    tail = "".join(current).strip()
    if tail:
        items.append(tail)

    return items


def parse_table_name(raw_table_name: str) -> Tuple[str, str]:
    table_fqn = normalize_table_name(raw_table_name.strip())
    schema_name, table_name = split_qualified_name(table_fqn)
    assert schema_name is not None
    return schema_name, table_name


def strip_optional_constraint_prefix(definition: str) -> str:
    """
    Поддержка определений вида:
    CONSTRAINT pk_users PRIMARY KEY (...)
    CONSTRAINT fk_users_manager ... REFERENCES ...
    """
    definition = definition.strip()

    if not definition.lower().startswith("constraint "):
        return definition

    parts = definition.split(None, 2)
    if len(parts) < 3:
        raise ValueError(f"Invalid CONSTRAINT definition: {definition}")

    return parts[2].strip()


def parse_inline_reference(definition_tail: str) -> Tuple[str, Optional[Tuple[str, str]]]:
    """
    Ищет inline REFERENCES table(column).
    Возвращает:
    - tail without REFERENCES
    - (referenced_table_fqn, referenced_column_name) | None
    """
    match = INLINE_REFERENCES_RE.match(definition_tail.strip())
    if not match:
        return definition_tail, None

    prefix = match.group("prefix").strip()
    ref_table_raw = match.group("ref_table").strip()
    ref_column_raw = match.group("ref_column").strip()
    suffix = match.group("suffix").strip()

    cleaned = " ".join(part for part in [prefix, suffix] if part).strip()

    ref_table_fqn = normalize_table_name(ref_table_raw)
    ref_column = normalize_column_name(ref_column_raw)

    return cleaned, (ref_table_fqn, ref_column)


def parse_column_definition(definition: str) -> ParsedColumn:
    raw = strip_optional_constraint_prefix(definition.strip())

    raw_without_ref, reference = parse_inline_reference(raw)

    tokens = raw_without_ref.split()
    if len(tokens) < 2:
        raise ValueError(f"Invalid column definition: {definition}")

    column_name = normalize_column_name(tokens[0])

    type_tokens: List[str] = []
    modifier_tokens: List[str] = []

    i = 1
    while i < len(tokens):
        token_upper = tokens[i].upper()
        if token_upper in {"NOT", "NULL", "PRIMARY", "KEY"}:
            modifier_tokens = tokens[i:]
            break
        type_tokens.append(tokens[i])
        i += 1

    if not type_tokens:
        raise ValueError(f"Column type is missing in definition: {definition}")

    data_type = normalize_data_type(" ".join(type_tokens))
    modifiers_upper = [token.upper() for token in modifier_tokens]

    nullable = True
    is_primary_key = False

    if "NOT" in modifiers_upper and "NULL" in modifiers_upper:
        nullable = False

    if "PRIMARY" in modifiers_upper and "KEY" in modifiers_upper:
        is_primary_key = True
        nullable = False

    return ParsedColumn(
        name=column_name,
        data_type=data_type,
        nullable=nullable,
        is_primary_key=is_primary_key,
        reference=reference,
    )


def parse_table_level_primary_key(definition: str) -> Optional[List[str]]:
    raw = strip_optional_constraint_prefix(definition.strip())
    match = TABLE_PK_RE.match(raw)
    if not match:
        return None

    columns_raw = match.group("columns")
    column_names = [
        normalize_column_name(part.strip())
        for part in split_top_level_commas(columns_raw)
    ]
    return column_names


def parse_create_table_statement(statement: str) -> ParsedTableStatement:
    match = CREATE_TABLE_RE.match(statement.strip())
    if not match:
        raise ValueError(f"Unsupported DDL statement: {statement}")

    raw_table_name = match.group("table").strip()
    body = match.group("body").strip()

    schema_name, table_name = parse_table_name(raw_table_name)
    builder = build_schema_graph(schema_name=schema_name)

    builder.add_table(table_name)

    definitions = split_top_level_commas(body)

    parsed_columns: List[ParsedColumn] = []
    table_level_pk_columns: List[str] = []

    for definition in definitions:
        maybe_pk = parse_table_level_primary_key(definition)
        if maybe_pk is not None:
            table_level_pk_columns.extend(maybe_pk)
            continue

        parsed_column = parse_column_definition(definition)
        parsed_columns.append(parsed_column)

    # Сначала создаём все колонки
    for column in parsed_columns:
        builder.add_column(
            table_name=table_name,
            column_name=column.name,
            data_type=column.data_type,
            nullable=column.nullable,
        )

    # Затем inline PK
    for column in parsed_columns:
        if column.is_primary_key:
            constraint_name = normalize_constraint_name(f"pk_{table_name}_{column.name}")
            builder.add_constraint(
                table_name=table_name,
                constraint_name=constraint_name,
                constraint_type=ConstraintType.PRIMARY_KEY,
                owner_column_name=column.name,
            )

    # Затем table-level PK
    if table_level_pk_columns:
        if len(table_level_pk_columns) == 1:
            column_name = table_level_pk_columns[0]
            constraint_name = normalize_constraint_name(f"pk_{table_name}")
            builder.add_constraint(
                table_name=table_name,
                constraint_name=constraint_name,
                constraint_type=ConstraintType.PRIMARY_KEY,
                owner_column_name=column_name,
            )
        else:
            raise ValueError(
                "Composite PRIMARY KEY is not supported in MVP parser yet"
            )

    collected_references = []

    for column in parsed_columns:
        if column.reference is None:
            continue

        ref_table_fqn, ref_column = column.reference
        collected_references.append(
            (
                schema_name,
                table_name,
                column.name,
                ref_table_fqn,
                ref_column,
            )
        )

    return ParsedTableStatement(
        graph=builder.build(),
        references=tuple(collected_references),
    )


def merge_graphs(graphs: List[SchemaGraph]) -> SchemaGraph:
    """
    Простое объединение графов нескольких CREATE TABLE statements.
    """
    if not graphs:
        raise ValueError("No graphs to merge")

    merged = build_schema_graph().graph

    for graph in graphs:
        for vertex in graph.vertices.values():
            if merged.get_vertex(vertex.object_id) is None:
                merged.add_vertex(vertex)
        for edge in graph.edges.values():
            if merged.get_edge(edge.edge_id) is None:
                merged.add_edge(edge)

    merged.validate()
    return merged


def parse_ddl_to_graph(sql: str) -> SchemaGraph:
    statements = split_sql_statements(sql)
    if not statements:
        raise ValueError("No SQL statements found")

    parsed_statements: List[ParsedTableStatement] = []

    for statement in statements:
        if statement.strip().lower().startswith("create table"):
            parsed_statements.append(parse_create_table_statement(statement))
        else:
            raise ValueError(f"Unsupported statement type: {statement}")

    merged = merge_graphs([item.graph for item in parsed_statements])

    # После объединения всех CREATE TABLE добавляем REFERENCES
    for item in parsed_statements:
        for (
            source_schema,
            source_table,
            source_column,
            target_table_fqn,
            target_column,
        ) in item.references:
            target_schema, target_table = split_qualified_name(target_table_fqn)
            assert target_schema is not None

            source_id = f"{source_schema}.{source_table}.{source_column}"
            target_id = f"{target_schema}.{target_table}.{target_column}"

            if merged.get_vertex(source_id) is None:
                raise ValueError(f"Source column does not exist: {source_id}")
            if merged.get_vertex(target_id) is None:
                raise ValueError(f"Target column does not exist: {target_id}")

            edge_id = f"references:{source_id}->{target_id}"
            edge = make_edge(
                edge_id=edge_id,
                edge_type=EdgeType.REFERENCES,
                source_id=source_id,
                target_id=target_id,
            )

            if merged.get_edge(edge_id) is None:
                merged.add_edge(edge)

    return merged
