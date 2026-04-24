from __future__ import annotations

from dataclasses import dataclass

from src.conflict_detector.core.models import (
    Conflict,
    DropOperation,
    EdgeType,
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


def make_reference_conflict(
    *,
    rule_id: str,
    message: str,
    source_id: str,
    target_id: str,
    context: RuleContext,
) -> Conflict:
    metadata = freeze_attrs(
        {
            "reference_source_id": source_id,
            "reference_target_id": target_id,
            "operation_a_type": type(context.operation_a).__name__,
            "operation_b_type": type(context.operation_b).__name__,
        }
    )

    return Conflict(
        rule_id=rule_id,
        message=message,
        object_ids=tuple(sorted({source_id, target_id})),
        severity=SeverityLevel.HIGH,
        operation_a=context.operation_a,
        operation_b=context.operation_b,
        metadata=metadata,
    )


def graph_has_reference_source_to_target(
    graph: SchemaGraph,
    source_id: str,
    target_id: str,
) -> bool:
    for edge in graph.find_edges_by_type(EdgeType.REFERENCES):
        if edge.source_id == source_id and edge.target_id == target_id:
            return True
    return False


@dataclass(frozen=True)
class DropReferencedTargetVsModifyReferenceSourceRule(BaseConflictRule):
    """
    Если одна ветка удаляет target ссылочной зависимости,
    а другая изменяет source-объект этой зависимости,
    это конфликт.

    Пример:
    - Drop(users.id)
    - Modify(orders.user_id)
    при наличии REFERENCES orders.user_id -> users.id
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        # Случай 1: A drops target, B modifies source
        if isinstance(a, DropOperation) and isinstance(b, ModifyOperation):
            if graph_has_reference_source_to_target(
                graph=context.graph_b,
                source_id=b.target,
                target_id=a.target,
            ):
                conflict = make_reference_conflict(
                    rule_id=self.rule_id,
                    message="Referenced target is dropped in one branch while reference source is modified in another branch.",
                    source_id=b.target,
                    target_id=a.target,
                    context=context,
                )
                return RuleCheckResult.from_conflict(conflict)

        # Случай 2: B drops target, A modifies source
        if isinstance(a, ModifyOperation) and isinstance(b, DropOperation):
            if graph_has_reference_source_to_target(
                graph=context.graph_a,
                source_id=a.target,
                target_id=b.target,
            ):
                conflict = make_reference_conflict(
                    rule_id=self.rule_id,
                    message="Referenced target is dropped in one branch while reference source is modified in another branch.",
                    source_id=a.target,
                    target_id=b.target,
                    context=context,
                )
                return RuleCheckResult.from_conflict(conflict)

        return RuleCheckResult.no_match()


REFERENCE_RULES = [
    DropReferencedTargetVsModifyReferenceSourceRule(
        rule_id="F1_DROP_REFERENCED_TARGET_VS_MODIFY_REFERENCE_SOURCE",
        description="Drop referenced target vs modify reference source",
    )
]
