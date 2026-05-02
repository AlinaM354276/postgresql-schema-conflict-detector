from __future__ import annotations

from typing import Any

from src.conflict_detector.core.models import (
    AddOperation,
    DropOperation,
    EdgeType,
    ModifyOperation,
    ReferenceChangeType,
    ReferenceOperation,
    RenameOperation,
)


def _attrs_from_operation(op: Any) -> dict:
    if hasattr(op, "params"):
        return dict(op.params)
    if hasattr(op, "delta"):
        return dict(op.delta)
    return {}


def _is_edge_add(op: AddOperation) -> bool:
    params = dict(op.params)
    return {"edge_type", "source_id", "target_id"}.issubset(params.keys())


def _object_type(op: AddOperation) -> str:
    return str(dict(op.params).get("object_type", "object"))


def _edge_type(op: AddOperation) -> str:
    return str(dict(op.params).get("edge_type", "edge"))


def _format_delta(delta: dict) -> str:
    if not delta:
        return "no visible attribute changes"

    parts = []
    for key, value in sorted(delta.items()):
        parts.append(f"{key}={value!r}")

    return ", ".join(parts)


def _format_add(op: AddOperation) -> str:
    params = dict(op.params)

    if _is_edge_add(op):
        edge_type = _edge_type(op)
        source = params.get("source_id")
        target = params.get("target_id")

        if edge_type == EdgeType.CONTAINS.value:
            return f"Add ownership relation: {source} contains {target}."

        if edge_type == EdgeType.TYPED_AS.value:
            return f"Add type relation: {source} has data type {target}."

        if edge_type == EdgeType.HAS_CONSTRAINT.value:
            return f"Add constraint relation: {source} has constraint {target}."

        if edge_type == EdgeType.HAS_INDEX.value:
            return f"Add index relation: {source} has index {target}."

        if edge_type == EdgeType.REFERENCES.value:
            return f"Add reference relation: {source} references {target}."

        return f"Add edge {op.target}: {source} -[{edge_type}]-> {target}."

    object_type = _object_type(op)

    if object_type == "Table":
        return f"Add table {op.target}."

    if object_type == "Column":
        nullable = params.get("nullable")
        data_type = params.get("data_type") or params.get("data_type_raw")

        details = []
        if data_type is not None:
            details.append(f"type={data_type}")
        if nullable is not None:
            details.append(f"nullable={nullable}")

        suffix = f" ({', '.join(details)})" if details else ""
        return f"Add column {op.target}{suffix}."

    if object_type == "Constraint":
        constraint_type = params.get("constraint_type")
        columns = params.get("columns")
        details = []

        if constraint_type:
            details.append(f"type={constraint_type}")
        if columns:
            details.append(f"columns={columns}")
        if params.get("on_delete"):
            details.append(f"on_delete={params.get('on_delete')}")
        if params.get("on_update"):
            details.append(f"on_update={params.get('on_update')}")

        suffix = f" ({', '.join(details)})" if details else ""
        return f"Add constraint {op.target}{suffix}."

    if object_type == "Index":
        table = params.get("table")
        columns = params.get("columns")
        unique = params.get("unique")

        details = []
        if table:
            details.append(f"table={table}")
        if columns:
            details.append(f"columns={columns}")
        if unique is not None:
            details.append(f"unique={unique}")

        suffix = f" ({', '.join(details)})" if details else ""
        return f"Add index {op.target}{suffix}."

    if object_type == "DataType":
        return f"Add data type {op.target}."

    return f"Add {object_type} {op.target}."


def _looks_like_constraint(target: str) -> bool:
    name = target.split(".")[-1].lower()
    return (
        name.startswith("pk_")
        or name.startswith("primary_key_")
        or name.startswith("fk_")
        or name.startswith("unique_")
        or name.startswith("check_")
        or "_pk_" in name
        or "_fk_" in name
        or "_unique_" in name
    )


def _looks_like_index(target: str) -> bool:
    name = target.split(".")[-1].lower()
    return (
        name.startswith("idx_")
        or name.startswith("index_")
        or "_idx_" in name
        or "_index_" in name
    )


def _format_drop(op: DropOperation) -> str:
    target = op.target

    if target.startswith(f"{EdgeType.CONTAINS.value}:"):
        return f"Drop ownership relation {target}."

    if target.startswith(f"{EdgeType.TYPED_AS.value}:"):
        return f"Drop type relation {target}."

    if target.startswith(f"{EdgeType.HAS_CONSTRAINT.value}:"):
        return f"Drop constraint relation {target}."

    if target.startswith(f"{EdgeType.HAS_INDEX.value}:"):
        return f"Drop index relation {target}."

    if target.startswith(f"{EdgeType.REFERENCES.value}:"):
        return f"Drop reference relation {target}."

    if _looks_like_constraint(target):
        return f"Drop constraint {target}."

    if _looks_like_index(target):
        return f"Drop index {target}."

    parts = target.split(".")
    if len(parts) >= 3:
        return f"Drop column {target}."

    if len(parts) == 2:
        return f"Drop table {target}."

    return f"Drop object {target}."


def _format_modify(op: ModifyOperation) -> str:
    delta = dict(op.delta)

    messages = []

    # ---------- FK referential actions ----------

    if "on_delete" in delta:
        messages.append(
            f"Change ON DELETE action of {op.target} to {delta['on_delete']}."
        )

    if "on_update" in delta:
        messages.append(
            f"Change ON UPDATE action of {op.target} to {delta['on_update']}."
        )

    # ---------- NULLABLE ----------

    if "nullable" in delta:
        nullable = delta["nullable"]

        if nullable is False:
            messages.append(
                f"Set NOT NULL constraint on {op.target}."
            )

        elif nullable is True:
            messages.append(
                f"Drop NOT NULL constraint from {op.target}."
            )

    # ---------- DATA TYPE ----------

    if "data_type" in delta or "data_type_raw" in delta:
        data_type = delta.get("data_type_raw") or delta.get("data_type")

        messages.append(
            f"Change data type of {op.target} to {data_type}."
        )

    # ---------- DEFAULT ----------

    if "default" in delta:
        messages.append(
            f"Change default value of {op.target} to {delta['default']!r}."
        )

    # ---------- FALLBACK ----------

    handled_keys = {
        "on_delete",
        "on_update",
        "nullable",
        "data_type",
        "data_type_raw",
        "default",
    }

    remaining = {
        k: v
        for k, v in delta.items()
        if k not in handled_keys
    }

    if remaining:
        messages.append(
            f"Modify {op.target}: {_format_delta(remaining)}."
        )

    if not messages:
        return f"Modify {op.target}."

    return " ".join(messages)


def _format_rename(op: RenameOperation) -> str:
    return f"Rename {op.target} to {op.new_name}."


def _format_reference(op: ReferenceOperation) -> str:
    if op.change_type == ReferenceChangeType.ADD:
        return f"Add foreign-key reference: {op.source} references {op.target}."

    if op.change_type == ReferenceChangeType.DROP:
        return f"Drop foreign-key reference: {op.source} no longer references {op.target}."

    if op.change_type == ReferenceChangeType.RETARGET:
        return f"Retarget foreign-key reference from {op.source} to {op.target}."

    return f"Change reference: {op.source} -> {op.target}."


def explain_operation(op: object) -> str:
    if isinstance(op, AddOperation):
        return _format_add(op)

    if isinstance(op, DropOperation):
        return _format_drop(op)

    if isinstance(op, ModifyOperation):
        return _format_modify(op)

    if isinstance(op, RenameOperation):
        return _format_rename(op)

    if isinstance(op, ReferenceOperation):
        return _format_reference(op)

    return str(op)
