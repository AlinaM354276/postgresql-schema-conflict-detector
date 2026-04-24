from __future__ import annotations

from src.conflict_detector.core.models import ModifyOperation, RenameOperation, freeze_attrs
from src.conflict_detector.graph.builders import build_schema_graph
from src.conflict_detector.merge.three_way_merge import build_merge_candidate


def build_base_graph():
    builder = build_schema_graph()
    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email", data_type="text", nullable=False)
    return builder.build()


def test_merge_candidate_defined_for_rename_then_modify():
    base_graph = build_base_graph()

    ops_a = (
        RenameOperation(
            target="public.users.email",
            new_name="email_address",
        ),
    )

    ops_b = (
        ModifyOperation(
            target="public.users.email_address",
            delta=freeze_attrs({"nullable": True}),
        ),
    )

    result = build_merge_candidate(
        base_graph=base_graph,
        operations_a=ops_a,
        operations_b=ops_b,
    )

    assert result.is_defined is True
    assert result.merged_graph is not None
    assert result.invariant_result.is_valid() is True

    obj = result.merged_graph.get_vertex("public.users.email_address")
    assert obj is not None
    assert obj.attr_dict()["nullable"] is True


def test_merge_candidate_undefined_for_invalid_target_after_rename_order():
    base_graph = build_base_graph()

    ops_a = (
        RenameOperation(
            target="public.users.email",
            new_name="email_address",
        ),
    )

    # modify всё ещё пытается обратиться к старому object_id
    ops_b = (
        ModifyOperation(
            target="public.users.email",
            delta=freeze_attrs({"nullable": True}),
        ),
    )

    result = build_merge_candidate(
        base_graph=base_graph,
        operations_a=ops_a,
        operations_b=ops_b,
    )

    assert result.is_defined is False
    assert len(result.conflicts) == 1
    assert result.conflicts[0].rule_id == "M1_MERGE_UNDEFINED"


def test_merge_candidate_detects_invariant_violation():
    base_graph = build_base_graph()

    # Сделаем колонку без datatype через drop typedAs
    ops_a = tuple()
    ops_b = tuple()

    # Подготовим граф с нарушением через последовательность:
    # сначала rename оставим в покое, а потом прямо удалим datatype edge
    # здесь проще воспользоваться DropOperation по ребру
    from src.conflict_detector.core.models import DropOperation

    ops_b = (
        DropOperation(target="typedAs:public.users.email->type.text"),
    )

    result = build_merge_candidate(
        base_graph=base_graph,
        operations_a=ops_a,
        operations_b=ops_b,
    )

    assert result.is_defined is False
    assert result.merged_graph is not None
    assert result.invariant_result.is_valid() is False
    assert any(c.rule_id.startswith("M2_INV_COLUMN_SINGLE_DATATYPE") for c in result.conflicts)
