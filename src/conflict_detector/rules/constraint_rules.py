from __future__ import annotations

from dataclasses import dataclass

from src.conflict_detector.core.models import (
    Conflict,
    ConstraintType,
    DropOperation,
    ModifyOperation,
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


@dataclass(frozen=True)
class DropPrimaryKeyVsModifyDependentRule(BaseConflictRule):
    """
    Если одна ветка удаляет PRIMARY KEY constraint,
    а другая изменяет объект, зависящий от него, это конфликт.

    MVP-трактовка:
    зависимость определяется через impact_of_targets().
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        if isinstance(a, DropOperation) and isinstance(b, ModifyOperation):
            if is_primary_key_constraint(context.graph_a, a.target):
                impacted = context.graph_b.impact_of_targets([b.target])
                if a.target in impacted or a.target == b.target:
                    conflict = make_constraint_conflict(
                        rule_id=self.rule_id,
                        message="Primary key constraint is dropped in one branch while a dependent object is modified in another branch.",
                        object_id=a.target,
                        dependent_id=b.target,
                        context=context,
                    )
                    return RuleCheckResult.from_conflict(conflict)

        if isinstance(a, ModifyOperation) and isinstance(b, DropOperation):
            if is_primary_key_constraint(context.graph_b, b.target):
                impacted = context.graph_a.impact_of_targets([a.target])
                if b.target in impacted or b.target == a.target:
                    conflict = make_constraint_conflict(
                        rule_id=self.rule_id,
                        message="Primary key constraint is dropped in one branch while a dependent object is modified in another branch.",
                        object_id=b.target,
                        dependent_id=a.target,
                        context=context,
                    )
                    return RuleCheckResult.from_conflict(conflict)

        return RuleCheckResult.no_match()


CONSTRAINT_RULES = [
    DropPrimaryKeyVsModifyDependentRule(
        rule_id="C1_DROP_PRIMARY_KEY_VS_MODIFY_DEPENDENT",
        description="Drop primary key vs modify dependent object",
    )
]
