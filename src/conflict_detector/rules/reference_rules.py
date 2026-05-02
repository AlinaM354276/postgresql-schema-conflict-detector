from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.conflict_detector.core.models import (
    Conflict,
    DropOperation,
    EdgeType,
    ModifyOperation,
    ReferenceChangeType,
    ReferenceOperation,
    SeverityLevel,
    freeze_attrs,
)
from src.conflict_detector.graph.builders import canonical_data_type_name
from src.conflict_detector.graph.schema_graph import SchemaGraph
from src.conflict_detector.rules.base import (
    BaseConflictRule,
    RuleCheckResult,
    RuleContext,
)


def normalize_type_spec(value: object) -> Optional[str]:
    if value is None:
        return None

    raw = " ".join(str(value).strip().lower().split())

    aliases = {
        "int": "integer",
        "int4": "integer",
        "integer": "integer",
        "bigint": "bigint",
        "int8": "bigint",
        "bool": "boolean",
        "boolean": "boolean",
        "character varying": "varchar",
    }

    if "(" not in raw:
        return aliases.get(raw, canonical_data_type_name(raw))

    raw = raw.replace(" (", "(")
    raw = raw.replace("( ", "(")
    raw = raw.replace(" )", ")")
    raw = raw.replace(" ,", ",")
    raw = raw.replace(", ", ",")

    if raw.startswith("character varying("):
        return "varchar" + raw.removeprefix("character varying")

    return raw


def get_column_type(graph: SchemaGraph | None, column_id: str) -> Optional[str]:
    if graph is None:
        return None

    obj = graph.get_vertex(column_id)
    if obj is None:
        return None

    attrs = obj.attr_dict()

    return normalize_type_spec(
        attrs.get("data_type_raw") or attrs.get("data_type")
    )


def modified_column_new_type(op: ModifyOperation) -> Optional[str]:
    delta = dict(op.delta)

    return normalize_type_spec(
        delta.get("data_type_raw") or delta.get("data_type")
    )


def make_reference_conflict(
    *,
    rule_id: str,
    message: str,
    source_id: str,
    target_id: str,
    context: RuleContext,
    severity: SeverityLevel,
    extra_metadata: Optional[dict] = None,
) -> Conflict:
    metadata = {
        "reference_source_id": source_id,
        "reference_target_id": target_id,
        "operation_a_type": type(context.operation_a).__name__,
        "operation_b_type": type(context.operation_b).__name__,
        "kind": "referential_integrity_conflict",
    }

    if extra_metadata:
        metadata.update(extra_metadata)

    return Conflict(
        rule_id=rule_id,
        message=message,
        object_ids=tuple(sorted({source_id, target_id})),
        severity=severity,
        operation_a=context.operation_a,
        operation_b=context.operation_b,
        metadata=freeze_attrs(metadata),
    )


def graph_has_reference_source_to_target(
    graph: SchemaGraph | None,
    source_id: str,
    target_id: str,
) -> bool:
    if graph is None:
        return False

    for edge in graph.find_edges_by_type(EdgeType.REFERENCES):
        if edge.source_id == source_id and edge.target_id == target_id:
            return True

    return False


def is_add_reference_operation(op: object) -> bool:
    return (
        isinstance(op, ReferenceOperation)
        and op.change_type == ReferenceChangeType.ADD
    )


@dataclass(frozen=True)
class DropReferencedTargetVsAddReferenceRule(BaseConflictRule):
    """
    R1. Разрушение ссылочной целостности.

    Одна ветка удаляет объект, другая создаёт FK-ссылку на него.
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        if isinstance(a, DropOperation) and is_add_reference_operation(b):
            assert isinstance(b, ReferenceOperation)

            if a.target == b.target:
                return RuleCheckResult.from_conflict(
                    make_reference_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "Referenced object is dropped in one branch while "
                            "a foreign-key reference to this object is added in another branch."
                        ),
                        source_id=b.source,
                        target_id=b.target,
                        context=context,
                        severity=SeverityLevel.CRITICAL,
                    )
                )

        if isinstance(b, DropOperation) and is_add_reference_operation(a):
            assert isinstance(a, ReferenceOperation)

            if b.target == a.target:
                return RuleCheckResult.from_conflict(
                    make_reference_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "Referenced object is dropped in one branch while "
                            "a foreign-key reference to this object is added in another branch."
                        ),
                        source_id=a.source,
                        target_id=a.target,
                        context=context,
                        severity=SeverityLevel.CRITICAL,
                    )
                )

        return RuleCheckResult.no_match()


@dataclass(frozen=True)
class ModifyReferencedTargetTypeVsAddReferenceRule(BaseConflictRule):
    """
    R2. Несовместимость типов.

    Одна ветка меняет тип целевого столбца,
    другая ветка добавляет FK, предполагающий старый тип.

    Пример:
    A: users.code INT -> VARCHAR(50)
    B: orders.user_code INT REFERENCES users(code)
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        if isinstance(a, ModifyOperation) and is_add_reference_operation(b):
            assert isinstance(b, ReferenceOperation)
            return self._check_modify_vs_reference(
                modify_op=a,
                reference_op=b,
                source_graph=context.graph_b,
                context=context,
            )

        if isinstance(b, ModifyOperation) and is_add_reference_operation(a):
            assert isinstance(a, ReferenceOperation)
            return self._check_modify_vs_reference(
                modify_op=b,
                reference_op=a,
                source_graph=context.graph_a,
                context=context,
            )

        return RuleCheckResult.no_match()

    def _check_modify_vs_reference(
        self,
        *,
        modify_op: ModifyOperation,
        reference_op: ReferenceOperation,
        source_graph: SchemaGraph | None,
        context: RuleContext,
    ) -> RuleCheckResult:
        if modify_op.target != reference_op.target:
            return RuleCheckResult.no_match()

        new_target_type = modified_column_new_type(modify_op)

        if new_target_type is None:
            return RuleCheckResult.no_match()

        source_type = get_column_type(
            graph=source_graph,
            column_id=reference_op.source,
        )

        if source_type is None:
            return RuleCheckResult.no_match()

        if source_type == new_target_type:
            return RuleCheckResult.no_match()

        return RuleCheckResult.from_conflict(
            make_reference_conflict(
                rule_id=self.rule_id,
                message=(
                    "Foreign-key reference is added using a source column whose type "
                    "is incompatible with the modified referenced column type."
                ),
                source_id=reference_op.source,
                target_id=reference_op.target,
                context=context,
                severity=SeverityLevel.HIGH,
                extra_metadata={
                    "source_type": source_type,
                    "new_target_type": new_target_type,
                    "modified_column_id": modify_op.target,
                    "kind": "type_inconsistency_conflict",
                },
            )
        )


@dataclass(frozen=True)
class DropReferencedTargetVsModifyReferenceSourceRule(BaseConflictRule):
    """
    Если одна ветка удаляет target ссылочной зависимости,
    а другая изменяет source-объект этой зависимости.
    """

    def check(self, context: RuleContext) -> RuleCheckResult:
        a = context.operation_a
        b = context.operation_b

        if isinstance(a, DropOperation) and isinstance(b, ModifyOperation):
            if graph_has_reference_source_to_target(
                graph=context.graph_b,
                source_id=b.target,
                target_id=a.target,
            ):
                return RuleCheckResult.from_conflict(
                    make_reference_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "Referenced target is dropped in one branch while "
                            "reference source is modified in another branch."
                        ),
                        source_id=b.target,
                        target_id=a.target,
                        context=context,
                        severity=SeverityLevel.HIGH,
                    )
                )

        if isinstance(a, ModifyOperation) and isinstance(b, DropOperation):
            if graph_has_reference_source_to_target(
                graph=context.graph_a,
                source_id=a.target,
                target_id=b.target,
            ):
                return RuleCheckResult.from_conflict(
                    make_reference_conflict(
                        rule_id=self.rule_id,
                        message=(
                            "Referenced target is dropped in one branch while "
                            "reference source is modified in another branch."
                        ),
                        source_id=a.target,
                        target_id=b.target,
                        context=context,
                        severity=SeverityLevel.HIGH,
                    )
                )

        return RuleCheckResult.no_match()


REFERENCE_RULES = [
    DropReferencedTargetVsAddReferenceRule(
        rule_id="R1_REFERENTIAL_INTEGRITY_DROP_VS_ADD_REFERENCE",
        description="Drop referenced object vs add foreign-key reference",
    ),
    ModifyReferencedTargetTypeVsAddReferenceRule(
        rule_id="R2_TYPE_INCONSISTENCY_MODIFY_TARGET_VS_ADD_REFERENCE",
        description="Modify referenced column type vs add foreign-key reference",
    ),
    DropReferencedTargetVsModifyReferenceSourceRule(
        rule_id="F1_DROP_REFERENCED_TARGET_VS_MODIFY_REFERENCE_SOURCE",
        description="Drop referenced target vs modify reference source",
    ),
]