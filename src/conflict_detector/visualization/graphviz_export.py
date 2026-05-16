from pathlib import Path
import subprocess

from src.conflict_detector.graph.schema_graph import SchemaGraph


def escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def graph_to_dot(graph: SchemaGraph, title: str) -> str:
    lines = [
        "digraph SchemaGraph {",
        '  graph [rankdir=LR, labelloc=t, fontsize=20];',
        f'  label="{escape(title)}";',
        "",
        '  node [style="rounded,filled", shape=box];',
        "",
    ]

    for object_id, obj in graph.vertices.items():
        color = {
            "Table": "lightblue",
            "Column": "lightgreen",
            "Constraint": "orange",
            "DataType": "lightgray",
        }.get(obj.object_type.value, "white")

        label = f"{object_id}\\n{obj.object_type.value}"

        lines.append(
            f'"{escape(object_id)}" '
            f'[label="{escape(label)}", fillcolor="{color}"];'
        )

    lines.append("")

    for edge_id, edge in graph.edges.items():
        edge_style = "solid"
        edge_color = "black"

        if edge.edge_type.value == "references":
            edge_color = "red"
            edge_style = "dashed"

        lines.append(
            f'"{escape(edge.source_id)}" -> '
            f'"{escape(edge.target_id)}" '
            f'[label="{edge.edge_type.value}", '
            f'color="{edge_color}", '
            f'style="{edge_style}"];'
        )

    lines.append("}")

    return "\n".join(lines)


def export_graph(
    graph: SchemaGraph,
    output_path: Path,
    title: str,
) -> None:
    dot_content = graph_to_dot(graph, title)

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
    except Exception:
        pass