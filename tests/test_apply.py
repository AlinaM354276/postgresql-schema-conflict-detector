from __future__ import annotations

from src.conflict_detector.core.models import (
    AddOperation,
    DropOperation,
    ModifyOperation,
    RenameOperation,
    freeze_attrs,
)
from src.conflict_detector.graph.builders import build_schema_graph
from src.conflict_detector.semantics.apply import (
    apply_add_operation,
    apply_drop_operation,
    apply_modify_operation,
    apply_rename_operation,
    apply_operations,
)


def build_base_graph():
    builder = build_schema_graph()
    builder.add_table("users")
    builder.add_column("users", "id", data_type="integer", nullable=False)
    builder.add_column("users", "email", data_type="text", nullable=False)
    return builder.build()


def test_apply_modify_operation_updates_vertex_attributes():
    graph = build_base_graph()

    modified = apply_modify_operation(
        graph,
        ModifyOperation(
            target="public.users.email",
            delta=freeze_attrs({"nullable": True}),
        ),
    )

    email = modified.get_vertex("public.users.email")
    assert email is not None
    assert email.attr_dict()["nullable"] is True


def test_apply_rename_operation_updates_vertex_and_edges():
    graph = build_base_graph()

    renamed = apply_rename_operation(
        graph,
        RenameOperation(
            target="public.users.email",
            new_name="email_address",
        ),
    )

    old_obj = renamed.get_vertex("public.users.email")
    new_obj = renamed.get_vertex("public.users.email_address")

    assert old_obj is None
    assert new_obj is not None
    assert new_obj.name == "email_address"

    edge_ids = set(renamed.edge_ids())
    assert "contains:public.users->public.users.email_address" in edge_ids
    assert "typedAs:public.users.email_address->type.text" in edge_ids

    assert "contains:public.users->public.users.email" not in edge_ids
    assert "typedAs:public.users.email->type.text" not in edge_ids


def test_apply_drop_operation_removes_vertex_and_incident_edges():
    graph = build_base_graph()

    dropped = apply_drop_operation(
        graph,
        DropOperation(target="public.users.email"),
    )

    assert dropped.get_vertex("public.users.email") is None
    assert "contains:public.users->public.users.email" not in dropped.edge_ids()
    assert "typedAs:public.users.email->type.text" not in dropped.edge_ids()


def test_apply_add_operation_adds_vertex():
    graph = build_base_graph()

    added = apply_add_operation(
        graph,
        AddOperation(
            target="public.users.username",
            params=freeze_attrs(
                {
                    "object_type": "Column",
                    "name": "username",
                    "schema": "public",
                    "table": "users",
                    "nullable": False,
                }
            ),
        ),
    )

    username = added.get_vertex("public.users.username")
    assert username is not None
    assert username.name == "username"


def test_apply_operations_sequence():
    graph = build_base_graph()

    result = apply_operations(
        graph,
        [
            RenameOperation(
                target="public.users.email",
                new_name="email_address",
            ),
            ModifyOperation(
                target="public.users.email_address",
                delta=freeze_attrs({"nullable": True}),
            ),
        ],
    )

    obj = result.get_vertex("public.users.email_address")
    assert obj is not None
    assert obj.name == "email_address"
    assert obj.attr_dict()["nullable"] is True
