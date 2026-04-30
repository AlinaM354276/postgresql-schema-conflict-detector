from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from src.conflict_detector.core.models import (
    AddOperation,
    Conflict,
    DropOperation,
    SeverityLevel,
    freeze_attrs,
)
from src.conflict_detector.rules.base import (
    BaseConflictRule,
    RuleCheckResult,
    RuleContext,
)


def params_dict(op: AddOperation) -> dict:
    return dict(op.params)


def is_add_index_operation(op: object) -> bool:
    if not isinstance(op, AddOperation):
        return False

    params = params_dict(op)
    return params.get("object_type") == "Index"


def parse_index_columns(raw: object) -> Tuple[str, ...]:
    if raw is None:
        return tuple()

    return tuple(
        part.strip()
        for part in str(raw).split(",")
        if part.strip()
    )


def column_id(schema: str, table: str, column: str) -> str:
    return f"{schema}.{table}.{column}"


def dropped_column_used_by_index(
    drop_op: DropOperation,
    add_index_op: AddOperation,
) -> Optional[str]:
    params = params_dict(add_index_op)

    schema = str(params.get("schema", "public"))
    table = params.get("table")
    columns = parse_index_columns(params.get("columns"))

    if not table or not columns:
        return None

    for column in columns:
        if drop_op.target == column_id(schema, str(table), column):
            return column

    return None


def make_index_conflict(
    *,
    dropped_column_id: str,
    index_id: str,
    index_column: str,
    context: RuleContext,
) -> Conflict:
    return Conflict(
        rule_id="I1_DROP_COLUMN_VS_ADD_INDEX",
        message=(
            "Column is dropped in one branch while an index depending on this "
            "column is added in another branch."
        ),
        object_ids=tuple(sorted({dropped_column_id, index_id})),
        severity=SeverityLevel.HIGH,
        operation_a=context.operation_a,
        operation_b=context.operation_b,
        metadata=freeze_attrs(
            {
                "dropped_column_id": dropped_column_id,
                "index_id": index_id,
                "index_column": index_column,
                "operation_a_type": type(context.operation_a).__name__,
                "operation_b_type": type(context.operation_b).__name__,
            }
        ),
    )


@dataclass(frozen=True)
class DropColumnVsAddIndexRule(BaseConflictRule):
    """
    Конфликт:
    - одна ветка удаляет колонку;
    - другая ветка добавляет индекс, построенный по этой колонке.

    Пример:
    A: ALTER TABLE orders DROP COLUMN status;
    B: CREATE INDEX idx_orders_status ON orders(status);
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        if isinstance(a, DropOperation) and is_add_index_operation(b):
            assert isinstance(b, AddOperation)
            index_column = dropped_column_used_by_index(a, b)

            if index_column is not None:
                return RuleCheckResult.from_conflict(
                    make_index_conflict(
                        dropped_column_id=a.target,
                        index_id=b.target,
                        index_column=index_column,
                        context=context,
                    )
                )

        if isinstance(b, DropOperation) and is_add_index_operation(a):
            assert isinstance(a, AddOperation)
            index_column = dropped_column_used_by_index(b, a)

            if index_column is not None:
                return RuleCheckResult.from_conflict(
                    make_index_conflict(
                        dropped_column_id=b.target,
                        index_id=a.target,
                        index_column=index_column,
                        context=context,
                    )
                )

        return RuleCheckResult.no_match()


INDEX_RULES = [
    DropColumnVsAddIndexRule(
        rule_id="I1_DROP_COLUMN_VS_ADD_INDEX",
        description="Drop column vs add index depending on that column",
    )
]
