from __future__ import annotations

from src.conflict_detector.comparison.delta import compute_delta
from src.conflict_detector.comparison.matching import build_matching
from src.conflict_detector.comparison.reconstruct import reconstruct_operations
from src.conflict_detector.core.models import (
    AddOperation,
    DropOperation,
    ModifyOperation,
    RenameOperation,
)
from src.conflict_detector.graph.builders import build_schema_graph


def extract_ops_by_type(operations, op_type):
    return [op for op in operations if isinstance(op, op_type)]


def build_base_users_graph():
    builder = build_schema_graph()

    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email", data_type="text", nullable=False)

    return builder.build()


def reconstruct(base_graph, branch_graph):
    matching = build_matching(base_graph, branch_graph)
    delta_details = compute_delta(base_graph, branch_graph, matching)
    result = reconstruct_operations(
        left_graph=base_graph,
        right_graph=branch_graph,
        matching=matching,
        delta_details=delta_details,
    )
    return result.operations


def test_reconstruct_rename_operation():
    base_graph = build_base_users_graph()

    builder = build_schema_graph()
    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email_address", data_type="text", nullable=False)
    branch_graph = builder.build()

    operations = reconstruct(base_graph, branch_graph)

    rename_ops = extract_ops_by_type(operations, RenameOperation)

    assert len(rename_ops) == 1
    assert rename_ops[0].target == "public.users.email"
    assert rename_ops[0].new_name == "email_address"


def test_reconstruct_modify_operation():
    base_graph = build_base_users_graph()

    builder = build_schema_graph()
    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email", data_type="text", nullable=True)
    branch_graph = builder.build()

    operations = reconstruct(base_graph, branch_graph)

    modify_ops = extract_ops_by_type(operations, ModifyOperation)

    assert len(modify_ops) == 1
    assert modify_ops[0].target == "public.users.email"
    assert ("nullable", True) in modify_ops[0].delta


def test_reconstruct_add_table_operation():
    base_graph = build_base_users_graph()

    builder = build_schema_graph()
    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email", data_type="text", nullable=False)

    builder.add_table("orders")
    builder.add_column("orders", "id", data_type="integer", nullable=False)

    branch_graph = builder.build()

    operations = reconstruct(base_graph, branch_graph)

    add_ops = extract_ops_by_type(operations, AddOperation)

    targets = {op.target for op in add_ops}

    assert "public.orders" in targets
    assert "public.orders.id" in targets


def test_reconstruct_drop_column_operation():
    base_graph = build_base_users_graph()

    builder = build_schema_graph()
    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    branch_graph = builder.build()

    operations = reconstruct(base_graph, branch_graph)

    drop_ops = extract_ops_by_type(operations, DropOperation)
    targets = {op.target for op in drop_ops}

    assert "public.users.email" in targets


def test_reconstruct_modify_not_split_into_add_and_drop():
    base_graph = build_base_users_graph()

    builder = build_schema_graph()
    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email", data_type="text", nullable=True)
    branch_graph = builder.build()

    operations = reconstruct(base_graph, branch_graph)

    modify_ops = extract_ops_by_type(operations, ModifyOperation)
    drop_ops = extract_ops_by_type(operations, DropOperation)
    add_ops = extract_ops_by_type(operations, AddOperation)

    assert len(modify_ops) == 1

    object_drop_targets = {
        op.target for op in drop_ops if not op.target.startswith(("contains:", "typedAs:"))
    }
    object_add_targets = {
        op.target for op in add_ops if not op.target.startswith(("contains:", "typedAs:"))
    }

    assert "public.users.email" not in object_drop_targets
    assert "public.users.email" not in object_add_targets


def test_rename_does_not_generate_edge_noise():
    base_graph = build_base_users_graph()

    builder = build_schema_graph()
    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email_address", data_type="text", nullable=False)
    branch_graph = builder.build()

    operations = reconstruct(base_graph, branch_graph)

    rename_ops = extract_ops_by_type(operations, RenameOperation)
    assert len(rename_ops) == 1

    noisy_ops = [
        op for op in operations
        if hasattr(op, "target") and (
            op.target.startswith("contains:")
            or op.target.startswith("typedAs:")
        )
    ]

    assert len(noisy_ops) == 0