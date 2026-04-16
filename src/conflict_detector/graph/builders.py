from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from src.conflict_detector.core.models import (
    Constraint,
    ConstraintType,
    DataType,
    EdgeType,
    Index,
    ObjectType,
    SchemaEdge,
    SchemaObject,
    Table,
    Column,
    freeze_attrs,
)
from src.conflict_detector.graph.schema_graph import SchemaGraph


DEFAULT_SCHEMA_NAME = "public"


def qname(*parts: str) -> str:
    """
    Собирает qualified name из непустых частей.
    """
    return ".".join(part for part in parts if part)


def make_table_id(
    table_name: str,
    schema_name: str = DEFAULT_SCHEMA_NAME,
) -> str:
    return qname(schema_name, table_name)


def make_column_id(
    table_name: str,
    column_name: str,
    schema_name: str = DEFAULT_SCHEMA_NAME,
) -> str:
    return qname(schema_name, table_name, column_name)


def make_constraint_id(
    table_name: str,
    constraint_name: str,
    schema_name: str = DEFAULT_SCHEMA_NAME,
) -> str:
    return qname(schema_name, table_name, constraint_name)


def make_index_id(
    table_name: str,
    index_name: str,
    schema_name: str = DEFAULT_SCHEMA_NAME,
) -> str:
    return qname(schema_name, table_name, index_name)


def make_data_type_id(type_name: str) -> str:
    return f"type.{type_name}"


def make_edge_id(
    edge_type: EdgeType,
    source_id: str,
    target_id: str,
) -> str:
    return f"{edge_type.value}:{source_id}->{target_id}"


def build_table(
    table_name: str,
    schema_name: str = DEFAULT_SCHEMA_NAME,
    **attrs: Any,
) -> Table:
    object_id = make_table_id(table_name=table_name, schema_name=schema_name)
    attributes = {
        "name": table_name,
        "schema": schema_name,
        **attrs,
    }
    return Table(
        object_id=object_id,
        object_type=ObjectType.TABLE,
        name=table_name,
        attributes=freeze_attrs(attributes),
    )


def build_column(
    table_name: str,
    column_name: str,
    schema_name: str = DEFAULT_SCHEMA_NAME,
    **attrs: Any,
) -> Column:
    object_id = make_column_id(
        table_name=table_name,
        column_name=column_name,
        schema_name=schema_name,
    )
    attributes = {
        "name": column_name,
        "table": table_name,
        "schema": schema_name,
        **attrs,
    }
    return Column(
        object_id=object_id,
        object_type=ObjectType.COLUMN,
        name=column_name,
        attributes=freeze_attrs(attributes),
    )


def build_constraint(
    table_name: str,
    constraint_name: str,
    schema_name: str = DEFAULT_SCHEMA_NAME,
    constraint_type: Optional[ConstraintType] = None,
    **attrs: Any,
) -> Constraint:
    object_id = make_constraint_id(
        table_name=table_name,
        constraint_name=constraint_name,
        schema_name=schema_name,
    )
    attributes = {
        "name": constraint_name,
        "table": table_name,
        "schema": schema_name,
        **attrs,
    }
    if constraint_type is not None:
        attributes["constraint_type"] = constraint_type.value

    return Constraint(
        object_id=object_id,
        object_type=ObjectType.CONSTRAINT,
        name=constraint_name,
        attributes=freeze_attrs(attributes),
    )


def build_index(
    table_name: str,
    index_name: str,
    schema_name: str = DEFAULT_SCHEMA_NAME,
    **attrs: Any,
) -> Index:
    object_id = make_index_id(
        table_name=table_name,
        index_name=index_name,
        schema_name=schema_name,
    )
    attributes = {
        "name": index_name,
        "table": table_name,
        "schema": schema_name,
        **attrs,
    }
    return Index(
        object_id=object_id,
        object_type=ObjectType.INDEX,
        name=index_name,
        attributes=freeze_attrs(attributes),
    )


def build_data_type(
    type_name: str,
    **attrs: Any,
) -> DataType:
    object_id = make_data_type_id(type_name)
    attributes = {
        "name": type_name,
        **attrs,
    }
    return DataType(
        object_id=object_id,
        object_type=ObjectType.DATA_TYPE,
        name=type_name,
        attributes=freeze_attrs(attributes),
    )


def build_edge(
    edge_type: EdgeType,
    source_id: str,
    target_id: str,
    edge_id: Optional[str] = None,
    **attrs: Any,
) -> SchemaEdge:
    actual_edge_id = edge_id or make_edge_id(
        edge_type=edge_type,
        source_id=source_id,
        target_id=target_id,
    )
    return SchemaEdge(
        edge_id=actual_edge_id,
        edge_type=edge_type,
        source_id=source_id,
        target_id=target_id,
        attributes=freeze_attrs(attrs),
    )


@dataclass
class GraphBuilder:
    """
    Утилита для удобной сборки SchemaGraph в тестах и MVP-сценариях.

    Основная идея:
    - быстро добавлять таблицы, столбцы, типы, ограничения, индексы
    - автоматически создавать типовые рёбра
    - не писать руками object_id и edge_id на каждом шаге
    """
    schema_name: str = DEFAULT_SCHEMA_NAME
    graph: SchemaGraph = field(default_factory=SchemaGraph)

    def add_table(self, table_name: str, **attrs: Any) -> str:
        table = build_table(
            table_name=table_name,
            schema_name=self.schema_name,
            **attrs,
        )
        self.graph.add_vertex(table)
        return table.object_id

    def add_column(
        self,
        table_name: str,
        column_name: str,
        data_type: Optional[str] = None,
        **attrs: Any,
    ) -> str:
        table_id = make_table_id(table_name, self.schema_name)
        if self.graph.get_vertex(table_id) is None:
            raise ValueError(f"Table does not exist: {table_id}")

        column = build_column(
            table_name=table_name,
            column_name=column_name,
            schema_name=self.schema_name,
            **attrs,
        )
        self.graph.add_vertex(column)

        contains_edge = build_edge(
            edge_type=EdgeType.CONTAINS,
            source_id=table_id,
            target_id=column.object_id,
        )
        self.graph.add_edge(contains_edge)

        if data_type is not None:
            dtype_id = self.ensure_data_type(data_type)
            typed_as_edge = build_edge(
                edge_type=EdgeType.TYPED_AS,
                source_id=column.object_id,
                target_id=dtype_id,
            )
            self.graph.add_edge(typed_as_edge)

        return column.object_id

    def add_constraint(
        self,
        table_name: str,
        constraint_name: str,
        constraint_type: Optional[ConstraintType] = None,
        owner_column_name: Optional[str] = None,
        **attrs: Any,
    ) -> str:
        owner_id = (
            make_column_id(table_name, owner_column_name, self.schema_name)
            if owner_column_name is not None
            else make_table_id(table_name, self.schema_name)
        )

        if self.graph.get_vertex(owner_id) is None:
            raise ValueError(f"Constraint owner does not exist: {owner_id}")

        constraint = build_constraint(
            table_name=table_name,
            constraint_name=constraint_name,
            schema_name=self.schema_name,
            constraint_type=constraint_type,
            **attrs,
        )
        self.graph.add_vertex(constraint)

        edge = build_edge(
            edge_type=EdgeType.HAS_CONSTRAINT,
            source_id=owner_id,
            target_id=constraint.object_id,
        )
        self.graph.add_edge(edge)

        return constraint.object_id

    def add_index(
        self,
        table_name: str,
        index_name: str,
        **attrs: Any,
    ) -> str:
        table_id = make_table_id(table_name, self.schema_name)
        if self.graph.get_vertex(table_id) is None:
            raise ValueError(f"Table does not exist: {table_id}")

        index = build_index(
            table_name=table_name,
            index_name=index_name,
            schema_name=self.schema_name,
            **attrs,
        )
        self.graph.add_vertex(index)

        edge = build_edge(
            edge_type=EdgeType.HAS_INDEX,
            source_id=table_id,
            target_id=index.object_id,
        )
        self.graph.add_edge(edge)

        return index.object_id

    def add_reference(
        self,
        source_table: str,
        source_column: str,
        target_table: str,
        target_column: str,
        **attrs: Any,
    ) -> str:
        source_id = make_column_id(source_table, source_column, self.schema_name)
        target_id = make_column_id(target_table, target_column, self.schema_name)

        if self.graph.get_vertex(source_id) is None:
            raise ValueError(f"Source column does not exist: {source_id}")
        if self.graph.get_vertex(target_id) is None:
            raise ValueError(f"Target column does not exist: {target_id}")

        edge = build_edge(
            edge_type=EdgeType.REFERENCES,
            source_id=source_id,
            target_id=target_id,
            **attrs,
        )
        self.graph.add_edge(edge)
        return edge.edge_id

    def ensure_data_type(self, type_name: str, **attrs: Any) -> str:
        type_id = make_data_type_id(type_name)
        existing = self.graph.get_vertex(type_id)
        if existing is None:
            data_type = build_data_type(type_name, **attrs)
            self.graph.add_vertex(data_type)
        return type_id

    def build(self, validate: bool = True) -> SchemaGraph:
        if validate:
            self.graph.validate()
        return self.graph


def build_schema_graph(
    schema_name: str = DEFAULT_SCHEMA_NAME,
) -> GraphBuilder:
    """
    Удобная точка входа:
        builder = build_schema_graph()
        builder.add_table(...)
        ...
        graph = builder.build()
    """
    return GraphBuilder(schema_name=schema_name)
