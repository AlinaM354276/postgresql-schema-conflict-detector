from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Iterable, Mapping, Optional, Set

from src.conflict_detector.core.models import (
    AddOperation,
    Conflict,
    DropOperation,
    ModifyOperation,
    Operation,
    RenameOperation,
)
from src.conflict_detector.graph.schema_graph import SchemaGraph


def escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def renamed_object_id(operation: RenameOperation) -> str:
    parts = operation.target.split(".")
    if len(parts) >= 3:
        return ".".join(parts[:-1] + [operation.new_name])
    return operation.new_name


def operation_related_object_ids(operation: Operation) -> set[str]:
    ids: set[str] = set()

    target = getattr(operation, "target", None)
    if target:
        ids.add(str(target))

    if isinstance(operation, RenameOperation):
        ids.add(renamed_object_id(operation))

    for attr in (
        "source",
        "source_id",
        "target_id",
        "reference_source_id",
        "reference_target_id",
        "referenced_object_id",
    ):
        value = getattr(operation, attr, None)
        if value:
            ids.add(str(value))

    params = getattr(operation, "params", None)
    if params:
        try:
            params_dict = dict(params)
            for key in (
                "source_id",
                "target_id",
                "reference_source_id",
                "reference_target_id",
            ):
                if key in params_dict:
                    ids.add(str(params_dict[key]))
        except Exception:
            pass

    return ids


def collect_operation_styles(
    operations: Iterable[Operation],
) -> dict[str, str]:
    styles: dict[str, str] = {}

    for operation in operations:
        if isinstance(operation, AddOperation):
            styles[operation.target] = "added"

        elif isinstance(operation, DropOperation):
            styles[operation.target] = "deleted"

        elif isinstance(operation, ModifyOperation):
            styles[operation.target] = "modified"

        elif isinstance(operation, RenameOperation):
            styles[operation.target] = "renamed"
            styles[renamed_object_id(operation)] = "renamed"

    return styles


def collect_branch_conflict_objects(
    conflicts: Iterable[Conflict],
    operations: Iterable[Operation],
) -> set[str]:
    branch_operation_ids = {id(operation) for operation in operations}
    result: set[str] = set()

    for conflict in conflicts:
        operation_a = getattr(conflict, "operation_a", None)
        operation_b = getattr(conflict, "operation_b", None)

        if operation_a is not None and id(operation_a) in branch_operation_ids:
            result.update(operation_related_object_ids(operation_a))

        if operation_b is not None and id(operation_b) in branch_operation_ids:
            result.update(operation_related_object_ids(operation_b))

    return result


def collect_overlay_deleted_objects(
    operations: Iterable[Operation],
) -> set[str]:
    return {
        operation.target
        for operation in operations
        if isinstance(operation, DropOperation)
    }


def node_style(
    object_type: str,
    semantic_style: Optional[str],
    is_conflict: bool,
) -> dict[str, str]:
    base_fill = {
        "Table": "lightblue",
        "Column": "lightgreen",
        "Constraint": "orange",
        "DataType": "lightgray",
        "Index": "khaki",
    }.get(object_type, "white")

    attrs = {
        "shape": "box",
        "style": "rounded,filled",
        "fillcolor": base_fill,
        "color": "black",
        "penwidth": "1",
    }

    if semantic_style == "added":
        attrs.update(
            {
                "fillcolor": "palegreen",
                "color": "darkgreen",
                "penwidth": "2",
            }
        )

    elif semantic_style == "deleted":
        attrs.update(
            {
                "fillcolor": "mistyrose",
                "color": "red",
                "penwidth": "2",
                "style": "rounded,filled,dashed",
            }
        )

    elif semantic_style == "modified":
        attrs.update(
            {
                "fillcolor": "khaki",
                "color": "goldenrod",
                "penwidth": "2",
            }
        )

    elif semantic_style == "renamed":
        attrs.update(
            {
                "fillcolor": "lightskyblue",
                "color": "blue",
                "penwidth": "2",
            }
        )

    if is_conflict:
        attrs.update(
            {
                "color": "red",
                "penwidth": "4",
            }
        )

    return attrs


def edge_style(
    edge_type: str,
    semantic_style: Optional[str],
    is_conflict: bool,
) -> dict[str, str]:
    attrs = {
        "color": "black",
        "style": "solid",
        "penwidth": "1",
        "fontsize": "10",
    }

    if edge_type == "references":
        attrs.update(
            {
                "color": "red",
                "style": "dashed",
                "penwidth": "2",
            }
        )

    if semantic_style == "deleted":
        attrs.update(
            {
                "color": "red",
                "style": "dashed",
                "penwidth": "2",
            }
        )

    if is_conflict:
        attrs.update(
            {
                "color": "red",
                "penwidth": "4",
            }
        )

    return attrs


def attrs_to_dot(attrs: Mapping[str, str]) -> str:
    return ", ".join(
        f'{key}="{escape(value)}"'
        for key, value in attrs.items()
    )


def graph_to_dot(
    graph: SchemaGraph,
    title: str,
    *,
    reference_graph: Optional[SchemaGraph] = None,
    operation_styles: Optional[Mapping[str, str]] = None,
    conflict_objects: Optional[Set[str]] = None,
    overlay_deleted_objects: Optional[Set[str]] = None,
) -> str:
    operation_styles = dict(operation_styles or {})
    conflict_objects = set(conflict_objects or set())
    overlay_deleted_objects = set(overlay_deleted_objects or set())

    display_vertices = dict(graph.vertices)
    display_edges = dict(graph.edges)

    if reference_graph is not None:
        for object_id in overlay_deleted_objects:
            if object_id not in display_vertices and object_id in reference_graph.vertices:
                display_vertices[object_id] = reference_graph.vertices[object_id]
                operation_styles[object_id] = "deleted"

        for edge_id, edge in reference_graph.edges.items():
            if edge_id in display_edges:
                continue

            if edge.source_id in overlay_deleted_objects or edge.target_id in overlay_deleted_objects:
                display_edges[edge_id] = edge
                operation_styles[edge_id] = "deleted"

    conflict_objects = expand_conflict_objects_by_graph(
        graph=graph,
        conflict_objects=conflict_objects,
    )

    lines = [
        "digraph SchemaGraph {",
        '  graph [rankdir=LR, labelloc=t, fontsize=20];',
        f'  label="{escape(title)}";',
        "",
        '  node [fontname="Arial"];',
        '  edge [fontname="Arial"];',
        "",
        '  subgraph cluster_legend {',
        '    label="Legend";',
        '    fontsize=12;',
        '    style="rounded,dashed";',
        '    legend_table [label="Table", shape=box, style="rounded,filled", fillcolor="lightblue"];',
        '    legend_column [label="Column", shape=box, style="rounded,filled", fillcolor="lightgreen"];',
        '    legend_constraint [label="Constraint", shape=box, style="rounded,filled", fillcolor="orange"];',
        '    legend_datatype [label="DataType", shape=box, style="rounded,filled", fillcolor="lightgray"];',
        '    legend_added [label="Added", shape=box, style="rounded,filled", fillcolor="palegreen", color="darkgreen", penwidth=2];',
        '    legend_deleted [label="Deleted", shape=box, style="rounded,filled,dashed", fillcolor="mistyrose", color="red", penwidth=2];',
        '    legend_modified [label="Modified", shape=box, style="rounded,filled", fillcolor="khaki", color="goldenrod", penwidth=2];',
        '    legend_renamed [label="Renamed", shape=box, style="rounded,filled", fillcolor="lightskyblue", color="blue", penwidth=2];',
        '    legend_conflict [label="Conflict", shape=box, style="rounded,filled", fillcolor="white", color="red", penwidth=4];',
        "  }",
        "",
    ]

    for object_id, obj in display_vertices.items():
        semantic_style = operation_styles.get(object_id)
        is_conflict = object_id in conflict_objects

        label = f"{object_id}\n{obj.object_type.value}"

        attrs = node_style(
            object_type=obj.object_type.value,
            semantic_style=semantic_style,
            is_conflict=is_conflict,
        )
        attrs["label"] = label

        lines.append(
            f'  "{escape(object_id)}" [{attrs_to_dot(attrs)}];'
        )

    lines.append("")

    for edge_id, edge in display_edges.items():
        semantic_style = operation_styles.get(edge_id)

        is_conflict = (
            edge_id in conflict_objects
            or (
                edge.edge_type.value == "references"
                and edge.source_id in conflict_objects
                and edge.target_id in conflict_objects
            )
        )

        attrs = edge_style(
            edge_type=edge.edge_type.value,
            semantic_style=semantic_style,
            is_conflict=is_conflict,
        )
        attrs["label"] = edge.edge_type.value

        lines.append(
            f'  "{escape(edge.source_id)}" -> '
            f'"{escape(edge.target_id)}" '
            f'[{attrs_to_dot(attrs)}];'
        )

    lines.append("}")

    return "\n".join(lines)


def export_graph(
    graph: SchemaGraph,
    output_path: Path,
    title: str,
    *,
    reference_graph: Optional[SchemaGraph] = None,
    operations: Iterable[Operation] = (),
    conflicts: Iterable[Conflict] = (),
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    operations = tuple(operations)
    conflicts = tuple(conflicts)

    operation_styles = collect_operation_styles(operations)
    conflict_objects = collect_branch_conflict_objects(conflicts, operations)
    overlay_deleted_objects = collect_overlay_deleted_objects(operations)

    dot_content = graph_to_dot(
        graph,
        title,
        reference_graph=reference_graph,
        operation_styles=operation_styles,
        conflict_objects=conflict_objects,
        overlay_deleted_objects=overlay_deleted_objects,
    )

    dot_path = output_path.with_suffix(".dot")
    png_path = output_path.with_suffix(".png")

    dot_path.write_text(dot_content, encoding="utf-8")

    try:
        subprocess.run(
            [
                "dot",
                "-Tpng",
                str(dot_path),
                "-o",
                str(png_path),
            ],
            check=True,
        )
        print(f"PNG graph saved: {png_path}")

    except Exception as e:
        print(f"Graphviz export failed: {e}")


def expand_conflict_objects_by_graph(
    graph: SchemaGraph,
    conflict_objects: Set[str],
) -> set[str]:
    """
    Расширяет множество конфликтных объектов по графу.

    Если конфликтным является столбец, участвующий в constraint,
    то сам constraint тоже должен считаться связанным с конфликтом.

    Особенно важно для FK:
        orders.user_id --hasConstraint--> fk_orders_user_email
        orders.user_id --references--> users.email
    """
    expanded = set(conflict_objects)

    changed = True
    while changed:
        changed = False

        for edge_id, edge in graph.edges.items():
            source_in_conflict = edge.source_id in expanded
            target_in_conflict = edge.target_id in expanded

            if edge.edge_type.value == "hasConstraint" and source_in_conflict:
                if edge.target_id not in expanded:
                    expanded.add(edge.target_id)
                    changed = True

            if edge.edge_type.value == "references":
                if source_in_conflict or target_in_conflict:
                    if edge.source_id not in expanded:
                        expanded.add(edge.source_id)
                        changed = True

                    if edge.target_id not in expanded:
                        expanded.add(edge.target_id)
                        changed = True

                    if edge_id not in expanded:
                        expanded.add(edge_id)
                        changed = True

    return expanded