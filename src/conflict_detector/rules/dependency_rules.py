from __future__ import annotations

from src.conflict_detector.core.models import EdgeType

from dataclasses import dataclass

from src.conflict_detector.core.models import (
    Conflict,
    DropOperation,
    ModifyOperation,
    RenameOperation,
    SeverityLevel,
    freeze_attrs,
)
from src.conflict_detector.graph.schema_graph import SchemaGraph
from src.conflict_detector.rules.base import (
    BaseConflictRule,
    RuleCheckResult,
    RuleContext,
)


def make_dependency_conflict(
    *,
    rule_id: str,
    message: str,
    severity: SeverityLevel,
    prerequisite_id: str,
    dependent_id: str,
    context: RuleContext,
) -> Conflict:
    metadata = freeze_attrs(
        {
            "prerequisite_id": prerequisite_id,
            "dependent_id": dependent_id,
            "operation_a_type": type(context.operation_a).__name__,
            "operation_b_type": type(context.operation_b).__name__,
        }
    )

    return Conflict(
        rule_id=rule_id,
        message=message,
        object_ids=tuple(sorted({prerequisite_id, dependent_id})),
        severity=severity,
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
class DropPrerequisiteVsModifyDependentRule(BaseConflictRule):
    """
    Если одна ветка удаляет prerequisite-объект,
    а другая изменяет dependent-объект, зависящий от него,
    это конфликт.
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        if isinstance(a, DropOperation) and isinstance(b, ModifyOperation):
            impacted = context.graph_b.impact_of_targets([b.target])
            if a.target in impacted and a.target != b.target:
                # если это прямой REFERENCES-case, его должен ловить более специальный rule
                if graph_has_reference_source_to_target(
                        graph=context.graph_b,
                        source_id=b.target,
                        target_id=a.target,
                ):
                    return RuleCheckResult.no_match()

                conflict = make_dependency_conflict(
                    rule_id=self.rule_id,
                    message="Prerequisite object is dropped in one branch while a dependent object is modified in another branch.",
                    severity=SeverityLevel.HIGH,
                    prerequisite_id=a.target,
                    dependent_id=b.target,
                    context=context,
                )
                return RuleCheckResult.from_conflict(conflict)

        if isinstance(a, ModifyOperation) and isinstance(b, DropOperation):
            impacted = context.graph_a.impact_of_targets([a.target])
            if b.target in impacted and b.target != a.target:
                # если это прямой REFERENCES-case, его должен ловить reference rule
                if graph_has_reference_source_to_target(
                        graph=context.graph_a,
                        source_id=a.target,
                        target_id=b.target,
                ):
                    return RuleCheckResult.no_match()

                conflict = make_dependency_conflict(
                    rule_id=self.rule_id,
                    message="Prerequisite object is dropped in one branch while a dependent object is modified in another branch.",
                    severity=SeverityLevel.HIGH,
                    prerequisite_id=b.target,
                    dependent_id=a.target,
                    context=context,
                )
                return RuleCheckResult.from_conflict(conflict)

        return RuleCheckResult.no_match()


@dataclass(frozen=True)
class DropPrerequisiteVsRenameDependentRule(BaseConflictRule):
    """
    Если одна ветка удаляет prerequisite-объект,
    а другая переименовывает dependent-объект, зависящий от него,
    это конфликт.

    Пример:
    - Drop(table users)
    - Rename(column users.email -> email_address)
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        if isinstance(a, DropOperation) and isinstance(b, RenameOperation):
            impacted = context.graph_b.impact_of_targets([b.target])
            if a.target in impacted and a.target != b.target:
                conflict = make_dependency_conflict(
                    rule_id=self.rule_id,
                    message="Prerequisite object is dropped in one branch while a dependent object is renamed in another branch.",
                    severity=SeverityLevel.HIGH,
                    prerequisite_id=a.target,
                    dependent_id=b.target,
                    context=context,
                )
                return RuleCheckResult.from_conflict(conflict)

        if isinstance(a, RenameOperation) and isinstance(b, DropOperation):
            impacted = context.graph_a.impact_of_targets([a.target])
            if b.target in impacted and b.target != a.target:
                conflict = make_dependency_conflict(
                    rule_id=self.rule_id,
                    message="Prerequisite object is dropped in one branch while a dependent object is renamed in another branch.",
                    severity=SeverityLevel.HIGH,
                    prerequisite_id=b.target,
                    dependent_id=a.target,
                    context=context,
                )
                return RuleCheckResult.from_conflict(conflict)

        return RuleCheckResult.no_match()


DEPENDENCY_RULES = [
    DropPrerequisiteVsModifyDependentRule(
        rule_id="D1_DROP_PREREQUISITE_VS_MODIFY_DEPENDENT",
        description="Drop prerequisite vs modify dependent",
    ),
    DropPrerequisiteVsRenameDependentRule(
        rule_id="D2_DROP_PREREQUISITE_VS_RENAME_DEPENDENT",
        description="Drop prerequisite vs rename dependent",
    ),
]
