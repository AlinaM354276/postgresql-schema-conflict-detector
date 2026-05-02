from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Set, Tuple

from src.conflict_detector.core.models import (
    AddOperation,
    Conflict,
    ConstraintType,
    DropOperation,
    EdgeType,
    ModifyOperation,
    ObjectType,
    Operation,
    ReferenceChangeType,
    ReferenceOperation,
    RenameOperation,
    SeverityLevel,
    freeze_attrs,
)
from src.conflict_detector.rules.base import (
    BaseConflictRule,
    RuleCheckResult,
    RuleContext,
)


def op_target(operation: Operation) -> str | None:
    return getattr(operation, "target", None)


def operation_targets(operation: Operation) -> Set[str]:
    result: Set[str] = set()

    target = getattr(operation, "target", None)
    source = getattr(operation, "source", None)

    if target is not None:
        result.add(target)

    if source is not None:
        result.add(source)

    if isinstance(operation, AddOperation):
        params = dict(operation.params)
        source_id = params.get("source_id")
        target_id = params.get("target_id")

        if source_id is not None:
            result.add(str(source_id))
        if target_id is not None:
            result.add(str(target_id))

    return result


def renamed_object_id(target: str, new_name: str) -> str:
    parts = target.split(".")
    if not parts:
        return new_name
    parts[-1] = new_name
    return ".".join(parts)


def is_table_id(object_id: str) -> bool:
    return len(object_id.split(".")) == 2


def parent_table_id(object_id: str) -> str | None:
    parts = object_id.split(".")

    if len(parts) < 3:
        return None

    return ".".join(parts[:2])


def table_contains_object(table_id: str, object_id: str) -> bool:
    return parent_table_id(object_id) == table_id


def drop_removes_reference_endpoint(
    drop_op: DropOperation,
    reference_op: ReferenceOperation,
) -> bool:
    """
    Проверяет, что DropOperation удаляет source/target ссылки.

    Случаи:
    - Drop(public.users.id) удаляет target public.users.id;
    - Drop(public.users) удаляет target public.users.id, потому что это таблица-владелец.
    """
    if drop_op.target in {reference_op.source, reference_op.target}:
        return True

    if is_table_id(drop_op.target):
        return (
            table_contains_object(drop_op.target, reference_op.source)
            or table_contains_object(drop_op.target, reference_op.target)
        )

    return False


def is_add_table_operation(op: Operation) -> bool:
    if not isinstance(op, AddOperation):
        return False

    params = dict(op.params)
    return params.get("object_type") == "Table"


def table_member_suffix(table_id: str, object_id: str) -> str | None:
    """
    Возвращает локальную часть объекта внутри таблицы.

    public.logs.id -> id
    public.logs.primary_key_logs_id -> primary_key_logs_id
    """
    prefix = table_id + "."

    if object_id.startswith(prefix):
        return object_id.removeprefix(prefix)

    return None


def graph_table_signature(graph, table_id: str) -> tuple:
    """
    Сигнатура содержимого таблицы в конкретной ветке.

    Используется для R4:
    две ветви добавили таблицу с одним именем, но с разным набором колонок /
    ограничений / индексов.
    """
    if graph is None:
        return tuple()

    members = []

    for obj in graph.vertices.values():
        if obj.object_id == table_id:
            continue

        suffix = table_member_suffix(table_id, obj.object_id)
        if suffix is None:
            continue

        attrs = tuple(sorted(obj.attr_dict().items()))

        members.append(
            (
                suffix,
                obj.object_type.value,
                obj.name,
                attrs,
            )
        )

    return tuple(sorted(members))


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


def add_operation_uses_column(op: AddOperation, column: str) -> bool:
    params = params_dict(op)

    schema = str(params.get("schema", "public"))
    table = params.get("table")
    columns = parse_columns(params.get("columns"))

    if not table:
        return False

    for col in columns:
        if column_id(schema, str(table), col) == column:
            return True

    return False


def add_operation_is_dependency_on_column(op: AddOperation, column: str) -> bool:
    params = params_dict(op)
    object_type = params.get("object_type")

    if object_type in {"Constraint", "Index"}:
        return add_operation_uses_column(op, column)

    edge_source = params.get("source_id")
    edge_target = params.get("target_id")

    return column in {
        str(edge_source) if edge_source is not None else "",
        str(edge_target) if edge_target is not None else "",
    }


def delta_dict(op: ModifyOperation) -> dict:
    return dict(op.delta)


def type_changed(op: ModifyOperation) -> bool:
    delta = delta_dict(op)
    return "data_type" in delta or "data_type_raw" in delta


def is_reference_add(op: Operation) -> bool:
    return (
        isinstance(op, ReferenceOperation)
        and op.change_type == ReferenceChangeType.ADD
    )


def is_reference_drop(op: Operation) -> bool:
    return (
        isinstance(op, ReferenceOperation)
        and op.change_type == ReferenceChangeType.DROP
    )


def operation_assumes_column_type(op: Operation, column: str) -> bool:
    """
    Проверяет, что операция зависит от типа данной колонки.

    Это нужно для R2:
    изменение типа в одной ветке конфликтует с constraint/index/reference,
    которые были добавлены во второй ветке и рассчитаны на старый тип.
    """
    if isinstance(op, ReferenceOperation):
        return column in {op.source, op.target}

    if isinstance(op, AddOperation):
        return add_operation_is_dependency_on_column(op, column)

    if isinstance(op, ModifyOperation):
        return op.target == column

    return False


def same_operation_kind(a: Operation, b: Operation) -> bool:
    return type(a) is type(b)


def operations_are_identical_or_compatible(a: Operation, b: Operation) -> bool:
    """
    Совместимые случаи, которые не должны превращаться в R6.
    """
    if isinstance(a, AddOperation) and isinstance(b, AddOperation):
        return a.target == b.target and a.params == b.params

    if isinstance(a, DropOperation) and isinstance(b, DropOperation):
        return a.target == b.target

    if isinstance(a, ModifyOperation) and isinstance(b, ModifyOperation):
        return a.target == b.target and a.delta == b.delta

    if isinstance(a, RenameOperation) and isinstance(b, RenameOperation):
        return a.target == b.target and a.new_name == b.new_name

    if isinstance(a, ReferenceOperation) and isinstance(b, ReferenceOperation):
        return (
            a.source == b.source
            and a.target == b.target
            and a.change_type == b.change_type
        )

    return False


def make_hashable(value: object) -> object:
    """
    Преобразует вложенные структуры в hashable-вид,
    чтобы их можно было безопасно передать в freeze_attrs().
    """
    if isinstance(value, dict):
        return tuple(
            sorted(
                (str(k), make_hashable(v))
                for k, v in value.items()
            )
        )

    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(make_hashable(item) for item in value)

    return value


def freeze_metadata(data: dict) -> frozenset:
    return freeze_attrs(
        {
            str(key): make_hashable(value)
            for key, value in data.items()
        }
    )


def make_conflict(
    *,
    rule_id: str,
    message: str,
    severity: SeverityLevel,
    context: RuleContext,
    object_ids: Iterable[str],
    metadata: dict | None = None,
) -> Conflict:
    metadata_payload = {
        "operation_a_type": type(context.operation_a).__name__,
        "operation_b_type": type(context.operation_b).__name__,
    }

    if context.shared_impact:
        metadata_payload["shared_impact"] = tuple(context.shared_impact)

    if context.dependency_trace:
        metadata_payload["dependency_trace"] = context.dependency_trace

    if metadata:
        metadata_payload.update(metadata)

    return Conflict(
        rule_id=rule_id,
        message=message,
        object_ids=tuple(sorted(set(object_ids))),
        severity=severity,
        operation_a=context.operation_a,
        operation_b=context.operation_b,
        metadata=freeze_metadata(metadata_payload),
    )


import re


def graph_vertex(graph, object_id: str):
    if graph is None:
        return None
    return graph.get_vertex(object_id)


def is_index_object(graph, object_id: str) -> bool:
    obj = graph_vertex(graph, object_id)
    return obj is not None and obj.object_type == ObjectType.INDEX


def is_constraint_object(graph, object_id: str) -> bool:
    obj = graph_vertex(graph, object_id)
    return obj is not None and obj.object_type == ObjectType.CONSTRAINT


def index_column_ids(graph, index_id: str) -> set[str]:
    """
    Возвращает колонки, на которых построен индекс.

    Например:
    public.orders.idx_orders_user_email(columns='user_email,id')
    ->
    {
        public.orders.user_email,
        public.orders.id
    }
    """
    obj = graph_vertex(graph, index_id)
    if obj is None:
        return set()

    attrs = obj.attr_dict()
    schema = str(attrs.get("schema", "public"))
    table = attrs.get("table")
    columns = parse_columns(attrs.get("columns"))

    if not table:
        return set()

    result: set[str] = set()

    for column in columns:
        if "(" in column or ")" in column or " " in column:
            continue

        result.add(column_id(schema, str(table), column))

    return result


def graph_has_reference_source_to_target(graph, source_id: str, target_id: str) -> bool:
    if graph is None:
        return False

    for edge in graph.find_edges_by_type(EdgeType.REFERENCES):
        if edge.source_id == source_id and edge.target_id == target_id:
            return True

    return False


def index_depends_on_changed_column(
    graph,
    index_id: str,
    changed_column_id: str,
) -> bool:
    """
    Проверяет, зависит ли индекс от изменённой колонки.

    Поддерживает:
    1. прямой индекс по этой колонке;
    2. индекс по FK-source колонке, которая references changed_column_id.

    Это нужно для R6:
    users.email меняет тип,
    orders.user_email индексируется,
    orders.user_email -> users.email.
    """
    columns = index_column_ids(graph, index_id)

    if changed_column_id in columns:
        return True

    for col_id in columns:
        if graph_has_reference_source_to_target(
            graph=graph,
            source_id=col_id,
            target_id=changed_column_id,
        ):
            return True

    return False


def is_modify_index_operation(op: Operation, graph) -> bool:
    return isinstance(op, ModifyOperation) and is_index_object(graph, op.target)


def is_modify_column_type_operation(op: Operation, graph) -> bool:
    obj = graph_vertex(graph, getattr(op, "target", ""))

    return (
        isinstance(op, ModifyOperation)
        and obj is not None
        and obj.object_type == ObjectType.COLUMN
        and type_changed(op)
    )


def make_r6_index_dependency_conflict(
    *,
    context: RuleContext,
    changed_column_id: str,
    index_id: str,
) -> Conflict:
    return make_conflict(
        rule_id="R6_TRANSITIVE_DEPENDENCY_CONFLICT",
        message=(
            "Column type is changed in one branch while another branch modifies "
            "an index that depends on this column through a transitive dependency."
        ),
        severity=SeverityLevel.MEDIUM,
        context=context,
        object_ids={changed_column_id, index_id},
        metadata={
            "kind": "transitive_dependency_conflict",
            "changed_column_id": changed_column_id,
            "dependent_index_id": index_id,
        },
    )


def is_add_check_constraint(op: Operation) -> bool:
    if not isinstance(op, AddOperation):
        return False

    params = dict(op.params)

    return (
        params.get("object_type") == ObjectType.CONSTRAINT.value
        and params.get("constraint_type") == ConstraintType.CHECK.value
    )


def check_constraint_table(op: AddOperation) -> str | None:
    params = dict(op.params)
    schema = str(params.get("schema", "public"))
    table = params.get("table")

    if not table:
        return None

    return f"{schema}.{table}"


def check_constraint_expression(op: AddOperation) -> str | None:
    params = dict(op.params)
    expression = params.get("expression")

    if expression is None:
        return None

    return str(expression).strip()


@dataclass(frozen=True)
class SimpleCheckBound:
    column: str
    lower_value: float | None = None
    lower_strict: bool = False
    upper_value: float | None = None
    upper_strict: bool = False


def _reverse_operator(op: str) -> str:
    return {
        ">": "<",
        ">=": "<=",
        "<": ">",
        "<=": ">=",
        "=": "=",
    }[op]


def parse_simple_check_bound(expression: str) -> SimpleCheckBound | None:
    """
    Разбирает простые CHECK-выражения вида:
    - price > 0
    - price >= 0
    - price < 0
    - price <= 0
    - 0 < price
    - 0 >= price

    Этого достаточно для кейса:
    CHECK(price > 0) vs CHECK(price <= 0).
    """
    expr = expression.strip().lower()
    expr = expr.strip("() ")
    expr = re.sub(r"\s+", " ", expr)

    ident = r"[a-zA-Z_][a-zA-Z0-9_]*"
    number = r"-?\d+(?:\.\d+)?"

    direct = re.match(
        rf"^(?P<column>{ident})\s*(?P<op>>=|<=|>|<|=)\s*(?P<value>{number})$",
        expr,
    )

    if direct:
        column = direct.group("column")
        op = direct.group("op")
        value = float(direct.group("value"))
    else:
        reverse = re.match(
            rf"^(?P<value>{number})\s*(?P<op>>=|<=|>|<|=)\s*(?P<column>{ident})$",
            expr,
        )
        if not reverse:
            return None

        column = reverse.group("column")
        op = _reverse_operator(reverse.group("op"))
        value = float(reverse.group("value"))

    if op == ">":
        return SimpleCheckBound(column=column, lower_value=value, lower_strict=True)

    if op == ">=":
        return SimpleCheckBound(column=column, lower_value=value, lower_strict=False)

    if op == "<":
        return SimpleCheckBound(column=column, upper_value=value, upper_strict=True)

    if op == "<=":
        return SimpleCheckBound(column=column, upper_value=value, upper_strict=False)

    if op == "=":
        return SimpleCheckBound(
            column=column,
            lower_value=value,
            lower_strict=False,
            upper_value=value,
            upper_strict=False,
        )

    return None


def check_bounds_contradict(
    left: SimpleCheckBound,
    right: SimpleCheckBound,
) -> bool:
    if left.column != right.column:
        return False

    lower_value = None
    lower_strict = False

    for bound in (left, right):
        if bound.lower_value is None:
            continue

        if lower_value is None or bound.lower_value > lower_value:
            lower_value = bound.lower_value
            lower_strict = bound.lower_strict
        elif bound.lower_value == lower_value:
            lower_strict = lower_strict or bound.lower_strict

    upper_value = None
    upper_strict = False

    for bound in (left, right):
        if bound.upper_value is None:
            continue

        if upper_value is None or bound.upper_value < upper_value:
            upper_value = bound.upper_value
            upper_strict = bound.upper_strict
        elif bound.upper_value == upper_value:
            upper_strict = upper_strict or bound.upper_strict

    if lower_value is None or upper_value is None:
        return False

    if lower_value > upper_value:
        return True

    if lower_value == upper_value and (lower_strict or upper_strict):
        return True

    return False


def check_constraints_contradict(left: AddOperation, right: AddOperation) -> bool:
    left_expr = check_constraint_expression(left)
    right_expr = check_constraint_expression(right)

    if not left_expr or not right_expr:
        return False

    left_bound = parse_simple_check_bound(left_expr)
    right_bound = parse_simple_check_bound(right_expr)

    if left_bound is None or right_bound is None:
        return False

    return check_bounds_contradict(left_bound, right_bound)


@dataclass(frozen=True)
class R3DanglingReferenceRule(BaseConflictRule):
    """
    R3. Ссылка на отсутствующий объект.

    Смысл:
    одна ветвь создаёт ссылку на объект, который в другой ветви удалён полностью.

    Типичный случай:
    - A: Add Reference(public.orders.user_id -> public.users.id)
    - B: Drop Table(public.users)

    Важно:
    R3 отличается от R1 тем, что здесь удаляется не просто атрибут,
    а родительский объект, из-за чего ссылка становится висячей.
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        if is_reference_add(a) and isinstance(b, DropOperation):
            assert isinstance(a, ReferenceOperation)

            # Для R3 главный случай — удаление таблицы/родительского объекта.
            if is_table_id(b.target) and drop_removes_reference_endpoint(b, a):
                return RuleCheckResult.from_conflict(
                    make_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "A foreign-key reference is added in one branch, "
                            "but the table containing its source or target is dropped "
                            "in another branch."
                        ),
                        severity=SeverityLevel.CRITICAL,
                        context=context,
                        object_ids={a.source, a.target, b.target},
                        metadata={
                            "reference_source_id": a.source,
                            "reference_target_id": a.target,
                            "dropped_object_id": b.target,
                            "kind": "dangling_reference",
                        },
                    )
                )

        if isinstance(a, DropOperation) and is_reference_add(b):
            assert isinstance(b, ReferenceOperation)

            if is_table_id(a.target) and drop_removes_reference_endpoint(a, b):
                return RuleCheckResult.from_conflict(
                    make_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "A foreign-key reference is added in one branch, "
                            "but the table containing its source or target is dropped "
                            "in another branch."
                        ),
                        severity=SeverityLevel.CRITICAL,
                        context=context,
                        object_ids={b.source, b.target, a.target},
                        metadata={
                            "reference_source_id": b.source,
                            "reference_target_id": b.target,
                            "dropped_object_id": a.target,
                            "kind": "dangling_reference",
                        },
                    )
                )

        return RuleCheckResult.no_match()


@dataclass(frozen=True)
class R2TypeInconsistencyRule(BaseConflictRule):
    """
    R2. Несовместимость типов.

    Modify(column, data_type/data_type_raw) конфликтует с операцией другой ветки,
    которая зависит от старого типа этой колонки:
    - Add FK/reference;
    - Add constraint;
    - Add index;
    - Modify зависимого объекта.
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        if isinstance(a, ModifyOperation) and type_changed(a):
            column = a.target

            if (
                column in set(context.shared_impact)
                or column in operation_targets(b)
                or operation_assumes_column_type(b, column)
            ):
                if operation_assumes_column_type(b, column):
                    return RuleCheckResult.from_conflict(
                        make_conflict(
                            rule_id=self.rule_id,
                            message=(
                                "Column data type is changed in one branch while "
                                "another branch adds or modifies a dependent object "
                                "that assumes the old column type."
                            ),
                            severity=SeverityLevel.HIGH,
                            context=context,
                            object_ids={column, *operation_targets(b)},
                            metadata={
                                "changed_column_id": column,
                                "new_type_delta": delta_dict(a),
                                "kind": "type_inconsistency",
                            },
                        )
                    )

        if isinstance(b, ModifyOperation) and type_changed(b):
            column = b.target

            if (
                column in set(context.shared_impact)
                or column in operation_targets(a)
                or operation_assumes_column_type(a, column)
            ):
                if operation_assumes_column_type(a, column):
                    return RuleCheckResult.from_conflict(
                        make_conflict(
                            rule_id=self.rule_id,
                            message=(
                                "Column data type is changed in one branch while "
                                "another branch adds or modifies a dependent object "
                                "that assumes the old column type."
                            ),
                            severity=SeverityLevel.HIGH,
                            context=context,
                            object_ids={column, *operation_targets(a)},
                            metadata={
                                "changed_column_id": column,
                                "new_type_delta": delta_dict(b),
                                "kind": "type_inconsistency",
                            },
                        )
                    )

        return RuleCheckResult.no_match()


@dataclass(frozen=True)
class R4NamingConflictRule(BaseConflictRule):
    """
    R4. Конфликт именования / correspondence conflict.

    Случаи:
    1. Обе ветви добавляют один и тот же object_id с разными параметрами.
    2. Обе ветви добавляют таблицу с одним именем, но разным содержимым.

    Пример:
    A: CREATE TABLE logs(id, message)
    B: CREATE TABLE logs(id, event_type, created_at)
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        if not (isinstance(a, AddOperation) and isinstance(b, AddOperation)):
            return RuleCheckResult.no_match()

        if a.target != b.target:
            return RuleCheckResult.no_match()

        # Один и тот же объект, но разные параметры.
        if a.params != b.params:
            return RuleCheckResult.from_conflict(
                make_conflict(
                    rule_id=self.rule_id,
                    message=(
                        "The same object identity is added in both branches, "
                        "but object definitions are different."
                    ),
                    severity=SeverityLevel.HIGH,
                    context=context,
                    object_ids={a.target},
                    metadata={
                        "kind": "naming_conflict",
                        "params_a": dict(a.params),
                        "params_b": dict(b.params),
                    },
                )
            )

        # Специальный случай: обе ветви добавили таблицу с одинаковым именем,
        # но с разным составом колонок/ограничений.
        if is_add_table_operation(a) and is_add_table_operation(b):
            signature_a = graph_table_signature(context.graph_a, a.target)
            signature_b = graph_table_signature(context.graph_b, b.target)

            if signature_a != signature_b:
                return RuleCheckResult.from_conflict(
                    make_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "The same table name is added in both branches, "
                            "but table structures are different."
                        ),
                        severity=SeverityLevel.HIGH,
                        context=context,
                        object_ids={a.target},
                        metadata={
                            "kind": "table_naming_conflict",
                            "table_id": a.target,
                            "table_signature_a": signature_a,
                            "table_signature_b": signature_b,
                        },
                    )
                )

        return RuleCheckResult.no_match()


@dataclass(frozen=True)
class R5RenameAwareConflictRule(BaseConflictRule):
    """
    R5. Rename-aware conflict.

    Обрабатывает:
    - Drop vs Rename одного объекта;
    - Rename vs Rename с разными new_name;
    - Rename vs Add, если rename приводит к уже добавленному object_id;
    - Rename vs Modify, если операция другой ветки работает со старой identity.
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        if isinstance(a, DropOperation) and isinstance(b, RenameOperation):
            if a.target == b.target:
                return RuleCheckResult.from_conflict(
                    make_conflict(
                        rule_id=self.rule_id,
                        message="Object is dropped in one branch and renamed in another branch.",
                        severity=SeverityLevel.HIGH,
                        context=context,
                        object_ids={a.target},
                        metadata={"kind": "drop_vs_rename"},
                    )
                )

        if isinstance(a, RenameOperation) and isinstance(b, DropOperation):
            if a.target == b.target:
                return RuleCheckResult.from_conflict(
                    make_conflict(
                        rule_id=self.rule_id,
                        message="Object is renamed in one branch and dropped in another branch.",
                        severity=SeverityLevel.HIGH,
                        context=context,
                        object_ids={a.target},
                        metadata={"kind": "rename_vs_drop"},
                    )
                )

        if isinstance(a, RenameOperation) and isinstance(b, RenameOperation):
            if a.target == b.target and a.new_name != b.new_name:
                return RuleCheckResult.from_conflict(
                    make_conflict(
                        rule_id=self.rule_id,
                        message="The same object is renamed differently in two branches.",
                        severity=SeverityLevel.HIGH,
                        context=context,
                        object_ids={a.target},
                        metadata={
                            "kind": "rename_vs_rename",
                            "new_name_a": a.new_name,
                            "new_name_b": b.new_name,
                        },
                    )
                )

        if isinstance(a, RenameOperation) and isinstance(b, AddOperation):
            renamed_id = renamed_object_id(a.target, a.new_name)
            if renamed_id == b.target:
                return RuleCheckResult.from_conflict(
                    make_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "Rename in one branch produces an object identity "
                            "that is independently added in another branch."
                        ),
                        severity=SeverityLevel.HIGH,
                        context=context,
                        object_ids={a.target, b.target},
                        metadata={
                            "kind": "rename_collision",
                            "renamed_object_id": renamed_id,
                        },
                    )
                )

        if isinstance(a, AddOperation) and isinstance(b, RenameOperation):
            renamed_id = renamed_object_id(b.target, b.new_name)
            if renamed_id == a.target:
                return RuleCheckResult.from_conflict(
                    make_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "Rename in one branch produces an object identity "
                            "that is independently added in another branch."
                        ),
                        severity=SeverityLevel.HIGH,
                        context=context,
                        object_ids={a.target, b.target},
                        metadata={
                            "kind": "rename_collision",
                            "renamed_object_id": renamed_id,
                        },
                    )
                )

        if isinstance(a, RenameOperation) and isinstance(b, ModifyOperation):
            if a.target == b.target:
                return RuleCheckResult.from_conflict(
                    make_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "Object is renamed in one branch while another branch "
                            "modifies the same object using the old identity."
                        ),
                        severity=SeverityLevel.MEDIUM,
                        context=context,
                        object_ids={a.target},
                        metadata={"kind": "rename_vs_modify"},
                    )
                )

        if isinstance(a, ModifyOperation) and isinstance(b, RenameOperation):
            if a.target == b.target:
                return RuleCheckResult.from_conflict(
                    make_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "Object is modified in one branch while another branch "
                            "renames the same object."
                        ),
                        severity=SeverityLevel.MEDIUM,
                        context=context,
                        object_ids={a.target},
                        metadata={"kind": "modify_vs_rename"},
                    )
                )

        return RuleCheckResult.no_match()


@dataclass(frozen=True)
class R1ReferentialIntegrityRule(BaseConflictRule):
    """
    R1. Разрушение ссылочной целостности.

    Смысл:
    одна ветвь удаляет объект, а другая ветвь создаёт или изменяет
    зависимость, использующую этот объект.

    Основные случаи:
    - Drop(column) vs Add Reference(source -> dropped column);
    - Drop(column) vs Add Constraint/Index, использующий dropped column;
    - Drop(prerequisite) vs Modify/Rename/Add dependent object через impact.
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        # Если одна операция добавляет ссылку, а другая удаляет таблицу,
        # это R3_DANGLING_REFERENCE, а не R1.
        if is_reference_add(a) and isinstance(b, DropOperation) and is_table_id(b.target):
            return RuleCheckResult.no_match()

        if isinstance(a, DropOperation) and is_reference_add(b) and is_table_id(a.target):
            return RuleCheckResult.no_match()

        # ---------- точный случай: Drop vs Add Reference ----------

        if isinstance(a, DropOperation) and is_reference_add(b):
            assert isinstance(b, ReferenceOperation)

            if a.target in {b.source, b.target}:
                return RuleCheckResult.from_conflict(
                    make_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "Object is dropped in one branch while another branch "
                            "adds a foreign-key reference using this object."
                        ),
                        severity=SeverityLevel.CRITICAL,
                        context=context,
                        object_ids={a.target, b.source, b.target},
                        metadata={
                            "dropped_object_id": a.target,
                            "reference_source_id": b.source,
                            "reference_target_id": b.target,
                            "kind": "referential_integrity_conflict",
                        },
                    )
                )

        if isinstance(b, DropOperation) and is_reference_add(a):
            assert isinstance(a, ReferenceOperation)

            if b.target in {a.source, a.target}:
                return RuleCheckResult.from_conflict(
                    make_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "Object is dropped in one branch while another branch "
                            "adds a foreign-key reference using this object."
                        ),
                        severity=SeverityLevel.CRITICAL,
                        context=context,
                        object_ids={b.target, a.source, a.target},
                        metadata={
                            "dropped_object_id": b.target,
                            "reference_source_id": a.source,
                            "reference_target_id": a.target,
                            "kind": "referential_integrity_conflict",
                        },
                    )
                )

        # ---------- Drop vs Add Constraint/Index using dropped column ----------

        if isinstance(a, DropOperation) and isinstance(b, AddOperation):
            if add_operation_is_dependency_on_column(b, a.target):
                return RuleCheckResult.from_conflict(
                    make_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "Object is dropped in one branch while another branch "
                            "adds a constraint or index depending on this object."
                        ),
                        severity=SeverityLevel.CRITICAL,
                        context=context,
                        object_ids={a.target, b.target},
                        metadata={
                            "dropped_object_id": a.target,
                            "dependent_object_id": b.target,
                            "kind": "referential_integrity_conflict",
                        },
                    )
                )

        if isinstance(b, DropOperation) and isinstance(a, AddOperation):
            if add_operation_is_dependency_on_column(a, b.target):
                return RuleCheckResult.from_conflict(
                    make_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "Object is dropped in one branch while another branch "
                            "adds a constraint or index depending on this object."
                        ),
                        severity=SeverityLevel.CRITICAL,
                        context=context,
                        object_ids={b.target, a.target},
                        metadata={
                            "dropped_object_id": b.target,
                            "dependent_object_id": a.target,
                            "kind": "referential_integrity_conflict",
                        },
                    )
                )

        # ---------- общий dependency/impact случай ----------

        if isinstance(a, DropOperation):
            impacted_b = (
                set(context.impact_b.impacted_objects)
                if context.impact_b is not None
                else set()
            )

            if a.target in impacted_b and a.target != getattr(b, "target", None):
                return RuleCheckResult.from_conflict(
                    make_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "Object is dropped in one branch while another branch "
                            "uses this object directly or through dependencies."
                        ),
                        severity=SeverityLevel.CRITICAL,
                        context=context,
                        object_ids={a.target, *operation_targets(b)},
                        metadata={
                            "dropped_object_id": a.target,
                            "kind": "referential_integrity_conflict",
                        },
                    )
                )

        if isinstance(b, DropOperation):
            impacted_a = (
                set(context.impact_a.impacted_objects)
                if context.impact_a is not None
                else set()
            )

            if b.target in impacted_a and b.target != getattr(a, "target", None):
                return RuleCheckResult.from_conflict(
                    make_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "Object is dropped in one branch while another branch "
                            "uses this object directly or through dependencies."
                        ),
                        severity=SeverityLevel.CRITICAL,
                        context=context,
                        object_ids={b.target, *operation_targets(a)},
                        metadata={
                            "dropped_object_id": b.target,
                            "kind": "referential_integrity_conflict",
                        },
                    )
                )

        return RuleCheckResult.no_match()


@dataclass(frozen=True)
class R7SemanticIncompatibilityRule(BaseConflictRule):
    """
    R7. Семантическая несовместимость.

    Здесь реализован практический случай:
    две ветви добавляют CHECK-ограничения, которые не могут одновременно
    выполняться.

    Пример:
    - CHECK(price > 0)
    - CHECK(price <= 0)
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        if not (is_add_check_constraint(a) and is_add_check_constraint(b)):
            return RuleCheckResult.no_match()

        assert isinstance(a, AddOperation)
        assert isinstance(b, AddOperation)

        table_a = check_constraint_table(a)
        table_b = check_constraint_table(b)

        if table_a != table_b:
            return RuleCheckResult.no_match()

        if not check_constraints_contradict(a, b):
            return RuleCheckResult.no_match()

        expr_a = check_constraint_expression(a)
        expr_b = check_constraint_expression(b)

        return RuleCheckResult.from_conflict(
            make_conflict(
                rule_id=self.rule_id,
                message=(
                    "Branches add CHECK constraints that cannot be satisfied "
                    "simultaneously."
                ),
                severity=SeverityLevel.CRITICAL,
                context=context,
                object_ids={a.target, b.target},
                metadata={
                    "kind": "semantic_incompatibility",
                    "constraint_a": a.target,
                    "constraint_b": b.target,
                    "expression_a": expr_a,
                    "expression_b": expr_b,
                },
            )
        )


@dataclass(frozen=True)
class R6TransitiveDependencyConflictRule(BaseConflictRule):
    """
    R6. Транзитивный конфликт.

    Основной сценарий:
    одна ветвь изменяет объект, а другая изменяет зависимый объект,
    причём зависимость выводится транзитивно.

    Пример:
    - A: users.email меняет тип;
    - B: индекс orders.idx_orders_user_email меняет состав колонок;
    - orders.user_email references users.email.
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        # Drop-сценарии — это R1/R3.
        if isinstance(a, DropOperation) or isinstance(b, DropOperation):
            return RuleCheckResult.no_match()

        # ---------- специальный R6: type change vs modified dependent index ----------

        if is_modify_column_type_operation(a, context.graph_a) and is_modify_index_operation(b, context.graph_b):
            if index_depends_on_changed_column(
                graph=context.graph_b,
                index_id=b.target,
                changed_column_id=a.target,
            ):
                return RuleCheckResult.from_conflict(
                    make_r6_index_dependency_conflict(
                        context=context,
                        changed_column_id=a.target,
                        index_id=b.target,
                    )
                )

        if is_modify_index_operation(a, context.graph_a) and is_modify_column_type_operation(b, context.graph_b):
            if index_depends_on_changed_column(
                graph=context.graph_a,
                index_id=a.target,
                changed_column_id=b.target,
            ):
                return RuleCheckResult.from_conflict(
                    make_r6_index_dependency_conflict(
                        context=context,
                        changed_column_id=b.target,
                        index_id=a.target,
                    )
                )

        # ---------- общий R6 ----------

        if not context.shared_impact:
            return RuleCheckResult.no_match()

        # Изменение типа само по себе не должно уходить в общий R6:
        # type inconsistency — это R2, а специальный index case обработан выше.
        if isinstance(a, ModifyOperation) and type_changed(a):
            return RuleCheckResult.no_match()

        if isinstance(b, ModifyOperation) and type_changed(b):
            return RuleCheckResult.no_match()

        # Add/Add-сценарии — это R4 или не конфликт.
        if isinstance(a, AddOperation) and isinstance(b, AddOperation):
            return RuleCheckResult.no_match()

        if operations_are_identical_or_compatible(a, b):
            return RuleCheckResult.no_match()

        return RuleCheckResult.no_match()


BASIC_RULES: List[BaseConflictRule] = [
    R3DanglingReferenceRule(
        rule_id="R3_DANGLING_REFERENCE",
        description="Reference points to object removed by table/object deletion",
    ),
    R1ReferentialIntegrityRule(
        rule_id="R1_REFERENTIAL_INTEGRITY",
        description="Drop prerequisite object used by another operation",
    ),
    R2TypeInconsistencyRule(
        rule_id="R2_TYPE_INCONSISTENCY",
        description="Type change conflicts with dependent operation",
    ),
    R4NamingConflictRule(
        rule_id="R4_NAMING_CONFLICT",
        description="Same name/object identity added with different definitions",
    ),
    R5RenameAwareConflictRule(
        rule_id="R5_RENAME_AWARE_CONFLICT",
        description="Rename-aware identity conflict",
    ),
    R7SemanticIncompatibilityRule(
        rule_id="R7_SEMANTIC_INCOMPATIBILITY",
        description="Contradictory semantic constraints",
    ),
    R6TransitiveDependencyConflictRule(
        rule_id="R6_TRANSITIVE_DEPENDENCY_CONFLICT",
        description="Dependency-induced conflict through impact intersection",
    ),
]

