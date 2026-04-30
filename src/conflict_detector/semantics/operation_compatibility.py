from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from src.conflict_detector.core.models import (
    ModifyOperation,
    Operation,
    RenameOperation,
    ReferenceOperation,
)
from src.conflict_detector.semantics.apply import rename_object_id


IDENTITY_ATTRS = {
    "name",
    "object_id",
    "schema",
    "table",
}


@dataclass(frozen=True)
class CompatibilityResult:
    is_compatible: bool
    reason: str


def modify_changes_identity(op: ModifyOperation) -> bool:
    delta = dict(op.delta)
    return any(key in IDENTITY_ATTRS for key in delta.keys())


def rename_and_modify_are_compatible(
    rename_op: RenameOperation,
    modify_op: ModifyOperation,
) -> CompatibilityResult:
    if rename_op.target != modify_op.target:
        return CompatibilityResult(
            is_compatible=False,
            reason="Rename and Modify target different objects.",
        )

    if modify_changes_identity(modify_op):
        return CompatibilityResult(
            is_compatible=False,
            reason="Modify changes identity attributes and cannot commute with Rename.",
        )

    return CompatibilityResult(
        is_compatible=True,
        reason="Rename and Modify are compatible: Modify changes only non-identity attributes.",
    )


def operations_are_semantically_compatible(
    op_a: Operation,
    op_b: Operation,
) -> CompatibilityResult:
    if isinstance(op_a, RenameOperation) and isinstance(op_b, ModifyOperation):
        return rename_and_modify_are_compatible(op_a, op_b)

    if isinstance(op_a, ModifyOperation) and isinstance(op_b, RenameOperation):
        return rename_and_modify_are_compatible(op_b, op_a)

    return CompatibilityResult(
        is_compatible=False,
        reason="No semantic compatibility rule matched.",
    )


def rewrite_operation_target_after_rename(
    op: Operation,
    rename_op: RenameOperation,
) -> Operation:
    new_target = rename_object_id(rename_op.target, rename_op.new_name)

    if isinstance(op, ModifyOperation) and op.target == rename_op.target:
        return ModifyOperation(
            target=new_target,
            delta=op.delta,
        )

    if isinstance(op, ReferenceOperation):
        source = new_target if op.source == rename_op.target else op.source
        target = new_target if op.target == rename_op.target else op.target

        if source != op.source or target != op.target:
            return ReferenceOperation(
                source=source,
                target=target,
                change_type=op.change_type,
            )

    return op


def rewrite_operations_after_prior_renames(
    operations: Iterable[Operation],
    prior_operations: Iterable[Operation],
) -> Tuple[Operation, ...]:
    rewritten = tuple(operations)

    prior_renames = [
        op for op in prior_operations
        if isinstance(op, RenameOperation)
    ]

    for rename_op in prior_renames:
        rewritten = tuple(
            rewrite_operation_target_after_rename(op, rename_op)
            for op in rewritten
        )

    return rewritten
