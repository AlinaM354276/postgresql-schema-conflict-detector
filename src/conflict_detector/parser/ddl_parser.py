from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from src.conflict_detector.core.models import (
    ConstraintType,
    EdgeType,
    SchemaEdge,
    SchemaObject,
)
from src.conflict_detector.graph.builders import (
    DEFAULT_SCHEMA_NAME,
    build_column,
    build_constraint,
    build_data_type,
    build_edge,
    build_index,
    build_table,
    canonical_data_type_name,
    make_column_id,
    make_constraint_id,
    make_data_type_id,
    make_index_id,
    make_table_id,
)
from src.conflict_detector.graph.schema_graph import SchemaGraph
from src.conflict_detector.parser.normalizer import (
    normalize_column_name,
    normalize_constraint_name,
    normalize_data_type,
    normalize_index_name,
    normalize_schema_name,
    normalize_table_name,
    split_qualified_name,
)


IDENT = r'(?:"[^"]+"|[a-zA-Z_][a-zA-Z0-9_$]*)'
QNAME = rf"{IDENT}(?:\s*\.\s*{IDENT})?"


CREATE_TABLE_RE = re.compile(
    rf"""
    ^
    create\s+
    (?P<temp>temporary\s+|temp\s+)?
    table
    \s+
    (?P<if_not_exists>if\s+not\s+exists\s+)?
    (?P<table>{QNAME})
    \s*
    \(
        (?P<body>.*)
    \)
    (?P<tail>.*)
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

CREATE_INDEX_RE = re.compile(
    rf"""
    ^
    create\s+
    (?P<unique>unique\s+)?
    index
    \s+
    (?P<if_not_exists>if\s+not\s+exists\s+)?
    (?P<index>{QNAME})
    \s+
    on
    \s+
    (?P<table>{QNAME})
    (?P<tail>.*)
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

DROP_INDEX_RE = re.compile(
    rf"""
    ^
    drop\s+index
    \s+
    (?P<if_exists>if\s+exists\s+)?
    (?P<index>{QNAME})
    (?P<tail>.*)
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

DROP_TABLE_RE = re.compile(
    rf"""
    ^
    drop\s+table
    \s+
    (?P<if_exists>if\s+exists\s+)?
    (?P<table>{QNAME})
    (?P<tail>.*)
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

ALTER_TABLE_RE = re.compile(
    rf"""
    ^
    alter\s+table
    \s+
    (?P<if_exists>if\s+exists\s+)?
    (?P<table>{QNAME})
    \s+
    (?P<action>.*)
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

INLINE_REFERENCES_RE = re.compile(
    rf"""
    (?P<prefix>.*?)
    \s+references\s+
    (?P<ref_table>{QNAME})
    \s*
    \(
        \s*(?P<ref_column>{IDENT})\s*
    \)
    (?P<suffix>.*)
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
    (?P<tail>.*)
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

TABLE_UNIQUE_RE = re.compile(
    r"""
    ^
    unique
    \s*
    \(
        (?P<columns>.+)
    \)
    (?P<tail>.*)
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

TABLE_CHECK_RE = re.compile(
    r"""
    ^
    check
    \s*
    \(
        (?P<expression>.+)
    \)
    (?P<tail>.*)
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

TABLE_FK_RE = re.compile(
    rf"""
    ^
    foreign\s+key
    \s*
    \(
        (?P<source_columns>.+?)
    \)
    \s+
    references\s+
    (?P<target_table>{QNAME})
    \s*
    \(
        (?P<target_columns>.+?)
    \)
    (?P<tail>.*)
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

REFERENTIAL_ACTION_RE = re.compile(
    r"""
    \b
    on
    \s+
    (?P<event>delete|update)
    \s+
    (?P<action>
        cascade
        | restrict
        | no\s+action
        | set\s+null
        | set\s+default
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

ALTER_ADD_COLUMN_RE = re.compile(
    r"""
    ^
    add\s+column\s+
    (?P<if_not_exists>if\s+not\s+exists\s+)?
    (?P<definition>.+)
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

ALTER_DROP_COLUMN_RE = re.compile(
    rf"""
    ^
    drop\s+column\s+
    (?P<if_exists>if\s+exists\s+)?
    (?P<column>{IDENT})
    (?P<tail>.*)
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

ALTER_RENAME_COLUMN_RE = re.compile(
    rf"""
    ^
    rename\s+column\s+
    (?P<old>{IDENT})
    \s+to\s+
    (?P<new>{IDENT})
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

ALTER_ALTER_COLUMN_TYPE_RE = re.compile(
    rf"""
    ^
    alter\s+column\s+
    (?P<column>{IDENT})
    \s+
    (type|set\s+data\s+type)
    \s+
    (?P<data_type>.+)
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

ALTER_SET_NOT_NULL_RE = re.compile(
    rf"""
    ^
    alter\s+column\s+
    (?P<column>{IDENT})
    \s+
    set\s+not\s+null
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

ALTER_DROP_NOT_NULL_RE = re.compile(
    rf"""
    ^
    alter\s+column\s+
    (?P<column>{IDENT})
    \s+
    drop\s+not\s+null
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

ALTER_ADD_CONSTRAINT_RE = re.compile(
    r"""
    ^
    add\s+
    (?P<constraint>constraint\s+[a-zA-Z0-9_"]+\s+)?
    (?P<body>.+)
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

ALTER_DROP_CONSTRAINT_RE = re.compile(
    rf"""
    ^
    drop\s+constraint\s+
    (?P<if_exists>if\s+exists\s+)?
    (?P<constraint>{IDENT})
    (?P<tail>.*)
    $
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)


@dataclass(frozen=True)
class ParsedReference:
    source_schema: str
    source_table: str
    source_column: str
    target_schema: str
    target_table: str
    target_column: str
    constraint_name: Optional[str] = None
    on_delete: Optional[str] = None
    on_update: Optional[str] = None


@dataclass(frozen=True)
class ParsedColumn:
    name: str
    data_type: str
    data_type_raw: str
    nullable: bool
    default: Optional[str]
    is_primary_key: bool
    is_unique: bool
    reference: Optional[Tuple[str, str, Optional[str], Optional[str]]] = None


@dataclass(frozen=True)
class TableConstraint:
    name: str
    constraint_type: ConstraintType
    columns: Tuple[str, ...]
    expression: Optional[str] = None
    references: Optional[Tuple[str, Tuple[str, ...]]] = None
    on_delete: Optional[str] = None
    on_update: Optional[str] = None


@dataclass(frozen=True)
class ParsedCreateTable:
    graph: SchemaGraph
    references: Tuple[ParsedReference, ...]


def strip_quotes(identifier: str) -> str:
    value = identifier.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def strip_sql_comments(sql: str) -> str:
    without_block = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    without_line = re.sub(r"--.*?$", "", without_block, flags=re.MULTILINE)
    return without_line


def split_sql_statements(sql: str) -> List[str]:
    if not isinstance(sql, str):
        raise ValueError("SQL input must be a string")

    cleaned = strip_sql_comments(sql)
    statements: List[str] = []
    current: List[str] = []
    quote: Optional[str] = None
    i = 0

    while i < len(cleaned):
        ch = cleaned[i]

        if quote is not None:
            current.append(ch)
            if ch == quote:
                if i + 1 < len(cleaned) and cleaned[i + 1] == quote:
                    current.append(cleaned[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue

        if ch in {"'", '"'}:
            quote = ch
            current.append(ch)
            i += 1
            continue

        if ch == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)

    return statements


def split_top_level_commas(value: str) -> List[str]:
    items: List[str] = []
    current: List[str] = []
    depth = 0
    quote: Optional[str] = None
    i = 0

    while i < len(value):
        ch = value[i]

        if quote is not None:
            current.append(ch)
            if ch == quote:
                if i + 1 < len(value) and value[i + 1] == quote:
                    current.append(value[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue

        if ch in {"'", '"'}:
            quote = ch
            current.append(ch)
            i += 1
            continue

        if ch == "(":
            depth += 1
            current.append(ch)
            i += 1
            continue

        if ch == ")":
            depth -= 1
            current.append(ch)
            i += 1
            continue

        if ch == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    tail = "".join(current).strip()
    if tail:
        items.append(tail)

    return items


def collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def normalize_referential_action(value: str) -> str:
    return collapse_spaces(value).lower()


def extract_referential_actions(tail: str) -> Tuple[Optional[str], Optional[str]]:
    on_delete: Optional[str] = None
    on_update: Optional[str] = None

    for match in REFERENTIAL_ACTION_RE.finditer(tail or ""):
        event = match.group("event").lower()
        action = normalize_referential_action(match.group("action"))

        if event == "delete":
            on_delete = action
        elif event == "update":
            on_update = action

    return on_delete, on_update


def parse_table_name(raw_table_name: str) -> Tuple[str, str]:
    table_fqn = normalize_table_name(raw_table_name.strip())
    schema_name, table_name = split_qualified_name(table_fqn)
    return normalize_schema_name(schema_name or DEFAULT_SCHEMA_NAME), table_name


def parse_index_name(
    raw_index_name: str,
    default_schema: str = DEFAULT_SCHEMA_NAME,
) -> Tuple[str, str]:
    schema_name, index_name = split_qualified_name(raw_index_name.strip())
    return normalize_schema_name(schema_name or default_schema), normalize_index_name(index_name)


def parse_column_list(raw: str) -> Tuple[str, ...]:
    return tuple(
        normalize_column_name(strip_quotes(part.strip()))
        for part in split_top_level_commas(raw)
        if part.strip()
    )


def strip_constraint_name(definition: str) -> Tuple[Optional[str], str]:
    raw = definition.strip()
    if not raw.lower().startswith("constraint "):
        return None, raw

    parts = raw.split(None, 2)
    if len(parts) < 3:
        raise ValueError(f"Invalid CONSTRAINT definition: {definition}")

    return normalize_constraint_name(strip_quotes(parts[1])), parts[2].strip()


def extract_default(raw_tail: str) -> Tuple[str, Optional[str]]:
    tokens = raw_tail.strip()
    if not tokens:
        return tokens, None

    match = re.search(
        r"\bdefault\b\s+(?P<expr>.+?)(?=\s+\bnot\b|\s+\bnull\b|\s+\bprimary\b|\s+\bunique\b|\s+\breferences\b|$)",
        tokens,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not match:
        return tokens, None

    default_expr = collapse_spaces(match.group("expr"))
    cleaned = (tokens[: match.start()] + " " + tokens[match.end():]).strip()
    return collapse_spaces(cleaned), default_expr


def parse_inline_reference(
    definition_tail: str,
) -> Tuple[str, Optional[Tuple[str, str, Optional[str], Optional[str]]]]:
    match = INLINE_REFERENCES_RE.match(definition_tail.strip())
    if not match:
        return definition_tail, None

    prefix = match.group("prefix").strip()
    ref_table_raw = match.group("ref_table").strip()
    ref_column_raw = match.group("ref_column").strip()
    suffix = match.group("suffix").strip()

    on_delete, on_update = extract_referential_actions(suffix)

    cleaned = " ".join(part for part in [prefix, suffix] if part).strip()
    ref_table_fqn = normalize_table_name(ref_table_raw)
    ref_column = normalize_column_name(strip_quotes(ref_column_raw))

    return cleaned, (ref_table_fqn, ref_column, on_delete, on_update)


def find_modifier_start(tokens: Sequence[str]) -> int:
    modifier_starters = {
        "not",
        "null",
        "primary",
        "unique",
        "references",
        "default",
        "check",
        "constraint",
        "collate",
        "generated",
        "identity",
    }

    for i, token in enumerate(tokens):
        if token.lower() in modifier_starters:
            return i

    return len(tokens)


def parse_column_definition(definition: str) -> ParsedColumn:
    raw = definition.strip()
    _, raw = strip_constraint_name(raw)

    raw_without_ref, reference = parse_inline_reference(raw)
    raw_without_default, default_expr = extract_default(raw_without_ref)

    tokens = raw_without_default.split()
    if len(tokens) < 2:
        raise ValueError(f"Invalid column definition: {definition}")

    column_name = normalize_column_name(strip_quotes(tokens[0]))
    rest_tokens = tokens[1:]
    modifier_index = find_modifier_start(rest_tokens)

    type_tokens = rest_tokens[:modifier_index]
    modifier_tokens = rest_tokens[modifier_index:]

    if not type_tokens:
        raise ValueError(f"Column type is missing in definition: {definition}")

    data_type_raw = collapse_spaces(" ".join(type_tokens)).lower()
    data_type = canonical_data_type_name(normalize_data_type(data_type_raw))
    modifiers_lower = [token.lower() for token in modifier_tokens]

    nullable = True
    is_primary_key = False
    is_unique = False

    if "not" in modifiers_lower and "null" in modifiers_lower:
        nullable = False

    if "primary" in modifiers_lower and "key" in modifiers_lower:
        is_primary_key = True
        nullable = False

    if "unique" in modifiers_lower:
        is_unique = True

    return ParsedColumn(
        name=column_name,
        data_type=data_type,
        data_type_raw=data_type_raw,
        nullable=nullable,
        default=default_expr,
        is_primary_key=is_primary_key,
        is_unique=is_unique,
        reference=reference,
    )


def default_constraint_name(
    table_name: str,
    constraint_type: ConstraintType,
    columns: Sequence[str],
    suffix: Optional[str] = None,
) -> str:
    if constraint_type == ConstraintType.PRIMARY_KEY:
        return normalize_constraint_name(f"pk_{table_name}")

    col_part = "_".join(columns) if columns else "table"
    base = f"{constraint_type.value.lower()}_{table_name}_{col_part}"
    if suffix:
        base = f"{base}_{suffix}"
    return normalize_constraint_name(base)


def parse_table_constraint(definition: str, table_name: str) -> Optional[TableConstraint]:
    explicit_name, body = strip_constraint_name(definition)
    body = body.strip()

    pk_match = TABLE_PK_RE.match(body)
    if pk_match:
        columns = parse_column_list(pk_match.group("columns"))

        if len(columns) != 1:
            raise ValueError(
                "Composite PRIMARY KEY is not supported yet"
            )

        name = explicit_name or default_constraint_name(
            table_name,
            ConstraintType.PRIMARY_KEY,
            columns,
        )
        return TableConstraint(
            name=name,
            constraint_type=ConstraintType.PRIMARY_KEY,
            columns=columns,
        )

    unique_match = TABLE_UNIQUE_RE.match(body)
    if unique_match:
        columns = parse_column_list(unique_match.group("columns"))
        name = explicit_name or default_constraint_name(
            table_name,
            ConstraintType.UNIQUE,
            columns,
        )
        return TableConstraint(
            name=name,
            constraint_type=ConstraintType.UNIQUE,
            columns=columns,
        )

    check_match = TABLE_CHECK_RE.match(body)
    if check_match:
        expression = collapse_spaces(check_match.group("expression"))
        name = explicit_name or default_constraint_name(
            table_name,
            ConstraintType.CHECK,
            tuple(),
            suffix=str(abs(hash(expression))),
        )
        return TableConstraint(
            name=name,
            constraint_type=ConstraintType.CHECK,
            columns=tuple(),
            expression=expression,
        )

    fk_match = TABLE_FK_RE.match(body)
    if fk_match:
        source_columns = parse_column_list(fk_match.group("source_columns"))
        target_table_fqn = normalize_table_name(fk_match.group("target_table").strip())
        target_columns = parse_column_list(fk_match.group("target_columns"))
        on_delete, on_update = extract_referential_actions(fk_match.group("tail"))

        if len(source_columns) != len(target_columns):
            raise ValueError(f"FOREIGN KEY column count mismatch: {definition}")

        name = explicit_name or default_constraint_name(
            table_name,
            ConstraintType.FOREIGN_KEY,
            source_columns,
        )
        return TableConstraint(
            name=name,
            constraint_type=ConstraintType.FOREIGN_KEY,
            columns=source_columns,
            references=(target_table_fqn, target_columns),
            on_delete=on_delete,
            on_update=on_update,
        )

    return None


def add_vertex_if_absent(graph: SchemaGraph, vertex: SchemaObject) -> None:
    if graph.get_vertex(vertex.object_id) is None:
        graph.add_vertex(vertex)


def add_edge_if_absent(graph: SchemaGraph, edge: SchemaEdge) -> None:
    if graph.get_edge(edge.edge_id) is None:
        graph.add_edge(edge)


def remove_edge(graph: SchemaGraph, edge_id: str) -> None:
    edge = graph.get_edge(edge_id)
    if edge is None:
        return

    graph.outgoing.get(edge.source_id, set()).discard(edge_id)
    graph.incoming.get(edge.target_id, set()).discard(edge_id)
    graph.edges.pop(edge_id, None)


def remove_vertex_and_incident_edges(graph: SchemaGraph, object_id: str) -> None:
    if graph.get_vertex(object_id) is None:
        return

    incident_edges = (
        set(graph.outgoing.get(object_id, set()))
        | set(graph.incoming.get(object_id, set()))
    )

    for edge_id in list(incident_edges):
        remove_edge(graph, edge_id)

    graph.outgoing.pop(object_id, None)
    graph.incoming.pop(object_id, None)
    graph.vertices.pop(object_id, None)


def ensure_table(graph: SchemaGraph, schema_name: str, table_name: str) -> str:
    table_id = make_table_id(table_name, schema_name)
    add_vertex_if_absent(
        graph,
        build_table(
            table_name=table_name,
            schema_name=schema_name,
        ),
    )
    return table_id


def ensure_data_type(graph: SchemaGraph, data_type: str) -> str:
    canonical_type = canonical_data_type_name(data_type)
    dtype_id = make_data_type_id(canonical_type)
    add_vertex_if_absent(graph, build_data_type(canonical_type))
    return dtype_id


def ensure_column(
    graph: SchemaGraph,
    schema_name: str,
    table_name: str,
    column: ParsedColumn,
) -> str:
    table_id = ensure_table(graph, schema_name, table_name)
    column_id = make_column_id(table_name, column.name, schema_name)

    column_attrs: Dict[str, object] = {
        "schema": schema_name,
        "table": table_name,
        "nullable": column.nullable,
        "data_type": column.data_type,
        "data_type_raw": column.data_type_raw,
    }

    if column.default is not None:
        column_attrs["default"] = column.default

    add_vertex_if_absent(
        graph,
        build_column(
            table_name=table_name,
            column_name=column.name,
            schema_name=schema_name,
            **column_attrs,
        ),
    )

    add_edge_if_absent(
        graph,
        build_edge(
            edge_type=EdgeType.CONTAINS,
            source_id=table_id,
            target_id=column_id,
        ),
    )

    dtype_id = ensure_data_type(graph, column.data_type)
    add_edge_if_absent(
        graph,
        build_edge(
            edge_type=EdgeType.TYPED_AS,
            source_id=column_id,
            target_id=dtype_id,
        ),
    )

    return column_id


def add_constraint_object(
    graph: SchemaGraph,
    schema_name: str,
    table_name: str,
    constraint_name: str,
    constraint_type: ConstraintType,
    owner_column: Optional[str] = None,
    columns: Sequence[str] = tuple(),
    expression: Optional[str] = None,
    references: Optional[Tuple[str, Tuple[str, ...]]] = None,
    on_delete: Optional[str] = None,
    on_update: Optional[str] = None,
) -> str:
    constraint_id = make_constraint_id(table_name, constraint_name, schema_name)

    attrs: Dict[str, object] = {
        "schema": schema_name,
        "table": table_name,
        "constraint_type": constraint_type.value,
    }

    if columns:
        attrs["columns"] = ",".join(columns)
    if expression is not None:
        attrs["expression"] = expression
    if references is not None:
        target_table, target_columns = references
        attrs["references_table"] = target_table
        attrs["references_columns"] = ",".join(target_columns)
    if on_delete is not None:
        attrs["on_delete"] = on_delete
    if on_update is not None:
        attrs["on_update"] = on_update

    constraint_attrs = attrs.copy()
    constraint_attrs.pop("constraint_type", None)

    add_vertex_if_absent(
        graph,
        build_constraint(
            table_name=table_name,
            constraint_name=constraint_name,
            schema_name=schema_name,
            constraint_type=constraint_type,
            **constraint_attrs,
        ),
    )

    owner_id = (
        make_column_id(table_name, owner_column, schema_name)
        if owner_column is not None
        else make_table_id(table_name, schema_name)
    )

    if graph.get_vertex(owner_id) is None:
        raise ValueError(f"Constraint owner does not exist: {owner_id}")

    add_edge_if_absent(
        graph,
        build_edge(
            edge_type=EdgeType.HAS_CONSTRAINT,
            source_id=owner_id,
            target_id=constraint_id,
        ),
    )

    return constraint_id


def add_reference_edge(
    graph: SchemaGraph,
    source_schema: str,
    source_table: str,
    source_column: str,
    target_table_fqn: str,
    target_column: str,
    constraint_name: Optional[str] = None,
    on_delete: Optional[str] = None,
    on_update: Optional[str] = None,
) -> None:
    target_schema, target_table = split_qualified_name(target_table_fqn)
    target_schema = normalize_schema_name(target_schema or DEFAULT_SCHEMA_NAME)

    source_id = make_column_id(source_table, source_column, source_schema)
    target_id = make_column_id(target_table, target_column, target_schema)

    if graph.get_vertex(source_id) is None:
        raise ValueError(f"Source column does not exist: {source_id}")
    if graph.get_vertex(target_id) is None:
        raise ValueError(f"Target column does not exist: {target_id}")

    attrs: Dict[str, object] = {}
    if constraint_name:
        attrs["constraint_name"] = constraint_name
    if on_delete is not None:
        attrs["on_delete"] = on_delete
    if on_update is not None:
        attrs["on_update"] = on_update

    add_edge_if_absent(
        graph,
        build_edge(
            edge_type=EdgeType.REFERENCES,
            source_id=source_id,
            target_id=target_id,
            **attrs,
        ),
    )


def add_index_object(
    graph: SchemaGraph,
    schema_name: str,
    table_name: str,
    index_name: str,
    columns: Sequence[str],
    unique: bool,
    expression: Optional[str] = None,
) -> str:
    table_id = make_table_id(table_name, schema_name)
    if graph.get_vertex(table_id) is None:
        raise ValueError(f"Table does not exist for index: {table_id}")

    index_id = make_index_id(table_name, index_name, schema_name)

    attrs: Dict[str, object] = {
        "schema": schema_name,
        "table": table_name,
        "columns": ",".join(columns),
        "unique": unique,
    }
    if expression is not None:
        attrs["expression"] = expression

    add_vertex_if_absent(
        graph,
        build_index(
            table_name=table_name,
            index_name=index_name,
            schema_name=schema_name,
            **attrs,
        ),
    )

    add_edge_if_absent(
        graph,
        build_edge(
            edge_type=EdgeType.HAS_INDEX,
            source_id=table_id,
            target_id=index_id,
        ),
    )

    return index_id


def parse_create_table_statement(statement: str) -> ParsedCreateTable:
    match = CREATE_TABLE_RE.match(statement.strip())
    if not match:
        raise ValueError(f"Unsupported CREATE TABLE statement: {statement}")

    schema_name, table_name = parse_table_name(match.group("table").strip())
    graph = SchemaGraph()
    references: List[ParsedReference] = []

    ensure_table(graph, schema_name, table_name)

    definitions = split_top_level_commas(match.group("body").strip())

    parsed_columns: List[ParsedColumn] = []
    table_constraints: List[TableConstraint] = []

    for definition in definitions:
        constraint = parse_table_constraint(definition, table_name)
        if constraint is not None:
            table_constraints.append(constraint)
            continue

        parsed_columns.append(parse_column_definition(definition))

    for column in parsed_columns:
        ensure_column(graph, schema_name, table_name, column)

    for column in parsed_columns:
        if column.is_primary_key:
            constraint_name = default_constraint_name(
                table_name,
                ConstraintType.PRIMARY_KEY,
                (column.name,),
            )
            add_constraint_object(
                graph=graph,
                schema_name=schema_name,
                table_name=table_name,
                constraint_name=constraint_name,
                constraint_type=ConstraintType.PRIMARY_KEY,
                owner_column=column.name,
                columns=(column.name,),
            )

        if column.is_unique:
            constraint_name = default_constraint_name(
                table_name,
                ConstraintType.UNIQUE,
                (column.name,),
            )
            add_constraint_object(
                graph=graph,
                schema_name=schema_name,
                table_name=table_name,
                constraint_name=constraint_name,
                constraint_type=ConstraintType.UNIQUE,
                owner_column=column.name,
                columns=(column.name,),
            )

        if column.reference is not None:
            target_table_fqn, target_column, on_delete, on_update = column.reference
            constraint_name = default_constraint_name(
                table_name,
                ConstraintType.FOREIGN_KEY,
                (column.name,),
            )
            add_constraint_object(
                graph=graph,
                schema_name=schema_name,
                table_name=table_name,
                constraint_name=constraint_name,
                constraint_type=ConstraintType.FOREIGN_KEY,
                owner_column=column.name,
                columns=(column.name,),
                references=(target_table_fqn, (target_column,)),
                on_delete=on_delete,
                on_update=on_update,
            )

            target_schema, target_table = split_qualified_name(target_table_fqn)
            references.append(
                ParsedReference(
                    source_schema=schema_name,
                    source_table=table_name,
                    source_column=column.name,
                    target_schema=normalize_schema_name(target_schema or DEFAULT_SCHEMA_NAME),
                    target_table=target_table,
                    target_column=target_column,
                    constraint_name=constraint_name,
                    on_delete=on_delete,
                    on_update=on_update,
                )
            )

    for constraint in table_constraints:
        owner_column = constraint.columns[0] if len(constraint.columns) == 1 else None

        add_constraint_object(
            graph=graph,
            schema_name=schema_name,
            table_name=table_name,
            constraint_name=constraint.name,
            constraint_type=constraint.constraint_type,
            owner_column=owner_column,
            columns=constraint.columns,
            expression=constraint.expression,
            references=constraint.references,
            on_delete=constraint.on_delete,
            on_update=constraint.on_update,
        )

        if constraint.constraint_type == ConstraintType.FOREIGN_KEY and constraint.references is not None:
            target_table_fqn, target_columns = constraint.references
            target_schema, target_table = split_qualified_name(target_table_fqn)

            for source_column, target_column in zip(constraint.columns, target_columns):
                references.append(
                    ParsedReference(
                        source_schema=schema_name,
                        source_table=table_name,
                        source_column=source_column,
                        target_schema=normalize_schema_name(target_schema or DEFAULT_SCHEMA_NAME),
                        target_table=target_table,
                        target_column=target_column,
                        constraint_name=constraint.name,
                        on_delete=constraint.on_delete,
                        on_update=constraint.on_update,
                    )
                )

    graph.validate()
    return ParsedCreateTable(graph=graph, references=tuple(references))


def parse_index_columns_from_tail(tail: str) -> Tuple[str, ...]:
    match = re.search(r"\((?P<columns>.+)\)", tail, flags=re.DOTALL)
    if not match:
        return tuple()

    result: List[str] = []

    for item in split_top_level_commas(match.group("columns")):
        cleaned = collapse_spaces(item)
        if re.match(r'^[a-zA-Z0-9_"]+$', cleaned):
            result.append(normalize_column_name(strip_quotes(cleaned)))
        else:
            result.append(cleaned.lower())

    return tuple(result)


def parse_create_index_statement(statement: str, graph: SchemaGraph) -> None:
    match = CREATE_INDEX_RE.match(statement.strip())
    if not match:
        raise ValueError(f"Unsupported CREATE INDEX statement: {statement}")

    unique = bool(match.group("unique"))
    raw_index_name = match.group("index").strip()
    raw_table_name = match.group("table").strip()

    table_schema, table_name = parse_table_name(raw_table_name)
    _, index_name = parse_index_name(raw_index_name, default_schema=table_schema)

    columns = parse_index_columns_from_tail(match.group("tail"))
    expression = None if columns else collapse_spaces(match.group("tail"))

    add_index_object(
        graph=graph,
        schema_name=table_schema,
        table_name=table_name,
        index_name=index_name,
        columns=columns,
        unique=unique,
        expression=expression,
    )


def merge_graphs(graphs: Sequence[SchemaGraph]) -> SchemaGraph:
    merged = SchemaGraph()

    for graph in graphs:
        for vertex in graph.vertices.values():
            add_vertex_if_absent(merged, vertex)

    for graph in graphs:
        for edge in graph.edges.values():
            add_edge_if_absent(merged, edge)

    merged.validate()
    return merged


def parse_drop_table_statement(statement: str, graph: SchemaGraph) -> None:
    match = DROP_TABLE_RE.match(statement.strip())
    if not match:
        raise ValueError(f"Unsupported DROP TABLE statement: {statement}")

    schema_name, table_name = parse_table_name(match.group("table").strip())
    table_id = make_table_id(table_name, schema_name)
    remove_vertex_and_incident_edges(graph, table_id)


def parse_drop_index_statement(statement: str, graph: SchemaGraph) -> None:
    match = DROP_INDEX_RE.match(statement.strip())
    if not match:
        raise ValueError(f"Unsupported DROP INDEX statement: {statement}")

    schema_name, index_name = parse_index_name(match.group("index").strip())
    # Индекс id требует table_name, поэтому удаляем по последнему компоненту имени.
    for vertex_id, vertex in list(graph.vertices.items()):
        if vertex.name == index_name:
            remove_vertex_and_incident_edges(graph, vertex_id)


def rename_column(
    graph: SchemaGraph,
    schema_name: str,
    table_name: str,
    old_column: str,
    new_column: str,
) -> None:
    old_name = normalize_column_name(strip_quotes(old_column))
    new_name = normalize_column_name(strip_quotes(new_column))

    old_id = make_column_id(table_name, old_name, schema_name)
    new_id = make_column_id(table_name, new_name, schema_name)

    obj = graph.get_vertex(old_id)
    if obj is None:
        raise ValueError(f"Column does not exist: {old_id}")

    attrs = obj.attr_dict()
    attrs["name"] = new_name

    graph.vertices.pop(old_id)
    graph.vertices[new_id] = SchemaObject(
        object_id=new_id,
        object_type=obj.object_type,
        name=new_name,
        attributes=tuple(sorted(attrs.items())),
    )

    incident_edges = (
        set(graph.outgoing.get(old_id, set()))
        | set(graph.incoming.get(old_id, set()))
    )

    for edge_id in list(incident_edges):
        edge = graph.get_edge(edge_id)
        if edge is None:
            continue

        remove_edge(graph, edge_id)

        source_id = new_id if edge.source_id == old_id else edge.source_id
        target_id = new_id if edge.target_id == old_id else edge.target_id

        add_edge_if_absent(
            graph,
            build_edge(
                edge_type=edge.edge_type,
                source_id=source_id,
                target_id=target_id,
                **edge.attr_dict(),
            ),
        )


def set_column_nullable(
    graph: SchemaGraph,
    schema_name: str,
    table_name: str,
    column_name: str,
    nullable: bool,
) -> None:
    normalized_column = normalize_column_name(strip_quotes(column_name))
    column_id = make_column_id(table_name, normalized_column, schema_name)
    obj = graph.get_vertex(column_id)

    if obj is None:
        raise ValueError(f"Column does not exist: {column_id}")

    attrs = obj.attr_dict()
    attrs["nullable"] = nullable

    graph.vertices[column_id] = SchemaObject(
        object_id=obj.object_id,
        object_type=obj.object_type,
        name=obj.name,
        attributes=tuple(sorted(attrs.items())),
    )


def alter_column_type(
    graph: SchemaGraph,
    schema_name: str,
    table_name: str,
    column_name: str,
    data_type_raw: str,
) -> None:
    normalized_column = normalize_column_name(strip_quotes(column_name))
    column_id = make_column_id(table_name, normalized_column, schema_name)
    obj = graph.get_vertex(column_id)

    if obj is None:
        raise ValueError(f"Column does not exist: {column_id}")

    normalized_raw = collapse_spaces(data_type_raw).lower()
    canonical_type = canonical_data_type_name(normalize_data_type(normalized_raw))

    attrs = obj.attr_dict()
    attrs["data_type"] = canonical_type
    attrs["data_type_raw"] = normalized_raw

    graph.vertices[column_id] = SchemaObject(
        object_id=obj.object_id,
        object_type=obj.object_type,
        name=obj.name,
        attributes=tuple(sorted(attrs.items())),
    )

    for edge in list(graph.edges_from(column_id)):
        if edge.edge_type == EdgeType.TYPED_AS:
            remove_edge(graph, edge.edge_id)

    dtype_id = ensure_data_type(graph, canonical_type)
    add_edge_if_absent(
        graph,
        build_edge(
            edge_type=EdgeType.TYPED_AS,
            source_id=column_id,
            target_id=dtype_id,
        ),
    )


def parse_alter_table_statement(statement: str, graph: SchemaGraph) -> None:
    match = ALTER_TABLE_RE.match(statement.strip())
    if not match:
        raise ValueError(f"Unsupported ALTER TABLE statement: {statement}")

    schema_name, table_name = parse_table_name(match.group("table").strip())
    action = match.group("action").strip()

    add_column_match = ALTER_ADD_COLUMN_RE.match(action)
    if add_column_match:
        column = parse_column_definition(add_column_match.group("definition"))
        ensure_column(graph, schema_name, table_name, column)

        if column.is_primary_key:
            constraint_name = default_constraint_name(
                table_name,
                ConstraintType.PRIMARY_KEY,
                (column.name,),
            )
            add_constraint_object(
                graph=graph,
                schema_name=schema_name,
                table_name=table_name,
                constraint_name=constraint_name,
                constraint_type=ConstraintType.PRIMARY_KEY,
                owner_column=column.name,
                columns=(column.name,),
            )

        if column.is_unique:
            constraint_name = default_constraint_name(
                table_name,
                ConstraintType.UNIQUE,
                (column.name,),
            )
            add_constraint_object(
                graph=graph,
                schema_name=schema_name,
                table_name=table_name,
                constraint_name=constraint_name,
                constraint_type=ConstraintType.UNIQUE,
                owner_column=column.name,
                columns=(column.name,),
            )

        if column.reference is not None:
            target_table_fqn, target_column, on_delete, on_update = column.reference
            constraint_name = default_constraint_name(
                table_name,
                ConstraintType.FOREIGN_KEY,
                (column.name,),
            )
            add_constraint_object(
                graph=graph,
                schema_name=schema_name,
                table_name=table_name,
                constraint_name=constraint_name,
                constraint_type=ConstraintType.FOREIGN_KEY,
                owner_column=column.name,
                columns=(column.name,),
                references=(target_table_fqn, (target_column,)),
                on_delete=on_delete,
                on_update=on_update,
            )
            add_reference_edge(
                graph,
                source_schema=schema_name,
                source_table=table_name,
                source_column=column.name,
                target_table_fqn=target_table_fqn,
                target_column=target_column,
                constraint_name=constraint_name,
                on_delete=on_delete,
                on_update=on_update,
            )
        return

    drop_column_match = ALTER_DROP_COLUMN_RE.match(action)
    if drop_column_match:
        column_name = normalize_column_name(strip_quotes(drop_column_match.group("column")))
        column_id = make_column_id(table_name, column_name, schema_name)
        remove_vertex_and_incident_edges(graph, column_id)
        return

    rename_column_match = ALTER_RENAME_COLUMN_RE.match(action)
    if rename_column_match:
        rename_column(
            graph,
            schema_name,
            table_name,
            rename_column_match.group("old"),
            rename_column_match.group("new"),
        )
        return

    alter_type_match = ALTER_ALTER_COLUMN_TYPE_RE.match(action)
    if alter_type_match:
        alter_column_type(
            graph,
            schema_name,
            table_name,
            alter_type_match.group("column"),
            alter_type_match.group("data_type"),
        )
        return

    set_not_null_match = ALTER_SET_NOT_NULL_RE.match(action)
    if set_not_null_match:
        set_column_nullable(graph, schema_name, table_name, set_not_null_match.group("column"), False)
        return

    drop_not_null_match = ALTER_DROP_NOT_NULL_RE.match(action)
    if drop_not_null_match:
        set_column_nullable(graph, schema_name, table_name, drop_not_null_match.group("column"), True)
        return

    add_constraint_match = ALTER_ADD_CONSTRAINT_RE.match(action)
    if add_constraint_match:
        raw = add_constraint_match.group("body")
        explicit_prefix = add_constraint_match.group("constraint")
        if explicit_prefix:
            raw = explicit_prefix + raw

        constraint = parse_table_constraint(raw, table_name)
        if constraint is None:
            raise ValueError(f"Unsupported ADD CONSTRAINT body: {action}")

        owner_column = constraint.columns[0] if len(constraint.columns) == 1 else None

        add_constraint_object(
            graph=graph,
            schema_name=schema_name,
            table_name=table_name,
            constraint_name=constraint.name,
            constraint_type=constraint.constraint_type,
            owner_column=owner_column,
            columns=constraint.columns,
            expression=constraint.expression,
            references=constraint.references,
            on_delete=constraint.on_delete,
            on_update=constraint.on_update,
        )

        if constraint.constraint_type == ConstraintType.FOREIGN_KEY and constraint.references is not None:
            target_table_fqn, target_columns = constraint.references
            for source_column, target_column in zip(constraint.columns, target_columns):
                add_reference_edge(
                    graph,
                    source_schema=schema_name,
                    source_table=table_name,
                    source_column=source_column,
                    target_table_fqn=target_table_fqn,
                    target_column=target_column,
                    constraint_name=constraint.name,
                    on_delete=constraint.on_delete,
                    on_update=constraint.on_update,
                )
        return

    drop_constraint_match = ALTER_DROP_CONSTRAINT_RE.match(action)
    if drop_constraint_match:
        constraint_name = normalize_constraint_name(strip_quotes(drop_constraint_match.group("constraint")))
        constraint_id = make_constraint_id(table_name, constraint_name, schema_name)

        remove_vertex_and_incident_edges(graph, constraint_id)

        for edge in list(graph.find_edges_by_type(EdgeType.REFERENCES)):
            if edge.attr_dict().get("constraint_name") == constraint_name:
                remove_edge(graph, edge.edge_id)
        return

    raise ValueError(f"Unsupported ALTER TABLE action: {action}")


def parse_ddl_to_graph(sql: str) -> SchemaGraph:
    statements = split_sql_statements(sql)
    if not statements:
        raise ValueError("No SQL statements found")

    create_table_graphs: List[SchemaGraph] = []
    references: List[ParsedReference] = []
    deferred_statements: List[str] = []

    for statement in statements:
        normalized = statement.strip().lower()

        if normalized.startswith("create table"):
            parsed = parse_create_table_statement(statement)
            create_table_graphs.append(parsed.graph)
            references.extend(parsed.references)
        else:
            deferred_statements.append(statement)

    graph = merge_graphs(create_table_graphs) if create_table_graphs else SchemaGraph()

    for ref in references:
        target_table_fqn = f"{ref.target_schema}.{ref.target_table}"
        add_reference_edge(
            graph=graph,
            source_schema=ref.source_schema,
            source_table=ref.source_table,
            source_column=ref.source_column,
            target_table_fqn=target_table_fqn,
            target_column=ref.target_column,
            constraint_name=ref.constraint_name,
            on_delete=ref.on_delete,
            on_update=ref.on_update,
        )

    for statement in deferred_statements:
        normalized = statement.strip().lower()

        if normalized.startswith("create index") or normalized.startswith("create unique index"):
            parse_create_index_statement(statement, graph)
        elif normalized.startswith("alter table"):
            parse_alter_table_statement(statement, graph)
        elif normalized.startswith("drop table"):
            raise ValueError(
                f"DROP TABLE is not supported in parse_ddl_to_graph: {statement}"
            )
        elif normalized.startswith("drop index"):
            parse_drop_index_statement(statement, graph)
        else:
            raise ValueError(f"Unsupported SQL statement: {statement}")

    graph.validate()
    return graph
