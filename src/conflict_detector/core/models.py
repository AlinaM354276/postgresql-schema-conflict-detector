from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, Iterable, Optional, Tuple
from typing import Union


class ObjectType(str, Enum):
    TABLE = "Table"
    COLUMN = "Column"
    CONSTRAINT = "Constraint"
    DATA_TYPE = "DataType"
    INDEX = "Index"


class EdgeType(str, Enum):
    CONTAINS = "contains"
    TYPED_AS = "typedAs"
    HAS_CONSTRAINT = "hasConstraint"
    REFERENCES = "references"
    HAS_INDEX = "hasIndex"


class ConstraintType(str, Enum):
    PRIMARY_KEY = "PRIMARY_KEY"
    FOREIGN_KEY = "FOREIGN_KEY"
    UNIQUE = "UNIQUE"
    CHECK = "CHECK"
    NOT_NULL = "NOT_NULL"


class OperationType(str, Enum):
    ADD = "Add"
    DROP = "Drop"
    MODIFY = "Modify"
    RENAME = "Rename"
    REFERENCE = "Reference"


class ReferenceChangeType(str, Enum):
    ADD = "add"
    DROP = "drop"
    RETARGET = "retarget"


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class SchemaObject:
    """
    Базовый объект схемы.

    object_id должен быть стабильным внутри схемы.
    Для MVP можно строить его как qualified name:
    - table: public.users
    - column: public.users.email
    - constraint: public.users.pk_users
    """
    object_id: str
    object_type: ObjectType
    name: str
    attributes: FrozenSet[Tuple[str, Any]] = field(default_factory=frozenset)

    def attr_dict(self) -> Dict[str, Any]:
        return dict(self.attributes)

    def attr_without_name(self) -> Dict[str, Any]:
        data = self.attr_dict()
        data.pop("name", None)
        return data


@dataclass(frozen=True)
class Table(SchemaObject):
    def __post_init__(self) -> None:
        if self.object_type != ObjectType.TABLE:
            raise ValueError("Table must have object_type=TABLE")


@dataclass(frozen=True)
class Column(SchemaObject):
    def __post_init__(self) -> None:
        if self.object_type != ObjectType.COLUMN:
            raise ValueError("Column must have object_type=COLUMN")


@dataclass(frozen=True)
class Constraint(SchemaObject):
    def __post_init__(self) -> None:
        if self.object_type != ObjectType.CONSTRAINT:
            raise ValueError("Constraint must have object_type=CONSTRAINT")


@dataclass(frozen=True)
class DataType(SchemaObject):
    def __post_init__(self) -> None:
        if self.object_type != ObjectType.DATA_TYPE:
            raise ValueError("DataType must have object_type=DATA_TYPE")


@dataclass(frozen=True)
class Index(SchemaObject):
    def __post_init__(self) -> None:
        if self.object_type != ObjectType.INDEX:
            raise ValueError("Index must have object_type=INDEX")


@dataclass(frozen=True)
class SchemaEdge:
    edge_id: str
    edge_type: EdgeType
    source_id: str
    target_id: str
    attributes: FrozenSet[Tuple[str, Any]] = field(default_factory=frozenset)

    def attr_dict(self) -> Dict[str, Any]:
        return dict(self.attributes)


@dataclass(frozen=True)
class Schema:
    """
    Упрощённое внутреннее представление схемы до графового слоя.
    """
    objects: FrozenSet[SchemaObject]

    def get_object(self, object_id: str) -> Optional[SchemaObject]:
        for obj in self.objects:
            if obj.object_id == object_id:
                return obj
        return None

    def objects_by_type(self, object_type: ObjectType) -> Tuple[SchemaObject, ...]:
        return tuple(obj for obj in self.objects if obj.object_type == object_type)


@dataclass(frozen=True)
class AddOperation:
    target: str
    params: FrozenSet[Tuple[str, Any]]
    operation_type: OperationType = OperationType.ADD


@dataclass(frozen=True)
class DropOperation:
    target: str
    operation_type: OperationType = OperationType.DROP


@dataclass(frozen=True)
class ModifyOperation:
    target: str
    delta: FrozenSet[Tuple[str, Any]]
    operation_type: OperationType = OperationType.MODIFY


@dataclass(frozen=True)
class RenameOperation:
    target: str
    new_name: str
    operation_type: OperationType = OperationType.RENAME


@dataclass(frozen=True)
class ReferenceOperation:
    source: str
    target: str
    change_type: ReferenceChangeType
    operation_type: OperationType = OperationType.REFERENCE


Operation = Union[
    AddOperation,
    DropOperation,
    ModifyOperation,
    RenameOperation,
    ReferenceOperation,
]


@dataclass(frozen=True)
class Conflict:
    rule_id: str
    message: str
    object_ids: Tuple[str, ...]
    severity: SeverityLevel
    operation_a: Optional[Operation] = None
    operation_b: Optional[Operation] = None
    metadata: FrozenSet[Tuple[str, Any]] = field(default_factory=frozenset)

    def metadata_dict(self) -> Dict[str, Any]:
        return dict(self.metadata)


@dataclass(frozen=True)
class Delta:
    added_vertices: FrozenSet[str] = field(default_factory=frozenset)
    removed_vertices: FrozenSet[str] = field(default_factory=frozenset)
    added_edges: FrozenSet[str] = field(default_factory=frozenset)
    removed_edges: FrozenSet[str] = field(default_factory=frozenset)
    modified_attributes: FrozenSet[Tuple[str, str]] = field(default_factory=frozenset)
    # (left_object_id, right_object_id)

    def is_empty(self) -> bool:
        return not (
            self.added_vertices
            or self.removed_vertices
            or self.added_edges
            or self.removed_edges
            or self.modified_attributes
        )


def freeze_attrs(data: Optional[Dict[str, Any]]) -> FrozenSet[Tuple[str, Any]]:
    """
    Безопасное преобразование dict -> frozenset(tuple) для hashable dataclass.
    """
    if not data:
        return frozenset()
    return frozenset(sorted(data.items(), key=lambda x: x[0]))


def make_table(object_id: str, name: str, **attrs: Any) -> Table:
    return Table(
        object_id=object_id,
        object_type=ObjectType.TABLE,
        name=name,
        attributes=freeze_attrs({"name": name, **attrs}),
    )


def make_column(object_id: str, name: str, **attrs: Any) -> Column:
    return Column(
        object_id=object_id,
        object_type=ObjectType.COLUMN,
        name=name,
        attributes=freeze_attrs({"name": name, **attrs}),
    )


def make_constraint(object_id: str, name: str, **attrs: Any) -> Constraint:
    return Constraint(
        object_id=object_id,
        object_type=ObjectType.CONSTRAINT,
        name=name,
        attributes=freeze_attrs({"name": name, **attrs}),
    )


def make_data_type(object_id: str, name: str, **attrs: Any) -> DataType:
    return DataType(
        object_id=object_id,
        object_type=ObjectType.DATA_TYPE,
        name=name,
        attributes=freeze_attrs({"name": name, **attrs}),
    )


def make_index(object_id: str, name: str, **attrs: Any) -> Index:
    return Index(
        object_id=object_id,
        object_type=ObjectType.INDEX,
        name=name,
        attributes=freeze_attrs({"name": name, **attrs}),
    )


def make_edge(
    edge_id: str,
    edge_type: EdgeType,
    source_id: str,
    target_id: str,
    **attrs: Any,
) -> SchemaEdge:
    return SchemaEdge(
        edge_id=edge_id,
        edge_type=edge_type,
        source_id=source_id,
        target_id=target_id,
        attributes=freeze_attrs(attrs),
    )