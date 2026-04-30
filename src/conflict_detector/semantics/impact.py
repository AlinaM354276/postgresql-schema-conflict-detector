from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Set, Tuple

from src.conflict_detector.core.models import (
    AddOperation,
    DropOperation,
    ModifyOperation,
    Operation,
    ReferenceOperation,
    RenameOperation,
)


@dataclass(frozen=True)
class OperationImpact:
    operation: Operation
    targets: Tuple[str, ...]
    impacted_objects: Tuple[str, ...]

    def target_set(self) -> Set[str]:
        return set(self.targets)

    def impact_set(self) -> Set[str]:
        return set(self.impacted_objects)


def _parse_columns(raw: object) -> Tuple[str, ...]:
    if raw is None:
        return tuple()

    return tuple(
        part.strip()
        for part in str(raw).split(",")
        if part.strip()
    )


def _column_id(schema: str, table: str, column: str) -> str:
    return f"{schema}.{table}.{column}"


def _is_expression_column(column: str) -> bool:
    return "(" in column or ")" in column or " " in column


def _targets_from_add_operation(op: AddOperation) -> Set[str]:
    targets = {op.target}
    params = dict(op.params)

    object_type = params.get("object_type")

    if object_type in {"Index", "Constraint"}:
        schema = str(params.get("schema", "public"))
        table = params.get("table")
        columns = _parse_columns(params.get("columns"))

        if table:
            for column in columns:
                if _is_expression_column(column):
                    continue
                targets.add(_column_id(schema, str(table), column))

    edge_type = params.get("edge_type")
    source_id = params.get("source_id")
    target_id = params.get("target_id")

    if edge_type and source_id and target_id:
        targets.add(str(source_id))
        targets.add(str(target_id))

    return targets


def extract_targets(op: Operation) -> Set[str]:
    """
    targets(op) — объекты, непосредственно затрагиваемые операцией.
    """

    if isinstance(op, AddOperation):
        return _targets_from_add_operation(op)

    if isinstance(op, DropOperation):
        return {op.target}

    if isinstance(op, ModifyOperation):
        return {op.target}

    if isinstance(op, RenameOperation):
        return {op.target}

    if isinstance(op, ReferenceOperation):
        return {op.source, op.target}

    target = getattr(op, "target", None)
    return {target} if target else set()


def compute_impact(
    op: Operation,
    dep_closure: Dict[str, Set[str]],
) -> OperationImpact:
    """
    impact(op) = targets(op) ∪ dep*(targets(op))
    """

    targets = extract_targets(op)
    impacted = set(targets)

    for target in targets:
        impacted |= dep_closure.get(target, set())

    return OperationImpact(
        operation=op,
        targets=tuple(sorted(targets)),
        impacted_objects=tuple(sorted(impacted)),
    )


def compute_impact_map(
    operations: Iterable[Operation],
    dep_closure: Dict[str, Set[str]],
) -> Dict[int, OperationImpact]:
    """
    Возвращает mapping id(operation) -> OperationImpact.

    Используем id(operation), чтобы не зависеть от hashability dataclass-операций.
    """

    return {
        id(operation): compute_impact(operation, dep_closure)
        for operation in operations
    }


def impact_of(
    impact_map: Dict[int, OperationImpact],
    op: Operation,
) -> OperationImpact:
    return impact_map[id(op)]


def impacts_intersect(
    impact_map: Dict[int, OperationImpact],
    op_a: Operation,
    op_b: Operation,
) -> Set[str]:
    return (
        impact_of(impact_map, op_a).impact_set()
        & impact_of(impact_map, op_b).impact_set()
    )
