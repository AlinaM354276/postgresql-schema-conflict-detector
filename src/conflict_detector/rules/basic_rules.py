from __future__ import annotations

from dataclasses import dataclass
from typing import List

from src.conflict_detector.core.models import (
    AddOperation,
    Conflict,
    DropOperation,
    ModifyOperation,
    Operation,
    RenameOperation,
    SeverityLevel,
    freeze_attrs,
)
from src.conflict_detector.rules.base import (
    BaseConflictRule,
    RuleCheckResult,
    RuleContext,
    same_target,
)


def op_target(operation: Operation) -> str | None:
    return getattr(operation, "target", None)


def make_conflict(
    *,
    rule_id: str,
    message: str,
    severity: SeverityLevel,
    context: RuleContext,
) -> Conflict:
    object_ids = tuple(
        sorted(
            {
                target
                for target in (
                    op_target(context.operation_a),
                    op_target(context.operation_b),
                )
                if target is not None
            }
        )
    )

    metadata = freeze_attrs(
        {
            "operation_a_type": type(context.operation_a).__name__,
            "operation_b_type": type(context.operation_b).__name__,
        }
    )

    return Conflict(
        rule_id=rule_id,
        message=message,
        object_ids=object_ids,
        severity=severity,
        operation_a=context.operation_a,
        operation_b=context.operation_b,
        metadata=metadata,
    )


@dataclass(frozen=True)
class DropVsModifyRule(BaseConflictRule):
    """
    Если одна ветка удаляет объект, а другая изменяет тот же объект,
    это конфликт высокой серьёзности.
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        cond_1 = isinstance(a, DropOperation) and isinstance(b, ModifyOperation)
        cond_2 = isinstance(a, ModifyOperation) and isinstance(b, DropOperation)

        if (cond_1 or cond_2) and same_target(a, b):
            conflict = make_conflict(
                rule_id=self.rule_id,
                message="Object is dropped in one branch and modified in another branch.",
                severity=SeverityLevel.HIGH,
                context=context,
            )
            return RuleCheckResult.from_conflict(conflict)

        return RuleCheckResult.no_match()


@dataclass(frozen=True)
class DropVsRenameRule(BaseConflictRule):
    """
    Если одна ветка удаляет объект, а другая переименовывает тот же объект,
    это конфликт высокой серьёзности.
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        cond_1 = isinstance(a, DropOperation) and isinstance(b, RenameOperation)
        cond_2 = isinstance(a, RenameOperation) and isinstance(b, DropOperation)

        if (cond_1 or cond_2) and same_target(a, b):
            conflict = make_conflict(
                rule_id=self.rule_id,
                message="Object is dropped in one branch and renamed in another branch.",
                severity=SeverityLevel.HIGH,
                context=context,
            )
            return RuleCheckResult.from_conflict(conflict)

        return RuleCheckResult.no_match()


@dataclass(frozen=True)
class RenameVsRenameRule(BaseConflictRule):
    """
    Если обе ветки переименовывают один и тот же объект в разные имена,
    это конфликт высокой серьёзности.
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        if not (isinstance(a, RenameOperation) and isinstance(b, RenameOperation)):
            return RuleCheckResult.no_match()

        if not same_target(a, b):
            return RuleCheckResult.no_match()

        if a.new_name != b.new_name:
            conflict = make_conflict(
                rule_id=self.rule_id,
                message="Object is renamed differently in two branches.",
                severity=SeverityLevel.HIGH,
                context=context,
            )
            return RuleCheckResult.from_conflict(conflict)

        return RuleCheckResult.no_match()


@dataclass(frozen=True)
class ModifyVsModifyRule(BaseConflictRule):
    """
    Если обе ветки модифицируют один и тот же объект и дельты различаются,
    считаем это конфликтом средней серьёзности.

    Для MVP правило простое:
    - одинаковый target
    - delta != delta
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        if not (isinstance(a, ModifyOperation) and isinstance(b, ModifyOperation)):
            return RuleCheckResult.no_match()

        if not same_target(a, b):
            return RuleCheckResult.no_match()

        if a.delta != b.delta:
            conflict = make_conflict(
                rule_id=self.rule_id,
                message="Object is modified differently in two branches.",
                severity=SeverityLevel.MEDIUM,
                context=context,
            )
            return RuleCheckResult.from_conflict(conflict)

        return RuleCheckResult.no_match()


@dataclass(frozen=True)
class AddVsAddRule(BaseConflictRule):
    """
    Если обе ветки добавляют один и тот же target, но с разными параметрами,
    считаем это конфликтом средней серьёзности.

    Для MVP сравниваем target и params.
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        if not (isinstance(a, AddOperation) and isinstance(b, AddOperation)):
            return RuleCheckResult.no_match()

        if not same_target(a, b):
            return RuleCheckResult.no_match()

        if a.params != b.params:
            conflict = make_conflict(
                rule_id=self.rule_id,
                message="Object is added differently in two branches.",
                severity=SeverityLevel.MEDIUM,
                context=context,
            )
            return RuleCheckResult.from_conflict(conflict)

        return RuleCheckResult.no_match()


@dataclass(frozen=True)
class RenameVsModifyRule(BaseConflictRule):
    """
    Если одна ветка переименовывает объект, а другая изменяет тот же объект,
    считаем это конфликтом средней серьёзности для MVP.
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        cond_1 = isinstance(a, RenameOperation) and isinstance(b, ModifyOperation)
        cond_2 = isinstance(a, ModifyOperation) and isinstance(b, RenameOperation)

        if (cond_1 or cond_2) and same_target(a, b):
            conflict = make_conflict(
                rule_id=self.rule_id,
                message="Object is renamed in one branch and modified in another branch.",
                severity=SeverityLevel.MEDIUM,
                context=context,
            )
            return RuleCheckResult.from_conflict(conflict)

        return RuleCheckResult.no_match()


BASIC_RULES: List[BaseConflictRule] = [
    DropVsModifyRule(
        rule_id="R1_DROP_VS_MODIFY",
        description="Drop vs Modify on the same target",
    ),
    DropVsRenameRule(
        rule_id="R2_DROP_VS_RENAME",
        description="Drop vs Rename on the same target",
    ),
    RenameVsRenameRule(
        rule_id="R3_RENAME_VS_RENAME",
        description="Different renames of the same target",
    ),
    ModifyVsModifyRule(
        rule_id="R4_MODIFY_VS_MODIFY",
        description="Different modifications of the same target",
    ),
    AddVsAddRule(
        rule_id="R5_ADD_VS_ADD",
        description="Different additions of the same target",
    ),
    RenameVsModifyRule(
        rule_id="R6_RENAME_VS_MODIFY",
        description="Rename vs Modify on the same target",
    ),
]
