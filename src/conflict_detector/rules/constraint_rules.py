from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from src.conflict_detector.core.models import (
    AddOperation,
    Conflict,
    ConstraintType,
    DropOperation,
    ModifyOperation,
    ObjectType,
    SeverityLevel,
    freeze_attrs,
)
from src.conflict_detector.graph.schema_graph import SchemaGraph
from src.conflict_detector.rules.base import (
    BaseConflictRule,
    RuleCheckResult,
    RuleContext,
)


def is_primary_key_constraint(graph: SchemaGraph, object_id: str) -> bool:
    obj = graph.get_vertex(object_id)
    if obj is None:
        return False

    attrs = obj.attr_dict()
    return attrs.get("constraint_type") == ConstraintType.PRIMARY_KEY.value


def make_constraint_conflict(
    *,
    rule_id: str,
    message: str,
    object_id: str,
    dependent_id: str,
    context: RuleContext,
) -> Conflict:
    return Conflict(
        rule_id=rule_id,
        message=message,
        object_ids=tuple(sorted({object_id, dependent_id})),
        severity=SeverityLevel.HIGH,
        operation_a=context.operation_a,
        operation_b=context.operation_b,
        metadata=freeze_attrs(
            {
                "constraint_id": object_id,
                "dependent_id": dependent_id,
                "operation_a_type": type(context.operation_a).__name__,
                "operation_b_type": type(context.operation_b).__name__,
            }
        ),
    )


def params_dict(op: AddOperation) -> dict:
    return dict(op.params)


def parse_columns(raw: object) -> Tuple[str, ...]:
    if raw is None:
        return tuple()

    return tuple(
        part.strip()
        for part in str(raw).split(",")
        if part.strip()
    )


def column_id(schema: str, table: str, column: str) -> str:
    return f"{schema}.{table}.{column}"


def is_add_constraint_operation(op: object) -> bool:
    if not isinstance(op, AddOperation):
        return False

    params = params_dict(op)
    return params.get("object_type") == ObjectType.CONSTRAINT.value


def constraint_columns(op: AddOperation) -> Tuple[str, ...]:
    return parse_columns(params_dict(op).get("columns"))


def constraint_schema(op: AddOperation) -> str:
    return str(params_dict(op).get("schema", "public"))


def constraint_table(op: AddOperation) -> Optional[str]:
    table = params_dict(op).get("table")
    return str(table) if table else None


def dropped_column_used_by_constraint(
    drop_op: DropOperation,
    add_constraint_op: AddOperation,
) -> Optional[str]:
    table = constraint_table(add_constraint_op)
    if table is None:
        return None

    schema = constraint_schema(add_constraint_op)

    for column in constraint_columns(add_constraint_op):
        if drop_op.target == column_id(schema, table, column):
            return column

    return None


def make_drop_column_vs_add_constraint_conflict(
    *,
    dropped_column_id: str,
    constraint_id: str,
    constraint_column: str,
    context: RuleContext,
) -> Conflict:
    return Conflict(
        rule_id="C2_DROP_COLUMN_VS_ADD_CONSTRAINT",
        message=(
            "Column is dropped in one branch while a constraint depending on this "
            "column is added in another branch."
        ),
        object_ids=tuple(sorted({dropped_column_id, constraint_id})),
        severity=SeverityLevel.HIGH,
        operation_a=context.operation_a,
        operation_b=context.operation_b,
        metadata=freeze_attrs(
            {
                "dropped_column_id": dropped_column_id,
                "constraint_id": constraint_id,
                "constraint_column": constraint_column,
                "operation_a_type": type(context.operation_a).__name__,
                "operation_b_type": type(context.operation_b).__name__,
            }
        ),
    )


@dataclass(frozen=True)
class DropPrimaryKeyVsModifyDependentRule(BaseConflictRule):
    """
    Если одна ветка удаляет PRIMARY KEY constraint,
    а другая изменяет объект, зависящий от него, это конфликт.
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        if isinstance(a, DropOperation) and isinstance(b, ModifyOperation):
            if context.graph_a is not None and is_primary_key_constraint(context.graph_a, a.target):
                impacted = context.graph_b.impact_of_targets([b.target]) if context.graph_b else set()
                if a.target in impacted or a.target == b.target:
                    conflict = make_constraint_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "Primary key constraint is dropped in one branch while "
                            "a dependent object is modified in another branch."
                        ),
                        object_id=a.target,
                        dependent_id=b.target,
                        context=context,
                    )
                    return RuleCheckResult.from_conflict(conflict)

        if isinstance(a, ModifyOperation) and isinstance(b, DropOperation):
            if context.graph_b is not None and is_primary_key_constraint(context.graph_b, b.target):
                impacted = context.graph_a.impact_of_targets([a.target]) if context.graph_a else set()
                if b.target in impacted or b.target == a.target:
                    conflict = make_constraint_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "Primary key constraint is dropped in one branch while "
                            "a dependent object is modified in another branch."
                        ),
                        object_id=b.target,
                        dependent_id=a.target,
                        context=context,
                    )
                    return RuleCheckResult.from_conflict(conflict)

        return RuleCheckResult.no_match()


@dataclass(frozen=True)
class DropColumnVsAddConstraintRule(BaseConflictRule):
    """
    Конфликт:
    - одна ветка удаляет колонку;
    - другая ветка добавляет constraint, зависящий от этой колонки.

    Пример:
    A: users.email удалён
    B: email VARCHAR(255) UNIQUE
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        if isinstance(a, DropOperation) and is_add_constraint_operation(b):
            assert isinstance(b, AddOperation)

            constraint_column = dropped_column_used_by_constraint(a, b)

            if constraint_column is not None:
                return RuleCheckResult.from_conflict(
                    make_drop_column_vs_add_constraint_conflict(
                        dropped_column_id=a.target,
                        constraint_id=b.target,
                        constraint_column=constraint_column,
                        context=context,
                    )
                )

        if isinstance(b, DropOperation) and is_add_constraint_operation(a):
            assert isinstance(a, AddOperation)

            constraint_column = dropped_column_used_by_constraint(b, a)

            if constraint_column is not None:
                return RuleCheckResult.from_conflict(
                    make_drop_column_vs_add_constraint_conflict(
                        dropped_column_id=b.target,
                        constraint_id=a.target,
                        constraint_column=constraint_column,
                        context=context,
                    )
                )

        return RuleCheckResult.no_match()


CONSTRAINT_RULES = [
    DropPrimaryKeyVsModifyDependentRule(
        rule_id="C1_DROP_PRIMARY_KEY_VS_MODIFY_DEPENDENT",
        description="Drop primary key vs modify dependent object",
    ),
    DropColumnVsAddConstraintRule(
        rule_id="C2_DROP_COLUMN_VS_ADD_CONSTRAINT",
        description="Drop column vs add constraint depending on that column",
    ),
]
